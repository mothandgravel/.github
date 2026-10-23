import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import axe from 'axe-core';
import {launchAuditBrowser} from './audit_browser.mjs';
const origin=process.env.SITE_URL??'http://127.0.0.1:8794',out='artifacts/design-review/datacenter-finland';
await mkdir(out,{recursive:true});const browser=await launchAuditBrowser(),results=[];
try{
 for(const [width,theme]of [[1440,'night'],[1440,'afterlight'],[390,'night'],[390,'afterlight']]){
  const page=await browser.newPage({viewport:{width,height:1050},reducedMotion:'reduce'}),errors=[],requests=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{requests.push(r.url());if(!['GET','HEAD'].includes(r.method()))writes.push(r.url());});
  await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
  await page.goto(`${origin}/specimens/data-center/`);
  assert.ok(!requests.some(x=>/finland.json|esif-week.json|datacenter-engine.mjs/.test(x)),'Recorded accounts stay on demand');
  await page.locator('#fi-open').click();await page.locator('#fi-workspace').waitFor({state:'visible'});assert.match(await page.locator('#fi-status').innerText(),/Verified Finnish extract/);
  assert.equal(await page.locator('#fi-homes-panel').isVisible(),true);
  assert.equal(await page.locator('#fi-homes-error').isHidden(),true);assert.equal(await page.locator('.fi-home-calculation').first().isVisible(),true);assert.equal(await page.locator('#fi-export').isEnabled(),true);
  assert.equal(await page.locator('#fi-apartment-change').innerText(),'+€30.00');assert.equal(await page.locator('#fi-electric-change').innerText(),'+€200.00');
  assert.equal(await page.locator('#fi-apartment-heat-value').innerText(),'Not quantified');assert.match(await page.locator('#fi-apartment-combined').innerText(),/remains open/);
  assert.match(await page.locator('#fi-apartment-total').innerText(),/711.21.*741.21/s);
  await page.locator('#fi-price-change').fill('2');assert.equal(await page.locator('#fi-apartment-change').innerText(),'+€60.00');assert.equal(await page.locator('#fi-electric-change').innerText(),'+€400.00');
  await page.locator('#fi-apartment-exposure').fill('50');assert.equal(await page.locator('#fi-apartment-change').innerText(),'+€30.00');
  await page.locator('#fi-electric-exposure').fill('0');assert.equal(await page.locator('#fi-electric-change').innerText(),'€0.00');
  await page.locator('#fi-homes-reset').click();
  assert.equal(await page.locator('#fi-homes-error').isHidden(),true);
  await page.locator('#fi-homes-panel').screenshot({path:`${out}/${width}-${theme}-homes.png`,style:'.site-header{visibility:hidden!important}'});
  await page.locator('#fi-heat-assumption').selectOption('assumed');assert.equal(await page.locator('#fi-apartment-heat-value').innerText(),'€75.00');
  await page.locator('#fi-heat-passthrough').fill('50');assert.equal(await page.locator('#fi-apartment-heat-value').innerText(),'€37.50');assert.equal(await page.locator('#fi-apartment-combined').innerText(),'−€7.50');assert.equal(await page.locator('#fi-apartment-change').innerText(),'+€30.00');
  const branchDownload=page.waitForEvent('download');await page.locator('#fi-export').click();const branchFile=`${out}/${width}-${theme}-heat-branch.json`;await(await branchDownload).saveAs(branchFile);const branch=JSON.parse(await readFile(branchFile,'utf8'));assert.equal(branch.householdComparison.apartment.heat.householdReductionEUR,37.5);assert.equal(branch.householdComparison.apartment.combinedChangeEUR,-7.5);assert.equal(branch.householdComparison.apartment.electricity.deltaEUR.total,30);assert.equal(branch.householdComparison.apartment.heat.attributedToRecoveredHeatEUR,null);
  await page.addScriptTag({content:axe.source});const assumedAxe=await page.evaluate(()=>axe.run(document.querySelector('#fi-account'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));assert.deepEqual(assumedAxe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.locator('#fi-electric-inspect').click();assert.match(await page.locator('#fi-receipt').innerText(),/no-direct-route/);assert.equal(await page.locator('.fi-receipts').getAttribute('open'),'');await page.locator('.fi-receipts summary').click();
  await page.locator('#fi-home-connection').selectOption('unknown');assert.equal(await page.locator('#fi-apartment-heat-value').innerText(),'Not quantified');
  await page.locator('#fi-home-connection').selectOption('not-connected');assert.equal(await page.locator('#fi-apartment-heat-value').innerText(),'€0.00');assert.equal(await page.locator('#fi-apartment-combined').innerText(),'+€30.00');
  await page.locator('#fi-home-connection').selectOption('connected');
  await page.locator('#fi-home-heat-diagram').screenshot({path:`${out}/${width}-${theme}-heat-route.png`});
  await page.locator('#fi-apartment-use').fill('');assert.equal(await page.locator('#fi-homes-error').isVisible(),true);assert.equal(await page.locator('#fi-export').isDisabled(),true);assert.equal(await page.locator('.fi-home-calculation').first().isHidden(),true);
  await page.locator('#fi-apartment-use').fill('3000');assert.equal(await page.locator('#fi-export').isEnabled(),true);
  await page.locator('#fi-price-change').fill('-1');assert.equal(await page.locator('#fi-electric-change').innerText(),'−€200.00');
  await page.locator('#fi-homes-reset').click();
  await page.addScriptTag({content:axe.source});const homeAxe=await page.evaluate(()=>axe.run(document.querySelector('#fi-account'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));assert.deepEqual(homeAxe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.locator('[data-fi-panel="bill"]').click();
  assert.equal(await page.locator('#fi-month option').count(),30);assert.equal(await page.locator('#fi-household option').count(),5);
  const initialBill=await page.locator('#fi-bill-total').innerText();assert.match(initialBill,/€/);
  await page.locator('#fi-household').selectOption('3000');assert.match(await page.locator('#fi-band').innerText(),/band C/);assert.notEqual(await page.locator('#fi-bill-total').innerText(),initialBill);
  await page.locator('#fi-month').selectOption('2024M01');assert.match(await page.locator('#fi-month-value').innerText(),/January 2024/);
  await page.locator('#fi-bill-panel').screenshot({path:`${out}/${width}-${theme}-bill.png`,style:'.site-header{visibility:hidden!important}'});
  await page.locator('[data-fi-panel="grid"]').click();assert.equal(await page.locator('#fi-bill-panel').isHidden(),true);
  const clock=await page.locator('#fi-grid-clock').innerText();await page.locator('#fi-hour').focus();await page.keyboard.press('ArrowRight');assert.notEqual(await page.locator('#fi-grid-clock').innerText(),clock);
  await page.locator('#fi-extra').fill('100');assert.match(await page.locator('#fi-grid-branch').innerText(),/\+100 MW/);
  await page.locator('#fi-play').click();await page.waitForTimeout(600);await page.locator('#fi-play').click();const paused=await page.locator('#fi-hour').inputValue();await page.waitForTimeout(550);assert.equal(await page.locator('#fi-hour').inputValue(),paused);
  await page.locator('#fi-week').selectOption('summer');assert.match(await page.locator('#fi-grid-clock').innerText(),/2024-07-01.*EET/);
  await page.locator('#fi-grid-panel').screenshot({path:`${out}/${width}-${theme}-grid.png`,style:'.site-header{visibility:hidden!important}'});
  await page.locator('[data-fi-panel="bill"]').click();assert.equal(await page.locator('#fi-month').inputValue(),'2024M01');assert.equal(await page.locator('#fi-household').inputValue(),'3000');
  await page.locator('[data-fi-panel="heat"]').click();assert.match(await page.locator('#fi-heat-sales').innerText(),/48.5 GWh/);assert.match(await page.locator('#fi-heat-homes').innerText(),/16.0 GWh/);
  await page.locator('[data-heat="residentialUse"]').click();assert.match(await page.locator('#fi-heat-selection').innerText(),/Taul5!R138/);assert.match(await page.locator('#fi-receipt').textContent(),/"cell": "R138"/);
  await page.locator('#fi-heat-panel').screenshot({path:`${out}/${width}-${theme}-heat.png`,style:'.site-header{visibility:hidden!important}'});
  await page.locator('#fi-heat-period').selectOption('2025');assert.equal(await page.locator('#fi-heat-homes').innerText(),'Not reported');assert.match(await page.locator('#fi-heat-caption').innerText(),/cannot be multiplied/);
  const download=page.waitForEvent('download');await page.locator('#fi-export').click();const file=`${out}/${width}-${theme}-inspection.json`;await(await download).saveAs(file);const inspection=JSON.parse(await readFile(file,'utf8'));assert.equal(inspection.heat.residentialUseGWh,null);assert.equal(inspection.household.annualKWh,3000);assert.equal(inspection.grid.branch.additionalMW,100);assert.equal(inspection.signed,false);assert.equal(inspection.schema,'moth-gravel/finland-inspection@2');assert.equal(inspection.householdComparison.apartment.heat.householdReductionEUR,null);assert.equal(inspection.householdComparison.apartment.electricity.deltaEUR.total,30);assert.equal(inspection.householdComparison.electricHome.electricity.deltaEUR.total,200);assert.equal(inspection.householdComparison.recordedHeatContext.source.cell,'R138');
  await page.locator('.fi-receipts summary').click();assert.match(await page.locator('#fi-receipt').innerText(),/originScope/);
  await page.addScriptTag({content:axe.source});const a=await page.evaluate(()=>axe.run(document.querySelector('#fi-account'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));assert.deepEqual(a.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  for(const target of ['homes','bill','grid','heat']){await page.locator(`[data-fi-panel="${target}"]`).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
  if(width===390){await page.setViewportSize({width:320,height:850});for(const target of ['homes','bill','grid','heat']){await page.locator(`[data-fi-panel="${target}"]`).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}}
  assert.ok(!requests.some(x=>/esif-week.json|datacenter-engine.mjs|studio-small|pathtracer.mjs/.test(x)),'Finnish account does not load US data or 3D');
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);results.push({width,theme,axeViolations:0,errors,writes,export:'source records and assumptions',overflow:false});await page.close();
 }
 // The failed-integrity state must leave source controls closed and offer retry.
 const page=await browser.newPage();await page.route('**/data-center/finland.json',async route=>{const response=await route.fetch();await route.fulfill({response,body:(await response.text())+' '});});await page.goto(`${origin}/specimens/data-center/`);await page.locator('#fi-open').click();await page.waitForFunction(()=>document.querySelector('#fi-status').textContent.includes('fingerprint differs'));assert.equal(await page.locator('#fi-workspace').isHidden(),true);assert.equal(await page.locator('#fi-open').isEnabled(),true);await page.close();
 await writeFile(`${out}/audit.json`,JSON.stringify({results,integrityFailure:'blocked and retryable'},null,2)+'\n');console.log('Finnish account: both themes, desktop/phone, source selection, exports, keyboard, missing data and integrity rejection passed.');
}finally{await browser.close();}
