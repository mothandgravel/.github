import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import axe from 'axe-core';
import {launchAuditBrowser} from './audit_browser.mjs';

const origin=process.env.SITE_URL??'http://127.0.0.1:8793';
const out='artifacts/design-review/coastal-weather';await mkdir(out,{recursive:true});
const data=JSON.parse(await readFile(new URL('../docs/data/coastal-weather/2026-11-11/notebook.json',import.meta.url),'utf8'));
const browser=await launchAuditBrowser();
const set=async(page,value)=>{
  await page.locator('#cw-second').evaluate((e,v)=>{e.value=String(v);e.dispatchEvent(new Event('input',{bubbles:true}));},value);
};
const settle=page=>page.waitForFunction(()=>document.getElementById('cw-cloud-map').getAttribute('aria-busy')==='false'&&document.getElementById('cw-radar-stage').getAttribute('aria-busy')==='false');
const scroll=async(page,selector)=>page.locator(selector).evaluate(e=>scrollTo({top:scrollY+e.getBoundingClientRect().top-260,behavior:'instant'}));
const reports=[];
try{
  for(const [width,theme]of [[1440,'night'],[1440,'afterlight'],[390,'night'],[390,'afterlight'],[320,'night'],[320,'afterlight']]){
    const page=await browser.newPage({viewport:{width,height:1080},reducedMotion:'reduce'}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
    await page.goto(origin+'/specimens/coastal-watch/source-notebook/#cw-passage');
    await page.locator('#cw-workbench').waitFor({state:'visible'});await settle(page);
    assert.equal(await page.locator('audio,video').count(),0);
    assert.equal(await page.locator('#cw-utc').textContent(),'10:00:06 UTC');
    assert.equal(await page.locator('#cw-sky').getAttribute('data-ready'),'true');
    assert.equal(await page.locator('#cw-radar-image').isVisible(),true);
    assert.equal(await page.locator('#cw-radar-pick').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
    await page.addStyleTag({content:'html{scroll-behavior:auto!important}'});
    await scroll(page,'#cw-passage');await page.screenshot({path:`${out}/passage-${width}-${theme}.png`});
    await scroll(page,'.cw-radar-panel');await page.screenshot({path:`${out}/radar-${width}-${theme}.png`});
    await scroll(page,'.cw-sea-panel');await page.screenshot({path:`${out}/sea-${width}-${theme}.png`});
    const range=await page.locator('#cw-second').boundingBox(),cursor=await page.locator('#cw-cloud-ribbon .cw-ribbon-cursor').boundingBox();
    // On mobile, ribbons and controls retain a common data domain, while labels occupy their own column.
    assert.ok(range.width>100&&cursor.width<4);
    await page.locator('#cw-cell-details summary').click();
    const bytes=gunzipSync(await readFile(new URL('../docs/data/coastal-weather/2026-11-11/'+data.radar[0].pixels,import.meta.url)));
    for(const kind of ['missing','below','numeric']){
      let cell=0;
      for(;cell<720*720;cell++){const n=bytes.readFloatLE(cell*4);if(kind==='missing'?n===65535:kind==='below'?n===0:n>0&&n<65535)break;}
      assert.ok(cell<720*720);
      await page.locator('#cw-cell-x').fill(String(cell%720));await page.locator('#cw-cell-y').fill(String(Math.floor(cell/720)));
      await page.waitForFunction(()=>!/Opening/.test(document.getElementById('cw-cell-value').textContent));
      const text=await page.locator('#cw-cell-value').textContent();
      if(kind==='missing')assert.match(text,/no data.*unknown/);else if(kind==='below')assert.match(text,/below detection.*No measured zero/);else assert.match(text,/Stored float.*mm\/h/);
    }
    await page.locator('#cw-cell-x').fill('720');assert.match(await page.locator('#cw-cell-value').textContent(),/0 to 719/);
    await page.locator('#cw-cell-x').fill('350');
    await set(page,43205);await settle(page);assert.equal(await page.locator('#cw-radar-image').isVisible(),false);
    await page.locator('#cw-radar-jump').click();await settle(page);assert.equal(await page.locator('#cw-utc').textContent(),'10:10:06 UTC');
    await page.locator('#cw-gap-jump').click();await settle(page);assert.equal(await page.locator('#cw-height').textContent(),'Missing');assert.match(await page.locator('#cw-buoy-gap').textContent(),/5 of 24.*missing/);
    assert.equal(await page.locator('#cw-height-history .cw-history-selected').count(),0);assert.equal(await page.locator('#cw-wave .cw-wave-line').count(),0);
    await page.locator('#cw-buoy-details summary').click();assert.equal(await page.locator('#cw-buoy-rows tr').count(),24);
    await page.locator('#cw-buoy').selectOption('134221');await page.locator('#cw-radar-jump').click();await settle(page);
    await page.locator('[data-cw-source=radar]').click();await page.locator('#cw-receipt-details summary').click();
    const receipt=JSON.parse(await page.locator('#cw-json').textContent());assert.equal(receipt.firstPublicationUtc,null);assert.equal(receipt.clouds.record.perPixelAcquisitionUtc,null);assert.equal(receipt.radar.record.georeferencing.verified,false);
    for(const id of ['cw-original','cw-http'])assert.equal((await page.request.get(await page.locator('#'+id).getAttribute('href'))).status(),200);
    const download=page.waitForEvent('download');await page.locator('#cw-export').click();assert.match((await download).suggestedFilename(),/coastal-watch-weather/);
    await page.locator('[data-cw-source=buoys]').click();for(const id of ['cw-original','cw-http'])assert.equal((await page.request.get(await page.locator('#'+id).getAttribute('href'))).status(),200);
    await page.locator('#cw-second').focus();await page.keyboard.press('End');await settle(page);assert.equal(await page.locator('#cw-utc').textContent(),'21:59:59 UTC');assert.equal(await page.locator('#cw-radar-image').isVisible(),false);
    await page.locator('#cw-second').focus();await page.keyboard.press('Home');await settle(page);assert.equal(await page.locator('#cw-utc').textContent(),'22:00:00 UTC');
    await page.locator('#cw-play').click();await page.waitForFunction(()=>Number(document.getElementById('cw-second').value)>0);assert.equal(await page.locator('#cw-cell-value').getAttribute('aria-live'),'off');await page.locator('#cw-play').click();
    assert.equal(await page.locator('#cw-play').getAttribute('aria-pressed'),'false');
    await page.locator('#ca-minute').evaluate(e=>{e.value='723';e.dispatchEvent(new Event('input',{bubbles:true}));});await settle(page);assert.equal(await page.locator('#cw-utc').textContent(),'10:03:00 UTC');
    await page.addScriptTag({content:axe.source});
    const a11y=await page.evaluate(async()=>axe.run(document.getElementById('cw-passage'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}));
    const violations=a11y.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal document overflow');
    reports.push({width,theme,errors,violations});await writeFile(out+'/audit.json',JSON.stringify(reports,null,2));assert.deepEqual(errors,[]);assert.deepEqual(violations,[]);
    await page.close();
  }
  // Actual request failures must clear the image; a retained previous frame is never silently displayed.
  for(const failed of ['cloud','radar','cells','notebook']){
    const page=await browser.newPage({viewport:{width:390,height:900},reducedMotion:'reduce'});
    const pattern=failed==='cloud'?'**/raw/eumetsat-20261111-1000.png':failed==='radar'?'**/comp.20261111100006.CAP.1256.png':failed==='cells'?'**/comp.20261111100006.CAP.1256.f32.gz':'**/coastal-weather/2026-11-11/notebook.json';
    await page.route(pattern,route=>route.abort());await page.goto(origin+'/specimens/coastal-watch/source-notebook/#cw-passage');
    if(failed==='notebook'){
      await page.locator('#cw-retry').waitFor({state:'visible'});await page.unroute(pattern);await page.locator('#cw-retry').click();await page.locator('#cw-workbench').waitFor({state:'visible'});await settle(page);assert.equal(await page.locator('#cw-second').evaluate(e=>e===document.activeElement),true);
    }else{
      await page.locator('#cw-workbench').waitFor({state:'visible'});await settle(page);
      if(failed==='cells'){
        await page.locator('#cw-cell-details summary').click();await page.locator('#cw-cell-retry').waitFor({state:'visible'});assert.match(await page.locator('#cw-cell-value').textContent(),/No physical value assigned/);await page.unroute(pattern);await page.locator('#cw-cell-retry').click();await page.waitForFunction(()=>/Column/.test(document.getElementById('cw-cell-value').textContent));
      }else{
        const retry=failed==='cloud'?'#cw-cloud-retry':'#cw-radar-retry';await page.locator(retry).waitFor({state:'visible'});
        if(failed==='cloud')assert.equal(await page.locator('#cw-cloud-map image').getAttribute('visibility'),'hidden');else assert.equal(await page.locator('#cw-radar-image').isVisible(),false);
        await page.unroute(pattern);await page.locator(retry).click();await settle(page);
        if(failed==='cloud')assert.equal(await page.locator('#cw-sky').getAttribute('data-ready'),'true');else assert.equal(await page.locator('#cw-radar-image').isVisible(),true);
      }
    }
    await page.close();
  }
  const short=await browser.newPage({viewport:{width:844,height:390},reducedMotion:'reduce'});await short.goto(origin+'/specimens/coastal-watch/source-notebook/#cw-passage');await short.locator('#cw-workbench').waitFor({state:'visible'});assert.equal(await short.locator('.cw-controls').evaluate(e=>getComputedStyle(e).position),'static');await short.close();
  console.log('Weather passage: 6 viewport/theme configurations, native cells, clock boundaries, playback, export, source links, gaps and four failure/retry paths passed.');
}finally{await browser.close();}
