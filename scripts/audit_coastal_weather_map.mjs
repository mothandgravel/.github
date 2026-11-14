import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import axe from 'axe-core';
import {launchAuditBrowser} from './audit_browser.mjs';
import {radarGridAt,radarCellLocation} from '../docs/assets/coastal-weather-model.mjs';
const origin=process.env.SITE_URL??'http://127.0.0.1:8793',out='artifacts/design-review/coastal-weather-map';
await mkdir(out,{recursive:true});
const data=JSON.parse(await readFile('docs/data/coastal-weather/2026-11-11/notebook.json','utf8'));
const path='/specimens/coastal-watch/source-notebook/#cw-passage',browser=await launchAuditBrowser(),reports=[];
const settle=p=>p.waitForFunction(()=>document.getElementById('cw-cloud-map').getAttribute('aria-busy')==='false'&&document.getElementById('cw-radar-stage').getAttribute('aria-busy')==='false');
const second=async(p,v)=>{await p.locator('#cw-second').evaluate((e,v)=>{e.value=String(v);e.dispatchEvent(new Event('input',{bubbles:true}));},v);await settle(p);};
const shot=async(p,name,selector='#cw-workbench')=>{await p.locator(selector).evaluate(e=>scrollTo({top:scrollY+e.getBoundingClientRect().top-110,behavior:'instant'}));await p.screenshot({path:`${out}/${name}.png`});};
try{
 for(const [width,theme]of [[1440,'night'],[1440,'afterlight'],[390,'night'],[390,'afterlight'],[320,'night'],[320,'afterlight']]){
  const page=await browser.newPage({viewport:{width,height:1080},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);await page.goto(origin+path);await page.locator('#cw-workbench').waitFor({state:'visible'});await settle(page);
  const rain=page.locator('#cw-map-rain');assert.equal(await rain.getAttribute('visibility'),'visible');assert.equal(await rain.getAttribute('data-frame-id'),data.radar[0].id);
  assert.equal(await page.locator('#cw-map-cloud-clock').textContent(),'10:00:00 UTC');assert.equal(await page.locator('#cw-map-radar-clock').textContent(),'10:00:06 UTC');assert.equal(await page.locator('#cw-map-buoy-clock').textContent(),'10:00:00 UTC');
  assert.equal(await page.locator('[data-cw-buoy-glyph]').count(),3);assert.equal(await page.locator('[data-cw-buoy-glyph="108495"] .cw-wave-arrow').count(),0);
  await shot(page,`map-${width}-${theme}`);
  await page.locator('#cw-layer-rain').click();assert.equal(await rain.evaluate(e=>getComputedStyle(e).opacity),'0');assert.equal(await page.locator('#cw-rain-opacity').isDisabled(),true);
  assert.equal(await page.locator('#cw-map-inspect').isDisabled(),true);assert.match(await page.locator('#cw-map-radar-state').textContent(),/Layer hidden/);
  await page.locator('#cw-layer-rain').click();await page.locator('#cw-rain-opacity').evaluate(e=>{e.value='45';e.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await rain.evaluate(e=>getComputedStyle(e).opacity),'0.45');
  assert.equal(JSON.parse(await page.locator('#cw-json').textContent()).presentation.rainOpacity,.45);
  await page.locator('#cw-layer-clouds').click();assert.equal(await page.locator('#cw-cloud-map image').first().evaluate(e=>getComputedStyle(e).opacity),'0');await page.locator('#cw-layer-clouds').click();
  await page.locator('#cw-layer-buoys').click();assert.equal(await page.locator('#cw-map-wave-glyphs').isVisible(),false);await page.locator('#cw-layer-buoys').click();
  await page.locator('#cw-rain-opacity').evaluate(e=>{e.value='85';e.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.locator('#cw-map-inspect').click();await page.waitForFunction(()=>/Column/.test(document.getElementById('cw-map-cell-context').textContent));
  assert.match(await page.locator('#cw-map-cell-context').textContent(),/Started at.*not rainfall measured by the buoy/);
  const expected=radarGridAt(data.radar[0],25.235,59.965),location=radarCellLocation(data.radar[0],expected.column,expected.row);
  let receipt=JSON.parse(await page.locator('#cw-json').textContent());assert.equal(receipt.radar.selectedCell.x,expected.column);assert.equal(receipt.radar.selectedCell.y,expected.row);assert.ok(Math.abs(receipt.radar.selectedCell.location.latitude-location.latitude)<1e-9);assert.equal(receipt.radar.selectedCell.location.accuracyMetres,null);
  await page.locator('#cw-placement-compare').click();assert.equal(await page.locator('.cw-map-alternative').count(),1);assert.match(await page.locator('#cw-map-cell-position').textContent(),/Not an accuracy bound/);
  // Pick the same longitude/latitude via actual SVG screen transforms, including the phone crop.
  await page.locator('#cw-cloud-map').evaluate(e=>e.scrollIntoView({block:'center',behavior:'instant'}));
  const point=await page.locator('#cw-cloud-map').evaluate(e=>{const pt=new DOMPoint((25.7-23)/5.5*1100,(61-60.3)/2*400).matrixTransform(e.getScreenCTM());return{x:pt.x,y:pt.y};});
  await page.mouse.click(point.x,point.y);await page.waitForFunction(()=>/Column/.test(document.getElementById('cw-map-cell-context').textContent));
  const picked=radarGridAt(data.radar[0],25.7,60.3);receipt=JSON.parse(await page.locator('#cw-json').textContent());
  // Native cells can be under one CSS pixel on a phone. The browser rounds mouse
  // coordinates, so compare within one native cell, not false subpixel precision.
  assert.ok(Math.abs(receipt.radar.selectedCell.x-picked.column)<=1);assert.ok(Math.abs(receipt.radar.selectedCell.y-picked.row)<=1);
  const held={x:receipt.radar.selectedCell.x,y:receipt.radar.selectedCell.y};await second(page,43801);await page.waitForFunction(()=>/Column/.test(document.getElementById('cw-map-cell-context').textContent));
  receipt=JSON.parse(await page.locator('#cw-json').textContent());assert.equal(receipt.radar.record.id,data.radar[2].id);assert.equal(receipt.radar.selectedCell.x,held.x);assert.equal(receipt.radar.selectedCell.y,held.y);
  await shot(page,`inspection-${width}-${theme}`,'.cw-map-toolbar');
  await page.locator('#cw-placement-details summary').click();await shot(page,`placement-${width}-${theme}`,'#cw-placement-details');
  await page.locator('#cw-map-native-controls').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('#cw-cell-details').getAttribute('open'),'');assert.equal(await page.locator('#cw-cell-x').evaluate(e=>e===document.activeElement),true);
  await page.keyboard.press('ArrowUp');await page.waitForFunction(()=>/Column/.test(document.getElementById('cw-map-cell-context').textContent));
  await page.locator('[data-cw-map-buoy="108495"]').click();assert.equal(await page.locator('#cw-buoy').inputValue(),'108495');assert.match(await page.locator('[data-cw-map-buoy="108495"] strong').textContent(),/Missing height/);
  for(const s of [43205,44103,45003,45903,46502]){await second(page,s);assert.equal(await rain.getAttribute('visibility'),'hidden');assert.equal(await rain.getAttribute('data-frame-id'),null);}
  await second(page,43206);assert.equal(await rain.getAttribute('visibility'),'visible');
  await page.addScriptTag({content:axe.source});const a11y=await page.evaluate(async()=>axe.run(document.getElementById('cw-passage'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}));
  const violations=a11y.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}));assert.deepEqual(violations,[]);assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  reports.push({width,theme,errors,violations});await writeFile(out+'/audit.json',JSON.stringify(reports,null,2));await page.close();
 }
 // Native and mapped images are separate requests. A failed or wrong-but-valid PNG is not a data gap.
 for(const failure of ['network','wrong-image','delayed']){
  const page=await browser.newPage({viewport:{width:390,height:900},reducedMotion:'reduce'});const pattern='**/'+data.radar[0].mapImage;let release;
  const gate=new Promise(r=>release=r);
  await page.route(pattern,async route=>{if(failure==='delayed'){await gate;await route.continue();}else if(failure==='network')await route.abort();else await route.fulfill({contentType:'image/png',body:await readFile('docs/data/coastal-weather/2026-11-11/raw/'+data.clouds[0].sourceFile)});});
  await page.goto(origin+path);await page.locator('#cw-workbench').waitFor({state:'visible'});
  if(failure==='delayed'){
   await second(page,43801);assert.equal(await page.locator('#cw-map-rain').getAttribute('data-frame-id'),data.radar[2].id);release();await page.waitForTimeout(300);assert.equal(await page.locator('#cw-map-rain').getAttribute('data-frame-id'),data.radar[2].id);
  }else{
   await settle(page);assert.equal(await page.locator('#cw-radar-image').isVisible(),true);assert.equal(await page.locator('#cw-map-rain').getAttribute('visibility'),'hidden');assert.match(await page.locator('#cw-map-status').textContent(),failure==='wrong-image'?/failed its integrity check.*source record exists/:/could not open.*source record exists/);assert.equal(await page.locator('#cw-radar-retry').isVisible(),true);
   await page.unroute(pattern);await page.locator('#cw-radar-retry').click();await settle(page);assert.equal(await page.locator('#cw-map-rain').getAttribute('visibility'),'visible');
  }
  await page.close();
 }
 const hidden=await browser.newPage({viewport:{width:390,height:900},reducedMotion:'reduce'});
 await hidden.route('**/raw/eumetsat-20261111-1010.png',r=>r.abort());await hidden.goto(origin+path);await hidden.locator('#cw-workbench').waitFor({state:'visible'});await settle(hidden);await hidden.locator('#cw-layer-clouds').click();
 await hidden.locator('#cw-play').click();await hidden.waitForFunction(()=>Number(document.getElementById('cw-second').value)>=43806);assert.equal(await hidden.locator('#cw-play').getAttribute('aria-pressed'),'true');assert.equal(await hidden.locator('#cw-cloud-message').isVisible(),false);await hidden.locator('#cw-play').click();
 assert.equal(await hidden.locator('#cw-map-rain').getAttribute('visibility'),'visible');await hidden.close();
 const scrub=await browser.newPage({viewport:{width:1440,height:1080},reducedMotion:'reduce'});await scrub.goto(origin+path);await scrub.locator('#cw-workbench').waitFor({state:'visible'});await settle(scrub);
 await scrub.evaluate(times=>{const e=document.getElementById('cw-second');for(const v of times){e.value=String(v);e.dispatchEvent(new Event('input',{bubbles:true}));}},data.radar.map(f=>(Date.parse(f.intervalEndUtc)-Date.parse(data.windowStartUtc))/1000));
 await scrub.waitForFunction(id=>document.getElementById('cw-map-rain').dataset.frameId===id&&document.getElementById('cw-radar-image').dataset.frameId===id&&document.getElementById('cw-radar-stage').getAttribute('aria-busy')==='false',data.radar.at(-1).id);
 assert.equal(await scrub.locator('#cw-map-rain').getAttribute('visibility'),'visible');
 assert.equal(await scrub.locator('#cw-map-rain').evaluate(async e=>(await fetch(e.getAttribute('href'))).status),200,'Rapid scrub retains the current decoded blob after cache eviction');await scrub.close();
 console.log('Shared weather map: six responsive/theme configurations; georeferenced picks, separate clocks, layers, metadata sensitivity, real gaps, SHA rejection and async failure/retry passed.');
}finally{await browser.close();}
