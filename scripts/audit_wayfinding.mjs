/** Collection discovery, native fallback and identical menu typography. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
const origin=process.env.SITE_URL||'http://127.0.0.1:8793';
const output=process.env.AUDIT_OUTPUT||'artifacts/design-review';
await mkdir(output,{recursive:true});
const browser=await launchAuditBrowser();
const results=[];
function assert(value,message){if(!value)throw new Error(message);}
try {
  for(const width of [320,375,600,768,1440]) for(const theme of ['night','afterlight']) {
    const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
    await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const response=await page.goto(origin+'/specimens/',{waitUntil:'networkidle'});
    assert(response.status()===200,'Collection must return 200');
    assert(await page.locator('.specimen-entry').count()===10,'Ten specimen identities, including Sohva');
    const links=page.locator('.collection-nav a');
    for(let i=0;i<2;i++)assert(await links.nth(i).isVisible(),'Persistent collection link');
    assert(await links.first().getAttribute('aria-current')==='page','Current collection state');
    assert(await page.locator('.specimens-intro a').evaluate(el=>el.getBoundingClientRect().bottom<900),'Direct TNT action is within first phone screen');
    const closed=await page.locator('#menu-toggle').boundingBox();
    await page.locator('#menu-toggle').click();
    await page.waitForFunction(()=>document.querySelector('#menu-toggle').getAttribute('aria-expanded')==='true');
    const faces=await page.locator('.nav-sheet-label').evaluateAll(els=>els.map(el=>{const s=getComputedStyle(el);return [s.fontFamily,s.fontWeight,s.fontSize,s.lineHeight,s.textTransform].join('|');}));
    assert(faces.length===4 && new Set(faces).size===1,'All four numbered rows share exactly one type treatment');
    assert(await page.locator('.nav-sheet-label').nth(1).evaluate(el=>el.clientHeight<=parseFloat(getComputedStyle(el).lineHeight)+1),'Field notes fits on one menu line');
    assert(await page.locator('.nav-shortcut').count()===3,'Exactly three curated shortcuts');
    assert(await page.locator('#primary-nav').evaluate(el=>{const b=el.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth&&b.bottom<=innerHeight;}),'Sheet fits viewport');
    const open=await page.locator('#menu-toggle').boundingBox();
    assert(['x','y','width','height'].every(k=>Math.abs(closed[k]-open[k])<.1),'Menu trigger remains still');
    if([320,375,1440].includes(width))await page.screenshot({path:`${output}/wayfinding-${width}-${theme}-menu.png`});
    await page.keyboard.press('Escape');
    assert(await page.locator('#menu-toggle').evaluate(el=>el===document.activeElement),'Escape restores focus');
    assert(!await page.locator('#primary-nav').isVisible(),'Escape closes sheet');
    await page.locator('#menu-toggle').press('Enter');
    await page.waitForFunction(()=>document.activeElement===document.querySelector('#primary-nav>a'));
    await page.keyboard.press('Shift+Tab');
    assert(await page.locator('#menu-toggle').evaluate(el=>el===document.activeElement),'Backward exit returns to the trigger');
    assert(!await page.locator('#primary-nav').isVisible(),'Backward exit closes sheet');
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'No horizontal overflow');
    assert(await page.locator('.specimen-trace').evaluate(el=>{const b=el.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth&&[...el.children].every(n=>{const r=n.getBoundingClientRect();return r.top>=b.top&&r.bottom<=b.bottom&&r.left>=b.left&&r.right<=b.right;});}),'Both saved Ajo states and the receiver count remain fully visible');
    await page.addScriptTag({content:axe.source});
    const violations=await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}})).violations);
    assert(!violations.length,JSON.stringify(violations));
    if([320,375,1440].includes(width))await page.screenshot({path:`${output}/wayfinding-${width}-${theme}-index.png`});
    assert(!errors.length,errors.join(';'));
    results.push({width,theme,faces});await page.close();
  }
  for(const path of ['/','/notes/017-the-grid-is-shared.html','/specimens/coastal-watch/radar-replay/','/specimens/maintenance-acceptance/tnt/','/workbench/','/404.html']) {
    for(const fallback of ['no-js','blocked-script']) {
      console.log(`Native route: ${path} / ${fallback}`);
      const page=await browser.newPage({viewport:{width:375,height:850},javaScriptEnabled:fallback!=='no-js'});
      if(fallback==='blocked-script')await page.route('**/assets/site.js',route=>route.abort());
      await page.goto(origin+path,{waitUntil:'networkidle'});
      assert(await page.locator('.collection-nav a').first().isVisible(),`${path} collection accessible without script`);
      await page.locator('#menu-toggle').click();
      assert(await page.locator('#primary-nav').isVisible(),`${path} native disclosure opens`);
      assert(await page.locator('.nav-shortcut').count()===3,`${path} shortcuts authored`);
      await page.screenshot({path:`${output}/native-${path.replace(/[^a-z0-9]/gi,'_')}-${fallback}.png`});
      console.log(await page.locator('#primary-nav>a').first().boundingBox());
      await page.locator('#primary-nav>a').first().click();
      assert(new URL(page.url()).pathname==='/specimens/',`${path} reaches actual collection`);
      results.push({path,fallback});await page.close();
    }
  }
  for(const path of ['/specimens/maintenance-acceptance/tnt/','/specimens/coastal-watch/radar-replay/']) for(const theme of ['night','afterlight']) {
    const page=await browser.newPage({viewport:{width:375,height:850},reducedMotion:'reduce'});
    await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
    await page.goto(origin+path,{waitUntil:'networkidle'});
    await page.addScriptTag({content:axe.source});
    const violations=await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}})).violations);
    assert(!violations.length,`${path} ${theme}: ${JSON.stringify(violations)}`);
    results.push({path,theme,deepPage:true});await page.close();
  }
  await writeFile(`${output}/wayfinding-audit.json`,JSON.stringify(results,null,2));
  console.log(`Wayfinding: ${results.length} responsive, theme and native fallback cases passed.`);
} finally {await browser.close();}
