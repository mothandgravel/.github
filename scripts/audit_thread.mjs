/** Follow the editorial route with native navigation; never submit an enquiry. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { join } from 'node:path';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
const route = '/threads/something-happened/';
await mkdir(output, { recursive:true });
const browser = await launchAuditBrowser({headless:true});
const results = [], failures = [];
let checks = 0;
function assert(value, label) { checks++; if (!value) failures.push(label); }
async function review(page, label, screenshot=false, accessibility=true) {
  await page.waitForLoadState('load');
  const geometry = await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));
  assert(geometry.content<=geometry.width+1,label+': overflow');
  let violations=[];
  if (accessibility) {
    await page.addScriptTag({content:axe.source});
    violations = await page.evaluate(async()=>(await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})));
    assert(!violations.length,label+': '+JSON.stringify(violations));
  }
  results.push({label,geometry,violations,accessibility});
  if (screenshot) {
    const scroll=await page.evaluate(()=>({x:scrollX,y:scrollY}));
    // Axe may focus a skip link. Capture the document at its actual top.
    await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo({top:0,behavior:'instant'});});
    await page.screenshot({path:join(output,label+'.png'),fullPage:true,animations:'disabled'});
    await page.evaluate(({x,y})=>window.scrollTo({left:x,top:y,behavior:'instant'}),scroll);
  }
}
async function atFragment(page, id, label) {
  await page.waitForURL(url=>url.hash==='#'+id);
  await page.waitForLoadState('domcontentloaded');
  const target=page.locator('#'+id);
  await target.waitFor({state:'visible'});
  await page.waitForFunction(id=>{const r=document.getElementById(id)?.getBoundingClientRect();return r&&r.top<innerHeight&&r.bottom>0;},id);
  assert(await target.isVisible(),label+': fragment visible');
  assert(await target.evaluate(el=>{const r=el.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0;}),label+': fragment in view');
}
try {
  for (const width of [1440,1024,768,390,320]) for (const theme of ['night','afterlight']) {
    const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
    const page=await context.newPage(), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(origin+route);
    if(theme==='afterlight') await page.locator('#light-switch').click();
    await review(page,`thread-${theme}-${width}`,width===1440||width===390||width===320);
    const nav=page.locator('.thread-map a');
    assert(await nav.count()===3,'Three distinct stops');
    for(const [i,id] of ['reading','reply','promise'].entries()) {
      await nav.nth(i).focus();await page.keyboard.press('Enter');
      await atFragment(page,id,`keyboard-${theme}-${width}-${id}`);
      assert(await page.evaluate(()=>document.activeElement.id)===id,'Keyboard focus follows the selected stop');
    }
    const motion=await page.locator('.thread-wire').first().evaluate(el=>getComputedStyle(el).animationName);
    assert(motion==='none','Reduced motion keeps thread still');
    if([1440,320].includes(width)) {
      await page.locator('a[href="../../specimens/connected-to-what/"]').click();
      await page.locator('#inspection-controls').waitFor({state:'visible'});
      await page.locator('#inspection-age').fill('18');
      assert((await page.locator('#measurement-state').innerText()).toLowerCase().includes('stale'),'Clock retains stale distinction');
      await page.getByRole('link',{name:'Next: no answer. Do we try again?'}).click();
      await atFragment(page,'reply','Return from LiveConnect');
      await page.getByRole('link',{name:'Open Ajo’s working record'}).click();
      await atFragment(page,'specimen-ajo','Ajo native record');
      await page.locator('#specimen-ajo summary').focus();await page.keyboard.press('Enter');
      assert(await page.locator('#specimen-ajo details').getAttribute('open')!==null,'Ajo record opens with keyboard');
      await page.getByRole('link',{name:'Continue the thread: a light’s promise'}).click();
      await atFragment(page,'promise','Return from Ajo');
      await page.getByRole('link',{name:'Read “A green light should mean something.”'}).click();
      await page.getByRole('link',{name:'Where does your surface say too much?'}).click();
      await atFragment(page,'your-question','Return from note');
      await page.getByRole('link',{name:'Bring your version'}).click();
      await atFragment(page,'signals-context','Question-sheet prompt');
      assert(await page.locator('#making').inputValue()==='','Prompt does not fill visitor’s words');
      assert(await page.evaluate(()=>sessionStorage.getItem('mg-loose-end-v1'))===null,'Prompt creates no draft');
      await review(page,`thread-prompt-${theme}-${width}`,true);
      await page.getByRole('link',{name:'Write your version below'}).focus();
      await page.keyboard.press('Enter');await page.keyboard.press('Tab');
      assert(await page.evaluate(()=>document.activeElement.name)==='intent','Keyboard handoff reaches the visitor’s answers');
      await page.locator('#question-next').click();
      await page.locator('#making').fill('People cannot tell whether their export finished.');
      for(let i=0;i<4;i++) await page.locator('#question-next').click();
      const brief=await page.locator('#brief-text').inputValue();
      assert(brief.includes('export finished')&&!brief.includes('LiveConnect')&&!brief.includes('What did the surface say?'),'Brief contains only visitor’s words');
      const downloading=page.waitForEvent('download');await page.locator('#download-brief').click();
      assert((await readFile(await (await downloading).path(),'utf8'))===brief,'Download preserves literal brief');
      await page.locator('#carry-question').click();
      await page.locator('#your-question').waitFor({state:'visible'});
      assert(await page.locator('#carried-brief').textContent()===brief,'Workbench carries the exact visitor brief after the thread');
      assert(await page.locator('#original-question').textContent()==='People cannot tell whether their export finished.','Thread material stays separate from the carried question');
      await page.getByRole('link',{name:'Back to your question'}).click();
      assert(!await page.locator('#signals-context').isVisible(),'Ordinary return does not show an unrequested thread prompt');
      assert(await page.locator('#making').inputValue()==='People cannot tell whether their export finished.','Return keeps the visitor’s question');
    }
    assert(!errors.length,JSON.stringify({width,theme,errors}));
    await context.close();
  }

  // Existing local material survives the editorial detour byte for byte.
  const context=await browser.newContext({reducedMotion:'reduce',viewport:{width:390,height:844}});
  const page=await context.newPage(), requests=[];
  page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
  await page.goto(origin+'/questions/');
  assert(!await page.locator('#signals-context').isVisible(),'Direct question-sheet entry retains its usual introduction');
  const saved=JSON.stringify({version:1,answers:{making:'My own question.',difficulty:'An ambiguous answer.',materials:'private-marker-thread-201'},brief:'My edited brief. Keep every word.'});
  await page.evaluate(value=>{sessionStorage.setItem('mg-loose-end-v1',value);sessionStorage.setItem('mg-mending-workbench-v1','{"version":1,"note":"Keep this observation"}');},saved);
  await page.goto(origin+route);
  await page.getByRole('link',{name:'Bring your version'}).click();
  assert(await page.locator('#making').inputValue()==='My own question.','Existing question retained');
  assert(await page.locator('#brief-text').inputValue()==='My edited brief. Keep every word.','Edited brief retained');
  assert(await page.locator('#materials').inputValue()==='private-marker-thread-201','Existing material retained');
  assert(await page.evaluate(()=>sessionStorage.getItem('mg-loose-end-v1'))===saved,'No draft mutation on arrival');
  assert((await page.evaluate(()=>sessionStorage.getItem('mg-mending-workbench-v1'))).includes('Keep this observation'),'Workbench observation retained');
  await page.getByRole('link',{name:'Write your version below'}).click();
  await page.goBack();
  assert(await page.locator('#signals-context').isVisible(),'Native back restores optional context');
  await page.getByRole('link',{name:'Back to the thread',exact:false}).click();
  await atFragment(page,'your-question','Exit prompt back to thread');
  assert(!requests.some(r=>r.method!=='GET'||r.url.includes('private-marker-thread-201')),'Visitor material is never transmitted');
  await context.close();

  // No storage is required to move from reading to a blank question sheet.
  const denied=await browser.newContext({reducedMotion:'reduce'});
  await denied.addInitScript(()=>{for(const key of ['sessionStorage','localStorage']) Object.defineProperty(window,key,{get(){throw new Error('Storage blocked');}});});
  const deniedPage=await denied.newPage();
  await deniedPage.goto(origin+route);await deniedPage.getByRole('link',{name:'Bring your version'}).click();
  await deniedPage.locator('#question-next').click();await deniedPage.locator('#making').fill('My signal is ambiguous.');
  assert(await deniedPage.locator('#making').inputValue()==='My signal is ambiguous.','Works when storage is denied');
  await denied.close();

  // Optional motion finishes while reading and link hit areas stay still.
  const motionContext=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'no-preference'});
  const moving=await motionContext.newPage();
  await moving.goto(origin+route);
  const label=moving.locator('.thread-map a').first();
  await label.scrollIntoViewIfNeeded();
  const before=await label.boundingBox();
  await label.hover();
  await moving.waitForFunction(()=>document.querySelector('.thread-wire').getAnimations().some(a=>a.playState==='running'));
  await moving.waitForFunction(()=>document.querySelector('.thread-wire').getAnimations().every(a=>a.playState==='finished'));
  assert(JSON.stringify(before)===JSON.stringify(await label.boundingBox()),'Optional glint never moves the question or its hit area');
  await moving.locator('#menu-toggle').click();
  assert(await moving.locator('.nav-sheet-invitation').getAttribute('href')===origin+'/questions/','Nested thread masthead resolves the correct question route');
  await moving.keyboard.press('Escape');
  assert(await moving.locator('#menu-toggle').evaluate(el=>el===document.activeElement),'Closing the menu restores keyboard focus');
  await moving.goto(origin+'/notes/');
  await moving.locator('#collection-thread-title a').click();
  await moving.waitForURL(origin+route);
  assert(await moving.locator('.thread-map').isVisible(),'The archive offers a working entry outside its filtered note list');
  await motionContext.close();
  const touchContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,reducedMotion:'no-preference'});
  const touching=await touchContext.newPage();await touching.goto(origin+route);
  await touching.locator('.thread-map a').first().tap();
  assert(await touching.locator('.thread-wire').first().evaluate(el=>getComputedStyle(el).animationName)==='none','Touch receives a still thread');
  await touchContext.close();

  // Native routes remain complete when scripts are absent or fail to load.
  for(const mode of ['no-javascript','blocked-scripts']) {
    const fallback=await browser.newContext({javaScriptEnabled:mode!=='no-javascript',reducedMotion:'reduce',viewport:{width:320,height:740}});
    if(mode==='blocked-scripts') await fallback.route(/\.(mjs|js)(\?|$)/,r=>r.abort());
    const p=await fallback.newPage();
    await p.goto(origin+'/');await p.getByRole('link',{name:'Something happened. I can’t tell what.'}).click();
    await review(p,'thread-'+mode,true,mode!=='no-javascript');
    await p.locator('.thread-map a').nth(1).click();await atFragment(p,'reply',mode+' Ajo');
    await p.getByRole('link',{name:'Bring your version'}).click();
    assert(await p.locator('#signals-context').isVisible(),mode+': contextual prompt visible');
    assert(await p.locator('#making').isVisible(),mode+': native question sheet visible');
    await review(p,'thread-prompt-'+mode,true,mode!=='no-javascript');
    await p.getByRole('link',{name:'Back to the thread',exact:false}).click();
    await atFragment(p,'your-question',mode+' return');
    await fallback.close();
  }
} finally {
  await browser.close();
  await writeFile(join(output,'thread-review.json'),JSON.stringify({checks,results,failures},null,2));
}
console.log(JSON.stringify({checks,states:results.length,failures},null,2));
if(failures.length) process.exitCode=1;
