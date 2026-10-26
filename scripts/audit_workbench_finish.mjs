/** Inspect the room's finish and the contracts beneath its material treatment. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
await mkdir(output, {recursive:true});
const browser = await launchAuditBrowser();
const results = [];
async function sketchSignature(locator) {
  return locator.evaluate(svg=>({viewBox:svg.getAttribute('viewBox'),drawing:[...svg.querySelectorAll('rect,text')].map(el=>({tag:el.tagName,attributes:[...el.attributes].map(a=>[a.name,a.value]).sort(),text:el.textContent}))}));
}
async function review(page, label) {
  await page.addScriptTag({content:axe.source});
  const violations = await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})));
  assert.deepEqual(violations,[],label);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),label+' overflow');
  await page.evaluate(async()=>{
    document.activeElement?.blur();scrollTo({top:0,behavior:'instant'});
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  });
  await page.screenshot({path:output+'/'+label+'.png',fullPage:true,animations:'disabled'});
  results.push({label,violations});
}
try {
  for(const width of [320,390,768,1024,1440]) for(const theme of ['night','afterlight']) {
    const context=await browser.newContext({viewport:{width,height:1000},reducedMotion:'reduce'});
    await context.addInitScript(theme=>localStorage.setItem('moth-and-gravel-theme',theme),theme);
    const page=await context.newPage(), errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(origin+'/workbench/');await page.locator('#mark-wrong').waitFor({state:'visible'});
    assert.match(await page.locator('.room-visits [aria-current="page"]').innerText(),/first look/i);
    const earlierSketches = { 'item-1':await sketchSignature(page.locator('[data-surface="item"] svg')), 'damage-1':await sketchSignature(page.locator('[data-surface="damage"] svg')) };
    const first=await page.locator('.artifact-view').boundingBox();
    await page.locator('input[name="surface"][value="damage"]').check();
    const second=await page.locator('.artifact-view').boundingBox();
    assert.ok(Math.abs(first.height-second.height)<1,'First-visit comparison must not resize the canvas');
    await page.locator('#mark-wrong').click();await page.locator('#annotation').fill('A note anchored to damage first.');
    assert.ok(await page.locator('#mark-wrong').isHidden(),'An open editor cannot be reset from its opener');
    await page.locator('input[name="surface"][value="item"]').check();
    assert.match(await page.locator('#annotation-context').innerText(),/Attached to: Start with the damage/);
    await page.locator('#pin-observation').click();
    assert.match(await page.locator('#annotation-record').innerText(),/^Start with the damage:/);
    assert.match(await page.locator('.room-specimen [data-room-feedback]').innerText(),/Observation pinned/);
    assert.ok(await page.locator('#draft-status').evaluate(el=>el.offsetWidth<=1&&getComputedStyle(el).display!=='none'),'The shared live status stays available without a duplicate visible message');
    await review(page,'room-first-'+theme+'-'+width);
    await page.locator('#mark-wrong').click();await page.locator('#annotation').fill('Unrecorded words must stay here.');
    await page.locator('.room-visits [aria-current="page"]').click();
    assert.equal(await page.locator('#annotation').inputValue(),'Unrecorded words must stay here.','The current-visit link must not reload and discard an open note');
    await page.locator('#cancel-observation').click();
    await page.locator('.room-visits a[href="return/"]').click();await page.locator('#open-return-note').waitFor({state:'visible'});
    assert.match(await page.locator('.room-visits [aria-current="page"]').innerText(),/What shifted/);
    const heights=[];
    for(const revision of ['damage-2','damage-1','item-1']) {
      await page.locator('input[name="revision"][value="'+revision+'"]').check();
      heights.push((await page.locator('.artifact-view').boundingBox()).height);
      if(revision!=='damage-2') {
        assert.deepEqual(await sketchSignature(page.locator('#revision-drawing svg')),earlierSketches[revision],'An earlier revision must keep the same drawing across visits');
        assert.ok(await page.locator('#return-choice-form button').isDisabled(),'An old inspected revision cannot be recorded as revision 2');
        assert.ok(await page.locator('#inspect-latest').isVisible(),'There is an explicit route back to the current decision');
      }
    }
    assert.ok(Math.max(...heights)-Math.min(...heights)<1,'Return comparison must keep a stable canvas');
    await page.locator('#inspect-latest').focus();await page.keyboard.press('Enter');
    assert.ok(await page.locator('input[name="revision"][value="damage-2"]').isChecked());
    assert.ok(await page.locator('input[name="revision"][value="damage-2"]').evaluate(el=>el===document.activeElement),'Revision return preserves keyboard focus');
    await page.locator('input[name="return-choice"][value="continue"]').check();await page.locator('#choice-reason').fill('Keep this unrecorded reason.');
    await page.locator('.room-visits [aria-current="page"]').click();
    assert.equal(await page.locator('#choice-reason').inputValue(),'Keep this unrecorded reason.','The current return-visit link must not discard an unrecorded reason');
    await page.locator('input[name="revision"][value="damage-1"]').check();
    // Defend the contract even if a caller bypasses the disabled submit control.
    await page.locator('#return-choice-form').evaluate(form=>form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true})));
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('mg-mending-return-v1')),null,'Wrong-revision submit cannot write a decision');
    await page.locator('#inspect-latest').click();
    assert.equal(await page.locator('#choice-reason').inputValue(),'Keep this unrecorded reason.');
    await page.locator('#return-choice-form button').click();
    assert.match(await page.locator('.room-direction [data-room-feedback]').innerText(),/Kept in this tab/);
    assert.match(await page.locator('#return-choice-record').innerText(),/revision 2: Keep damage first/);
    assert.ok(await page.locator('#return-choice-record').evaluate(el=>el===document.activeElement&&el.getBoundingClientRect().top>=document.querySelector('.site-header').getBoundingClientRect().bottom),'The kept direction receives focus below the masthead');
    await review(page,'room-return-'+theme+'-'+width);
    assert.deepEqual(errors,[]);
    await context.close();
  }
  const blocked=await browser.newContext({reducedMotion:'reduce'});
  await blocked.addInitScript(()=>{Storage.prototype.setItem=function(){throw Error('blocked');};});
  const page=await blocked.newPage();await page.goto(origin+'/workbench/return/');
  await page.locator('#open-return-note').click();await page.locator('#return-note').fill('Keep this only in memory.');
  await page.locator('#return-note-editor button[type="submit"]').click();
  assert.match(await page.locator('.room-specimen [data-room-feedback]').innerText(),/Storage is unavailable/);
  await blocked.close();
  for(const path of ['/workbench/','/workbench/return/']) {
    const context=await browser.newContext({javaScriptEnabled:false,viewport:{width:320,height:844}});
    const p=await context.newPage();await p.goto(origin+path);
    assert.ok(await p.locator('.room-visits a').count()===2);
    assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    if(path.endsWith('/return/')) {
      const svg=p.locator('#revision-drawing svg');
      assert.match(await svg.getAttribute('aria-label'),/loose seam/);
      assert.doesNotMatch(await svg.getAttribute('aria-label'),/delivery/);
      assert.ok(await p.locator('#return-choice-form').isHidden());
    } else assert.ok(await p.locator('[data-surface]').count()===2);
    await context.close();
  }
  console.log('Workbench finish: 20 responsive/theme reviews, zero axe violations; stable canvases, local feedback, note anchors, revision scope, unrecorded answers, keyboard return and native fallbacks pass.');
} finally {
  await browser.close();await writeFile(output+'/workbench-finish-review.json',JSON.stringify({results},null,2));
}
