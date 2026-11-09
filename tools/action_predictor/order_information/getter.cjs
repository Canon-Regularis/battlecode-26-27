'use strict';
function priority(game,engine,perspective,champion,next){
 const getter=game.wasmExports.Game_API_Champion_GetPriority;
 if(typeof getter!=='function'||getter.length!==5)throw Error('Unsupported scoped priority ABI');
 const code=getter(game.handle,game.perspectivePointer(perspective),champion,Number(next),game.args);
 return {code,available:code===0,value:code===0?engine.memory.getInt32(game.args,true):null};
}
module.exports={priority};
