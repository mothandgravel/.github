/** Capture the running specimen; no reconstructed numbers or composited UI. */
import {mkdir,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {launchAuditBrowser} from './audit_browser.mjs';
const origin=process.env.SITE_URL??'http://127.0.0.1:8794',out='artifacts/design-review/datacenter-film',publicOut='docs/assets/specimens/data-center';
await mkdir(out,{recursive:true});await mkdir(publicOut,{recursive:true});
const browser=await launchAuditBrowser(process.platform==='win32'?{args:['--use-angle=d3d11','--ignore-gpu-blocklist']}:{});
const sourceNotice=await (await import('node:fs/promises')).readFile('docs/assets/data-center/publisher-notice.txt','utf8');
const context=await browser.newContext({viewport:{width:1280,height:960},recordVideo:{dir:out,size:{width:1280,height:960}}});
const page=await context.newPage(),start=Date.now(),cues=[];let trim=0;
const cue=async(text,ms)=>{const from=(Date.now()-start)/1000-trim;await page.waitForTimeout(ms);cues.push({from,to:(Date.now()-start)/1000-trim,text});};
const scroll=selector=>page.locator(selector).evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));
try{
 await page.goto(`${origin}/specimens/data-center/`);await page.locator('#dc-load-data').click();await page.locator('#dc-workspace').waitFor({state:'visible'});
 await scroll('.dc-stage');await page.locator('#dc-start-room').evaluate(b=>b.click());await page.waitForFunction(()=>document.querySelector('#dc-room').dataset.rendered==='true',{},{timeout:120000});
 await page.addStyleTag({content:'.site-header{position:relative!important}.skip-link{visibility:hidden!important}html{scroll-behavior:auto!important}.dc-room{height:540px!important}'});await scroll('.dc-stage');await page.waitForTimeout(1500);trim=(Date.now()-start)/1000;
 await cue('Where the power goes. An authored room beside recorded ESIF facility power.',4000);
 await page.locator('[data-camera="overview"]').click();await scroll('.dc-stage');await cue('Constructed racks, working lights and water services. No per-rack readings are inferred.',4500);
 await page.locator('[data-camera="pump_kw"]').click();await scroll('.dc-stage');await cue('Approach the water loop. Its meter is a whole-facility category.',4500);
 await page.locator('[data-camera="aisle"]').click();await scroll('.dc-stage');await cue('The geometry is authored. The source clock and raw records stay separately inspectable.',3500);
 await page.locator('#dc-example').click();await scroll('.dc-comparison');await cue('Two recorded hours: period PUE falls while estimated mean facility power rises by 10.077%.',6000);
 await page.locator('#dc-run-rehearsal').click();await scroll('.dc-rehearsal');await cue('A separate supply scenario: grid cap, battery reserve, conversion loss and unmet energy.',5500);
 await context.close();const raw=await page.video().path();
 for(const [extension,codec]of [['mp4',['-c:v','libx264','-preset','slow','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart']],['webm',['-c:v','libvpx-vp9','-b:v','0','-crf','32','-row-mt','1','-cpu-used','3']]])execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-ss',String(trim),'-i',raw,'-an','-metadata','title=Where the power goes / recorded inspection','-metadata','artist=Moth & Gravel','-metadata',`comment=Recorded data: DOE/NREL/ALLIANCE; Clark & Strelka; DOI 10.7799/3015212. Authored room and supply assumptions: Moth & Gravel.\n${sourceNotice}`,...codec,`${publicOut}/recorded-account.${extension}`],{stdio:'inherit'});
 const timestamp=s=>{const ms=Math.max(0,Math.floor(s*1000));return `00:${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;};
 await writeFile(`${publicOut}/recorded-account.vtt`,'WEBVTT\n\n'+cues.map((c,i)=>`${i+1}\n${timestamp(c.from)} --> ${timestamp(c.to)}\n${c.text}\n`).join('\n'));
 await writeFile(`${out}/capture.json`,JSON.stringify({origin,viewport:{width:1280,height:960},recording:'Actual browser interactions; recorded facility power, authored geometry, separate counterfactual supply branch. No audio.',trim,cues},null,2)+'\n');
 console.log(`${publicOut}/recorded-account.mp4`);
}finally{await browser.close();}
