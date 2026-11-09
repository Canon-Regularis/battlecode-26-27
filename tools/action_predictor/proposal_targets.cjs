// Personal read-only altar-lock queries at recorded eligible PREs. No actions.
'use strict';
const fs=require('node:fs'),crypto=require('node:crypto');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function run(q){
 const jobs=JSON.parse(fs.readFileSync('.cambc/action-predictor/v7/jobs.json','utf8'));
 const j=jobs.find(j=>j.record.raw_sha256===q.raw_sha256&&j.split===q.split);
 if(!j||!['train','validation'].includes(q.split))throw Error('Not an eligible original job');
 if(q.requests.some(r=>r.index<j.offset||r.index>=j.offset+j.rows||![0,1].includes(r.perspective.team)))throw Error('Invalid personal request');
 const base=JSON.parse(fs.readFileSync(q.original_query,'utf8'));
 if(base.raw_sha256!==q.raw_sha256)throw Error('Raw binding');
 const {open,restore}=require(base.reader+'/frozen_v1_5/micro_playback.cjs');
 const {position}=require(base.reader+'/frozen_v1_5/playback.cjs');
 const {game,engine,version,wasm}=await open(base);const fd=fs.openSync(q.output,'wx');
 const emit=row=>fs.writeSync(fd,JSON.stringify(row)+'\n');
 try{
  if(game.constants.wardPlacementRange!==2)throw Error('Historical ward range changed');
  emit({record:'metadata',raw_sha256:q.raw_sha256,engine:version,wasm_sha256:wasm,query_sha256:sha(process.argv[2]),source_sha256:sha(__filename)});
  for(const r of q.requests){
   restore(game,r.pre);const h=game.header();
   if(position(h)!==r.pre||h.phase!==10||h.currentChampion!==r.perspective.champion)throw Error('PRE ownership');
   const locks=JSON.parse(JSON.stringify(game.altarLocks(r.perspective)));
   emit({record:'personal_targets',index:r.index,pre:r.pre,perspective:r.perspective,availability:'personal_api',altar_locks:locks});
  }
  emit({record:'complete',rows:q.requests.length});
 }finally{fs.closeSync(fd);game.destroy();engine.destroy();}
}
run(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(e=>{console.error(e.stack);process.exitCode=1;});
