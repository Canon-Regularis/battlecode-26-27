'use strict';
const assert=require('node:assert/strict');
const {collect,eligibility}=require('./capture.cjs');
assert.throws(()=>eligibility({split:'reserved'}),/Ineligible split/);
function fixture(fault){
 const calls=[],logs=[];
 const snapshot={champions:[
  {entity:{index:7},team:0,known:1,priority:-13,nextPriority:27},
  {entity:{index:8},team:0,known:1,priority:-2147483648,nextPriority:2147483647},
  {entity:{index:9},team:1,known:1,priority:123,nextPriority:2080375425},
  {entity:{index:10},team:1,known:0,priority:999999,nextPriority:999998}]};
 const engine={memory:{getInt32(pointer,little){assert.equal(little,true);return value;}}};let value=0;
 const game={handle:1,args:0,perspectivePointer(p){assert.deepEqual(p,{team:0,champion:7});return 2;},
  wasmExports:{Game_API_Champion_GetPriority:function(h,p,c,next,out){calls.push([c,next]);
   if(fault==='error'&&c===8)return 42;
   if(c===9&&!next)return 97;
   const unit=snapshot.champions.find(x=>x.entity.index===c);value=next?unit.nextPriority:unit.priority;return 0;}}};
 const item={row:123,pre:'9:3',actor:7,round:6,current:-13,scheduled:27,current_available:true,scheduled_available:true,label:'must_not_be_emitted'};
 return {game,engine,item,snapshot,calls,logs,emit:r=>logs.push(r)};
}
const a=fixture();const row=collect(a.game,a.engine,a.item,0,a.emit,a.snapshot);
assert.deepEqual(a.calls,[[7,0],[7,1],[8,0],[8,1],[9,0],[9,1]]);
assert.equal(row.others.length,2);assert.equal(row.others[0].current,-2147483648);assert.equal(row.others[0].scheduled,2147483647);
assert.equal(row.others[1].current,null);assert.equal(row.others[1].current_available,false);assert.equal(row.others[1].scheduled,2080375425);
assert.equal(row.others[1].role,'enemy');assert.equal(row.label,undefined);assert.equal(row.others[0].entity_index,undefined);
const b=fixture('error');assert.throws(()=>collect(b.game,b.engine,b.item,0,b.emit,b.snapshot),/Unexpected other query/);
assert.equal(b.logs.at(-1).code,42);assert(!b.logs.some(x=>x.record==='order_pre'));
const c=fixture();c.item.current=123;assert.throws(()=>collect(c.game,c.engine,c.item,0,c.emit,c.snapshot),/Own API differs/);
assert.equal(c.logs[0].record,'own_query');assert(!c.calls.some(x=>x[0]!==7));
console.log('Integration getter contracts passed: scoped masks, exact integers, pairing, unknown-unit exclusion and raw-before-check failure.');
