'use strict';
// Read-only queries on recorded PREs. Never act, branch, create a match or load bots.
const fs=require('node:fs'),crypto=require('node:crypto');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const clone=x=>JSON.parse(JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v));

async function run(plan){
 const results=[];
 const rawFd=fs.openSync(plan.raw_output,'wx');
 const emit=row=>fs.writeSync(rawFd,JSON.stringify(row)+'\n');
 try{for(const selected of plan.games){
  const bytes=fs.readFileSync(selected.query);
  if(hash(bytes)!==selected.query_sha256)throw Error('Bound query changed');
  const q=JSON.parse(bytes.toString('utf8'));
  const {open,restore,recordedHeader}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
  const {game,engine,version}=await open(q);
  if(version!==selected.expected_engine)throw Error('Unexpected historical engine version');
  const stats={cases:0,own_queries:0,own_exact:0,own_different_cases:0,negative_own_queries:0,
   other_known_champions:0,other_unknown_champions:0,known_queries:0,known_successes:0,
   unknown_queries:0,unknown_successes:0,successful_known_snapshot_matches:0};
  const errors={},cases=[];
  try{
   const getter=game.wasmExports.Game_API_Champion_GetPriority;
   if(typeof getter!=='function'||getter.length!==5)throw Error('Historical query ABI not established');
   for(const item of selected.cases){
    restore(game,item.pre);
    const before=recordedHeader(game.header());
    emit({record:'case_start',engine:version,actor:item.actor,pre:item.pre,header:before});
    if(before.phase!==10||before.currentChampion!==item.actor||before.round!==item.round)
      throw Error('Recorded PRE ownership mismatch');
    const perspective={team:q.team,champion:item.actor};
    const snapshot=clone(game.snapshot(perspective));
    const own=snapshot.champions.find(e=>e.entity.index===item.actor);
    if(!own||!(own.known&1))throw Error('Own personal state unavailable');
    const pointer=game.perspectivePointer(perspective),output=game.args;
    const query=(champion,next)=>{
     const code=getter(game.handle,pointer,champion,Number(next),output);
     const result={code,value:code===0?engine.memory.getInt32(output,true):null};
     const known=Boolean(snapshot.champions.find(c=>c.entity.index===champion)?.known&1);
     emit({record:'query',engine:version,actor:item.actor,pre:item.pre,champion,known,next,
           code,value:known?result.value:null,audit_only:true});
     return result;
    };
    for(const next of [false,true]){
     const result=query(item.actor,next),expected=next?own.nextPriority:own.priority;
     stats.own_queries++;
     if(result.code!==0||result.value!==expected)throw Error('Own historical getter/snapshot mismatch');
     stats.own_exact++;stats.negative_own_queries+=Number(result.value<0);
    }
    stats.own_different_cases+=Number(own.priority!==own.nextPriority);
    const row={actor:item.actor,pre:item.pre,round:item.round,known:[],unknown_query_codes:[]};
    for(const champion of snapshot.champions){
     if(champion.entity.index===item.actor)continue;
     const known=Boolean(champion.known&1);
     stats[known?'other_known_champions':'other_unknown_champions']++;
     const values=[];
     for(const next of [false,true]){
      const result=query(champion.entity.index,next);
      stats[known?'known_queries':'unknown_queries']++;
      if(result.code===0){
       stats[known?'known_successes':'unknown_successes']++;
       if(known){
        const expected=next?champion.nextPriority:champion.priority;
        if(result.value!==expected)throw Error('Successful known query differs from snapshot');
        stats.successful_known_snapshot_matches++;
       }
      }else errors[String(result.code)]=(errors[String(result.code)]||0)+1;
      values.push(result);
     }
     if(known)row.known.push({team:champion.team,type:champion.type,
       current:values[0].value,current_available:values[0].code===0,
       scheduled:values[1].value,scheduled_available:values[1].code===0});
     else row.unknown_query_codes.push(values.map(v=>v.code)); // Never retain unknown values.
    }
    if(JSON.stringify(recordedHeader(game.header()))!==JSON.stringify(before))throw Error('Query changed replay header');
    if(JSON.stringify(clone(game.snapshot(perspective)))!==JSON.stringify(snapshot))throw Error('Query changed personal state');
    cases.push(row);stats.cases++;
   }
   if(stats.own_different_cases===0||stats.negative_own_queries===0)
    throw Error('Required signed/current-next semantic controls absent');
   results.push({engine:version,raw_sha256:q.raw_sha256,stats,error_codes:errors,cases,
    api:'Game_API_Champion_GetPriority(game,perspective,champion,next,out_i32)',
    getter_arity:getter.length,no_action_calls:true,unknown_values_retained:false});
  }finally{game.destroy();engine.destroy();}
 }}catch(error){emit({record:'failure',error:error.stack});throw error;}
 finally{fs.closeSync(rawFd);}
 return {games:results,engine_queries:'Read-only scoped priority getters on existing recorded PREs only',
  models_fitted:0,new_matches:0,reserved_opened:0};
}
if(require.main===module){
 const plan=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 for(const [path,expected] of Object.entries(plan.bindings)){
  if(hash(fs.readFileSync(path))!==expected)throw Error('Availability dependency changed: '+path);
 }
 run(plan).then(result=>{
  fs.writeFileSync(plan.output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify(result.games.map(g=>({engine:g.engine,stats:g.stats,error_codes:g.error_codes}))));
 }).catch(error=>{console.error(error.stack);process.exitCode=1;});
}
module.exports={run};
