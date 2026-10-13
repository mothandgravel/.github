/** Actual 3D render/failure review. SwiftShader is a CI renderer, not hardware evidence. */
import { chromium } from 'playwright';
import { mkdir,writeFile } from 'node:fs/promises';
import { join } from 'node:path';
const origin=process.env.SITE_URL||'http://127.0.0.1:8793';
const output=process.env.AUDIT_OUTPUT||'artifacts/design-review';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const failures=[],results=[];let checks=0;
const assert=(value,message)=>{checks++;if(!value)failures.push(message);};
const ready=async page=>{
  await page.locator('#moth-interlude').scrollIntoViewIfNeeded();
  await page.locator('[data-moth-ready]').waitFor();
};
const state=(page,value)=>page.waitForFunction(v=>document.querySelector('#moth-interlude').dataset.mothState===v,value);
const phase=(page,value)=>page.waitForFunction(v=>document.querySelector('#moth-interlude').dataset.mothPhase===v,value);
const pixels=page=>page.locator('.moth-volume').evaluate(canvas=>{
  const gl=canvas.getContext('webgl'),data=new Uint8Array(canvas.width*canvas.height*4);
  gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,data);
  let occupied=0,checksum=0;for(let i=0;i<data.length;i+=4)if(data[i+3]){occupied++;checksum=(checksum+data[i]*(i+1)+data[i+1])%2147483647;}
  return {occupied,checksum,error:gl.getError(),width:canvas.width,height:canvas.height};
});
try {
  for(const width of [320,390,768,901,1024,1440])for(const theme of ['night','afterlight']){
    const label=`volume-${width}-${theme}`;
    const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'no-preference'});
    const requested=[],errors=[];page.on('request',r=>requested.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(theme=>{
      localStorage.setItem('moth-and-gravel-theme',theme);window.volumeDraws=0;
      const draw=WebGLRenderingContext.prototype.drawArrays;
      WebGLRenderingContext.prototype.drawArrays=function(...args){window.volumeDraws++;return draw.apply(this,args);};
    },theme);
    await page.goto(origin,{waitUntil:'networkidle'});
    assert(!requested.some(u=>/moth-(webgl|mesh|model)/.test(u)),label+': 3D fetched during opening');
    await ready(page);assert(await page.locator('#moth-interlude').getAttribute('data-moth-renderer')==='webgl',label+': not an actual 3D performance');
    await phase(page,'travel');await page.locator('[data-moth-pause]').click();await state(page,'paused');
    const first=await pixels(page),draws=await page.evaluate(()=>window.volumeDraws);
    assert(first.occupied>100&&first.error===0,label+': empty/invalid GPU output');
    assert(first.width<=216&&first.height<=124,label+': canvas budget exceeded');
    await page.waitForTimeout(150);assert(JSON.stringify(first)===JSON.stringify(await pixels(page)),label+': paused pixels changed');
    assert(draws===await page.evaluate(()=>window.volumeDraws),label+': pause keeps rendering');
    if([390,1440].includes(width))await page.locator('#moth-interlude').screenshot({path:join(output,label+'-flight.png'),style:'.site-header{visibility:hidden!important}'});
    await page.locator('[data-moth-pause]').click();await phase(page,'settle');await page.waitForTimeout(200);
    const settlingDraws=await page.evaluate(()=>window.volumeDraws);
    await page.waitForTimeout(100);
    assert(settlingDraws===await page.evaluate(()=>window.volumeDraws),label+': still perch keeps drawing');
    await page.locator('[data-moth-pause]').click();const landed=await pixels(page);
    assert(first.checksum!==landed.checksum,label+': articulated pose did not change pixels');
    const contact=await page.locator('.moth-volume').evaluate(canvas=>{
      const gl=canvas.getContext('webgl'),data=new Uint8Array(canvas.width*canvas.height*4);
      gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,data);
      const node=canvas.parentElement,stage=document.querySelector('.moth-stage').getBoundingClientRect(),perch=document.querySelector('.moth-perch').getBoundingClientRect();
      const m=new DOMMatrix(getComputedStyle(node).transform),w=node.clientWidth,h=node.clientHeight;
      let distance=Infinity;
      for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++)if(data[(y*canvas.width+x)*4+3]>100){
        const px=(x+.5)*w/canvas.width-w/2,py=(canvas.height-y-.5)*h/canvas.height-h/2;
        const wx=stage.left+w/2+m.a*px+m.c*py+m.e,wy=stage.top+h/2+m.b*px+m.d*py+m.f;
        if(wx>=perch.left&&wx<=perch.right)distance=Math.min(distance,Math.abs(wy-perch.top));
      }
      return distance;
    });
    assert(contact<=3,label+': sculpture floats above the perch '+contact);
    if([390,1440].includes(width))await page.locator('#moth-interlude').screenshot({path:join(output,label+'-settle.png'),style:'.site-header{visibility:hidden!important}'});
    await page.locator('[data-moth-pause]').click();await state(page,'idle');const done=await page.evaluate(()=>window.volumeDraws);
    await page.waitForTimeout(100);assert(done===await page.evaluate(()=>window.volumeDraws),label+': idle GPU clock');
    assert(errors.length===0,label+': browser errors '+errors.join(';'));
    results.push({label,flight:first,settle:landed,contact});await page.close();
  }

  const page=await browser.newPage({viewport:{width:1440,height:900}});
  await page.goto(origin,{waitUntil:'networkidle'});await ready(page);await state(page,'playing');
  await page.locator('.moth-volume').evaluate(canvas=>canvas.getContext('webgl').getExtension('WEBGL_lose_context').loseContext());
  await state(page,'idle');assert(await page.locator('#moth-interlude').getAttribute('data-moth-renderer')==='svg','Actual context loss did not return to source rig');
  assert(await page.locator('.moth-source img').isVisible(),'Context loss lost resting mark');
  await page.locator('[data-moth-play]').click();await state(page,'playing');
  assert(await page.locator('.moth-traveller svg').isVisible(),'Context loss cannot replay fallback');
  await page.locator('[data-moth-finish]').click();await page.close();

  for(const fault of ['moth-webgl.mjs','moth-mesh.mjs','moth-model.json','bad-model','bad-pivot','no-webgl','shader','upload','framebuffer']){
    const fallback=await browser.newPage({viewport:{width:390,height:900}});
    const errors=[];fallback.on('pageerror',e=>errors.push(e.message));
    if(fault==='bad-model')await fallback.route('**/moth-model.json',r=>r.fulfill({body:'{}',contentType:'application/json'}));
    else if(fault==='bad-pivot')await fallback.route('**/moth-model.json',async r=>{
      const response=await r.fetch(),model=await response.json();model.wings[0].pivot[0]='broken';
      await r.fulfill({body:JSON.stringify(model),contentType:'application/json'});
    });
    else if(fault==='no-webgl')await fallback.addInitScript(()=>{
      const original=HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl'?null:original.call(this,type,...args);};
    });
    else if(fault==='shader')await fallback.addInitScript(()=>{
      const original=WebGLRenderingContext.prototype.getShaderParameter;
      WebGLRenderingContext.prototype.getShaderParameter=function(shader,p){return p===this.COMPILE_STATUS?false:original.call(this,shader,p);};
    });
    else if(fault==='upload'||fault==='framebuffer')await fallback.addInitScript(fault=>{
      const getError=WebGLRenderingContext.prototype.getError;
      WebGLRenderingContext.prototype.getError=function(){const error=window.injectedGPUError;if(error){window.injectedGPUError=0;return error;}return getError.call(this);};
      if(fault==='upload')WebGLRenderingContext.prototype.bufferData=function(){window.injectedGPUError=this.OUT_OF_MEMORY;};
      else {const draw=WebGLRenderingContext.prototype.drawArrays;WebGLRenderingContext.prototype.drawArrays=function(...args){window.injectedGPUError=this.INVALID_FRAMEBUFFER_OPERATION;return draw.apply(this,args);};}
    },fault);
    else await fallback.route('**/'+fault,r=>r.abort());
    await fallback.goto(origin,{waitUntil:'networkidle'});await ready(fallback);
    if(fault==='framebuffer'){await state(fallback,'idle');await fallback.locator('[data-moth-play]').click();}
    await state(fallback,'playing');
    assert(await fallback.locator('#moth-interlude').getAttribute('data-moth-renderer')==='svg',fault+': failed enhancement strands scene');
    assert(await fallback.locator('.moth-traveller svg').isVisible(),fault+': source flight not visible');
    assert(await fallback.locator('.moth-volume').count()===0,fault+': leaked partial GPU surface');
    assert(errors.length===0,fault+': unhandled error '+errors.join(';'));
    await fallback.locator('.moth-question a').click();assert(fallback.url().endsWith('/questions/'),fault+': question route lost');
    await fallback.close();
  }
  const reduced=await browser.newPage({viewport:{width:390,height:900},reducedMotion:'reduce'}),requests=[];
  reduced.on('request',r=>requests.push(r.url()));await reduced.goto(origin,{waitUntil:'networkidle'});await ready(reduced);
  assert(!requests.some(u=>/moth-(webgl|mesh|model)/.test(u)),'Reduced entry fetched 3D resources');
  assert(await reduced.locator('.moth-volume').count()===0,'Reduced entry allocated GPU surface');await reduced.close();

  for(const resource of ['moth-webgl.mjs','moth-model.json']){
    const delayed=await browser.newPage({viewport:{width:390,height:900}}),errors=[];
    delayed.on('pageerror',e=>errors.push(e.message));let release;
    const hold=new Promise(r=>release=r);
    await delayed.route('**/'+resource,async r=>{await hold;await r.continue().catch(()=>{});});
    await delayed.goto(origin,{waitUntil:'networkidle'});await ready(delayed);await state(delayed,'playing');
    assert(await delayed.locator('#moth-interlude').getAttribute('data-moth-renderer')==='svg',resource+': stalled setup blocks fallback');
    await delayed.locator('[data-moth-finish]').click();release();await delayed.waitForTimeout(350);
    assert(await delayed.locator('.moth-volume').count()===0,resource+': late setup leaks a GPU surface');
    assert(await delayed.locator('#moth-interlude').getAttribute('data-moth-state')==='idle',resource+': late setup restarts flight');
    assert(errors.length===0,resource+': late promise rejection');await delayed.close();
  }
  for(const event of ['blur','pagehide','Escape','reduced']){
    const cancelled=await browser.newPage({viewport:{width:390,height:900}});let release,requested;
    const hold=new Promise(r=>release=r),hit=new Promise(r=>requested=r);
    await cancelled.route('**/moth-model.json',async r=>{requested();await hold;await r.continue().catch(()=>{});});
    await cancelled.goto(origin,{waitUntil:'networkidle'});await cancelled.locator('#moth-interlude').scrollIntoViewIfNeeded();await hit;
    if(event==='Escape')await cancelled.keyboard.press('Escape');
    else if(event==='reduced')await cancelled.emulateMedia({reducedMotion:'reduce'});
    else await cancelled.evaluate(name=>dispatchEvent(new Event(name)),event);
    await cancelled.locator('[data-moth-ready]').waitFor();await cancelled.waitForTimeout(100);
    assert(await cancelled.locator('#moth-interlude').getAttribute('data-moth-state')==='idle',event+': interrupted setup autoplays late');
    assert(await cancelled.locator('.moth-volume').count()===0,event+': cancelled setup allocated a canvas');
    release();await cancelled.waitForTimeout(100);
    assert(await cancelled.locator('#moth-interlude').getAttribute('data-moth-state')==='idle',event+': late response restarts flight');
    if(event==='reduced')await cancelled.emulateMedia({reducedMotion:'no-preference'});
    await cancelled.locator('[data-moth-play]').click();await state(cancelled,'playing');
    assert(await cancelled.locator('.moth-traveller svg').isVisible(),event+': explicit fallback replay unavailable');
    await cancelled.close();
  }
  const early=await browser.newPage({viewport:{width:390,height:900}});let releaseRig,rigRequested;
  const holdRig=new Promise(r=>releaseRig=r),rigHit=new Promise(r=>rigRequested=r);
  await early.route('**/moth-rig.svg',async r=>{rigRequested();await holdRig;await r.continue().catch(()=>{});});
  await early.goto(origin,{waitUntil:'networkidle'});await early.locator('#moth-interlude').scrollIntoViewIfNeeded();await rigHit;
  await early.evaluate(()=>dispatchEvent(new Event('blur')));releaseRig();
  await early.locator('[data-moth-ready]').waitFor();await early.waitForTimeout(100);
  assert(await early.locator('#moth-interlude').getAttribute('data-moth-state')==='idle','Core rig delay loses early interruption');
  await early.locator('[data-moth-play]').click();await state(early,'playing');
  assert(await early.locator('[data-moth-finish]').isEnabled(),'Early interruption loses explicit replay');await early.close();
  for(const dpr of [1.25,2,3]){
    const scaled=await browser.newPage({viewport:{width:390,height:900},deviceScaleFactor:dpr});
    await scaled.goto(origin,{waitUntil:'networkidle'});await ready(scaled);await phase(scaled,'travel');await scaled.locator('[data-moth-pause]').click();
    const sample=await pixels(scaled);
    assert(sample.occupied>100&&sample.error===0,'DPR '+dpr+': missing GPU pixels');
    assert(sample.width<=216&&sample.height<=124,'DPR '+dpr+': GPU buffer exceeds cap');
    await scaled.close();
  }

  const proof=await browser.newPage({viewport:{width:800,height:600}});await proof.goto(origin,{waitUntil:'networkidle'});
  const envelope=await proof.evaluate(async()=>{
    const {createMothRenderer}=await import('/assets/moth-webgl.mjs'),{sampleScene}=await import('/assets/moth-choreography.mjs');
    const box=document.createElement('div');document.body.append(box);const r=await createMothRenderer(box,()=>{});
    const layout={width:800,height:430,source:{x:150,y:170,size:108},perch:{x:420,y:300,size:68}};
    let clipped=0,empty=0;const gl=r.canvas.getContext('webgl');
    for(let t=0;t<=4800;t+=16){
      r.render(sampleScene(t,layout),t,108);const w=r.canvas.width,h=r.canvas.height,data=new Uint8Array(w*h*4);
      gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,data);let occupied=0,edge=false;
      for(let y=0;y<h;y++)for(let x=0;x<w;x++)if(data[(y*w+x)*4+3]){occupied++;if(x===0||y===0||x===w-1||y===h-1)edge=true;}
      if(edge)clipped++;if(!occupied)empty++;
    }
    const checksum=()=>{const data=new Uint8Array(r.canvas.width*r.canvas.height*4);gl.readPixels(0,0,r.canvas.width,r.canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,data);return data.reduce((sum,v,i)=>(sum+v*(i+1))%2147483647,0);};
    r.render(sampleScene(3250,layout),3250,108);const before=checksum();
    r.render(sampleScene(3335,layout),3335,108);const adjustment=checksum()!==before;
    const result={clipped,empty,triangles:r.triangles,adjustment};r.dispose();box.remove();return result;
  });
  assert(envelope.clipped===0,'Actual 3D mesh clips its drawing surface: '+envelope.clipped);
  assert(envelope.empty===0,'Actual 3D performance has blank poses');
  assert(envelope.triangles<5000,'GPU triangle budget exceeded');results.push({envelope});await proof.close();
  assert(envelope.adjustment,'Body/antenna settlement is absent from actual volume pixels');
} finally {await browser.close();}
await writeFile(join(output,'moth-volume-audit.json'),JSON.stringify({checks,results,failures},null,2));
console.log(JSON.stringify({checks,results,failures},null,2));if(failures.length)process.exitCode=1;
