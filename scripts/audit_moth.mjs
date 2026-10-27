/** Browser review of the finite moth scene. Runs in development/CI only. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
await mkdir(output,{recursive:true});
const browser = await launchAuditBrowser();
const failures = [], results = [];
let checks = 0;
const assert = (value,message) => { checks++;if(!value) failures.push(message); };
const room = page => page.locator('#moth-interlude');
const ready = async page => {
  await room(page).scrollIntoViewIfNeeded();
  await page.locator('#moth-interlude[data-moth-ready="true"]').waitFor();
};
const state = (page,value) => page.waitForFunction(value=>document.querySelector('#moth-interlude').dataset.mothState===value,value);
const phase = (page,value) => page.waitForFunction(value=>document.querySelector('#moth-interlude').dataset.mothPhase===value,value);
const start = async page => { await page.locator('[data-moth-play]').click();await state(page,'playing'); };
const quiet = async (page,label) => {
  await state(page,'idle');
  assert(await room(page).locator('.moth-traveller').isHidden(),label+': stranded traveller');
  assert(await room(page).locator('.moth-shadow').isHidden(),label+': stranded shadow');
  assert(await room(page).getAttribute('data-moth-phase')===null,label+': stale phase');
  // Idle precedes the source mark's fade back in. Observe its completion
  // instead of assuming a 220ms wall-clock pause includes a rendered frame.
  await page.waitForFunction(()=>{
    const room=document.querySelector('#moth-interlude');
    return Number(getComputedStyle(room.querySelector('.moth-source img')).opacity)===1&&
      room.getAnimations({subtree:true}).length===0;
  },null,{timeout:5000}).catch(()=>{});
  assert(await room(page).locator('.moth-source img').evaluate(el=>Number(getComputedStyle(el).opacity)===1),label+': mark not restored');
};

try {
  for (const width of [320,390,768,901,1024,1440]) for (const theme of ['night','afterlight']) {
    const label = `moth-${width}-${theme}`;
    const page = await browser.newPage({viewport:{width,height:900},reducedMotion:'no-preference'});
    const errors = [], requested = [];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>requested.push(request.url()));
    await page.addInitScript(theme=>{localStorage.setItem('moth-and-gravel-theme',theme);},theme);
    await page.goto(origin,{waitUntil:'networkidle'});
    assert(!requested.some(url=>/moth-(interlude|choreography|rig)/.test(url)),label+': scene fetched during opening');
    assert(await page.locator('.moth-art').evaluate(el=>getComputedStyle(el).animationName==='none'),label+': hero still loops');
    await ready(page);
    await state(page,'playing');
    const questionBefore = await room(page).locator('.moth-question').boundingBox();
    // Inspect the actual rendered flight, independently of the planned route check.
    await page.evaluate(()=>{
      window.mothSamples=[];
      window.mothProbe=setInterval(()=>{
        const r=document.querySelector('#moth-interlude'),n=r.querySelector('.moth-traveller');
        if(n.hidden)return;
        const b=n.getBoundingClientRect(),s=r.querySelector('.moth-stage').getBoundingClientRect(),q=r.querySelector('.moth-question').getBoundingClientRect();
        window.mothSamples.push({phase:r.dataset.mothPhase,b:{left:b.left,top:b.top,right:b.right,bottom:b.bottom},
          inStage:b.left>=s.left-1&&b.right<=s.right+1&&b.top>=s.top-1&&b.bottom<=s.bottom+1,
          overlaps:b.right>q.left&&b.left<q.right&&b.bottom>q.top&&b.top<q.bottom});
      },40);
    });
    await phase(page,'travel');
    await page.locator('[data-moth-pause]').click();
    await state(page,'paused');
    const pose = await room(page).locator('.moth-traveller').getAttribute('style');
    const wing = await room(page).locator('#wing-soft-fore').getAttribute('transform');
    await page.waitForTimeout(150);
    assert(pose===await room(page).locator('.moth-traveller').getAttribute('style') && wing===await room(page).locator('#wing-soft-fore').getAttribute('transform'),label+': pause does not freeze pose');
    assert(JSON.stringify(questionBefore)===JSON.stringify(await room(page).locator('.moth-question').boundingBox()),label+': flight moved question');
    assert(await room(page).locator('.moth-traveller').evaluate(el=>getComputedStyle(el).pointerEvents==='none'),label+': traveller blocks controls');
    if ([390,1440].includes(width)) {
      await page.addScriptTag({content:axe.source});
      const a = await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})));
      assert(a.length===0,label+': accessibility '+JSON.stringify(a));
      await room(page).screenshot({path:join(output,label+'-flight.png'),style:'.site-header,.skip-link{visibility:hidden!important}'});
    }
    await page.locator('[data-moth-pause]').click();
    await phase(page,'settle');
    const settled = await room(page).locator('.moth-traveller').getAttribute('style');
    await page.waitForTimeout(200);
    assert(settled===await room(page).locator('.moth-traveller').getAttribute('style'),label+': moth does not actually settle');
    if ([390,1440].includes(width)) {
      await page.locator('[data-moth-pause]').click();
      await room(page).screenshot({path:join(output,label+'-settle.png'),style:'.site-header,.skip-link{visibility:hidden!important}'});
      await page.locator('[data-moth-pause]').click();
    }
    await quiet(page,label+' completion');
    const samples = await page.evaluate(()=>{clearInterval(window.mothProbe);return window.mothSamples;});
    assert(samples.length>35 && samples.every(s=>s.inStage&&!s.overlaps),label+': actual flight clips stage/question');
    assert(['travel','inspect','land','settle','depart'].every(p=>samples.some(s=>s.phase===p)),label+': missing performed phase');
    assert(await room(page).evaluate(el=>el.getAnimations({subtree:true}).length===0),label+': animation continues after completion');
    await page.reload({waitUntil:'networkidle'});await ready(page);await page.waitForTimeout(160);
    assert(await room(page).getAttribute('data-moth-state')==='idle',label+': automatic scene repeats in same tab');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),label+': horizontal overflow');
    assert(errors.length===0,label+': browser errors '+errors.join(';'));
    results.push({label,samples:samples.length,errors});await page.close();
  }

  const page = await browser.newPage({viewport:{width:390,height:900},reducedMotion:'no-preference'});
  await page.goto(origin,{waitUntil:'networkidle'});await ready(page);await state(page,'playing');
  await page.locator('[data-moth-finish]').click();await quiet(page,'Finish');
  assert(await page.locator('[data-moth-play]').evaluate(el=>document.activeElement===el),'Finish: keyboard focus not restored');
  await start(page);await page.locator('[data-moth-pause]').focus();await page.keyboard.press('Escape');await quiet(page,'Escape');
  await start(page);await page.locator('#light-switch').focus();await page.keyboard.press('Escape');await quiet(page,'Escape outside');
  assert(await page.locator('#light-switch').evaluate(el=>document.activeElement===el),'Escape: unrelated focus stolen');
  await start(page);await page.emulateMedia({reducedMotion:'reduce'});await quiet(page,'changed reduced motion');
  assert(await page.locator('[data-moth-play]').isDisabled(),'Reduced motion: replay still animates');
  await page.emulateMedia({reducedMotion:'no-preference'});await start(page);
  await page.setViewportSize({width:768,height:900});await quiet(page,'resize');
  await ready(page);await start(page);await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));await quiet(page,'leave stage');
  await ready(page);await start(page);await page.evaluate(()=>window.dispatchEvent(new Event('blur')));await quiet(page,'window blur handler');
  await start(page);await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));await quiet(page,'pagehide handler');
  await start(page);await room(page).locator('.moth-question a').click();
  await page.locator('#question-next').waitFor({state:'visible'});
  assert(page.url().endsWith('/questions/'),'Flight blocks the actual question route');
  await page.locator('#question-next').click();await page.locator('#making').waitFor({state:'visible'});
  assert(await page.locator('#making').isVisible(),'Question route cannot reach the editable starting question');
  await page.close();

  const aborted = await browser.newPage({viewport:{width:390,height:740},reducedMotion:'no-preference'});
  await aborted.addInitScript(()=>sessionStorage.setItem('moth-and-gravel-interlude-seen','yes'));
  await aborted.goto(origin,{waitUntil:'networkidle'});await ready(aborted);await aborted.waitForTimeout(100);
  await aborted.evaluate(()=>{const s=document.querySelector('.moth-stage').getBoundingClientRect();scrollTo({top:scrollY+s.top+260,behavior:'instant'});});
  await aborted.waitForTimeout(100);await aborted.locator('[data-moth-play]').click();
  await aborted.evaluate(()=>scrollTo({top:0,behavior:'instant'}));await aborted.waitForTimeout(250);
  await ready(aborted);await aborted.waitForTimeout(250);
  assert(await room(aborted).getAttribute('data-moth-state')==='idle','Aborted pending replay starts unexpectedly on return');
  await start(aborted);await state(aborted,'playing');await aborted.close();

  for (const settings of [
    {label:'reduced',reducedMotion:'reduce'},
    {label:'no-js',javaScriptEnabled:false},
    {label:'failed-rig',fault:'moth-rig.svg'},
    {label:'failed-style',fault:'moth-interlude.css'},
    {label:'failed-module',fault:'moth-interlude.mjs'},
  ]) {
    const fallback = await browser.newPage({viewport:{width:320,height:740},reducedMotion:settings.reducedMotion||'no-preference',javaScriptEnabled:settings.javaScriptEnabled});
    const errors=[];fallback.on('pageerror',error=>errors.push(error.message));
    if(settings.fault)await fallback.route('**/assets/'+settings.fault,route=>route.abort());
    await fallback.goto(origin,{waitUntil:'networkidle'});await room(fallback).scrollIntoViewIfNeeded();await fallback.waitForTimeout(350);
    assert(await room(fallback).locator('.moth-source img').isVisible(),settings.label+': resting mark missing');
    assert(await room(fallback).locator('.moth-question a').isVisible(),settings.label+': real question link missing');
    if(settings.label==='reduced')assert(await fallback.locator('[data-moth-play]').isDisabled(),settings.label+': motion allowed');
    else assert(await fallback.locator('[data-moth-play]').isHidden(),settings.label+': dead motion controls');
    assert(errors.length===0,settings.label+': unhandled browser error '+errors.join(';'));
    await room(fallback).locator('.moth-question a').click();assert(fallback.url().endsWith('/questions/'),settings.label+': native route broken');
    results.push({label:settings.label,errors});await fallback.close();
  }
  // At 200% equivalent narrow width, content remains readable; a tight route stays quiet.
  const narrow = await browser.newPage({viewport:{width:180,height:740},reducedMotion:'no-preference'});
  await narrow.goto(origin,{waitUntil:'networkidle'});await ready(narrow);await narrow.waitForTimeout(100);
  assert(await room(narrow).locator('.moth-question').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Narrow view: question clipped');
  assert(await room(narrow).getAttribute('data-moth-state')==='idle'&&await narrow.locator('[data-moth-play]').isDisabled(),'Narrow view: unsafe scene played');
  await narrow.setViewportSize({width:390,height:900});await ready(narrow);await start(narrow);await state(narrow,'playing');
  await narrow.close();
} finally { await browser.close(); }
await writeFile(join(output,'moth-audit.json'),JSON.stringify({checks,results,failures},null,2));
console.log(JSON.stringify({checks,results,failures},null,2));
if(failures.length)process.exitCode=1;
