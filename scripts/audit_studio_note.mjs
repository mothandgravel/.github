/** Field Note 013: readable real evidence, responsive layout and no-script access. */
import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
const origin=process.env.SITE_URL||'http://127.0.0.1:8793';
const output=process.env.AUDIT_OUTPUT||'artifacts/design-review';
await mkdir(output,{recursive:true});
const options=process.env.BROWSER_EXECUTABLE ? {executablePath:process.env.BROWSER_EXECUTABLE} : {};
const browser=await chromium.launch(options);
const results=[];
try {
  for(const width of [320,390,1050,1440]) for(const theme of ['night','afterlight']) {
    const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(value=>localStorage.setItem('moth-and-gravel-theme',value),theme);
    await page.goto(origin+'/notes/013-work-outlives-the-window.html',{waitUntil:'networkidle'});
    await page.locator('article.note-prose').scrollIntoViewIfNeeded();
    for(const image of await page.locator('main img').all()) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(image=>image.decode());
    }
    const check=await page.evaluate(()=>({
      overflow:document.documentElement.scrollWidth>innerWidth,
      headings:document.querySelectorAll('h1').length,
      main:!!document.querySelector('main#main'),
      images:[...document.querySelectorAll('main img')].every(image=>image.naturalWidth>0 && image.alt.trim()),
      caption:document.querySelector('.note-cover-figure figcaption').textContent.includes('controlled test fixture'),
      diagram:!!document.querySelector('a[href$="013-work-ownership.svg"]'),
      source:!!document.querySelector('a[href*="571cc165835da5edd1c9959950c2e89198a39807"]'),
      next:document.querySelector('article').textContent.includes('The next specimen is this note.'),
      canonical:document.querySelector('link[rel=canonical]').href,
    }));
    if(check.overflow||check.headings!==1||!check.main||!check.images||!check.caption||!check.diagram||!check.source||!check.next||!check.canonical.endsWith('/notes/013-work-outlives-the-window.html')||errors.length) throw Error(JSON.stringify({width,theme,check,errors}));
    await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));
    if([390,1440].includes(width)) {
      await page.screenshot({path:`${output}/studio-note-${width}-${theme}-opening.png`});
      await page.screenshot({path:`${output}/studio-note-${width}-${theme}.png`,fullPage:true});
    }
    results.push({width,theme,...check}); await page.close();
  }
  const page=await browser.newPage({viewport:{width:390,height:844},javaScriptEnabled:false});
  await page.goto(origin+'/notes/013-work-outlives-the-window.html',{waitUntil:'networkidle'});
  if(!(await page.locator('article.note-prose').isVisible()) || await page.locator('h1').count()!==1 || await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('Written experiment must remain readable without JavaScript');
  await page.goto(origin+'/notes/',{waitUntil:'networkidle'});
  if(await page.locator('a[href="./013-work-outlives-the-window.html"]').count()<1) throw Error('New note missing from no-script archive');
  await page.close();
  await writeFile(`${output}/studio-note-review.json`,JSON.stringify({results,noScript:true},null,2));
  console.log(`PASS: Studio Field Note at ${results.length} viewport/theme combinations and no-script access`);
} finally { await browser.close(); }
