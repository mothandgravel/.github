import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {prepareFinnishAccount,bandFor,householdAccount,gridAccount,heatAccount,finnishInspection,priceExposure,householdHeatRoute,householdComparison} from '../docs/assets/datacenter-finland-model.mjs';
const text=readFileSync(new URL('../docs/assets/data-center/finland.json',import.meta.url),'utf8').replaceAll('\r\n','\n'),data=JSON.parse(text),manifest=JSON.parse(readFileSync(new URL('../docs/design/finland-provenance.json',import.meta.url),'utf8'));
const homeSettings=()=>({changeCentsIncludingVAT:1,apartment:{annualKWh:3000,exposedPercent:100},electricHome:{annualKWh:20000,exposedPercent:100},heat:{connection:'connected',tariff:'unreported',allocatedHeatMWh:null,reductionEURPerMWh:null,passedThroughPercent:null}});
const close=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-9,`${actual} != ${expected}`);

test('one VAT-inclusive cent reaches each chosen annual electricity use exactly once',()=>{
 const a=householdComparison(data,'2026M06',homeSettings());
 close(a.apartment.electricity.baseline.annualEUR.total,711.21);
 close(a.electricHome.electricity.baseline.annualEUR.total,2978.40);
 assert.equal(a.apartment.electricity.deltaEUR.total,30);assert.equal(a.electricHome.electricity.deltaEUR.total,200);
 close(a.apartment.electricity.afterEUR.total,741.21);close(a.electricHome.electricity.afterEUR.total,3178.40);
 close(a.apartment.electricity.deltaEUR.energy,23.90438247011952);close(a.apartment.electricity.deltaEUR.tax,6.09561752988048);
 assert.equal(a.apartment.electricity.deltaEUR.network,0);assert.equal(a.apartment.electricity.baseline.band,'C');assert.equal(a.electricHome.electricity.baseline.band,'E');
});
test('source-month VAT convention changes the split, never the gross shock',()=>{
 const profile={annualKWh:3000,exposedPercent:100};
 for(const month of ['2024M01','2024M08','2024M09','2026M06']){
  const a=priceExposure(data,month,profile,1);assert.equal(a.deltaEUR.total,30);
  assert.equal(a.vatRate,month<'2024M09'?.24:.255);close(a.deltaEUR.energy+a.deltaEUR.tax,30);
  close(a.afterEUR.total-a.baseline.annualEUR.total,30);
 }
 close(priceExposure(data,'2024M01',profile,1).deltaEUR.energy,24.193548387096776);
});
test('only exposed kWh change; the source band still uses full annual use',()=>{
 const a=priceExposure(data,'2026M06',{annualKWh:20000,exposedPercent:25},2);
 assert.equal(a.baseline.band,'E');assert.equal(a.exposedKWh,5000);assert.equal(a.deltaEUR.total,100);
 const fixed=priceExposure(data,'2026M06',{annualKWh:20000,exposedPercent:0},10);
 assert.deepEqual(fixed.afterEUR,fixed.baseline.annualEUR);assert.equal(fixed.deltaEUR.total,0);
});
test('reductions and zero use remain valid; all source component residuals are retained',()=>{
 assert.equal(priceExposure(data,'2024M01',{annualKWh:3000,exposedPercent:100},-1).deltaEUR.total,-30);
 assert.equal(priceExposure(data,'2024M01',{annualKWh:0,exposedPercent:100},1).afterEUR.total,0);
 for(const row of data.prices.rows){const use={A:750,B:2000,C:3000,D:10000,E:20000}[row.band];
  const a=priceExposure(data,row.month,{annualKWh:use,exposedPercent:75},-3);
  close(a.afterEUR.total-a.afterEUR.energy-a.afterEUR.network-a.afterEUR.tax,a.baseline.roundingEUR);
 }
});
test('invalid input and missing source components cannot produce a household branch',()=>{
 for(const [annualKWh,exposedPercent,change]of [[NaN,100,1],[Infinity,100,1],[-1,100,1],[60001,100,1],[3000,-1,1],[3000,101,1],[3000,NaN,1],[3000,100,Infinity],[3000,100,-4],[3000,100,11]])assert.throws(()=>priceExposure(data,'2026M06',{annualKWh,exposedPercent},change));
 const d=structuredClone(data);d.prices.rows.find(r=>r.month==='2026M06'&&r.band==='C').tax=null;
 assert.throws(()=>priceExposure(d,'2026M06',{annualKWh:3000,exposedPercent:100},1),/unavailable/);
});
test('a connected building with no reported tariff effect keeps benefits unknown',()=>{
 const a=householdComparison(data,'2026M06',homeSettings());
 assert.equal(a.apartment.heat.status,'tariff-unreported');assert.equal(a.apartment.heat.householdReductionEUR,null);assert.equal(a.apartment.combinedChangeEUR,null);
 assert.equal(a.electricHome.heat.status,'no-direct-route');assert.equal(a.electricHome.heat.householdReductionEUR,0);assert.equal(a.electricHome.combinedChangeEUR,200);
 assert.equal(a.recordedHeatContext.residentialUseGWh,16);assert.equal(a.recordedHeatContext.source.cell,'R138');assert.equal(a.recordedHeatContext.recoveredHeatDeliveredToHomesGWh,null);
});
test('a chosen lower heat charge follows the thermal allocation and pass-through, not electricity',()=>{
 const settings=homeSettings();settings.heat={connection:'connected',tariff:'assumed',allocatedHeatMWh:7.5,reductionEURPerMWh:10,passedThroughPercent:50};
 const a=householdComparison(data,'2026M06',settings);
 assert.equal(a.apartment.heat.allocatedEnergyChargeReductionEUR,75);assert.equal(a.apartment.heat.householdReductionEUR,37.5);assert.equal(a.apartment.combinedChangeEUR,-7.5);
 assert.equal(a.apartment.electricity.deltaEUR.total,30);close(a.apartment.electricity.afterEUR.total,741.21);
 assert.equal(a.electricHome.heat.householdReductionEUR,0);assert.equal(a.electricHome.combinedChangeEUR,200);
 assert.equal(a.apartment.heat.attributedToRecoveredHeatEUR,null);assert.equal(a.apartment.heat.measuredHouseholdSavingEUR,null);
});
test('unknown connections, no connection and assumed no change have distinct meanings',()=>{
 const base={tariff:'assumed',allocatedHeatMWh:7.5,reductionEURPerMWh:10,passedThroughPercent:100};
 const unknown=householdHeatRoute({...base,connection:'unknown'});assert.equal(unknown.householdReductionEUR,null);assert.equal(unknown.status,'connection-unknown');
 const outside=householdHeatRoute({...base,connection:'not-connected'});assert.equal(outside.householdReductionEUR,0);assert.equal(outside.status,'no-direct-route');
 const unchanged=householdHeatRoute({...base,connection:'connected',tariff:'unchanged'});assert.equal(unchanged.householdReductionEUR,0);assert.equal(unchanged.status,'assumed-no-change');
 const retained=householdHeatRoute({...base,connection:'connected',passedThroughPercent:0});assert.equal(retained.allocatedEnergyChargeReductionEUR,75);assert.equal(retained.householdReductionEUR,0);
});
test('heat sensitivity rejects invalid assumptions and cannot claim causal measured savings',()=>{
 const base={connection:'connected',tariff:'assumed',allocatedHeatMWh:7.5,reductionEURPerMWh:10,passedThroughPercent:100};
 for(const patch of [{connection:'nearby'},{tariff:'reported'},{allocatedHeatMWh:null},{allocatedHeatMWh:Infinity},{allocatedHeatMWh:-1},{allocatedHeatMWh:51},{reductionEURPerMWh:101},{passedThroughPercent:101},{passedThroughPercent:NaN}])assert.throws(()=>householdHeatRoute({...base,...patch}));
 for(const connection of ['connected','not-connected','unknown'])for(const tariff of ['unreported','unchanged','assumed']){const a=householdHeatRoute({...base,connection,tariff});assert.equal(a.attributedToRecoveredHeatEUR,null);assert.equal(a.measuredHouseholdSavingEUR,null);}
});
test('the household export preserves null unknowns, source indices and every active choice without rewriting observations',()=>{
 const before=JSON.stringify(data),settings=homeSettings();settings.apartment.exposedPercent=50;
 const a=finnishInspection(data,{month:'2026M06',annualKWh:20000,windowId:'winter',index:112,additionalMW:100,heatYear:2025,comparison:settings},manifest.sha256,manifest);
 assert.equal(a.schema,'moth-gravel/finland-inspection@2');assert.equal(a.householdComparison.apartment.electricity.deltaEUR.total,15);
 assert.deepEqual(a.householdComparison.assumptions,settings);assert.equal(a.householdComparison.apartment.combinedChangeEUR,null);
 assert.deepEqual(a.householdComparison.apartment.electricity.baseline.source.valueIndices,[582,587,592,597]);
 assert.equal(a.heat.residentialUseGWh,null);assert.equal(a.grid.branch.priceEffect,null);assert.equal(JSON.stringify(data),before);
 a.householdComparison.assumptions.apartment.annualKWh=1;assert.equal(settings.apartment.annualKWh,3000);
});

