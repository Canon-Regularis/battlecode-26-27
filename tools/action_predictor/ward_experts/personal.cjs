// Recorded PRE queries only. Never calls actions, sandbox, bots or new games.
'use strict';const fs=require('node:fs'),crypto=require('node:crypto');const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function run(q){
 const jobs=JSON.parse(fs.readFileSync('.cambc/action-predictor/v7/jobs.json'));const j=jobs.find(j=>j.split===q.split&&j.record.raw_sha256===q.raw_sha256);if(!j||!['train','validation'].includes(j.split))throw Error('Ineligible replay');
 const base=JSON.parse(fs.readFileSync(q.original_query));if(base.raw_sha256!==q.raw_sha256)throw Error('Raw binding');const {open,restore}=require(base.reader+'/frozen_v1_5/micro_playback.cjs');const {position}=require(base.reader+'/frozen_v1_5/playback.cjs');const {game,engine,version,wasm}=await open(base);const fd=fs.openSync(q.output,'wx');const emit=x=>fs.writeSync(fd,JSON.stringify(x)+'\n');
 try{
  const radius=game.wasmExports.Game_Visualiser_WardPlacementRange();if(radius!==2||game.wardPlacementRange!==2)throw Error('Historical radius changed');emit({record:'metadata',version,wasm_sha256:wasm,radius,source_sha256:sha(__filename),query_sha256:sha(process.argv[2]),original_query_sha256:sha(q.original_query)});
  for(const r of q.requests){
   if(![0,1].includes(r.perspective.team)||r.index<j.offset||r.index>=j.offset+j.rows)throw Error('Personal eligibility');restore(game,r.pre);const h=game.header();if(position(h)!==r.pre||h.phase!==10||h.currentChampion!==r.perspective.champion)throw Error('PRE ownership');
   const p=r.perspective,resources=game.getWards(p,p.champion);const occupied={};
   for(const [name,method] of [['ally','Game_API_GetAllyWardOccupancy'],['enemy','Game_API_GetEnemyWardOccupancy'],['allyControl','Game_API_GetAllyControlWardOccupancy'],['enemyControl','Game_API_GetEnemyControlWardOccupancy']]){
    const board=game.createVisualiserBitboard();try{game.check(game.wasmExports[method](game.handle,game.perspectivePointer(p),board.buffer));occupied[name]=Array.from(board.getSetBits());}finally{board.destroy();}
   }
   const snapshot=game.snapshot(p);let wards=[];
   for(const [field,kind] of [['wards',3],['controlWards',4]])for(const w of snapshot[field]||[]){
    const key=(w.team===p.team?'ally':'enemy')+(kind===4?'Control':'');if(!occupied[key].some(v=>v.x===w.position.x&&v.y===w.position.y))continue;
    // Personal API must authorize this exact entity before its personal-snapshot
    // fields enter the cache. No owner live state or omniscient snapshot read.
    game.check(game.wasmExports[kind===3?'Game_API_Ward_Get':'Game_API_ControlWard_Get'](game.handle,game.perspectivePointer(p),w.entity.index,game.args));
    wards.push({kind,position:w.position,team:w.team,own:w.owner?.index===p.champion,timer:w.timer,radius:w.radius,disabled:w.disabled});
   }
   const board=game.createVisualiserBitboard();let range;try{board.drawChebyshev(r.position.x,r.position.y,radius);range=Array.from(board.getSetBits());}finally{board.destroy();}
   const candidates=range.filter(v=>!occupied.ally.some(a=>a.x===v.x&&a.y===v.y));emit({record:'ward_pre',index:r.index,pre:r.pre,perspective:p,availability:'personal_api',resources,wards,occupied,candidates});
  }
  emit({record:'complete',rows:q.requests.length});
 }finally{fs.closeSync(fd);game.destroy();engine.destroy();}
}
run(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(e=>{console.error(e.stack);process.exitCode=1});
