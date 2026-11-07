'use strict';
// D01 diagnostic only: read recorded MAIN; never act, branch, run bots or match.
const fs=require('node:fs');
async function main(q){
 const {open,restore,recordedHeader,canonical}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
 const {recordedState,position}=require(q.reader+'/frozen_v1_5/playback.cjs');
 const {game,engine,version}=await open(q);
 const own=actor=>{
  const state=recordedState(game.snapshot({team:q.team,champion:actor}));
  const me=state.champions.find(e=>e.entity.index===actor);
  if(!me||me.team!==q.team||!(me.known&4))throw Error('Personal own channel state unavailable');
  return Object.fromEntries(['known','channelType','channelTimer','roundFlags','priority','nextPriority'].map(k=>[k,me[k]]));
 };
 const rows=[];
 try{
  for(const sample of q.samples){
   restore(game,sample.pre);const pre=recordedHeader(game.header());
   if(pre.phase!==10||pre.currentChampion!==sample.actor)throw Error('PRE actor or phase');
   const before=own(sample.actor);game.replayNext();const post=recordedHeader(game.header());
   if(position(post)!==sample.event||canonical(post)!==canonical(sample.header))throw Error('Target header mismatch');
   const after=own(sample.actor),following=[];
   // Header-only future evidence is diagnostic, never saved as predictor input.
   for(let i=0;i<24;i++){
    const old=position(game.header());game.replayNext();const h=recordedHeader(game.header());
    if(position(h)===old)break;
    following.push({cursor:position(h),phase:h.phase,currentChampion:h.currentChampion,step:h.step});
    if(h.step.substep===0)break;
   }
   rows.push({id:sample.id,actor:sample.actor,pre:sample.pre,event:sample.event,before,after,pre_header:pre,post_header:post,following});
  }
  if(fs.existsSync(q.output))throw Error('Refuse overwrite of completed probe output');
  fs.writeFileSync(q.output,JSON.stringify({record:'diagnostic',split:'train',version,raw_sha256:q.raw_sha256,rows,new_fits:0,input_features_created:false})+'\n',{flag:'wx'});
 }finally{game.destroy();engine.destroy();}
}
main(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(e=>{console.error(e.stack);process.exitCode=1;});
