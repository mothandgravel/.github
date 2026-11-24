/** Browser audit for the live brief builder and its optional, local workbench handoff. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { briefText, draftKey, roomKey } from '../docs/assets/loose-end-model-v2.mjs';

const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const route = origin + '/questions/';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser({ headless: true });
const results = [];
const sizes = [[1440,900],[1024,768],[768,1024],[390,844],[320,740]];
const marker = 'draft-only-324';
const open = button => button.locator('#journey-controls').waitFor({state:'visible'});
const preview = page => page.locator('#brief-text');
const extras = page => page.locator('.brief-extras summary');
const step = (page, i) => page.locator('[data-brief-step="'+i+'"]').click();

function mailParams(href) {
  const url = new URL(href);
  assert.equal(url.protocol, 'mailto:');
  assert.equal(url.pathname, 'hello@mothandgravel.com');
  return url.searchParams;
}

try {
  for (const [width,height] of sizes) for (const theme of ['night','afterlight']) {
    const page = await browser.newPage({viewport:{width,height},reducedMotion:'reduce',
      colorScheme:theme==='night'?'dark':'light'});
    const errors = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => requests.push({url:request.url(),method:request.method(),body:request.postData()}));
    await page.goto(route);
    await open(page);
    assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
    assert.equal(await preview(page).inputValue(),'');
    assert.equal(await page.locator('#loose-end [required], #loose-end [type=email]').count(),0);
    assert.equal(await page.locator('[data-step]').count(),4);
    for(let i=0;i<4;i++){
      await step(page,i);
      assert.equal(await page.locator('[data-step]:visible').count(),1);
      assert.equal(await page.locator('[data-brief-step="'+i+'"]').getAttribute('aria-current'),'step');
    }
    await page.locator('#question-next').click();
    assert(await preview(page).evaluate(el=>document.activeElement===el),'The last step can go straight to the empty editable brief');
    await step(page,0);
    await page.getByLabel('Interface where people hesitate',{exact:true}).check();
    await page.getByLabel('Connected device / telemetry',{exact:true}).check();
    await page.locator('#making').fill('Operator console for field units '+marker);
    assert.match(await preview(page).inputValue(),/Interface where people hesitate\n- Connected device \/ telemetry\nOperator console/);
    await page.getByLabel('Interface where people hesitate',{exact:true}).uncheck();
    assert.doesNotMatch(await preview(page).inputValue(),/Interface where people hesitate/);
    await page.locator('#question-next').click();
    await page.getByLabel('System parts disagree on state',{exact:true}).check();
    await page.getByLabel('Status looks green, nobody trusts it',{exact:true}).check();
    await page.locator('#difficulty').fill('Two displays show different results.\nPeople retry the action.');
    assert.match(await preview(page).inputValue(),/People retry the action\./);
    await step(page,2);
    await page.getByLabel('Working prototype',{exact:true}).check();
    await page.getByLabel('Technical spike',{exact:true}).check();
    assert.doesNotMatch(await preview(page).inputValue(),/Working prototype/);
    await page.locator('#clear-artifact').click();
    assert.doesNotMatch(await preview(page).inputValue(),/Technical spike/);
    await page.getByLabel('Not sure — help narrow it',{exact:true}).check();
    await step(page,3);
    await page.getByLabel('Hardware/firmware is fixed',{exact:true}).check();
    await page.getByLabel('Open timeline',{exact:true}).check();
    await page.locator('#constraints').fill('The field terminal stays offline. A + B & C.');
    let brief = await preview(page).inputValue();
    assert.match(brief,/## First artifact\n- Not sure — help narrow it/);
    assert.match(brief,/Hardware\/firmware is fixed\n- Open timeline\nThe field terminal/);
    assert.equal(mailParams(await page.locator('#send-brief').getAttribute('href')).get('body').replace(/\r\n/g,'\n'),brief);
    assert.match(mailParams(await page.locator('#send-brief').getAttribute('href')).get('subject'),/^A brief for Moth & Gravel/);
    await preview(page).fill(brief.replace('People retry the action.','My exact manual note: “do not retry.”'));
    await page.getByLabel('Open timeline',{exact:true}).uncheck();
    brief = await preview(page).inputValue();
    assert.match(brief,/My exact manual note: “do not retry\.”/);
    assert.doesNotMatch(brief,/- Open timeline/);
    await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copiedBrief=text;}},configurable:true}));
    await page.locator('#copy-brief').click();
    assert.equal(await page.evaluate(()=>window.copiedBrief),brief);
    assert.equal(await page.locator('#draft-status').textContent(),'Brief copied.');
    await step(page,0);
    const layout = await page.evaluate(() => {
      const left = document.querySelector('.brief-controls').getBoundingClientRect();
      const right = document.querySelector('.brief-output').getBoundingClientRect();
      return { pageFits:document.documentElement.scrollWidth <= innerWidth+1,
        placement:right.left >= left.right ? 'beside' : right.top >= left.bottom ? 'below' : 'overlap' };
    });
    assert.deepEqual(layout,{pageFits:true,placement:width>900?'beside':'below'});
    await page.addScriptTag({content:axe.source});
    const violations = await page.evaluate(async()=> (await window.axe.run('#loose-end',{
      runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}
    })).violations.map(v=>[v.id,v.nodes.map(n=>n.target)]));
    assert.deepEqual(violations,[],width+' '+theme);
    if ([1440,390].includes(width)){
      await page.evaluate(()=>{document.activeElement.blur();document.getElementById('brief-text').scrollTop=0;scrollTo(0,0);});
      await page.screenshot({path:join(output,`brief-builder-${width}-${theme}.png`),fullPage:width===390});
    }
    assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),draftKey),null,'Typing does not store a draft until explicitly carried');
    assert(requests.every(r=>r.method==='GET'&&!r.body&&!r.url.includes(marker)&&!r.url.includes('enquiry-config')), 'There is no form or draft transmission');
    assert.deepEqual(errors,[]);
    results.push({width,theme,accessibility:violations.length});
    await page.close();
  }

  const page = await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
  await page.goto(route);
  await open(page);
  const answers = {making:'An existing question.',materials:'An old sample to retain.'};
  const multiline = {...answers, making:'An existing question.\nWith another line.'};
  await page.evaluate(({key, draft})=>sessionStorage.setItem(key,draft),{
    key:draftKey, draft:JSON.stringify({version:1,answers:multiline,brief:briefText(multiline)})
  });
  await page.reload();
  await open(page);
  assert.equal(await page.locator('#making').inputValue(),'An existing question. With another line.');
  assert.match(await preview(page).inputValue(),/## System\nAn existing question\.\nWith another line\./);
  await page.getByLabel('Cloud or mobile software',{exact:true}).check();
  assert.match(await preview(page).inputValue(),/An existing question\.\nWith another line\./);
  await page.locator('#making').fill('Refined question.');
  assert.doesNotMatch(await preview(page).inputValue(),/An existing question/);
  assert.match(await preview(page).inputValue(),/An old sample to retain/);
  const legacy = JSON.stringify({version:1,answers,brief:'My edited brief. Keep this.'});
  await page.evaluate(({key,legacy})=>sessionStorage.setItem(key,legacy),{key:draftKey,legacy});
  await page.reload();
  await open(page);
  assert.equal(await page.locator('#making').inputValue(),'An existing question.');
  assert.equal(await preview(page).inputValue(),'My edited brief. Keep this.');
  assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),draftKey),legacy);
  await page.getByLabel('Cloud or mobile software',{exact:true}).check();
  assert.match(await preview(page).inputValue(),/My edited brief\. Keep this\.[\s\S]*Cloud or mobile software/);
  await step(page,2);
  await page.getByLabel('Working prototype',{exact:true}).check();
  const edited = 'Here is the draft.\nEvery line and punctuation survives. + & 🌒';
  await preview(page).fill(edited);
  await extras(page).click();
  const downloading = page.waitForEvent('download');
  await page.locator('#download-brief').click();
  const download = await downloading;
  assert.equal(await readFile(await download.path(),'utf8'),edited);
  await page.locator('#carry-question').click();
  await page.waitForURL(origin+'/workbench/#your-question');
  assert.equal(await page.locator('#carried-brief').textContent(),edited);
  assert.match(await page.locator('#your-question dl').textContent(),/An old sample to retain/);
  assert.match(await page.locator('#your-question dl').textContent(),/Working prototype/);
  await page.locator('#mark-wrong').click();
  await page.locator('#annotation').fill('Keep a local observation.');
  await page.locator('#pin-observation').click();
  await page.getByRole('link',{name:'Back to your question'}).click();
  await open(page);
  assert.equal(await preview(page).inputValue(),edited);
  assert(await page.getByLabel('Cloud or mobile software',{exact:true}).isChecked());
  assert.match(await page.evaluate(key=>sessionStorage.getItem(key),roomKey),/Keep a local observation/);
  await step(page,2);
  await page.locator('#clear-artifact').click();
  await extras(page).click();
  await page.locator('#carry-question').click();
  await page.waitForURL(origin+'/workbench/#your-question');
  assert.doesNotMatch(await page.locator('#your-question dl').textContent(),/Working prototype/);
  await page.getByRole('link',{name:'Back to your question'}).click();
  await open(page);
  await extras(page).click();
  await page.locator('#clear-draft').click();
  assert.equal(await preview(page).inputValue(),'');
  assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),draftKey),null);
  assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),roomKey),null);
  await page.close();

  const history = await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
  await history.goto(route);
  await open(history);
  await history.locator('#making').fill('Keep this as I go back.');
  await history.locator('#question-next').click();
  await history.goBack();
  await history.locator('#making').waitFor({state:'visible'});
  assert.equal(await history.locator('#making').inputValue(),'Keep this as I go back.');
  await history.goForward();
  await history.locator('#difficulty').waitFor({state:'visible'});
  assert.equal(history.url(),route);
  await history.getByRole('link',{name:'go straight to the brief'}).click();
  assert.equal(new URL(history.url()).hash,'#brief-heading');
  assert(await history.locator('#difficulty').isVisible(),'An in-page link keeps the active step');
  await history.goBack();
  assert(await history.locator('#difficulty').isVisible(),'Back across the in-page link keeps the active step');
  await history.goBack();
  assert(await history.locator('#making').isVisible(),'Back across a step restores the earlier step');
  await history.getByLabel('Connected device / telemetry',{exact:true}).check();
  await step(history,2);
  await history.getByLabel('Working prototype',{exact:true}).check();
  const manual = (await preview(history).inputValue()) + '\n\nKeep my manual note.';
  await preview(history).fill(manual);
  await history.goto(origin+'/specimens/');
  await history.goBack();
  await open(history);
  await history.waitForFunction(() => {
    const text = document.getElementById('brief-text').value;
    const email = new URL(document.getElementById('send-brief').href).searchParams.get('body');
    return email.replace(/\r\n/g,'\n') === text;
  });
  const returned = await preview(history).inputValue();
  // A full browser history traversal may restore native fields or load them fresh.
  if (await history.getByLabel('Working prototype',{exact:true}).isChecked()) {
    assert.equal(returned,manual);
    await history.locator('#clear-artifact').click();
    assert.doesNotMatch(await preview(history).inputValue(),/Working prototype/);
    assert.match(await preview(history).inputValue(),/Keep my manual note/);
  } else {
    assert.equal(returned,'');
  }
  await history.close();

  const denied = await browser.newContext({viewport:{width:320,height:740},reducedMotion:'reduce'});
  await denied.addInitScript(()=> {
    Object.defineProperty(window,'sessionStorage',{get(){throw new Error('Storage denied');}});
    Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('Clipboard denied');}},configurable:true});
  });
  const fallback = await denied.newPage();
  await fallback.goto(route);
  await open(fallback);
  await preview(fallback).fill('Write directly without using any steps.\n'+'🌒 & + '.repeat(600));
  const long = await preview(fallback).inputValue();
  assert.equal(mailParams(await fallback.locator('#send-brief').getAttribute('href')).get('body').replace(/\r\n/g,'\n'),long);
  assert(await fallback.locator('#send-limit').isVisible());
  await fallback.locator('#copy-brief').click();
  assert.match(await fallback.locator('#draft-status').textContent(),/selected for you to copy/);
  assert(await preview(fallback).evaluate(el=>el.selectionEnd===el.value.length && el.selectionStart===0));
  await extras(fallback).click();
  await fallback.locator('#carry-question').click();
  assert.match(await fallback.locator('#draft-status').textContent(),/cannot carry/);
  assert.equal(await preview(fallback).inputValue(),long);
  assert.equal(fallback.url(),route);
  await denied.close();

  const late = await browser.newPage({viewport:{width:390,height:844}});
  await late.goto(route);
  await open(late);
  await preview(late).fill('Old text');
  await late.evaluate(()=>Object.defineProperty(navigator,'clipboard',{
    value:{writeText:()=>new Promise((resolve,reject)=>{window.rejectCopy=reject;})},configurable:true
  }));
  await late.locator('#copy-brief').click();
  await preview(late).fill('Newer text');
  await late.evaluate(()=>window.rejectCopy(new Error('Late clipboard response')));
  assert.equal(await preview(late).inputValue(),'Newer text');
  assert.equal(await late.locator('#draft-status').textContent(),'');
  await late.close();

  for (const javaScriptEnabled of [false,true]) {
    const native = await browser.newPage({viewport:{width:320,height:740},javaScriptEnabled});
    if(javaScriptEnabled) await native.route('**/assets/brief-builder.mjs*',request=>request.abort());
    await native.goto(route);
    assert.equal(await native.locator('[data-step]:visible').count(),4);
    assert(await native.locator('#making').isVisible()&&await preview(native).isEditable());
    assert(await native.locator('#brief-fallback').isVisible());
    assert.equal(mailParams(await native.locator('#send-brief').getAttribute('href')).has('body'),false);
    await extras(native).click();
    assert(await native.locator('#workbench-fallback').isVisible());
    await native.close();
  }
  await writeFile(join(output,'loose-end-audit.json'),JSON.stringify({results},null,2));
  console.log('PASS: four optional steps, live editing, exact output, local handoff, storage and clipboard recovery, and native fallback.');
} finally {
  await browser.close();
}
