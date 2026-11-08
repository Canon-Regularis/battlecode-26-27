'use strict';
const assert=require('node:assert/strict');
const {priority}=require('./getter.cjs');
const memory=new DataView(new ArrayBuffer(32));
const game={handle:11,args:0,perspectivePointer:p=>{assert.deepEqual(p,{team:1,champion:3});return 8;},
 wasmExports:{Game_API_Champion_GetPriority:function(handle,perspective,champion,next,output){
  assert.equal(handle,11);assert.equal(perspective,8);assert.equal(output,0);
  if(champion===4)return 97;
  assert.equal(champion,3);memory.setInt32(output,next?701:-3,true);return 0;
 }}};
assert.deepEqual(priority(game,{memory},{team:1,champion:3},3,false),{code:0,available:true,value:-3});
assert.deepEqual(priority(game,{memory},{team:1,champion:3},3,true),{code:0,available:true,value:701});
assert.deepEqual(priority(game,{memory},{team:1,champion:3},4,false),{code:97,available:false,value:null});
console.log('Signed little-endian and unavailable scoped getter checks passed.');
