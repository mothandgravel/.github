import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import axe from 'axe-core';
import {launchAuditBrowser} from './audit_browser.mjs';
const origin=process.env.SITE_URL??'http://127.0.0.1:8793',out='artifacts/design-review';
await mkdir(out,{recursive:true});
const browser=await launchAuditBrowser();
try{
  for(const [width,theme]of [[1440,'night'],[390,'afterlight'],[320,'night']]){
    const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
    await page.goto(origin+'/specimens/coastal-watch/source-notebook/');
    await page.locator('#cs-workbench').waitFor({state:'visible'});
    assert.equal(await page.locator('#cs-observed').textContent(),'2026-11-10T22:00:00Z');
    assert.equal(await page.locator('audio,video').count(),0);
    await page.locator('#cs-try-gap').click();
    assert.equal(await page.locator('#cs-count').textContent(),'5/24');
    assert.equal(await page.locator('#cs-value').textContent(),'Missing');
    assert.equal(await page.locator('#cs-raw-value').textContent(),'NaN');
    assert.equal(await page.locator('#cs-plot .cs-gap').count(),19);
    await page.locator('#cs-hour').press('End');
    assert.equal(await page.locator('#cs-hour-label').textContent(),'23:00 EET');
    assert.equal(await page.locator('#cs-observed').textContent(),'2026-11-11T21:00:00Z');
    await page.locator('#cs-try-datum').click();
    assert.equal(await page.locator('#cs-value').textContent(),'0');
    assert.equal(await page.locator('#cs-datum').textContent(),'THEORETICAL MEAN WATER');
    await page.locator('#cs-try-datum').click();
    assert.equal(await page.locator('#cs-value').textContent(),'211');
    assert.equal(await page.locator('#cs-datum').textContent(),'N2000 DATUM');
    await page.locator('.cs-receipt summary').click();
    const receipt=JSON.parse(await page.locator('#cs-receipt-json').textContent());
    assert.equal(receipt.originalReceiverTime,null);assert.equal(receipt.firstPublication,null);
    assert.equal(receipt.unit,'mm');assert.match(receipt.requestStartedAt,/^2026-11-13/);
    assert.equal(receipt.downloadCompletedAt,null);assert.match(receipt.retrievalTimeMeaning,/request start/);
    for(const id of ['cs-raw-link','cs-http-link','cs-parameter-link']){
      const response=await page.request.get(await page.locator('#'+id).getAttribute('href'));assert.equal(response.status(),200);
    }
    await page.locator('.cs-sample-table summary').click();
    assert.equal(await page.locator('#cs-samples tr').count(),24);
    assert.equal(await page.locator('#cs-samples tr[aria-current=true]').count(),1);
    await page.getByText('Inspect acquisition and publication times',{exact:true}).click();
    await page.getByText('Inspect the archive checks',{exact:true}).click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.addScriptTag({content:axe.source});
    const result=await page.evaluate(async()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}));
    const violations=result.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}));
    await writeFile(`${out}/coastal-sources-${width}-${theme}.json`,JSON.stringify({width,theme,errors,violations},null,2));
    assert.deepEqual(errors,[]);assert.deepEqual(violations,[]);
    await page.locator('#cs-channel').selectOption({index:4});
    await page.locator('#cs-hour').press('Home');
    await page.locator('#cs-channel').scrollIntoViewIfNeeded();
    await page.screenshot({path:`${out}/coastal-sources-${width}-${theme}.png`});
    await page.close();console.log(`Coastal sources ${width}/${theme}: real gaps, clocks, datums, keyboard and WCAG checks passed`);
  }
}finally{await browser.close();}
