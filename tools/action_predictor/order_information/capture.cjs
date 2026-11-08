'use strict';
// Recorded eligible TRAIN PREs only. No action calls, branches, matches or bots.
const fs=require('node:fs'),crypto=require('node:crypto');
const {priority}=require('./getter.cjs');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const clone=x=>JSON.parse(JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v));
async function run(q){
 for(const [path,expected]of Object.entries(q.bindings))if(hash(fs.readFileSync(path))!==expected)throw Error('Capture dependency changed: '+path);
 const {open,restore,recordedHeader}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
 const {game,engine,version}=await open(q);
 const fd=fs.openSync(q.output,'wx');
 const emit=r=>fs.writeSync(fd,JSON.stringify(r)+'\n');
 const stats={rows:0,own_queries:0,other_queries:0,other_available:0,other_unavailable:0};
 try{
  if(version!==q.expected_engine)throw Error('Historical engine mismatch');
  for(const item of q.rows){
   restore(game,item.pre);
   const before=recordedHeader(game.header());
   emit({record:'begin',row:item.row,pre:item.pre,actor:item.actor});
   if(before.phase!==10||before.currentChampion!==item.actor||before.round!==item.round)throw Error('PRE actor/order mismatch');
   const perspective={team:q.team,champion:item.actor},snapshot=clone(game.snapshot(perspective));
   const me=snapshot.champions.find(c=>c.entity.index===item.actor);
   if(!me||!(me.known&1)||me.team!==q.team)throw Error('Own personal state unavailable');
   const row={record:'order_pre',row:item.row,pre:item.pre,actor:item.actor,own:{},others:[]};
   for(const [next,time]of [[false,'current'],[true,'scheduled']]){
    const result=priority(game,engine,perspective,item.actor,next);stats.own_queries++;
    emit({record:'own_query',row:item.row,time,...result});
    row.own[time]=result.value;row.own[time+'_available']=result.available;
    if(!result.available||result.value!==item[time])throw Error('Own priority differs from bound causal cache');
   }
   for(const champion of snapshot.champions){
    if(champion.entity.index===item.actor||!(champion.known&1))continue;
    const unit={known:true,role:champion.team===q.team?'ally':'enemy'};
    for(const [next,time]of [[false,'current'],[true,'scheduled']]){
     const result=priority(game,engine,perspective,champion.entity.index,next);stats.other_queries++;
     emit({record:'other_query',row:item.row,entity_index:champion.entity.index,time,...result});
     if(result.code!==0&&result.code!==97)throw Error('Unexpected personal query error '+result.code);
     unit[time]=result.value;unit[time+'_available']=result.available;
     if(result.available){stats.other_available++;if(result.value!==(next?champion.nextPriority:champion.priority))throw Error('Getter/snapshot mismatch');}
     else stats.other_unavailable++;
    }
    row.others.push(unit);
   }
   emit(row); // Preserve successful raw inputs before state-validation checks.
   if(JSON.stringify(recordedHeader(game.header()))!==JSON.stringify(before))throw Error('Read query changed header');
   if(JSON.stringify(clone(game.snapshot(perspective)))!==JSON.stringify(snapshot))throw Error('Read query changed personal state');
   stats.rows++;
  }
  emit({record:'complete',stats,engine:version,raw_sha256:q.raw_sha256,no_actions:true});
 }catch(error){emit({record:'failure',error:error.stack});throw error;}
 finally{fs.closeSync(fd);game.destroy();engine.destroy();}
}
if(require.main===module)run(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(e=>{console.error(e.stack);process.exitCode=1;});
module.exports={run};
