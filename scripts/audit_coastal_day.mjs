import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import axe from 'axe-core';
import {launchAuditBrowser} from './audit_browser.mjs';
const origin=process.env.SITE_URL??'http://127.0.0.1:8797', route='/specimens/coastal-watch/source-notebook/21-november/', out='artifacts/design-review/coastal-day';
await mkdir(out,{recursive:true});
const browser=await launchAuditBrowser();
const results=[];
let rawLinksVerified=0,fallbackLinksVerified=0;
try {
  for(const [width,theme] of [[1440,'night'],[1440,'afterlight'],[390,'night'],[390,'afterlight'],[320,'night'],[320,'afterlight']]) {
    const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'}), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
    await page.goto(origin+route);await page.locator('#cd-workbench').waitFor({state:'visible'});
    assert.equal(await page.locator('audio,video').count(),0);
    assert.equal(await page.locator('#cd-report-rows tr').count(),76);
    assert.equal(await page.locator('#cd-ledger article').count(),15);
    assert.match(await page.locator('[data-channel="108495:WaveHs"] .cd-number').textContent(),/^0.8 m$/);
    const center=await page.locator('#cd-ais-mark circle').last().getAttribute('cx');
    await page.locator('[data-second="32400"]').click();
    assert.equal(await page.locator('#cd-ais-mark').getAttribute('visibility'),'hidden');
    await page.locator('#cd-gap').click();
    assert.equal(await page.locator('[data-channel="108495:WaveHs"] .cd-number').textContent(),'Source NaN');
    assert.equal(await page.locator('[data-channel="134221:WaveHs"] .cd-number').textContent(),'1.0 m');
    assert.match(await page.locator('#cd-receipt').textContent(),/NaN/);
    assert.equal(await page.locator('#cd-ais-mark').getAttribute('visibility'),'visible');
    assert.equal(await page.locator('#cd-ais-mark circle').last().getAttribute('cx'),center);
    await page.locator('[data-channel="134254:WLEVN2K_PT1S_INSTANT"]').click();
    assert.match(await page.locator('#cd-receipt').textContent(),/575.0/);
    await page.locator('[data-second="72000"]').click();
    assert.equal(await page.locator('.cd-number').allTextContents().then(x=>x.every(v=>v==='Not collected')),true);
    assert.equal(await page.locator('#cd-ais-mark').getAttribute('visibility'),'hidden');
    await page.locator('#cd-time').focus();await page.locator('#cd-time').press('End');
    assert.equal(await page.locator('#cd-time-label').textContent(),'23:59:59 EET');
    assert.match(await page.locator('#cd-time').getAttribute('aria-valuetext'),/outside saved query/);
    await page.locator('[data-second="32400"]').click();await page.locator('#cd-time').press('ArrowRight');
    assert.equal(await page.locator('#cd-time-label').textContent(),'09:10:00 EET');
    await page.locator('[data-second="32503"]').click();
    await page.locator('[data-channel="108495:WaveHs"]').click();
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    assert.equal(overflow,false,`${width}/${theme} horizontal overflow`);
    await page.addScriptTag({content:axe.source});
    const scan=await page.evaluate(()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
    assert.deepEqual(scan.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
    assert.deepEqual(errors,[]);
    if(width>=390) {
      await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});
      await page.screenshot({path:`${out}/${width}-${theme}-hero.png`});
      await page.screenshot({path:`${out}/${width}-${theme}-page.png`,fullPage:true});
      await page.locator('.cd-map-wrap').screenshot({path:`${out}/${width}-${theme}-map.png`});
    }
    results.push({width,theme,accessibilityViolations:0,horizontalOverflow:false,errors});
    await page.close();
  }
  const page=await browser.newPage();
  await page.route('**/coastal-days/2026-11-21/notebook.json',r=>r.abort());
  await page.goto(origin+route);await page.locator('#cd-retry').waitFor({state:'visible'});
  assert.match(await page.locator('#cd-loading').textContent(),/could not be downloaded/);
  assert.equal(await page.locator('#cd-fallback').getAttribute('open'),'');
  for(const a of await page.locator('#cd-fallback .cd-static-links a').all()) {
    const response=await page.request.get(new URL(await a.getAttribute('href'),page.url()).href);assert.equal(response.ok(),true);
    fallbackLinksVerified++;
  }
  await page.unroute('**/coastal-days/2026-11-21/notebook.json');await page.locator('#cd-retry').click();
  await page.locator('#cd-workbench').waitFor({state:'visible'});
  for(const a of await page.locator('#cd-ledger article>a').all()) {
    const response=await page.request.get(await a.getAttribute('href'));assert.equal(response.ok(),true);
    rawLinksVerified++;
  }
  await page.close();
  const noCoast=await browser.newPage();
  await noCoast.route('**/coastal-replay-land.json',r=>r.abort());
  await noCoast.goto(origin+route);await noCoast.locator('#cd-workbench').waitFor({state:'visible'});
  assert.equal(await noCoast.locator('#cd-map-warning').isVisible(),true);
  assert.equal(await noCoast.locator('.cd-instrument').count(),4);await noCoast.close();
  const noJs=await browser.newPage({javaScriptEnabled:false});await noJs.goto(origin+route);
  assert.equal(await noJs.locator('#cd-loading').isVisible(),false);
  await noJs.locator('#cd-fallback summary').click();assert.equal(await noJs.locator('#cd-fallback .cd-static-links a').first().isVisible(),true);await noJs.close();
  await writeFile(`${out}/audit.json`,JSON.stringify({origin,results,failedFetchRecovery:true,rawLinksVerified,fallbackLinksVerified,noCoastWorks:true,noJavaScriptWorks:true},null,2)+'\n');
  console.log(`Coastal day: ${results.length} responsive/theme passes; source-time gates, gaps, no drift, raw links and failed-fetch recovery passed.`);
} finally {await browser.close();}
