import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import axe from 'axe-core';
import {launchAuditBrowser} from './audit_browser.mjs';
const origin=process.env.SITE_URL??'http://127.0.0.1:8794',out='artifacts/design-review/datacenter';
await mkdir(out,{recursive:true});
const browser=await launchAuditBrowser(process.env.DATACENTER_SOFTWARE==='1'?{args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}:process.platform==='win32'?{args:['--use-angle=d3d11','--ignore-gpu-blocklist']}:{}),results=[];
try{
 for(const [width,theme] of [[1440,'night'],[390,'afterlight']]){
  const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'}),errors=[],requests=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{requests.push(r.url());if(!['GET','HEAD'].includes(r.method()))writes.push(r.url());});
  await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
  await page.goto(`${origin}/specimens/data-center/`);await page.screenshot({path:`${out}/${width}-opening.png`});
  assert.ok(!requests.some(u=>/esif-week|datacenter-engine|studio-small|pathtracer\.mjs/.test(u)),'heavy account and renderer stay on demand');
  await page.locator('#dc-load-data').click();await page.locator('#dc-workspace').waitFor({state:'visible'});
  assert.match(await page.locator('#dc-load-status').innerText(),/Verified extract/);
  assert.ok(!requests.some(u=>/datacenter-engine|studio-small|pathtracer\.mjs/.test(u)),'data-only mode does not fetch 3D');
  assert.equal(await page.locator('#dc-hour-a option').count(),168);assert.equal(await page.locator('#dc-hours button').count(),168);
  assert.match(await page.locator('#dc-contrast').innerText(),/10.08% higher/);
  assert.match(await page.locator('#dc-accounts').innerText(),/2,682.661/);assert.match(await page.locator('#dc-accounts').innerText(),/2,952.992/);
  await page.locator('[data-meter="pump_kw"]').click();assert.match(await page.locator('#dc-meter-copy').innerText(),/filter-pump allowance belongs to the cooling/);
  await page.locator('#dc-scrub').focus();await page.keyboard.press('Home');const clock=await page.locator('#dc-clock').innerText();await page.keyboard.press('ArrowRight');assert.notEqual(await page.locator('#dc-clock').innerText(),clock);
  await page.locator('#dc-play').click();await page.waitForTimeout(750);await page.locator('#dc-play').click();const paused=await page.locator('#dc-clock').innerText();await page.waitForTimeout(700);assert.equal(await page.locator('#dc-clock').innerText(),paused);
  await page.locator('#dc-example').click();await page.locator('#dc-run-rehearsal').click();assert.match(await page.locator('#dc-rehearsal-result').innerText(),/130.99/);
  const downloadEvent=page.waitForEvent('download');await page.locator('#dc-export').click();const dl=await downloadEvent;const file=`${out}/${width}-inspection.json`;await dl.saveAs(file);const inspection=JSON.parse(await readFile(file,'utf8'));
  assert.equal(inspection.signed,false);assert.match(inspection.licenseNotice,/USE OR PERFORMANCE OF THE DATA/);assert.ok(Math.abs(inspection.rehearsal.deliveredKWh-322)<1e-7);assert.equal(inspection.source.inputSha256['power.parquet'],'19cd12405dde9144b1a360e8c8418666c399a3d0d15a7f846880d71ab22f9dd4');
  await page.locator('#dc-grid-cap').selectOption('3000');assert.match(await page.locator('#dc-rehearsal-result').innerText(),/Assumptions changed/);await page.locator('#dc-run-rehearsal').click();assert.match(await page.locator('#dc-rehearsal-result').innerText(),/0.00/);
  await page.locator('#dc-hours [aria-pressed="true"]').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#dc-hour-b').inputValue(),'2025-07-18T10');assert.match(await page.locator('#dc-rehearsal-result').innerText(),/Account B changed/);
  await page.locator('#dc-swap').click();assert.equal(await page.locator('#dc-hour-a').inputValue(),'2025-07-18T10');
  await page.locator('#dc-example').click();await page.locator('.dc-comparison').screenshot({path:`${out}/${width}-comparison.png`,style:'.site-header{visibility:hidden!important}'});
  await page.addScriptTag({content:axe.source});const a=await page.evaluate(()=>axe.run(document.querySelector('main'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));assert.deepEqual(a.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(width===390){await page.setViewportSize({width:320,height:850});await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
  await page.locator('.dc-film summary').click();await page.locator('video').evaluate(v=>v.load());await page.waitForFunction(()=>document.querySelector('video').readyState>=1);const media=await page.locator('video').evaluate(v=>({duration:v.duration,width:v.videoWidth,tracks:v.textTracks.length}));assert.ok(media.duration>25&&media.duration<60);assert.equal(media.width,1280);assert.equal(media.tracks,1);await page.locator('video').evaluate(async v=>{v.muted=true;await v.play();});await page.waitForFunction(()=>document.querySelector('video').currentTime>.2);await page.locator('video').evaluate(v=>v.pause());await page.locator('.dc-film summary').click();
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);results.push({width,theme,axeViolations:0,errors,writes,account:'measured',comparison:'energy-weighted',export:'full notice and assumptions',overflow:false});await page.close();
 }
 // Exercise real WebGL separately at a compact viewport. Software devices receive
 // an explicitly reduced scene; the numerical account is identical.
 const graphics=await browser.newPage({viewport:{width:640,height:600},reducedMotion:'reduce'}),graphicsErrors=[];
 graphics.on('pageerror',e=>graphicsErrors.push(e.message));graphics.on('console',m=>{if(m.type()==='error')graphicsErrors.push(m.text());});
 await graphics.goto(`${origin}/specimens/data-center/`);await graphics.locator('#dc-load-data').click();await graphics.locator('#dc-workspace').waitFor({state:'visible'});
 await graphics.locator('#dc-room').scrollIntoViewIfNeeded();await graphics.locator('#dc-start-room').evaluate(b=>b.click());
 await graphics.waitForFunction(()=>document.querySelector('#dc-room').dataset.rendered==='true',{},{timeout:120000});
 assert.equal(await graphics.locator('#dc-poster').isHidden(),true);assert.equal(await graphics.locator('#dc-room canvas').count(),1);
 await graphics.locator('[data-camera="pump_kw"]').click();await graphics.waitForTimeout(700);await graphics.locator('#dc-room').scrollIntoViewIfNeeded();
 await graphics.locator('#dc-room').screenshot({path:`${out}/working-room.png`,timeout:120000});
 assert.deepEqual(graphicsErrors,[]);await graphics.close();
 // A deliberately unavailable graphics context must leave the measured account usable.
 const fallback=await browser.newPage();await fallback.addInitScript(()=>{HTMLCanvasElement.prototype.getContext=new Proxy(HTMLCanvasElement.prototype.getContext,{apply(fn,that,args){return /webgl/.test(args[0])?null:Reflect.apply(fn,that,args);}});});
 await fallback.goto(`${origin}/specimens/data-center/`);await fallback.locator('#dc-load-room').click();await fallback.waitForFunction(()=>document.querySelector('#dc-load-status').textContent.includes('renderer is unavailable'));assert.equal(await fallback.locator('#dc-export').isEnabled(),true);assert.equal(await fallback.locator('#dc-poster').isVisible(),true);await fallback.close();
 await writeFile(`${out}/audit.json`,JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results,null,2));
}finally{await browser.close();}