test('published Finnish extract matches its fingerprint and declared dimensions',()=>{assert.equal(createHash('sha256').update(text).digest('hex'),manifest.sha256);assert.equal(prepareFinnishAccount(data),data);assert.equal(data.grid.windows.length,2);assert.equal(data.grid.year.hours,8784);assert.equal(data.prices.updated,'2026-09-24T05:00:00Z');});
test('consumer-band boundaries match the published classes, including exactly 15000',()=>{for(const [use,band]of [[0,'A'],[999,'A'],[1000,'B'],[2499,'B'],[2500,'C'],[4999,'C'],[5000,'D'],[15000,'D'],[15001,'E']])assert.equal(bandFor(use),band);for(const use of [NaN,Infinity,-1,'1000'])assert.throws(()=>bandFor(use));});
test('all 150 household accounts retain published totals and do not add VAT twice',()=>{for(const r of data.prices.rows){const use={A:750,B:2000,C:3000,D:10000,E:20000}[r.band],a=householdAccount(data,r.month,use);assert.equal(a.source,r);assert.equal(a.annualEUR.total,r.total*use/100);assert.ok(Math.abs(a.roundingEUR)<.41);assert.equal(a.annualEUR.tax,r.tax*use/100);}});
test('zero household use is a valid zero; missing month or component stays unavailable',()=>{assert.equal(householdAccount(data,'2024M01',0).annualEUR.total,0);assert.throws(()=>householdAccount(data,'2027M01',1000));const broken=structuredClone(data);broken.prices.rows[0].energy=null;assert.throws(()=>prepareFinnishAccount(broken),/Missing/);});
test('independent January 2024 band-C account agrees with the published decimal rates',()=>{const a=householdAccount(data,'2024M01',3000);assert.equal(a.source.energy,10.880);assert.equal(a.source.network,7.532);assert.equal(a.source.tax,7.213);assert.equal(a.source.total,25.625);assert.equal(a.annualEUR.total,768.75);assert.ok(Math.abs(a.annualEUR.energy-326.40)<1e-10);assert.ok(Math.abs(a.annualEUR.network-225.96)<1e-10);assert.ok(Math.abs(a.annualEUR.tax-216.39)<1e-10);});
test('price record indices address the original multidimensional query deterministically',()=>{for(const r of data.prices.rows){const t=data.prices.months.indexOf(r.month),b='ABCDE'.indexOf(r.band);assert.deepEqual(r.valueIndices,[t*20+b,t*20+5+b,t*20+10+b,t*20+15+b]);}});
test('grid uses interval means, preserves signed exports, and reconciles every selected hour',()=>{for(const w of data.grid.windows){const a=gridAccount(data,w.id,0);assert.equal(a.coveredHours,168);assert.ok(Math.abs(a.consumptionMWh-Number(w.consumptionMWhDecimal))<1e-7);for(let i=0;i<w.rows.length;i++){const r=gridAccount(data,w.id,i);assert.ok(Math.abs(r.residualMW)<1e-6);assert.equal(r.netImportMW,r.source.import+r.source.exportSigned);}}});
test('summer source clock remains UTC+2 and every hour retains its original workbook cell row',()=>{const r=data.grid.windows[1].rows[0];assert.equal(r.start,'2024-07-01T00:00:00+02:00');assert.equal(r.sourceHour,1);assert.equal(r.sourceDay,'2024-07-01');assert.ok(Number.isInteger(r.row));assert.equal(data.grid.sourceColumns.exportSigned,'Q');});
test('added demand cannot change observed prices, supply, heat or imply a price/capacity forecast',()=>{const before=JSON.stringify(data),bill=householdAccount(data,'2024M01',20000);const a=gridAccount(data,'winter',0,500);assert.equal(a.branch.totalDemandMW,a.source.consumption+500);assert.equal(a.branch.additionalMWhOneHour,500);assert.equal(a.branch.priceEffect,null);assert.equal(a.branch.availableGridCapacityMW,null);assert.deepEqual(householdAccount(data,'2024M01',20000),bill);assert.equal(JSON.stringify(data),before);for(const v of [-1,NaN,Infinity])assert.throws(()=>gridAccount(data,'winter',0,v));assert.throws(()=>gridAccount(data,'winter',168));});
test('missing or duplicate grid intervals are rejected instead of filled',()=>{for(const mutate of [d=>d.grid.windows[0].rows.splice(3,1),d=>d.grid.windows[0].rows[1].start=d.grid.windows[0].rows[0].start,d=>d.grid.windows[0].rows[0].import=null]){const d=structuredClone(data);mutate(d);assert.throws(()=>prepareFinnishAccount(d));}});
test('heat reconciles supply, losses, customer classes and exact source cells',()=>{const a=heatAccount(data,2024);assert.equal(a.customerUseGWh,48.5);assert.equal(a.residentialUseGWh,16);assert.equal(a.values.recoveryAndHeatPump,22.7);for(const k of ['inputResidualGWh','outputResidualGWh','customerResidualGWh'])assert.ok(Math.abs(a[k])<1e-10);assert.equal(data.heat.cells.find(c=>c.id==='residentialUse').cell,'R138');assert.equal(a.heatProductionElectricityMWh,null);assert.equal(data.heat.cells.find(c=>c.id==='productionElectricityMWh').raw,'..');assert.equal(a.recoveredHeatDeliveredToHomesGWh,null);});
test('newer heat sales cannot acquire an invented residential or recovered-heat allocation',()=>{const a=heatAccount(data,2025);assert.equal(a.complete,false);assert.equal(a.customerUseGWh,43.1);assert.equal(a.residentialUseGWh,null);assert.equal(a.centralNetworkRecoveryPercent,41);assert.match(a.source.originScope,/central network only/);assert.throws(()=>heatAccount(data,2026));});
test('inspection export carries originals, source scope, assumptions, methods and attribution',()=>{const x=finnishInspection(data,{month:'2026M06',annualKWh:20000,windowId:'winter',index:112,additionalMW:100,heatYear:2025},manifest.sha256,manifest);assert.equal(x.signed,false);assert.equal(x.provenance.inputs['grid.xlsx'].sha256,manifest.inputs['grid.xlsx'].sha256);assert.match(x.provenance.inputs['grid.xlsx'].url,/energia.fi/);assert.equal(x.extractSHA256,manifest.sha256);assert.equal(x.grid.branch.additionalMW,100);assert.equal(x.heat.residentialUseGWh,null);assert.match(x.attribution.prices,/CC BY 4.0/);assert.ok(x.household.source.valueIndices.length===4);assert.equal(x.grid.source.row,data.grid.windows[0].rows[112].row);assert.equal(x.methods.heat,data.methods.heat);});
