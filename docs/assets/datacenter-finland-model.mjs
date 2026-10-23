// Source records are immutable. Rehearsals never rewrite observed prices or flows.
export const FINLAND_METHOD_VERSION='2026-10-23.1';
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const demand=v=>{if(!finite(v)||v<0)throw Error('Demand must be a finite, nonnegative number.');return v;};
export function bandFor(annualKWh){demand(annualKWh);if(annualKWh<1000)return'A';if(annualKWh<2500)return'B';if(annualKWh<5000)return'C';if(annualKWh<=15000)return'D';return'E';}
export function prepareFinnishAccount(data){
 if(data.schema!=='moth-gravel/finland-account@1')throw Error('Unrecognised Finnish account.');
 if(data.prices.months.length!==30||data.prices.rows.length!==150)throw Error('Incomplete price window.');
 const keys=new Set();
 for(const r of data.prices.rows){const key=`${r.month}/${r.band}`;if(keys.has(key))throw Error('Duplicate price record.');keys.add(key);if(!data.prices.months.includes(r.month)||!['A','B','C','D','E'].includes(r.band))throw Error('Invalid price key.');for(const k of ['energy','network','tax','total'])if(!finite(r[k])||r[k]<0)throw Error('Missing or invalid price component.');if(Math.abs(r.energy+r.network+r.tax-r.total)>.002)throw Error('Price components do not reconcile.');}
 for(const w of data.grid.windows){if(w.rows.length!==168)throw Error('Incomplete grid week.');for(let i=0;i<w.rows.length;i++){const r=w.rows[i];for(const k of ['consumption','production','import','exportSigned','wind'])if(!finite(r[k]))throw Error('Missing grid measurement.');if(Math.abs(r.production+r.import+r.exportSigned-r.consumption)>1e-6)throw Error('Grid flows do not reconcile.');if(i&&Date.parse(r.start)-Date.parse(w.rows[i-1].start)!==3600000)throw Error('Grid interval missing or repeated.');}}
 return data;
}
export function householdAccount(data,month,annualKWh){
 demand(annualKWh);const band=bandFor(annualKWh),source=data.prices.rows.find(r=>r.month===month&&r.band===band);if(!source)throw Error('Price record unavailable.');
 const annualEUR=Object.fromEntries(['energy','network','tax','total'].map(k=>[k,source[k]*annualKWh/100]));
 return{kind:'annualised illustration',month,annualKWh,band,source,annualEUR,roundingEUR:annualEUR.total-annualEUR.energy-annualEUR.network-annualEUR.tax,formula:'annual kWh × selected-month c/kWh ÷ 100; VAT already in tax channel',scope:'National consumer-band price statistic. Authored annual use. Not an actual household bill, offered tariff, forecast or data-centre price effect.'};
}
export function gridAccount(data,windowId,index,additionalMW=0){
 demand(additionalMW);const window=data.grid.windows.find(w=>w.id===windowId);if(!window||!Number.isInteger(index)||index<0||index>=window.rows.length)throw Error('Grid record unavailable.');
 const source=window.rows[index],consumptionMWh=window.rows.reduce((s,r)=>s+r.consumption,0);
 return{source,windowId,index,coveredHours:window.rows.length,consumptionMWh,netImportMW:source.import+source.exportSigned,residualMW:source.production+source.import+source.exportSigned-source.consumption,branch:{kind:'authored requirement / fixed historical supply',additionalMW,totalDemandMW:source.consumption+additionalMW,additionalMWhOneHour:additionalMW,priceEffect:null,availableGridCapacityMW:null},scope:'National historical power flows. Imports are not spare capacity. Added demand has no dispatch or price response model.'};
}
export function heatAccount(data,year){
 if(year===2025)return{year,complete:false,customerUseGWh:data.heat.report2025.salesGWh,residentialUseGWh:null,centralNetworkRecoveryPercent:data.heat.report2025.centralNetworkRecoveryPercent,source:data.heat.report2025,scope:data.heat.report2025.scope};
 if(year!==2024)throw Error('Heat year unavailable.');
 const values=Object.fromEntries(data.heat.cells.map(c=>[c.id,c.value]));
 for(const id of ['fuelHeat','recoveryAndHeatPump','supply','customerUse','lossAndMeterDifference','residentialUse','industrialUse','otherUse'])if(!finite(values[id]))throw Error('Heat balance incomplete.');
 const inputResidualGWh=values.fuelHeat+values.recoveryAndHeatPump-values.supply,outputResidualGWh=values.supply-values.customerUse-values.lossAndMeterDifference,customerResidualGWh=values.customerUse-values.residentialUse-values.industrialUse-values.otherUse;
 if(Math.max(Math.abs(inputResidualGWh),Math.abs(outputResidualGWh),Math.abs(customerResidualGWh))>.001)throw Error('Heat account does not reconcile.');
 return{year,complete:true,values,residentialUseGWh:values.residentialUse,customerUseGWh:values.customerUse,source:data.heat.cells,inputResidualGWh,outputResidualGWh,customerResidualGWh,heatProductionElectricityMWh:values.productionElectricityMWh,recoveredHeatDeliveredToHomesGWh:null,scope:data.heat.scope2024};
}
export function finnishInspection(data,{month,annualKWh,windowId,index,additionalMW,heatYear},manifestSHA,provenance=null){return{schema:'moth-gravel/finland-inspection@1',methodVersion:FINLAND_METHOD_VERSION,extractSHA256:manifestSHA,retrieved:data.retrieved,signed:false,provenance,household:householdAccount(data,month,annualKWh),grid:gridAccount(data,windowId,index,additionalMW),heat:heatAccount(data,heatYear),methods:data.methods,attribution:{prices:'Source: Statistics Finland, energy prices, table 13rb / CC BY 4.0. https://creativecommons.org/licenses/by/4.0/ Bounded extract and annualised calculations by Moth & Gravel.',gridAndHeat:'Source: Energiateollisuus ry / bounded factual extracts, source workbook sheet and cell references retained.',heat2025:'Source: Nivos Vesi ja Lämpö Oy, 2025 annual report, PDF page 3, and central Mäntsälä origin disclosure. Different scopes kept separate.'}};}
