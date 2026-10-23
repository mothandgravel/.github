/** Optional, on-demand MIT WebGL path tracer. Never part of the initial page load. */
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {createHash} from 'node:crypto';
const root=resolve(process.argv[2]??'artifacts/graphics-runtime/node_modules');
const packages=[['three-gpu-pathtracer','0.0.26'],['three-mesh-bvh','0.9.15'],['xatlas-web','0.1.0']];
const licenses=[];
for(const [name,version] of packages){const p=JSON.parse(await readFile(join(root,name,'package.json'),'utf8'));if(p.version!==version)throw Error(`Unreviewed ${name}`);licenses.push(`${name} ${version}\n${await readFile(join(root,name,'LICENSE'),'utf8')}`);}
const result=await Bun.build({entrypoints:[join(root,'three-gpu-pathtracer/src/core/WebGLPathTracer.js')],target:'browser',minify:true,plugins:[{name:'shared-reviewed-three',setup(b){b.onResolve({filter:/^three$/},()=>({path:'./datacenter-engine.mjs',external:true}));b.onResolve({filter:/^three\//},({path})=>({path:join(root,'three/examples/jsm',path.replace(/^three\/(?:addons|examples\/jsm)\//,''))}));}}]});
if(!result.success)throw new AggregateError(result.logs,'Path tracer build failed');
const body='/* Optional path tracer, MIT. See datacenter-pathtracer.LICENSE.txt. */\n'+(await result.outputs[0].text()).replaceAll('from"three"','from"./datacenter-engine.mjs"');
await writeFile('docs/assets/datacenter-pathtracer.mjs',body);
await writeFile('docs/assets/datacenter-pathtracer.LICENSE.txt',licenses.join('\n\n'));
await writeFile('docs/assets/data-center/pathtracer.json',JSON.stringify({packages,sha256:createHash('sha256').update(body).digest('hex'),license:'MIT',source:'https://github.com/gkjohnson/three-gpu-pathtracer/tree/v0.0.26',scope:'Optional progressive light-transport rendering; no thermal or energy simulation.'},null,2)+'\n');
console.log(`${body.length} bytes`);
