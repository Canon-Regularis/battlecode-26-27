// Four recorded DEV PRE restorations; personal API only, no proposed actions.
'use strict';
const fs=require('node:fs'),crypto=require('node:crypto');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function main(){
 const queryPath='.cambc/action-predictor/v11/U00-target-kind-query.json';
 const cases=JSON.parse(fs.readFileSync(queryPath,'utf8')),rows=[];
 if(cases.length!==4)throw Error('Expected four previously identified missing targets');
 for(const c of cases){
  if(![0,1].includes(c.team))throw Error('No omniscient perspective');
  const q=JSON.parse(fs.readFileSync(c.query,'utf8'));
  if(q.raw_sha256!==c.raw_sha256)throw Error('Raw binding');
  const {open,restore}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
  const {position}=require(q.reader+'/frozen_v1_5/playback.cjs');
  const {game,engine,version,wasm}=await open(q);
  try{
   restore(game,c.pre);const h=game.header();
   if(position(h)!==c.pre||h.phase!==10||h.currentChampion!==c.actor)throw Error('Personal PRE ownership');
   // Pinned wrapper altarLocks(perspective) queries API ally/enemy occupancy and
   // Game_API_GetAltarLock with this same personal perspective. No visualiser
   // omniscient snapshot is used. Only returned personally available locks read.
   const locks=JSON.parse(JSON.stringify(game.altarLocks({team:c.team,champion:c.actor})));
   rows.push({index:c.index,raw_sha256:c.raw_sha256,pre:c.pre,actor:c.actor,team:c.team,engine:version,wasm_sha256:wasm,target:c.target,matching_personal_altar_locks:locks.filter(v=>v.position.x===c.target.x&&v.position.y===c.target.y),reader_sha256:hash(q.reader+'/frozen_v1_5/micro_playback.cjs')});
  }finally{game.destroy();engine.destroy();}
 }
 const output='tools/action_predictor/experiments/v11/U00-target-kinds.json';
 fs.writeFileSync(output,JSON.stringify({source_sha256:hash(__filename),query_sha256:hash(queryPath),scope:'Four originalDEVrecordedPREs;personalAPIaltarlockswithactor/perspectivevalidation. Noaction/simulation/newreplaydownload. TargetcoordinateevidencedoesnotuniquelycertifyoriginalentityID.',rows,new_fits:0,reserved_opened:0},null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify(rows));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
