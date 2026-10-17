import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
const url=process.env.SITE_URL||'http://127.0.0.1:8793',output=process.env.AUDIT_OUTPUT||'artifacts/design-review';
await mkdir(output,{recursive:true});const b=await launchAuditBrowser();const results=[];
try{
for(const theme of ['night','afterlight'])for(const width of [320,390,768,1024,1440]){
 const c=await b.newContext({viewport:{width,height:900},acceptDownloads:true});const p=await c.newPage();let transmitted=false;
 await p.addInitScript(theme=>{localStorage.setItem('moth-and-gravel-theme',theme);sessionStorage.setItem('mg-mending-workbench-v1',JSON.stringify({version:1,note:'Earlier local concern',noteSurface:'item',choice:'open'}));},theme);
 p.on('request',r=>{if(r.postData()||r.url().includes('Earlier%20local'))transmitted=true;});
 await p.goto(url+'/workbench/return/');await p.locator('#open-return-note').waitFor({state:'visible'});
 assert.equal(await p.locator('html').getAttribute('data-theme'),theme);await p.locator('#earlier-local summary').click();assert.match(await p.locator('#earlier-local-note').innerText(),/Object first · revision 1/);
 await p.locator('input[value="damage-1"]').check();await p.locator('#open-return-note').click();await p.locator('#return-note').fill('<img src=x onerror=alert(1)> A note on the old sketch.');await p.locator('input[value="damage-2"]').check();await p.locator('#return-note-editor button[type="submit"]').click();
 assert.match(await p.locator('#return-note-records').innerText(),/Damage first · revision 1/);assert.equal(await p.locator('#return-note-records img').count(),0);
 await p.locator('#open-return-note').click();await p.locator('#return-note').fill('Cancelled');await p.locator('#cancel-return-note').click();assert.equal(await p.locator('#return-note-records .return-record').count(),1);
 await p.locator('#interpretation').fill('The category itself is the problem.');await p.locator('#interpretation-form button').click();
 await p.locator('input[value="continue"]').check();await p.locator('#choice-reason').fill('A route to test, not approval.');await p.locator('#return-choice-form button').click();
 await p.locator('input[value="reopen"]').check();await p.locator('#choice-reason').fill('We need a different question.');await p.locator('#return-choice-form button').click();await p.locator('#direction-history summary').click();assert.match(await p.locator('#return-choice-history').innerText(),/Keep damage first/);assert.match(await p.locator('#return-next').innerText(),/return to what the first screen should ask/);
 await p.reload();await p.locator('#open-return-note').waitFor({state:'visible'});assert.match(await p.locator('#return-choice-record').innerText(),/Reopen/);assert.match(await p.locator('#return-note-records').innerText(),/revision 1/);assert.match(await p.locator('#interpretation-records').innerText(),/category itself/);
 await p.locator('#return-note-records button').click();assert.ok(await p.locator('input[value="damage-1"]').isChecked());assert.match(await p.locator('#revision-caption').innerText(),/revision 1/);
 const download=p.waitForEvent('download');await p.locator('#export-return').click();const d=await download;assert.equal(d.suggestedFilename(),'moth-and-gravel-return-visit.txt');const exported=await readFile(await d.path(),'utf8');assert.match(exported,/FICTIONAL STUDY: mending notebook/);assert.doesNotMatch(exported,/check-in|meeting guest|courier|working kiosk/i);
 await p.addScriptTag({content:axe.source});const violations=await p.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})));assert.deepEqual(violations,[]);assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await p.evaluate(()=>{document.activeElement?.blur();document.documentElement.style.scrollBehavior='auto';scrollTo({top:0,behavior:'instant'});});await p.screenshot({path:output+'/specimen-'+theme+'-'+width+'.png',fullPage:true});
 await p.locator('#reset-return').click();assert.match(await p.locator('#return-note-records').innerText(),/No return-visit notes/);assert.equal(await p.evaluate(()=>sessionStorage.getItem('mg-mending-return-v1')),null);assert.ok(await p.evaluate(()=>sessionStorage.getItem('mg-mending-workbench-v1')));assert.equal(transmitted,false);results.push({theme,width,axeViolations:0,overflow:false,revisionAnchor:true,reopenHistory:true,reload:true,localOnly:true});await c.close();
}
const separated=await b.newContext();const sp=await separated.newPage();
await sp.addInitScript(()=>{
 sessionStorage.setItem('mg-workbench-v1',JSON.stringify({version:1,note:'Retired example marker',noteSurface:'retired',choice:'open'}));
 sessionStorage.setItem('mg-specimen-return-v1',JSON.stringify({version:1,notes:[],corrections:['Retired interpretation marker'],choices:[]}));
 sessionStorage.setItem('mg-loose-end-v1',JSON.stringify({version:1,answers:{making:'A carried question'},brief:'My existing edited brief'}));
});
await sp.goto(url+'/workbench/');await sp.locator('#mark-wrong').waitFor({state:'visible'});assert.match(await sp.locator('#carried-brief').textContent(),/My existing edited brief/);assert.equal(await sp.locator('#annotation-record').innerText(),'No observation pinned yet.');assert.doesNotMatch(await sp.locator('main').innerText(),/Retired example marker/);
await sp.locator('#mark-wrong').click();await sp.locator('#annotation').fill('New mending observation');await sp.locator('#pin-observation').click();
await sp.goto(url+'/workbench/return/');await sp.locator('#open-return-note').waitFor({state:'visible'});await sp.locator('#earlier-local summary').click();assert.match(await sp.locator('#earlier-local-note').innerText(),/Object first.*New mending observation/);assert.match(await sp.locator('#return-brief-text').innerText(),/My existing edited brief/);assert.doesNotMatch(await sp.locator('main').innerText(),/Retired interpretation marker|Retired example marker/);assert.ok(await sp.evaluate(()=>sessionStorage.getItem('mg-workbench-v1')));assert.ok(await sp.evaluate(()=>sessionStorage.getItem('mg-specimen-return-v1')));await separated.close();
const blocked=await b.newContext();const page=await blocked.newPage();await page.addInitScript(()=>{Storage.prototype.getItem=function(){throw Error('blocked')};Storage.prototype.setItem=function(){throw Error('blocked')};});await page.goto(url+'/workbench/return/');await page.locator('#open-return-note').click();await page.locator('#return-note').fill('Memory only');await page.locator('#return-note-editor button[type="submit"]').click();assert.match(await page.locator('#return-status').innerText(),/Storage is unavailable/);await blocked.close();
const nojs=await b.newContext({javaScriptEnabled:false});const np=await nojs.newPage();await np.goto(url+'/workbench/return/');assert.match(await np.locator('main').innerText(),/Revision 1 asked/);assert.ok(await np.locator('#return-choice-form').isHidden());await nojs.close();
await writeFile(output+'/specimen-audit.json',JSON.stringify({results,blockedStorage:true,noJavaScript:true,retiredStudyIsolation:true},null,2));console.log('Specimen return: 10 responsive/theme reviews, zero axe violations; anchors, cancellation, correction, reopening/history, reload, export and isolated clear pass.');
}finally{await b.close();}
