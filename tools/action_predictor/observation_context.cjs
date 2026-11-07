'use strict';
// Earlier own PRE observations only. Read recorded MAIN, never create/branch/act.
const fs=require('node:fs'),zlib=require('node:zlib');
const {once}=require('node:events');
async function main(q){
 const {open,restore,observation,recordedHeader,canonical}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
 const {position,recordedState}=require(q.reader+'/frozen_v1_5/playback.cjs');
 const {game,engine}=await open(q);
 const output=fs.createWriteStream(q.output,{flags:'wx'}),gzip=zlib.createGzip();gzip.pipe(output);
 const clone=x=>JSON.parse(JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v));
 async function emit(row){if(!gzip.write(JSON.stringify(row)+'\n'))await once(gzip,'drain');}
 let count=0;
 try{
  for(const turn of q.turns){
   restore(game,turn.entry);
   for(const root of turn.roots){
    let walked=0;
    while(position(game.header())!==root.pre){game.replayNext();if(++walked>100000)throw Error('PRE nonprogress');}
    const header=recordedHeader(game.header());
    if(header.phase!==10||header.currentChampion!==turn.actor||header.round!==turn.round)throw Error('History PRE actor/round/phase mismatch');
    const perspective={team:q.team,champion:turn.actor};
    const state=clone(recordedState(game.snapshot(perspective)));
    const obs=observation(state,turn.actor),me=state.champions.find(e=>e.entity.index===turn.actor),own={};
    if(obs.perspective.team!==q.team||obs.perspective.champion!==turn.actor)throw Error('History perspective mismatch');
    if(me.known&1)for(const k of ['position','health','maxHealth','strength','focus','attackRange','chebyshevRange','alive'])if(me[k]!==undefined)own[k]=me[k];
    if(me.known&2)for(const k of ['items','gems','consumables','ward'])if(me[k]!==undefined)own[k]=me[k];
    if(me.known&4)for(const k of ['roundFlags','channelType','channelTimer'])if(me[k]!==undefined)own[k]=me[k];
    if(me.known&8)own.gold=me.gold;
    const movement=[];
    if(me.alive&&me.position){const board=game.createBitboard(perspective);try{game.championMovementMask(turn.actor,board);movement.push(...clone(board.getSetBits()));}finally{board.destroy();}}
    const supplement={pre:root.pre,own,movement,restrictions:game.championRestrictions(perspective,turn.actor),
       can_shop:game.canShop(perspective,turn.actor,false),can_shop_consumables:game.canShop(perspective,turn.actor,true)};
    const row={record:'history',id:q.raw_sha256+'/main/'+root.event,actor:turn.actor,team:q.team,turn:turn.id,
       round:turn.round,pre:root.pre,event:root.event,pre_header:header,observation:obs,supplement};
    game.replayNext();
    if(position(game.header())!==root.event||canonical(recordedHeader(game.header()))!==canonical(root.header))throw Error('Prior recorded action verification mismatch');
    await emit(row);count++;
   }
  }
  await emit({record:'complete',frames:count});gzip.end();await once(output,'finish');
 }catch(error){gzip.destroy();output.destroy();throw error;}
 finally{game.destroy();engine.destroy();}
}
main(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(e=>{console.error(e.stack);process.exitCode=1;});
