/** Bundle the reviewed Three.js runtime already used by Raivari. */
import {readFile,writeFile,mkdtemp,rm,mkdir} from 'node:fs/promises';
import {resolve,join,dirname,basename} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash} from 'node:crypto';
const root=resolve(process.argv[2]??'');
if(!process.argv[2])throw Error('Supply the Three.js package directory');
const pkg=JSON.parse(await readFile(join(root,'package.json'),'utf8'));
if(pkg.version!=='0.185.1')throw Error('Unreviewed Three.js version');
const scratch=await mkdtemp(join(tmpdir(),'mg-datacenter-engine-'));
try{
 const entry=join(scratch,'entry.js');
 const exports=[['controls/OrbitControls','OrbitControls'],['environments/RoomEnvironment','RoomEnvironment'],['loaders/RGBELoader','RGBELoader'],['geometries/RoundedBoxGeometry','RoundedBoxGeometry'],['lights/RectAreaLightUniformsLib','RectAreaLightUniformsLib'],['postprocessing/EffectComposer','EffectComposer'],['postprocessing/RenderPass','RenderPass'],['postprocessing/GTAOPass','GTAOPass'],['postprocessing/OutputPass','OutputPass'],['utils/BufferGeometryUtils','mergeGeometries']];
 await writeFile(entry,'import * as THREE from "three";export {THREE};export * from "three";\n'+exports.map(([p,n])=>`export {${n}} from "three/addons/${p}.js";`).join('\n'));
 const result=await Bun.build({entrypoints:[entry],target:'browser',minify:true,plugins:[{name:'reviewed-three',setup(b){b.onResolve({filter:/^three(?:\/.*)?$/},({path})=>({path:path==='three'?join(root,'build/three.module.js'):join(root,'examples/jsm',path.replace(/^three\/(?:addons|examples\/jsm)\//,''))}));}}]});
 if(!result.success)throw new AggregateError(result.logs,'Renderer build failed');
 const body=`/* Three.js ${pkg.version}, MIT. See datacenter-engine.LICENSE.txt. Rebuild: scripts/build_datacenter_engine.ts */\n`+await result.outputs[0].text();
 await mkdir('docs/assets/data-center',{recursive:true});
 await writeFile('docs/assets/datacenter-engine.mjs',body);
 await writeFile('docs/assets/datacenter-engine.LICENSE.txt',await readFile(join(root,'LICENSE')));
 await writeFile('docs/assets/data-center/engine.json',JSON.stringify({library:'Three.js',version:pkg.version,sha256:createHash('sha256').update(body).digest('hex'),license:'MIT',source:'https://github.com/mrdoob/three.js/tree/r185',scope:'Renderer and unmodified addons. Authored room geometry is separate from measured ESIF telemetry.'},null,2)+'\n');
 console.log(`${body.length} bytes`);
}finally{if(dirname(scratch)!==resolve(tmpdir())||!basename(scratch).startsWith('mg-datacenter-engine-'))throw Error('Unsafe scratch directory');await rm(scratch,{recursive:true});}
