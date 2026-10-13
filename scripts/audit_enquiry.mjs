/** Private-handoff UI with a simulated endpoint. Never contacts Resend. */
import { chromium } from 'playwright';
import axe from 'axe-core';
import { mkdir,writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const origin=process.env.SITE_URL||'http://127.0.0.1:8793';
const endpoint='https://handoff.example.test';
const output=process.env.AUDIT_OUTPUT||'artifacts/design-review';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true});const results=[];
try {
 for(const theme of ['night','afterlight'])for(const width of [320,390,768,1024,1440]) {
  const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();let posts=0,saved=null;
  await page.addInitScript(theme=>localStorage.setItem('moth-and-gravel-theme',theme),theme);
  await page.route('**/assets/enquiry-config.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({enabled:true,endpoint})}));
  await page.route(endpoint+'/**',async route=>{
   const request=route.request(),path=new URL(request.url()).pathname;
   const headers={'access-control-allow-origin':origin,'access-control-allow-headers':'Authorization,Content-Type','access-control-allow-methods':'GET,POST,OPTIONS'};
   if(request.method()==='OPTIONS')return route.fulfill({status:204,headers});
   if(path==='/config')return route.fulfill({headers,contentType:'application/json',body:JSON.stringify({accepting:true,contract:1})});
   if(request.method()==='POST'){posts++;saved=request.postDataJSON();return route.abort('failed');}
   return route.fulfill({headers,status:saved?200:404,contentType:'application/json',body:JSON.stringify(saved?{id:saved.id,receivedAt:'2026-10-13T00:00:00Z',receipt:'saved',notification:'accepted'}:{error:'not_found'})});
  });
  await page.goto(origin+'/questions/');
  await page.waitForFunction(()=>!document.getElementById('private-enquiry').hidden);
  assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
  for(let i=0;i<5;i++){if(i===1)await page.locator('#making').fill('A difficult handoff');await page.locator('#question-next').click();}
  await page.locator('#brief-text').fill('The words we reviewed. <keep as text>');
  await page.locator('#enquiry-name').fill('A visitor');await page.locator('#enquiry-email').fill('visitor@example.test');
  await page.getByRole('button',{name:'Review what will travel'}).click();assert.equal(posts,0);
  await page.locator('#brief-text').fill('An edit made after review');
  await page.locator('#send-enquiry').click();await page.waitForFunction(()=>document.getElementById('enquiry-status').textContent.includes('cannot confirm'));
  assert.equal(posts,1);assert.equal(saved.brief,'The words we reviewed. <keep as text>');
  const frozenId=saved.id;await page.reload();await page.waitForFunction(()=>!document.getElementById('private-enquiry').hidden);
  for(let i=0;i<5;i++){if(i===1)await page.locator('#making').fill('A difficult handoff');await page.locator('#question-next').click();}
  await page.locator('#retry-enquiry').click();await page.waitForFunction(()=>document.getElementById('enquiry-status').textContent.includes('saved privately'));
  assert.equal(posts,1);assert.equal(saved.id,frozenId);assert.ok(await page.locator('#retry-enquiry').isHidden());
  assert.match(await page.locator('#enquiry-status').innerText(),/Delivery is not yet confirmed/);
  await page.addScriptTag({content:axe.source});const violations=await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations);
  assert.deepEqual(violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})),[]);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.evaluate(()=>{document.activeElement?.blur();document.documentElement.style.scrollBehavior="auto";window.scrollTo({top:0,behavior:"instant"});});
  await page.waitForFunction(()=>scrollY===0);
  await page.screenshot({path:output+'/enquiry-'+theme+'-'+width+'.png',fullPage:true});results.push({theme,width,posts,receipt:'saved',email:'accepted',axeViolations:0});
  await context.close();
 }
 const context=await browser.newContext();const page=await context.newPage();let external=0;
 page.on('request',r=>{if(r.url().startsWith(endpoint))external++;});await page.goto(origin+'/questions/');await page.waitForTimeout(250);
 assert.ok(await page.locator('#private-enquiry').isHidden());assert.equal(external,0);await context.close();
 await writeFile(output+'/enquiry-audit.json',JSON.stringify({fixture:'simulated endpoint; no email sent',results,disabledDefault:true},null,2));console.log('Private enquiry: 10 theme/viewport reviews, zero accessibility violations; lost response recovered without another POST. Default disabled.');
}finally{await browser.close();}
