import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { buildMothMeshes } from '../docs/assets/moth-mesh.mjs';
const source=JSON.parse(await readFile(new URL('../docs/assets/moth-model.json',import.meta.url)));

test('model is bound to the studio rig and keeps every gravel piece',async()=>{
  const raw=await readFile(new URL('../docs/assets/moth-rig.svg',import.meta.url));
  assert.equal(source.sourceSha256,createHash('sha256').update(raw).digest('hex'));
  assert.equal(source.wings.reduce((n,w)=>n+(w.stones?.length||0),0),37);
});
test('all articulated parts have actual depth, finite vertices and unit normals',()=>{
  const meshes=buildMothMeshes(source);assert.equal(meshes.length,6);
  let triangles=0;
  for(const mesh of meshes){
    assert.equal(mesh.data.length%27,0);triangles+=mesh.data.length/27;
    let lo=Infinity,hi=-Infinity;
    for(let i=0;i<mesh.data.length;i+=9){
      assert.ok([...mesh.data.slice(i,i+9)].every(Number.isFinite));
      assert.ok(Math.abs(Math.hypot(...mesh.data.slice(i+3,i+6))-1)<.001);
      assert.ok([...mesh.data.slice(i+6,i+9)].every(v=>v>=0&&v<=1));
      lo=Math.min(lo,mesh.data[i+2]);hi=Math.max(hi,mesh.data[i+2]);
    }
    assert.ok(hi-lo>(mesh.name==='moth-antennae'?5:15),mesh.name+' is a flat card');
  }
  assert.ok(triangles<5000,'small-scene triangle budget');
});
test('malformed model cannot silently become an empty performance',()=>{
  assert.throws(()=>buildMothMeshes({version:1,wings:[],antennae:[]}),/Invalid/);
});
