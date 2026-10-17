/** Reading planes, navigation sheet and material feedback; development only. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
const origin=process.env.SITE_URL||'http://127.0.0.1:8793';
const output=process.env.AUDIT_OUTPUT||'artifacts/design-review';
await mkdir(output,{recursive:true});
const browser=await launchAuditBrowser();
const failures=[],results=[];let checks=0;
const assert=(v,label)=>{checks++;if(!v)failures.push(label);};
const boxes=locator=>locator.evaluateAll(els=>els.map(el=>{const b=el.getBoundingClientRect();return[b.x+scrollX,b.y+scrollY,b.width,b.height];}));
const audit=async(page,label)=>{
  await page.addScriptTag({content:axe.source});
  const violations=await page.evaluate(async()=> {
    const scope=document.querySelector('#menu-toggle')?.getAttribute('aria-expanded')==='true'?document.querySelector('#primary-nav'):document;
    return (await axe.run(scope,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.html)}));
  });
  assert(!violations.length,label+': accessibility '+JSON.stringify(violations));
};
const opened=page=>page.waitForFunction(()=>document.querySelector('#menu-toggle').getAttribute('aria-expanded')==='true');
const closed=async(page,label)=>{
  await page.waitForFunction(()=>document.querySelector('#menu-toggle').getAttribute('aria-expanded')==='false',null,{timeout:2000}).catch(()=>{});
  assert(await page.locator('#menu-toggle').getAttribute('aria-expanded')==='false',label+': sheet stays open');
};
try{
  for(const width of [320,390,768,901,1024,1100,1101,1440])for(const theme of ['night','afterlight']){
    const label=`rooms-${width}-${theme}`;
    const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'no-preference'});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(t=>localStorage.setItem('moth-and-gravel-theme',t),theme);
    await page.goto(origin,{waitUntil:'networkidle'});
    const menu=page.locator('#menu-toggle'),nav=page.locator('#primary-nav');
    assert(await menu.isVisible(),label+': no desktop/mobile sheet control');
    assert(await nav.isVisible()===(width>1100),label+': compact navigation boundary');
    const before=await menu.boundingBox();await menu.click();await opened(page);
    await page.waitForTimeout(280);
    assert(await page.evaluate(()=>document.activeElement===document.querySelector('#primary-nav>a')),label+': opening focus does not reach first route');
    assert(await nav.evaluate(el=>{const b=el.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth&&b.bottom<=innerHeight;}),label+': sheet clips at viewport');
    const after=await menu.boundingBox();
    assert(['x','y','width','height'].every(key=>Math.abs(before[key]-after[key])<.02),label+': trigger moves on opening');
    assert(await nav.locator('.nav-sheet-heading').isVisible(),label+': no composed heading');
    assert(await nav.locator('.nav-sheet-invitation').getAttribute('href')===origin+'/questions/',label+': question route is wrong');
    if([390,1440].includes(width))await page.screenshot({path:join(output,label+'-menu.png')});
    if([320,390,1440].includes(width))await audit(page,label+' open');
    await page.keyboard.press('Escape');await closed(page,label+' Escape');
    assert(await menu.evaluate(el=>el===document.activeElement),label+': Escape focus not restored');
    await page.locator('#light-switch').focus();await page.keyboard.press('Escape');
    assert(await page.locator('#light-switch').evaluate(el=>el===document.activeElement),label+': closed Escape steals focus');
    await menu.click();await page.keyboard.press('Shift+Tab');await closed(page,label+' leave by keyboard');
    assert(await page.locator('.brand').evaluate(el=>el===document.activeElement),label+': backward keyboard exit is trapped');
    await menu.click();await page.locator('#primary-nav>a[href="#ethos"]').click();await closed(page,label+' room selection');
    assert(await page.evaluate(()=>document.activeElement.id==='ethos'),label+': room selection leaves hidden focus');
    await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));await menu.click();
    await page.evaluate(()=>dispatchEvent(new Event('blur')));await closed(page,label+' blur');
    await menu.click();await page.mouse.click(3,200);await closed(page,label+' outside');
    await menu.click();await page.setViewportSize({width:width+1,height:760});await closed(page,label+' resize');
    await page.setViewportSize({width,height:900});
    await page.locator('#field-notes').scrollIntoViewIfNeeded();
    assert(await page.locator('#field-notes').evaluate(el=>getComputedStyle(el).color==='rgb(32, 34, 34)'),label+': reading room not on paper');
    await page.locator('#work').scrollIntoViewIfNeeded();
    assert(await page.locator('#work').evaluate(el=>getComputedStyle(el).color==='rgb(241, 238, 230)'),label+': material room lost its contrast');
    assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),label+': horizontal overflow');
    if([390,1440].includes(width)){
      await page.locator('#field-notes').screenshot({path:join(output,label+'-reading.png'),style:'.site-header,.skip-link{visibility:hidden!important}'});
      await page.locator('#work').screenshot({path:join(output,label+'-specimens.png'),style:'.site-header,.skip-link{visibility:hidden!important}'});
      await audit(page,label+' rooms');
    }
    assert(!errors.length,label+': browser errors '+errors.join(';'));
    results.push({label});await page.close();
  }
  for(const route of ['/notes/','/notes/008-one-undo.html','/questions/','/workbench/']){
    const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
    await page.goto(origin+route,{waitUntil:'networkidle'});
    await page.locator('#menu-toggle').click();await opened(page);
    assert(await page.locator('.nav-sheet-invitation').getAttribute('href')===origin+'/questions/',route+': nested page resolves wrong invitation');
    assert(await page.locator('#primary-nav').evaluate(el=>el.getAnimations().length===0),route+': reduced sheet animates');
    await audit(page,route+' sheet');
    await page.keyboard.press('Escape');await closed(page,route);
    if(route==='/notes/'){
      await page.locator('#menu-toggle').click();await page.locator('.nav-sheet-invitation').click();
      assert(new URL(page.url()).pathname==='/questions/',route+': invitation does not navigate');
    }
    await page.close();
  }
  for(const option of ['pointer','reduced','touch','no-js','failed-script']){
    const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:option==='reduced'?'reduce':'no-preference',javaScriptEnabled:option!=='no-js',hasTouch:option==='touch',isMobile:option==='touch'});
    if(option==='failed-script')await page.route('**/assets/site.js',route=>route.abort());
    await page.goto(origin,{waitUntil:'networkidle'});
    if(['no-js','failed-script'].includes(option)){
      // A failed script must not leave the old has-js mobile navigation hidden.
      if(option==='failed-script')await page.setViewportSize({width:390,height:844});
      assert(await page.locator('#primary-nav').isVisible(),option+': native routes inaccessible');
      assert(!(await page.locator('#menu-toggle').isVisible()),option+': dead menu control');
      assert(!(await page.locator('#light-switch').isVisible()),option+': dead theme control');
      await page.close();continue;
    }
    const figure=page.locator('#specimen-skystack .work-specimen');await figure.scrollIntoViewIfNeeded();
    await page.locator('#specimen-skystack [data-depth-ready]').waitFor();await page.waitForTimeout(550);
    const card=page.locator('#specimen-skystack'),image=card.locator('img');
    const targets=card.locator('h3,figcaption,summary,.work-card-link');
    const before=await boxes(targets);
    const bounds=await image.boundingBox();
    await image.hover();await page.waitForTimeout(300);
    const after=await boxes(targets);
    assert(JSON.stringify(before)===JSON.stringify(after),option+': material feedback moves reading/controls');
    const transform=await image.evaluate(el=>getComputedStyle(el).transform);
    assert(option==='pointer'?transform!=='none':transform==='none',option+': incorrect image motion');
    if(option==='pointer'){
      assert((await image.boundingBox()).width>bounds.width,option+': no small image response');
      await page.mouse.move(0,0);await card.locator('summary').focus();await page.waitForTimeout(300);
      assert(await image.evaluate(el=>getComputedStyle(el).transform==='none'||getComputedStyle(el).transform==='matrix(1, 0, 0, 1, 0, 0)'),option+': keyboard image moves');
      const marker=await card.locator('.work-card-top span').first().evaluate(el=>getComputedStyle(el,'::before').backgroundColor);
      assert(marker!=='rgba(0, 0, 0, 0)',option+': no keyboard index response');
    }
    await page.close();
  }
}finally{await browser.close();}
await writeFile(join(output,'rooms-audit.json'),JSON.stringify({checks,results,failures},null,2));
console.log(JSON.stringify({checks,results,failures},null,2));if(failures.length)process.exitCode=1;
