/** Browser audit for the actual intake -> local workbench journey. No enquiries sent. */
import { chromium } from 'playwright';
import axe from 'axe-core';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { join } from 'node:path';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const results = [], failures = [];
const assert = (value, label) => { if (!value) failures.push(label); };
const viewports = [{width:1440,height:900},{width:1024,height:768},{width:768,height:1024},{width:390,height:844},{width:320,height:740}];
async function audit(page, label, capture = false) {
  const geometry = await page.evaluate(() => ({ width: innerWidth, content: document.documentElement.scrollWidth }));
  assert(geometry.content <= geometry.width + 1, label + ': horizontal overflow');
  const noJS = label.endsWith('no-javascript');
  if (!noJS) await page.addScriptTag({ content: axe.source });
  const accessibility = noJS ? [] : await page.evaluate(async () => (await window.axe.run(document, { runOnly: { type:'tag', values:['wcag2a','wcag2aa','wcag21aa','wcag22aa'] } })).violations.map(v => ({id:v.id,targets:v.nodes.map(n=>n.target),details:v.nodes.map(n=>n.failureSummary)})));
  accessibility.forEach(v => assert(false, label + ': axe ' + JSON.stringify(v)));
  results.push({ label, geometry, accessibility, axeRan: !noJS });
  if (capture) {
    await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo({top:0,behavior:'instant'});});
    await page.waitForTimeout(100);
    await page.screenshot({ path:join(output,label+'.png'), fullPage:true, animations:'disabled' });
  }
}
async function next(page) { await page.locator('#question-next').click(); }
async function makeBrief(page, text = 'A screen that helps someone find their footing.') {
  await next(page);
  await page.locator('#making').fill(text);
  await next(page);
  await page.locator('#difficulty').fill('The first step assumes too much.');
  await page.locator('#people').fill('A first-time visitor.');
  await next(page);
  await page.locator('#outcome').fill('They know what to do next.');
  await next(page);
  await page.locator('#constraints').fill('Keep the existing system working.');
  await next(page);
}
try {
  for (const viewport of viewports) for (const theme of ['night','afterlight']) {
    const context = await browser.newContext({viewport,reducedMotion:'reduce'});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.url().includes('private-prototype-marker')) errors.push('Existing material was fetched without an action');});
    await page.goto(origin+'/questions/');
    if (theme==='afterlight') await page.locator('#light-switch').click();
    await page.locator('#question-progress').waitFor({state:'visible'});
    const contrast = await page.evaluate(() => {
      const link = document.querySelector('.journey-aside a');
      const foreground=getComputedStyle(link).color, background=getComputedStyle(document.body).backgroundColor;
      const luminance=color=>color.match(/[\d.]+/g).slice(0,3).map(Number).map(c=>{const v=c/255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,c,i)=>s+c*[.2126,.7152,.0722][i],0);
      const fg=luminance(foreground),bg=luminance(background);
      return {foreground,background,ratio:(Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05)};
    });
    assert(contrast.ratio>=4.5,`intake-${theme}-${viewport.width}: rendered contact contrast `+JSON.stringify(contrast));
    await audit(page,`intake-${theme}-${viewport.width}`,viewport.width===1440||viewport.width===320);
    await next(page);
    await next(page);
    assert(await page.locator('#making').getAttribute('aria-invalid')==='true','Empty brief needs a focused, specific error');
    assert(await page.locator('#making').evaluate(el=>el===document.activeElement),'Validation must focus the missing starting point');
    await audit(page,`intake-error-${theme}-${viewport.width}`);
    await page.locator('#making').fill('A screen that helps someone find their footing.');
    await next(page);
    if ([1440,320].includes(viewport.width)) await audit(page,`difficulty-${theme}-${viewport.width}`);
    await next(page);
    if ([1440,320].includes(viewport.width)) await audit(page,`outcome-${theme}-${viewport.width}`);
    await next(page);
    const withFollowups=[1440,320].includes(viewport.width);
    if (withFollowups) {
      for (const [key,value] of Object.entries({timing:'November, with a flexible date.',budget:'USD 2,000–4,000; still scoping.',materials:'https://example.invalid/private-prototype-marker'})) {
        await page.locator(`[data-followup]:has(#${key}) summary`).click();
        await page.locator('#'+key).fill(value);
      }
      await audit(page,`constraints-${theme}-${viewport.width}`,true);
    }
    await next(page);
    const fullBrief=await page.locator('#brief-text').inputValue();
    assert(withFollowups ? fullBrief.includes('USD 2,000–4,000')&&fullBrief.includes('private-prototype-marker') : !fullBrief.includes('Working budget\n'), 'Optional follow-ups must be included only when answered');
    await audit(page,`brief-${theme}-${viewport.width}`,viewport.width===1440||viewport.width===320);
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#download-brief').click();
    const download = await downloadPromise;
    const downloaded = await readFile(await download.path(),'utf8');
    assert(downloaded.includes('find their footing'),'Download must include the visitor’s actual answers');
    assert(!withFollowups||downloaded.includes('private-prototype-marker'),'Download must retain the material at the end of the brief');
    await page.locator('#carry-question').click();
    await page.locator('#your-question').waitFor({state:'visible'});
    assert((await page.locator('#your-question').innerText()).includes('find their footing'),'Question handoff lost the visitor’s words');
    await page.locator('#your-question summary').filter({hasText:'Open your original answers'}).click();
    assert(!withFollowups||(await page.locator('#your-question dl').innerText()).includes('USD 2,000–4,000'),'Workbench must carry optional commercial context literally');
    await page.locator('#your-question summary').filter({hasText:'Open your original answers'}).click();
    await audit(page,`workbench-${theme}-${viewport.width}`,viewport.width===1440||viewport.width===320);
    await page.locator('input[name="surface"][value="reason"]').check();
    assert(await page.locator('[data-surface="reason"]').isVisible()&&!await page.locator('[data-surface="host"]').isVisible(),'Prototype selection must show the matching sketch');
    await page.locator('#mark-wrong').click();
    await page.locator('#annotation').fill('I do not know which choice fits me.');
    await audit(page,`observation-${theme}-${viewport.width}`,viewport.width===320);
    await page.locator('#pin-observation').click();
    assert((await page.locator('#annotation-record').innerText()).startsWith('Ask for the reason first:'),'Observation must retain the inspected approach');
    await page.locator('input[name="choice"][value="open"]').check();
    assert((await page.locator('#recorded-choice').innerText())==='No draft choice recorded.','Choosing a radio must not silently commit a decision');
    await page.locator('#record-choice').click();
    await page.reload();
    assert((await page.locator('#recorded-choice').innerText()).includes('Keep the question open'),'Recorded local choice must survive same-tab reload');
    assert((await page.locator('#annotation-record').innerText()).includes('which choice fits me'),'Pinned observation must survive same-tab reload');
    if (withFollowups) {
      await page.goto(origin+'/questions/');
      for (const [key,value] of Object.entries({timing:'November, with a flexible date.',budget:'USD 2,000–4,000; still scoping.',materials:'https://example.invalid/private-prototype-marker'})) {
        assert(await page.locator('#'+key).inputValue()===value, 'Return must preserve '+key);
        assert(await page.locator('#'+key).evaluate(el=>el.closest('details').open), 'Return must reopen answered '+key);
      }
      await page.goto(origin+'/workbench/');
      await page.locator('#your-question').waitFor({state:'visible'});
    }
    await page.locator('#clear-room').click();
    assert(!await page.locator('#your-question').isVisible(),'Clear draft must remove the carried question');
    await page.goto(origin+'/questions/');
    assert(await page.locator('#making').inputValue()==='','Cleared answers must not return');
    for (const key of ['timing','budget','materials']) assert(await page.locator('#'+key).inputValue()==='', 'Cleared '+key+' must not return');
    assert(errors.length===0,JSON.stringify({viewport,theme,errors}));
    await context.close();
  }

  const context = await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
  const page = await context.newPage();
  const requests = [];
  page.on('request',r=>requests.push({url:r.url(),method:r.method(),body:r.postData()}));
  await page.goto(origin+'/questions/');
  const hostile = '<img src=x onerror="window.__draftInjection=1"> private-marker-983';
  await makeBrief(page,hostile);
  await page.locator('#brief-text').fill('My edited brief. private-marker-983');
  await page.locator('#edit-answers').click();
  await page.locator('#making').waitFor({state:'visible'});
  await page.locator('#making').fill(hostile+' edited');
  await next(page);await next(page);await next(page);await next(page);
  assert(await page.locator('#brief-text').inputValue()==='My edited brief. private-marker-983','Returning from answers must preserve manual brief edits');
  await page.locator('#carry-question').click();
  await page.locator('#your-question').waitFor({state:'visible'});
  await page.locator('#your-question summary').filter({hasText:'Your edited brief'}).click();
  assert((await page.locator('#carried-brief').innerText())==='My edited brief. private-marker-983','Handoff must preserve the edited brief separately from original answers');
  assert(await page.evaluate(()=>!window.__draftInjection),'Visitor text must never execute as HTML');
  await page.locator('#mark-wrong').click();
  await page.locator('#annotation').fill(hostile);
  await page.locator('#cancel-observation').click();
  assert(await page.locator('#annotation-record').innerText()==='No observation pinned yet.','Cancelled observation must not be recorded');
  assert(requests.every(r=>r.method==='GET'&&!r.url.includes('private-marker')&&!r.body),'Answers must not travel in requests or URLs');
  await page.goto(origin+'/questions/');
  await next(page); await next(page); await next(page); await next(page); await next(page);
  assert(await page.locator('#brief-text').inputValue()==='My edited brief. private-marker-983','Returning from the room must restore the edited brief');
  await page.locator('#clear-draft').click();
  await makeBrief(page,'A replacement question.');
  await page.locator('#carry-question').click();
  assert(await page.locator('#annotation-record').innerText()==='No observation pinned yet.','A new question must not inherit an old project annotation');
  assert(await page.locator('#recorded-choice').innerText()==='No draft choice recorded.','A new question must not inherit an old project choice');
  results.push({label:'edits-cancellation-replacement-no-transmission',passed:true});
  await context.close();

  const historyPage = await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
  await historyPage.goto(origin+'/questions/');
  await historyPage.locator('input[name="intent"]').first().check();
  await next(historyPage);
  assert((await historyPage.locator('#making-help').innerText()).includes('possibility'),'Idea entrance must guide the next prompt');
  await historyPage.locator('#making').fill('Keep my words when I go back.');
  await next(historyPage);
  await historyPage.goBack();
  await historyPage.locator('#making').waitFor({state:'visible'});
  assert(await historyPage.locator('#making').inputValue()==='Keep my words when I go back.','Browser Back must restore the preceding question with its answer');
  await historyPage.goForward();
  await historyPage.locator('#difficulty').waitFor({state:'visible'});
  assert(!historyPage.url().includes('Keep'),'Question history must not expose answers in URLs');
  await historyPage.locator('#clear-draft').click();
  await historyPage.goBack();
  await historyPage.locator('#making').waitFor({state:'visible'});
  assert(await historyPage.locator('#making').inputValue()==='','History must not recover cleared words');
  results.push({label:'browser-back-forward',passed:true});
  await historyPage.close();

  const blocked = await browser.newContext({viewport:{width:320,height:740},reducedMotion:'reduce'});
  await blocked.addInitScript(() => { for (const key of ['localStorage','sessionStorage']) Object.defineProperty(window,key,{get(){throw new Error('Storage blocked');}}); });
  const blockedPage=await blocked.newPage();
  await blockedPage.goto(origin+'/questions/');
  await makeBrief(blockedPage);
  await blockedPage.locator('#carry-question').click();
  assert(blockedPage.url().endsWith('/questions/'),'Failed handoff must retain the visitor’s brief');
  assert((await blockedPage.locator('#draft-status').innerText()).includes('cannot carry'),'Storage failure must offer a truthful recovery');
  await blockedPage.goto(origin+'/workbench/');
  await blockedPage.locator('input[name="choice"][value="host"]').check();
  await blockedPage.locator('#record-choice').click();
  assert((await blockedPage.locator('#draft-status').innerText()).includes('visit only'),'Unavailable persistence must not claim a saved choice');
  results.push({label:'storage-denied',passed:true});
  await blocked.close();

  for (const fallback of ['no-javascript','module-unavailable']) {
    const context=await browser.newContext({viewport:{width:320,height:740},javaScriptEnabled:fallback!=='no-javascript',reducedMotion:'reduce'});
    if (fallback==='module-unavailable') await context.route('**/assets/loose-end*.mjs',route=>route.abort());
    const page=await context.newPage();
    await page.goto(origin+'/questions/');
    assert(await page.locator('#making').isVisible()&&await page.locator('#constraints').isVisible(),fallback+': complete question sheet must remain visible');
    assert(!await page.locator('#question-next').isVisible(),fallback+': dead guided controls must stay hidden');
    await page.locator('[data-followup]:has(#materials) summary').click();
    assert(await page.locator('#materials').isVisible(),fallback+': optional material needs a native disclosure');
    await page.goto(origin+'/workbench/');
    assert(await page.locator('[data-surface="host"]').isVisible()&&await page.locator('[data-surface="reason"]').isVisible(),fallback+': both approaches must remain inspectable');
    await page.locator('summary').filter({hasText:'What we left aside'}).click();
    assert(await page.locator('h3').filter({hasText:'A single search for everything.'}).isVisible(),fallback+': rejected approach must remain inspectable');
    await audit(page,'workbench-'+fallback,true);
    await context.close();
  }
} catch(error) { failures.push(error.stack); }
finally {
  await writeFile(join(output,'loose-end-audit.json'),JSON.stringify({results,failures},null,2));
  console.log(JSON.stringify({checks:results.length,failures},null,2));
  await browser.close();
}
if(failures.length)process.exitCode=1;
