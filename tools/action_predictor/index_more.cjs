// Derive a terminal cursor and index an existing recording. No new games/actions.
'use strict';
const fs=require('node:fs');
const q=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const {open,restore,extract}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
const {position}=require(q.reader+'/frozen_v1_5/playback.cjs');
async function run(){
 const {game,engine}=await open(q);
 try{
  const size=game.timelineInfo().size;
  restore(game,`${size}:0`);
  let walked=0;
  while(!game.header().outcome&&game.header().phase!==11){
   if(++walked>10000)throw Error('Terminal replay cursor not found');
   const before=position(game.header());game.replayNext();
   if(before===position(game.header()))throw Error('Terminal replay did not progress');
  }
  q.terminal=position(game.header());
 }finally{game.destroy();engine.destroy();}
 fs.writeFileSync(q.terminalOutput,JSON.stringify({terminal:q.terminal}));
 await extract(q);
}
run().catch(e=>{console.error(e.stack);process.exitCode=1;});
