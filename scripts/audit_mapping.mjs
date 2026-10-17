/** Original-capture framing, reading and accessible inspection; never a robot replay. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
const route = '/specimens/whose-map/';
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser();
const failures = [], results = [];
let checks = 0;
const check = (value, label) => { checks++; if (!value) failures.push(label); };
const captureStyle = '.site-header,.site-header *,.skip-link{visibility:hidden!important}';
const accessibility = async (page, label) => {
  await page.addScriptTag({content:axe.source});
  const violations = await page.evaluate(async () => (await axe.run(document, {
    runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']},
  })).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})));
  check(!violations.length, label + ': accessibility ' + JSON.stringify(violations));
};
try {
  for (const width of [320,390,768,1440]) for (const theme of ['night','afterlight']) {
    const label = `mapping-${width}-${theme}`;
    const page = await browser.newPage({viewport:{width,height:900},hasTouch:width<=390,reducedMotion:'reduce'});
    const errors=[], requests=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>requests.push({method:r.method(),url:r.url()}));
    await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
    await page.goto(origin+route,{waitUntil:'networkidle'});
    check(await page.locator('.mapping-camera img').evaluate(img=>img.complete&&img.naturalWidth>0&&img.currentSrc.includes('/camera-preview-')),label+': camera delivery preview missing');
    check(await page.locator('.mapping-camera a').getAttribute('href')==='../../assets/specimens/buggy/camera-rays.jpg',label+': original camera capture unreachable');
    for (const key of ['local','onboard']) {
      const panel=page.locator(`[data-capture-name="${key==='local'?'A grid built here.':'A grid received from there.'}"]`);
      const fieldset=panel.locator('fieldset');await fieldset.waitFor({state:'visible'});
      const source=await panel.locator('image').getAttribute('href');
      const expected=JSON.parse(await panel.getAttribute('data-views'));
      const viewport=panel.locator('svg.capture-viewport');
      const geometry = () => viewport.evaluate(el => {
        const r = el.getBoundingClientRect();
        return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height};
      });
      const before=await geometry();
      const choices=fieldset.locator('input');await choices.nth(0).focus();
      for (let i=0;i<4;i++) {
        if(i)await choices.nth(i-1).press('ArrowRight');
        const name=Object.keys(expected)[i],view=expected[name];
        check(await choices.nth(i).isChecked(),label+': native radio selection '+key+'/'+name);
        check(await viewport.getAttribute('viewBox')===view.box.join(' '),label+': wrong source crop '+key+'/'+name);
        const rectangle=await panel.locator('[data-crop]').evaluate(el=>['x','y','width','height'].map(k=>Number(el.getAttribute(k))));
        check(rectangle.every((n,j)=>n===view.box[j]),label+': clipping drops selected pixels '+key+'/'+name);
        check(await panel.locator('image').getAttribute('href')===source,label+': source replaced during inspection '+key+'/'+name);
        check((await panel.locator('svg title').textContent()).includes(view.label),label+': selected view has no accessible name '+key+'/'+name);
        check(await panel.locator('[data-view-caption]').textContent()===view.caption,label+': source caption lost '+key+'/'+name);
        const after=await geometry();
        check(['x','y','width','height'].every(k=>Math.abs(before[k]-after[k])<.1),label+': inspection viewport moves '+key+'/'+name);
      }
      // Touch/native activation also reaches the world map without changing the other capture.
      if(width<=390)await panel.getByText('World map',{exact:true}).tap();
      else await panel.getByLabel('World map',{exact:true}).check();
      check(await viewport.getAttribute('viewBox')===expected.world.box.join(' '),label+': direct/touch choice '+key);
    }
    await accessibility(page,label);
    check(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),label+': horizontal overflow');
    check(!requests.some(r=>r.method!=='GET'||!r.url.startsWith(origin)),label+': study transmits or requests external content');
    check(!errors.length,label+': browser errors '+errors.join(';'));
    if ([390,1440].includes(width)) {
      await page.evaluate(()=>document.activeElement?.blur());
      await page.screenshot({path:join(output,label+'-full.png'),fullPage:true,style:captureStyle});
      for(const panel of await page.locator('[data-mapping-capture]').all())await panel.getByLabel('Occupancy grid',{exact:true}).check();
      await page.evaluate(()=>document.activeElement?.blur());
      await page.locator('#inspect').screenshot({path:join(output,label+'-grids.png'),style:captureStyle});
    }
    const savedViews = await page.locator('[data-mapping-capture]').evaluateAll(panels=>panels.map(p=>({
      selected:p.querySelector('input:checked').value,
      box:p.querySelector('svg').getAttribute('viewBox'),
      caption:p.querySelector('[data-view-caption]').textContent,
    })));
    const checkRestored = async destination => {
      await page.locator('fieldset').first().waitFor({state:'visible'});
      const restored = await page.locator('[data-mapping-capture]').evaluateAll(panels=>panels.map(p=>({
        selected:p.querySelector('input:checked').value,
        box:p.querySelector('svg').getAttribute('viewBox'),
        caption:p.querySelector('[data-view-caption]').textContent,
      })));
      check(JSON.stringify(restored)===JSON.stringify(savedViews),label+': Back from '+destination+' restores selection, crop and caption together');
    };
    await page.getByRole('link',{name:'Return to the mapping Field Note'}).click();
    check(new URL(page.url()).hash==='#bench-captures',label+': visual addendum route');
    check(await page.locator('#bench-captures').isVisible(),label+': addendum not reached');
    await page.locator('#bench-captures img').evaluateAll(images=>Promise.all(images.map(img=>img.decode())));
    check(await page.locator('#bench-captures img').count()===2,label+': addendum camera/map pair');
    check(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),label+': Field Note overflow');
    await accessibility(page,label+': Field Note');
    if(width===390)await page.locator('#bench-captures').screenshot({path:join(output,label+'-addendum.png'),style:captureStyle});
    await page.goBack();check(new URL(page.url()).pathname===route,label+': Back loses specimen');
    await checkRestored('Field Note');
    await page.locator('[data-mapping-capture]').first().getByRole('link',{name:'Open the full-resolution capture'}).click();
    await page.waitForURL('**/assets/specimens/buggy/world-local.webp');
    await page.goBack();await checkRestored('source image');
    results.push({label});await page.close();
  }
  // A missing source must not leave apparently usable controls over an empty plot.
  const broken=await browser.newPage({viewport:{width:390,height:844}});
  await broken.route('**/world-local.webp',r=>r.abort());
  await broken.goto(origin+route,{waitUntil:'networkidle'});
  const failed=broken.locator('[data-mapping-capture]').first();
  check(await failed.locator('fieldset').isHidden(),'failed image: dead controls hidden');
  check(await failed.locator('svg').isHidden(),'failed image: blank plot hidden');
  check((await failed.locator('[data-view-caption]').textContent()).includes('could not load'),'failed image: explicit retry explanation');
  check(await failed.getByRole('link',{name:'Open the full-resolution capture'}).isVisible(),'failed image: source retry link reachable');
  check(await broken.locator('[data-mapping-capture]').last().locator('fieldset').isVisible(),'failed image: other capture still usable');
  await accessibility(broken,'failed image');
  await broken.close();
  for(const mode of ['no-js','failed-module']) {
    const page=await browser.newPage({viewport:{width:390,height:844},javaScriptEnabled:mode!=='no-js'});
    if(mode==='failed-module')await page.route('**/assets/mapping-study.mjs',r=>r.abort());
    await page.goto(origin+route,{waitUntil:'networkidle'});
    for(const panel of await page.locator('[data-mapping-capture]').all()) {
      check(await panel.locator('fieldset').isHidden(),mode+': dead crop controls');
      check(await panel.locator('svg').getAttribute('viewBox')==='0 0 1920 967',mode+': full capture lost');
      check(await panel.getByRole('link',{name:'Open the full-resolution capture'}).isVisible(),mode+': source inaccessible');
    }
    await page.locator('.mapping-record summary').click();
    check((await page.locator('.mapping-record').innerText()).includes('capture times'),mode+': provenance hidden');
    check(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),mode+': overflow');
    await page.close();
  }
  const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
  await page.goto(origin,{waitUntil:'networkidle'});
  await page.locator('#specimen-kitronik').scrollIntoViewIfNeeded();
  const image=page.locator('#specimen-kitronik img');
  // A card can exceed the viewport, and content-visibility resolves its height on
  // arrival. Bring the lazy image itself into view before awaiting its pixels.
  await image.scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>{
    const img=document.querySelector('#specimen-kitronik img');
    return img.complete&&img.naturalWidth>0;
  },null,{timeout:10000});
  await image.evaluate(img=>img.decode());
  check(await image.evaluate(img=>img.naturalWidth>0&&img.currentSrc.includes('/camera-preview-')), 'workbench camera delivery preview missing');
  await page.getByRole('link',{name:'Inspect the Kitronik buggy camera and mapping captures'}).click();
  check(new URL(page.url()).pathname===route,'workbench study route');await page.close();
} finally {
  await browser.close();
  await writeFile(join(output,'mapping-summary.json'),JSON.stringify({checks,failures,results},null,2));
}
console.log(JSON.stringify({checks,failures,results},null,2));
if(failures.length)process.exitCode=1;
