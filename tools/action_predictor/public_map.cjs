'use strict';
// STATIC map queries only: no snapshots, dynamic camp state, seeks or actions.
const fs=require('node:fs');
async function main(q){
 const {open}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
 const {publicRouteMetadata}=require(q.reader+'/decisions/destinations_static.cjs');
 const {game,engine}=await open(q);
 try{
  const route=publicRouteMetadata(game),walls=[],holes=[],bushes=[];
  for(let y=0;y<route.height;y++)for(let x=0;x<route.width;x++){
   const i=y*route.width+x;
   if(game.isWall(x,y))walls.push(i);
   if(game.isHole(x,y))holes.push(i);
   if(game.isBush(x,y))bushes.push(i);
  }
  const camps=game.campSpawns.map(p=>({x:p.x,y:p.y}));
  fs.writeFileSync(q.output,JSON.stringify({schema:1,route,walls,holes,bushes,camps})+'\n',{flag:'wx'});
 }finally{game.destroy();engine.destroy();}
}
main(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(e=>{console.error(e.stack);process.exitCode=1;});
