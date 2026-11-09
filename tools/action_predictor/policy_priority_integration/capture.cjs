'use strict';
// Existing recorded eligible PREs only. Never call action, branch or match APIs.
const fs=require('node:fs'),crypto=require('node:crypto');
const path=require('node:path'),cp=require('node:child_process');
const {priority}=require('../order_information/getter.cjs');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const clone=x=>JSON.parse(JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v));

function eligibility(q){
 if(!['train','validation'].includes(q.split))throw Error('Ineligible split');
 const root=path.resolve(__dirname,'../../..');
 const jobsPath=path.join(root,'.cambc/action-predictor/v7/jobs.json');
 const jobsBytes=fs.readFileSync(jobsPath);
 if(hash(jobsBytes)!=='80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba')throw Error('Canonical eligible jobs changed');
 const job=JSON.parse(jobsBytes).find(j=>j.split===q.split&&j.record.raw_sha256===q.raw_sha256);
 if(!job)throw Error('Payload not in canonical eligible jobs');
 const relative='tools/action_predictor/experiments/v8/priority-data-ready.json';
 const readyBytes=cp.execFileSync('git',['show','bcfc9949271de9baf9f1d10b815658e1e8eb423d:'+relative],{cwd:root,windowsHide:true});
 if(!readyBytes.equals(fs.readFileSync(path.join(root,relative))))throw Error('Anchored own recovery receipt changed');
 const oldDir=path.join(root,'.cambc/action-predictor/v8/priority',q.raw_sha256);
 const receiptBytes=fs.readFileSync(path.join(oldDir,'receipt.json'));
 if(hash(receiptBytes)!==JSON.parse(readyBytes).receipts[q.raw_sha256])throw Error('Old eligible receipt changed');
 const queryBytes=fs.readFileSync(path.join(oldDir,'query.json'));
 if(hash(queryBytes)!==JSON.parse(receiptBytes).files['query.json'])throw Error('Old eligible query changed');
 const old=JSON.parse(queryBytes);
 for(const key of ['raw','reader','assets','team'])if(q[key]!==old[key])throw Error('Query differs from eligible recording: '+key);
 for(const item of q.rows)if(item.row<job.offset||item.row>=job.offset+job.rows)throw Error('Query row outside eligible job');
}

function collect(game,engine,item,team,emit,snapshot){
 const perspective={team,champion:item.actor};
 const me=snapshot.champions.find(c=>c.entity.index===item.actor);
 if(!me||!(me.known&1)||me.team!==team)throw Error('Own personal state unavailable');
 const row={record:'order_pre',row:item.row,pre:item.pre,actor:item.actor,round:item.round,own:{},others:[]};
 for(const [next,time]of [[false,'current'],[true,'scheduled']]){
  if(typeof item[time+'_available']!=='boolean')throw Error('Missing bound own availability');
  const r=priority(game,engine,perspective,item.actor,next);
  emit({record:'own_query',row:item.row,time,...r});
  if(r.code!==0&&r.code!==97)throw Error('Unexpected own query error '+r.code);
  row.own[time]=r.value;row.own[time+'_available']=r.available;
  if(r.available!==item[time+'_available']||(r.available&&r.value!==item[time]))throw Error('Own API differs from bound PRE cache');
 }
 for(const champion of snapshot.champions){
  if(champion.entity.index===item.actor||!(champion.known&1))continue;
  const unit={known:true,role:champion.team===team?'ally':'enemy'};
  for(const [next,time]of [[false,'current'],[true,'scheduled']]){
   const r=priority(game,engine,perspective,champion.entity.index,next);
   emit({record:'other_query',row:item.row,entity_index:champion.entity.index,time,...r});
   if(r.code!==0&&r.code!==97)throw Error('Unexpected other query error '+r.code);
   unit[time]=r.value;unit[time+'_available']=r.available;
   if(r.available&&r.value!==(next?champion.nextPriority:champion.priority))throw Error('Scoped getter/snapshot mismatch');
  }
  row.others.push(unit);
 }
 emit(row);
 return row;
}

async function run(q){
 eligibility(q); // Membership and approved raw path before any payload is opened.
 for(const [path,expected]of Object.entries(q.bindings))if(hash(fs.readFileSync(path))!==expected)throw Error('Recovery dependency changed: '+path);
 const {open,restore,recordedHeader}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
 const {game,engine,version}=await open(q);
 const fd=fs.openSync(q.output,'wx'),emit=r=>fs.writeSync(fd,JSON.stringify(r)+'\n');
 const stats={rows:0,other_units:0,available_fields:0,unavailable_fields:0,deep_nonmutation_checks:0};
 const deep=new Set([0,Math.floor(q.rows.length/2),q.rows.length-1]);
 try{
  if(version!==q.expected_engine)throw Error('Historical engine mismatch');
  for(let i=0;i<q.rows.length;i++){
   const item=q.rows[i];restore(game,item.pre);
   const before=recordedHeader(game.header());emit({record:'begin',row:item.row,pre:item.pre,actor:item.actor});
   if(before.phase!==10||before.currentChampion!==item.actor||before.round!==item.round)throw Error('PRE actor/order mismatch');
   const perspective={team:q.team,champion:item.actor},snapshot=clone(game.snapshot(perspective));
   const row=collect(game,engine,item,q.team,emit,snapshot);
   if(JSON.stringify(recordedHeader(game.header()))!==JSON.stringify(before))throw Error('Read getter changed header');
   if(deep.has(i)){
    if(JSON.stringify(clone(game.snapshot(perspective)))!==JSON.stringify(snapshot))throw Error('Read getter changed personal snapshot');
    stats.deep_nonmutation_checks++;
   }
   for(const unit of row.others){stats.other_units++;for(const time of ['current','scheduled'])stats[unit[time+'_available']?'available_fields':'unavailable_fields']++;}
   stats.rows++;
  }
  emit({record:'complete',rows:stats.rows,stats,engine:version,raw_sha256:q.raw_sha256,no_actions:true});
 }catch(error){emit({record:'failure',error:error.stack});throw error;}
 finally{fs.closeSync(fd);game.destroy();engine.destroy();}
}
if(require.main===module)run(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(e=>{console.error(e.stack);process.exitCode=1;});
module.exports={collect,run,eligibility};
