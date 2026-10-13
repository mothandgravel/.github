/** Light/handling browser review; never shipped to readers. */
import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
await mkdir(output, {recursive:true});
const browser = await chromium.launch();
const failures = [], results = [];
let checks = 0;
const assert = (value, message) => { checks++; if (!value) failures.push(message); };
const inspect = async page => {
  await page.locator('#specimen-ajo .work-specimen').scrollIntoViewIfNeeded();
  await page.locator('#specimen-ajo [data-depth-ready]').waitFor();
};
const playing = page => page.locator('#specimen-ajo [data-arriving]').waitFor();
const quiet = page => page.waitForFunction(() => !document.querySelector('[data-arriving]'));

try {
  for (const width of [390,1440]) for (const theme of ['night','afterlight']) {
    const label = `${width}-${theme}`;
    const page = await browser.newPage({viewport:{width,height:900},reducedMotion:'no-preference'});
    await page.addInitScript(theme => localStorage.setItem('moth-and-gravel-theme',theme),theme);
    await page.goto(origin,{waitUntil:'networkidle'});
    // Sample document coordinates while the marker arrives; scroll does not count as a shift.
    await page.evaluate(() => {
      window.handlingFrames=[];
      window.handlingProbe=setInterval(() => {
        const card=document.querySelector('#specimen-ajo');
        const plane=card.querySelector('.specimen-plane');
        const boxes=[card.querySelector('h3'),card.querySelector('summary'),card.querySelector('figcaption')].map(el=>{
          const b=el.getBoundingClientRect();return [b.x+scrollX,b.y+scrollY,b.width,b.height];
        });
        window.handlingFrames.push({boxes,arriving:plane.hasAttribute('data-arriving'),
          transform:getComputedStyle(plane,'::after').transform});
      },20);
    });
    await inspect(page); await playing(page); await quiet(page);
    const samples = await page.evaluate(() => { clearInterval(window.handlingProbe); return window.handlingFrames; });
    assert(samples.some(s=>s.arriving && s.transform!=='none'),label+': marker never arrived');
    assert(samples.every(s=>JSON.stringify(s.boxes)===JSON.stringify(samples[0].boxes)),label+': arrival moved reading/controls');
    const plane=page.locator('#specimen-ajo .specimen-plane');
    assert(await plane.evaluate(el=>el.getAnimations({subtree:true}).length===0),label+': arrival did not settle');
    assert(await plane.getAttribute('data-arrival-seen')!==null,label+': opportunity not consumed');
    await page.evaluate(()=>scrollTo({top:0,behavior:'instant'})); await page.waitForTimeout(100);
    await inspect(page); await page.waitForTimeout(160);
    assert(await page.locator('[data-arriving]').count()===0,label+': arrival repeats on return');
    assert(await plane.evaluate(el=>getComputedStyle(el).boxShadow.includes('6px 9px')),label+': contact light direction missing');
    await page.locator('#specimen-ajo summary').focus(); await page.keyboard.press('Enter');
    assert(await page.locator('#specimen-ajo details').getAttribute('open')!==null,label+': record cannot open');
    assert(await page.locator('#specimen-ajo summary').evaluate(el=>getComputedStyle(el).outlineStyle!=='none'),label+': focus invisible');
    const link=page.locator('.hero-actions .button');
    await link.scrollIntoViewIfNeeded(); const before=await link.boundingBox();
    await link.hover(); await page.waitForTimeout(250);
    assert(JSON.stringify(before)===JSON.stringify(await link.boundingBox()),label+': button hit area moves');
    assert(await link.locator('.button-arrow').evaluate(el=>getComputedStyle(el).transform!=='none'),label+': pointer feedback absent');
    await link.focus(); await page.waitForTimeout(250);
    assert(await link.locator('.button-arrow').evaluate(el=>getComputedStyle(el).transform==='matrix(1, 0, 0, 1, 0, 0)'||getComputedStyle(el).transform==='none'),label+': keyboard arrow still moves');
    await page.reload({waitUntil:'networkidle'}); await inspect(page); await page.waitForTimeout(100);
    assert(await page.locator('[data-arriving]').count()===0,label+': restored reload unexpectedly animates');
    await page.locator('#moth-interlude').scrollIntoViewIfNeeded();
    await page.locator('#moth-interlude').screenshot({path:join(output,'light-room-'+label+'.png'),style:'.site-header{visibility:hidden!important}'});
    results.push({label,samples:samples.length}); await page.close();
  }
  for (const action of ['focus','reduced','blur','pagehide','resize','keyboard','leave']) {
    const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'no-preference'});
    await page.goto(origin,{waitUntil:'networkidle'});await inspect(page);await playing(page);
    if(action==='focus')await page.locator('#specimen-ajo summary').focus();
    if(action==='reduced')await page.emulateMedia({reducedMotion:'reduce'});
    if(action==='blur')await page.evaluate(()=>dispatchEvent(new Event('blur')));
    if(action==='pagehide')await page.evaluate(()=>dispatchEvent(new PageTransitionEvent('pagehide')));
    if(action==='resize')await page.setViewportSize({width:1024,height:900});
    if(action==='keyboard')await page.keyboard.press('PageDown');
    if(action==='leave')await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
    await quiet(page);
    assert(await page.locator('#specimen-ajo .specimen-plane').evaluate(el=>el.getAnimations({subtree:true}).length===0),action+': interrupted arrival survives');
    await inspect(page);await page.waitForTimeout(120);
    assert(await page.locator('#specimen-ajo [data-arriving]').count()===0,action+': interrupted arrival resumes');
    await page.close();
  }
  for(const option of ['reduced','hash','no-js','touch']) {
    const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:option==='reduced'?'reduce':'no-preference',javaScriptEnabled:option!=='no-js',hasTouch:option==='touch',isMobile:option==='touch'});
    await page.goto(origin+(option==='hash'?'/#work':''),{waitUntil:'networkidle'});
    await page.locator('#specimen-ajo .work-specimen').scrollIntoViewIfNeeded();
    if(option!=='no-js')await page.locator('#specimen-ajo [data-depth-ready]').waitFor();
    await page.waitForTimeout(550);
    assert(await page.locator('[data-arriving]').count()===0,option+': arrival should be quiet');
    assert(await page.locator('#specimen-ajo h3').isVisible(),option+': question unavailable');
    if(option==='touch') {
      const link=page.locator('#specimen-ajo .work-card-link');await link.scrollIntoViewIfNeeded();
      await link.dispatchEvent('pointerover',{pointerType:'touch'});
      assert(await link.locator('span').evaluate(el=>getComputedStyle(el).transform==='none'),option+': hover-dependent arrow');
    }
    await page.locator('#specimen-ajo summary').click();
    assert(await page.locator('#specimen-ajo details').getAttribute('open')!==null,option+': native record unavailable');
    await page.close();
  }
} finally { await browser.close(); }
await writeFile(join(output,'handling-audit.json'),JSON.stringify({checks,results,failures},null,2));
console.log(JSON.stringify({checks,results,failures},null,2));
if(failures.length)process.exitCode=1;
