// Pinned read-only constants queries in two explicitly eligible TRAIN recordings.
// No createGame, actions, hypothetical branches or simulation calls.
'use strict';
const fs=require('node:fs');
async function run(){
 const jobs=JSON.parse(fs.readFileSync('.cambc/action-predictor/v7/jobs.json','utf8'));
 const results=[];
 for(const version of ['2.0.0','3.0.0']){
  const job=jobs.find(j=>j.split==='train'&&j.record.engine_version===version);
  if(!job)throw Error('Missing eligible TRAIN engine');
  const path=job.work+'/supplement/'+job.record.raw_sha256+'/query.json';
  const q=JSON.parse(fs.readFileSync(path,'utf8'));
  const {open}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
  const {game,engine}=await open(q);
  try{results.push({engine_version:version,raw_sha256:job.record.raw_sha256,constants:game.constants,methods:Object.getOwnPropertyNames(Object.getPrototypeOf(game)).filter(k=>/movement|ward|cast|reach|distance|bitboard/i.test(k))});}
  finally{game.destroy();engine.destroy();}
 }
 const output='tools/action_predictor/experiments/v10/C01-historical-constants.json';
 fs.writeFileSync(output,JSON.stringify({scope:'2eligibleTRAINread-onlypinnedreaderqueries;nohypotheticalactions',reserved_opened:0,results},(_,v)=>typeof v==='bigint'?v.toString():v,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify(results));
}
run().catch(e=>{console.error(e.stack);process.exitCode=1;});
