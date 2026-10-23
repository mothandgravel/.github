/** Capture a fixed authored room, with source and pixel checks before publication. */
import {launchAuditBrowser} from './audit_browser.mjs';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
const out='artifacts/design-review/datacenter';
await mkdir(out,{recursive:true});
const hash=body=>createHash('sha256').update(body).digest('hex');
const sourceSHA256=hash((await readFile('docs/assets/datacenter-room.mjs','utf8')).replaceAll('\r\n','\n'));
const browser=await launchAuditBrowser(process.platform==='win32'?{args:['--use-angle=d3d11','--ignore-gpu-blocklist']}:{});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000},reducedMotion:'reduce'}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(`${process.env.SITE_URL??'http://127.0.0.1:8794'}/specimens/data-center/`);
 await page.setContent('<style>html,body{margin:0;background:#161c1d}#room{width:1600px;height:1000px}canvas{display:block;width:100%;height:100%}</style><div id="room"></div>');
 await page.evaluate(async()=>{const {createRoom}=await import('/assets/datacenter-room.mjs');window.room=await createRoom(document.getElementById('room'));});
 await page.waitForFunction(()=>document.getElementById('room').dataset.rendered==='true',{},{timeout:90000});
 await page.waitForTimeout(1000);await page.evaluate(()=>window.room.refine(128,{scale:1}));
 await page.waitForFunction(()=>window.room.getInfo().samples>=128||window.room.getInfo().contextLost,{},{timeout:900000});
 const renderer=await page.evaluate(()=>window.room.getInfo());assert.equal(renderer.contextLost,false);assert.ok(renderer.samples>=128);
 const probe=await page.evaluate(()=>window.room.probe());assert.ok(probe.every(Number.isFinite));assert.ok(probe.slice(0,3).some(v=>v>.001));
 const pixels=await page.evaluate(()=>window.room.capture());
 const imageCheck=await page.evaluate(async url=>{const img=await createImageBitmap(await(await fetch(url)).blob());const c=new OffscreenCanvas(img.width,img.height),ctx=c.getContext('2d');ctx.drawImage(img,0,0);const values=ctx.getImageData(0,0,img.width,img.height).data;let sum=0,sum2=0,n=0;for(let i=0;i<values.length;i+=256){const lum=(values[i]+values[i+1]+values[i+2])/3;sum+=lum;sum2+=lum*lum;n++;}return {mean:sum/n,variance:sum2/n-(sum/n)**2,width:img.width,height:img.height};},pixels);
 assert.ok(imageCheck.mean>8&&imageCheck.mean<245,JSON.stringify(imageCheck));assert.ok(imageCheck.variance>100,JSON.stringify(imageCheck));assert.deepEqual(errors,[]);
 assert.equal(hash((await readFile('docs/assets/datacenter-room.mjs','utf8')).replaceAll('\r\n','\n')),sourceSHA256,'Room source changed during capture');
 await writeFile(`${out}/room-refined.png`,Buffer.from(pixels.split(',')[1],'base64'));
 await writeFile(`${out}/room-capture.json`,JSON.stringify({renderer,imageCheck,probe,viewport:{width:1600,height:1000},sourceSHA256,method:'Native 1600 x 1000 radiance buffer; 128 samples, four light bounces, authored edge-aware denoising and AgX tone mapping. No telemetry-derived rack power or light simulation.'},null,2)+'\n');
 console.log(JSON.stringify({renderer,imageCheck,probe}));
}finally{await browser.close();}
for(const [target,options]of[
 ['docs/assets/specimens/data-center/room-cover.jpg',['-q:v','3']],
 ['docs/assets/notes/016-cover-1600.webp',['-c:v','libwebp','-quality','87']],
 ['docs/assets/notes/016-cover-800.webp',['-vf','scale=800:-1','-c:v','libwebp','-quality','87']],
 ['docs/assets/notes/016-cover-social.jpg',['-vf','scale=1200:-1,crop=1200:630','-q:v','3']]
])execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-i',`${out}/room-refined.png`,...options,target],{stdio:'inherit'});
