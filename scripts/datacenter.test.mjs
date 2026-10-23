import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {COMPONENTS,clockUs,prepareDataset,integrate,hourAccount,precedingWeather,capacityRehearsal,comparison,exportInspection} from '../docs/assets/datacenter-model.mjs';
const payload=JSON.parse(await readFile('docs/assets/data-center/esif-week.json','utf8')),data=prepareDataset(payload);
const approx=(a,b,tol=1e-8)=>assert.ok(Math.abs(a-b)<=tol,`${a} != ${b}`);
const record=(seconds,kw=100,overrides={})=>({us:seconds*1e6,sourceClock:'test',validPower:true,it_power_kw:kw,cooling_kw:10,pump_kw:5,hvac_kw:4,plug_and_light_kw:1,totalKW:kw+20,...overrides});
test('published captures bind their actual room source and retain their checked image and media bytes',async()=>{
 const receipt=JSON.parse(await readFile('docs/assets/specimens/data-center/capture.json','utf8'));
 assert.equal(receipt.still.sourceSHA256,createHash('sha256').update((await readFile('docs/assets/datacenter-room.mjs','utf8')).replaceAll('\r\n','\n')).digest('hex'));
 assert.equal(receipt.still.renderer.contextLost,false);assert.equal(receipt.still.renderer.samples,128);assert.ok(receipt.still.imageCheck.mean>8);assert.ok(receipt.still.imageCheck.variance>100);
 for(const file of receipt.files){let bytes=await readFile(`docs/${file.file}`);if(file.canonicalLF)bytes=Buffer.from(bytes.toString('utf8').replaceAll('\r\n','\n'));assert.equal(bytes.length,file.bytes);assert.equal(createHash('sha256').update(bytes).digest('hex'),file.sha256);}
});
test('published extract, renderer and material assets match their provenance hashes',async()=>{
 const manifest=JSON.parse(await readFile('docs/design/datacenter-provenance.json','utf8'));
 const text=(await readFile(`docs/${manifest.file}`,'utf8')).replaceAll('\r\n','\n');assert.equal(createHash('sha256').update(text).digest('hex'),manifest.sha256);
 const engine=JSON.parse(await readFile('docs/assets/data-center/engine.json','utf8'));
 assert.equal(createHash('sha256').update((await readFile('docs/assets/datacenter-engine.mjs','utf8')).replaceAll('\r\n','\n')).digest('hex'),engine.sha256);
 const tracer=JSON.parse(await readFile('docs/assets/data-center/pathtracer.json','utf8'));assert.equal(createHash('sha256').update((await readFile('docs/assets/datacenter-pathtracer.mjs','utf8')).replaceAll('\r\n','\n')).digest('hex'),tracer.sha256);
 for(const asset of JSON.parse(await readFile('docs/assets/data-center/materials.json','utf8')))assert.equal(createHash('sha256').update(await readFile(`docs/assets/data-center/${asset.file}`)).digest('hex'),asset.sha256);
});
test('source-clock arithmetic preserves microseconds and rejects invalid calendars without local timezone conversion',()=>{
 assert.equal(clockUs('2025-07-14T00:00:00.000001')-clockUs('2025-07-14T00:00:00'),1);
 assert.equal(clockUs('2024-03-31T03:00:00')-clockUs('2024-03-31T02:00:00'),3600e6);
 for(const s of ['2025-02-29T00:00:00','2025-07-14T24:00:00','2025-07-14T00:00:60','2025-07-14T00:00:00Z','2025-07-14T00:00:00+03:00'])assert.throws(()=>clockUs(s));
});
test('selected week contains 10080 raw records and two distinct boundary observations',()=>{
 assert.equal(data.window.length,10080);assert.equal(data.records.length,10082);assert.ok(data.records[0].us<data.start);assert.ok(data.records.at(-1).us>data.end);
 assert.equal(data.payload.source.inputSha256['power.parquet'],'19cd12405dde9144b1a360e8c8418666c399a3d0d15a7f846880d71ab22f9dd4');
});
test('one hour of constant demand uses physical kW-to-kWh units and shared coverage',()=>{
 const records=Array.from({length:61},(_,i)=>record(i*60));const r=integrate(records,0,3600e6);
 approx(r.ITKWh,100);approx(r.totalKWh,120);approx(r.PUE,1.2);assert.equal(r.coveredSeconds,3600);
});
test('clipped linear segments are integrated exactly at non-sample boundaries',()=>{
 const r=integrate([record(0,0),record(60,120)],15e6,45e6);
 approx(r.ITKWh,60*30/3600);approx(r.totalKWh,80*30/3600);assert.equal(r.coveredSeconds,30);
});
test('long gaps, missing components and negative components leave uncovered time instead of zeros',()=>{
 for(const records of [[record(0),record(91)],[record(0),record(60,100,{validPower:false,cooling_kw:null})],[record(0),record(60,100,{validPower:false,pump_kw:-1})]]){
  const r=integrate(records,0,60e6);assert.equal(r.coveredSeconds,0);assert.equal(r.uncoveredSeconds,60);assert.equal(r.PUE,null);
 }
 const r=integrate([record(60),record(120)],0,180e6);assert.equal(r.coveredSeconds,60);assert.equal(r.uncoveredSeconds,120);
});
test('period PUE is ratio of energy integrals, not mean of instantaneous ratios',()=>{
 const records=[record(0,10),record(60,100)];const r=integrate(records,0,60e6);
 approx(r.PUE,75/55);assert.notEqual(r.PUE,((30/10)+(120/100))/2);
});
test('JavaScript agrees with independent 50-digit Decimal boundary-insertion references',async()=>{
 const reference=JSON.parse(await readFile('docs/assets/data-center/numerical-reference.json','utf8'));
 assert.equal(reference.licenseNotice,payload.licenseNotice);
 for(const ref of reference.accounts){const r=integrate(data.records,clockUs(ref.start),clockUs(ref.end));
  approx(r.totalKWh,Number(ref.totalKWh),1e-8);approx(r.PUE,Number(ref.periodPUE),1e-11);
  for(const c of COMPONENTS)approx(r.energy[c.id],Number(ref.componentKWh[c.id]),1e-8);
 }
});
test('all 168 hour intervals cover exactly an hour and add back to the week',()=>{
 let sum=0;
 for(let start=data.start;start<data.end;start+=3600e6){const r=integrate(data.records,start,start+3600e6);assert.equal(r.coveredSeconds,3600);assert.equal(r.uncoveredSeconds,0);sum+=r.totalKWh;}
 const week=integrate(data.records,data.start,data.end);assert.equal(week.coveredSeconds,604800);approx(week.totalKWh,sum,1e-6);
});
test('the published contrast uses two measured hours and holds after correct integration',()=>{
 const c=comparison(data,'2025-07-14T23','2025-07-18T09');assert.ok(c.right.PUE<c.left.PUE);assert.ok(c.right.meanKW>c.left.meanKW);
 approx(c.powerChangePercent,10.076968752741934,1e-9);assert.equal(c.left.samples,60);assert.equal(c.right.samples,60);
 approx(c.left.PUE,1.0630146191221814,1e-12);approx(c.right.PUE,1.0529365881972028,1e-12);
});
test('weather selection uses earlier-only readings, rejects old values, and converts F to C',()=>{
 const d={weather:[{us:0,tempF:32,humidity:50},{us:60e6,tempF:68,humidity:55}]};
 approx(precedingWeather(d,30e6).tempC,0);assert.equal(precedingWeather(d,30e6).ageSeconds,30);approx(precedingWeather(d,60e6).tempC,20);
 assert.equal(precedingWeather(d,151e6),null);assert.equal(precedingWeather(d,-1),null);
});
test('recovery arithmetic conserves energy, respects reserve and reports shortfall',()=>{
 const h=hourAccount(data,'2025-07-18T09'),r=capacityRehearsal(data.records,h.start,h.end);
 approx(r.gridKWh+r.deliveredKWh+r.unmetKWh,r.baseline.totalKWh,1e-7);
 approx(500*.8-r.storedKWh,r.deliveredKWh+r.lossKWh,1e-8);approx(r.storedKWh,50);approx(r.deliveredKWh,322,1e-7);assert.ok(r.unmetKWh>130);
 const capped=capacityRehearsal(data.records,h.start,h.end,{gridKW:0,outputKW:10,batteryKWh:1000});assert.ok(capped.deliveredKWh<=10+1e-8);
 const covered=capacityRehearsal(data.records,h.start,h.end,{gridKW:4000});approx(covered.deliveredKWh,0);approx(covered.unmetKWh,0);approx(covered.storedKWh,400);
});
test('input notice, column order, nonfinite values and replay ordering are checked',()=>{
 assert.throws(()=>prepareDataset({...payload,licenseNotice:''}));assert.throws(()=>prepareDataset({...payload,columns:[...payload.columns].reverse()}));
 const bad=structuredClone(payload);bad.rows[1][2]=NaN;assert.throws(()=>prepareDataset(bad));
 const reversed=structuredClone(payload);[reversed.rows[1],reversed.rows[2]]=[reversed.rows[2],reversed.rows[1]];assert.throws(()=>prepareDataset(reversed));
 assert.throws(()=>capacityRehearsal(data.records,data.start,data.start+3600e6,{efficiency:1.1}));
});
test('export retains raw source fields, full notice, method and hypothetical status',()=>{
 const before=JSON.stringify(data.window[0]),h=hourAccount(data,'2025-07-18T09'),rehearsal=capacityRehearsal(data.records,h.start,h.end);
 const out=exportInspection(data,0,'2025-07-14T23','2025-07-18T09',rehearsal);
 assert.equal(out.signed,false);assert.equal(out.licenseNotice,payload.licenseNotice);assert.match(out.rehearsal.kind,/counterfactual/);assert.equal(out.record.sourceRow,payload.rows[1][0]);assert.equal(JSON.stringify(data.window[0]),before);
 assert.equal(out.interpretation.time,'source clock; timezone unspecified');assert.throws(()=>exportInspection(data,-1,'2025-07-14T23','2025-07-18T09'));
});
