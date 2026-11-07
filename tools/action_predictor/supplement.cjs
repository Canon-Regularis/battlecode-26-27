// Read-only MAIN playback and personal queries. No game creation/actions/branches.
'use strict';
const fs=require('node:fs');
async function run(q){
 const {open,restore,recordedHeader,observation}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
 const {position,recordedState}=require(q.reader+'/frozen_v1_5/playback.cjs');
 const {publicRouteMetadata}=require(q.reader+'/decisions/destinations_static.cjs');
 const {game,engine}=await open(q);
 const clone=x=>JSON.parse(JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v));
 try{
  if(q.probe){
   restore(game,q.turns[0].entry);let actor=q.turns[0].actor,team=q.turns[0].team;
   const state=clone(recordedState(game.snapshot({team,champion:actor})));
   console.log(JSON.stringify({methods:Object.getOwnPropertyNames(Object.getPrototypeOf(game)),own:state.champions.find(c=>c.entity.index===actor),route:publicRouteMetadata(game)}));return;
  }
  const fd=fs.openSync(q.output,'wx');
  const emit=x=>fs.writeSync(fd,JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v)+'\n');
  emit({record:'map',route:publicRouteMetadata(game)});
  let count=0;
  for(const turn of q.turns){
   restore(game,turn.entry);
   for(const r of turn.roots){
    let walked=0;
    while(position(game.header())!==r.pre){game.replayNext();if(++walked>10000)throw Error('Nonprogress');}
    const pre=recordedHeader(game.header());
    if(pre.currentChampion!==turn.actor||pre.phase!==10)throw Error('PRE ownership');
    const perspective={team:turn.team,champion:turn.actor};
    const state=clone(recordedState(game.snapshot(perspective)));
    const me=state.champions.find(c=>c.entity.index===turn.actor),own={};
    if(me.known&1)for(const k of ['position','health','maxHealth','strength','focus','attackRange','chebyshevRange','alive'])if(me[k]!==undefined)own[k]=me[k];
    if(me.known&2)for(const k of ['items','gems','consumables','ward'])if(me[k]!==undefined)own[k]=me[k];
    if(me.known&4)for(const k of ['roundFlags','channelType','channelTimer'])if(me[k]!==undefined)own[k]=me[k];
    if(me.known&8)own.gold=me.gold;
    const movement=[];
    if(me.alive&&me.position){const board=game.createBitboard(perspective);try{game.championMovementMask(turn.actor,board);movement.push(...clone(board.getSetBits()));}finally{board.destroy();}}
    const row={record:'pre',id:q.raw_sha256+'/main/'+r.event,pre:r.pre,own,movement,
          restrictions:game.championRestrictions(perspective,turn.actor),
          can_shop:game.canShop(perspective,turn.actor,false),can_shop_consumables:game.canShop(perspective,turn.actor,true)};
    if(q.includeObservation){row.observation=observation(state,turn.actor);row.pre_header=pre;}
    if(q.includeObservation){
     game.replayNext();
     if(position(game.header())!==r.event||game.header().step.kind!==r.header.step.kind)throw Error('Recorded root differs');
     if(r.header.step.kind===4){const p=clone(game.snapshot(perspective)).champions.find(c=>c.entity.index===turn.actor).position;row.post_move_matches=JSON.stringify(p)===JSON.stringify(r.header.step.to);}
    }
    if(r.classification==='shop'){
     if(!q.includeObservation)game.replayNext();
     if(position(game.header())!==r.event)throw Error('Transaction cursor mismatch');
     const after=clone(game.snapshot(perspective)).champions.find(c=>c.entity.index===turn.actor);
     const delta=(a,b)=>(b||[]).map((v,i)=>v-(a?.[i]||0));
     row.transaction_label={gold:after.gold-me.gold,items:delta(me.items,after.items),consumables:delta(me.consumables,after.consumables)};
    }
    emit(row);
    count++;
   }
  }
  emit({record:'complete',decisions:count});fs.closeSync(fd);
 }finally{game.destroy();engine.destroy();}
}
const query=JSON.parse(fs.readFileSync(process.argv[2],'utf8').replace(/^\uFEFF/,''));
run(query).catch(e=>{console.error(e.stack);process.exitCode=1;});
