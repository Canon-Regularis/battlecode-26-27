'use strict';
// Recorded MAIN replay only. No action calls, branching, matches or bot code.
const fs=require('node:fs'),zlib=require('node:zlib');
const {once}=require('node:events');
async function main(q){
 const {open,restore,recordedHeader,canonical}=require(q.reader+'/frozen_v1_5/micro_playback.cjs');
 const {position}=require(q.reader+'/frozen_v1_5/playback.cjs');
 const {game,engine}=await open(q);
 const output=fs.createWriteStream(q.output,{flags:'wx'}),gzip=zlib.createGzip();gzip.pipe(output);
 const stats={setters:0,unchanged_setters:0,post_scheduled_matches:0,rollovers:0,rollover_mismatches:0,samples:[],mismatches:[]};
 const previous=new Map();let rows=0;
 async function emit(row){if(!gzip.write(JSON.stringify(row)+'\n'))await once(gzip,'drain');}
 function own(actor){return game.snapshot({team:q.team,champion:actor}).champions.find(e=>e.entity.index===actor);}
 function value(me,key){return (me.known&1)&&Number.isSafeInteger(me[key])?me[key]:null;}
 try{
  for(const turn of q.turns){
   restore(game,turn.entry);
   for(const root of turn.roots){
    let walked=0;
    while(position(game.header())!==root.pre){game.replayNext();if(++walked>100000)throw Error('PRE nonprogress');}
    const h=recordedHeader(game.header());
    if(h.phase!==10||h.currentChampion!==turn.actor||h.round!==turn.round)throw Error('PRE actor/round/phase');
    const me=own(turn.actor);
    if(me.team!==q.team||me.entity.index!==turn.actor)throw Error('Personal perspective mismatch');
    // Copy scalar values before replayNext: SDK snapshots may alias engine memory.
    const current=value(me,'priority'),scheduled=value(me,'nextPriority');
    const row={record:'priority_pre',actor:turn.actor,team:q.team,turn:turn.id,round:turn.round,pre:root.pre,event:root.event,
       current,scheduled,current_available:current!==null,scheduled_available:scheduled!==null,target:root.target};
    const prev=previous.get(turn.actor);
    if(prev&&turn.round>prev.round&&prev.scheduled!==null&&current!==null){
     stats.rollovers++;if(current!==prev.scheduled){stats.rollover_mismatches++;if(stats.mismatches.length<12)stats.mismatches.push({actor:turn.actor,pre:root.pre,round:turn.round,current,previous:prev});}
    }
    await emit(row);rows++;
    game.replayNext();
    if(position(game.header())!==root.event||canonical(recordedHeader(game.header()))!==canonical(root.header))throw Error('Recorded action verification');
    let next=scheduled;
    if(root.classification==='priority'){
     const argument=root.header.step.priority;
     if(!Number.isSafeInteger(argument))throw Error('Noninteger recorded priority');
     const after=own(turn.actor);next=value(after,'nextPriority');stats.setters++;
     if(scheduled===argument)stats.unchanged_setters++;
     if(next===argument)stats.post_scheduled_matches++;
     else throw Error('Recorded setter does not produce scheduled priority');
     if(stats.samples.length<4)stats.samples.push({actor:turn.actor,pre:root.pre,event:root.event,current,scheduled,recorded_argument:argument,post_scheduled:next,post_current:value(after,'priority')});
    }
    previous.set(turn.actor,{round:turn.round,scheduled:next});
   }
  }
  // POST samples are audit-only and never consumed as neural input features.
  await emit({record:'audit_complete',rows,stats});gzip.end();await once(output,'finish');
 }catch(error){gzip.destroy();output.destroy();throw error;}
 finally{game.destroy();engine.destroy();}
}
main(JSON.parse(fs.readFileSync(process.argv[2],'utf8'))).catch(error=>{console.error(error.stack);process.exitCode=1;});
