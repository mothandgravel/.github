// Source records are immutable. Rehearsals never rewrite observed prices or flows.
export const FINLAND_METHOD_VERSION='2026-10-23.2';
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
export function priceExposure(data,month,{annualKWh,exposedPercent},changeCentsIncludingVAT){
 demand(annualKWh);
 if(annualKWh>60000||!finite(exposedPercent)||exposedPercent<0||exposedPercent>100)throw Error('Use must be 0–60,000 kWh; exposure must be 0–100%.');
 if(!finite(changeCentsIncludingVAT)||changeCentsIncludingVAT< -3||changeCentsIncludingVAT>10)throw Error('Choose a price change from −3 to +10 c/kWh, including VAT.');
 const baseline=householdAccount(data,month,annualKWh);
 for(const key of ['energy','network','tax','total'])if(!finite(baseline.source[key])||baseline.source[key]<0)throw Error('Price component unavailable for this household.');
 if(!/^202[4-6]M(0[1-9]|1[0-2])$/.test(month)||month>'2026M06')throw Error('VAT convention unavailable for this source month.');
 const vatRate=month<'2024M09'?.24:.255,exposedKWh=annualKWh*exposedPercent/100;
 const total=exposedKWh*changeCentsIncludingVAT/100,energy=total/(1+vatRate),tax=total-energy;
 const deltaEUR={energy,network:0,tax,total};
 const afterEUR=Object.fromEntries(Object.keys(deltaEUR).map(k=>[k,baseline.annualEUR[k]+deltaEUR[k]]));
 return{kind:'authored price sensitivity',baseline,exposedPercent,exposedKWh,changeCentsIncludingVAT,vatRate,deltaEUR,afterEUR,
  formula:'exposed annual kWh × VAT-inclusive change in c/kWh ÷ 100; energy delta = gross delta ÷ (1 + source-month VAT); VAT delta = gross − net',
  vatSource:'https://www.vero.fi/yritykset-ja-yhteisot/verot-ja-maksut/arvonlisaverotus/arvonlisaveroprosentit/',
  scope:'Constant selected-month consumer-band rates; chosen annual use and exposed kWh share. Exposure is not calendar months or a measured hourly load profile. Network, electricity excise, fixed-charge assumptions and total use stay unchanged. No data-centre price forecast or behavioural response.'};
}
export function householdHeatRoute({connection,tariff,allocatedHeatMWh,reductionEURPerMWh,passedThroughPercent}){
 if(!['connected','not-connected','unknown'].includes(connection)||!['unreported','unchanged','assumed'].includes(tariff))throw Error('Choose a valid heat connection and tariff assumption.');
 for(const [value,max]of [[allocatedHeatMWh,50],[reductionEURPerMWh,100],[passedThroughPercent,100]])if(!(value===null&&tariff!=='assumed')&&(!finite(value)||value<0||value>max))throw Error('Heat assumptions are outside the stated bounds.');
 let status='tariff-unreported',allocatedEnergyChargeReductionEUR=null,householdReductionEUR=null;
 if(connection==='not-connected'){status='no-direct-route';allocatedEnergyChargeReductionEUR=0;householdReductionEUR=0;}
 else if(connection==='unknown'){status='connection-unknown';}
 else if(tariff==='unchanged'){status='assumed-no-change';allocatedEnergyChargeReductionEUR=0;householdReductionEUR=0;}
 else if(tariff==='assumed'){status='assumed-reduction';allocatedEnergyChargeReductionEUR=allocatedHeatMWh*reductionEURPerMWh;householdReductionEUR=allocatedEnergyChargeReductionEUR*passedThroughPercent/100;}
 return{connection,tariff,allocatedHeatMWh,reductionEURPerMWh,passedThroughPercent,status,allocatedEnergyChargeReductionEUR,householdReductionEUR,
  attributedToRecoveredHeatEUR:null,measuredHouseholdSavingEUR:null,
  formula:'chosen household allocation in thermal MWh × chosen VAT-inclusive energy-charge reduction in EUR/MWh × chosen pass-through fraction',
  scope:'Separate district-heat charge sensitivity. The thermal allocation is chosen, not a household heat meter. Fixed heat charges stay unchanged. Pass-through is a scenario, not a claim about a landlord or housing company. No source-to-home recovered-heat allocation or causal saving is inferred; indirect electricity-market effects are unmodelled.'};
}
export function householdComparison(data,month,settings){
 const {changeCentsIncludingVAT,apartment,electricHome,heat}=settings;
 const apartmentElectricity=priceExposure(data,month,apartment,changeCentsIncludingVAT),homeElectricity=priceExposure(data,month,electricHome,changeCentsIncludingVAT);
 const apartmentHeat=householdHeatRoute(heat),electricHomeHeat=householdHeatRoute({...heat,connection:'not-connected'});
 const observed=heatAccount(data,2024);
 return{kind:'two authored homes / separate recorded context',month,assumptions:structuredClone(settings),
  apartment:{electricity:apartmentElectricity,heat:apartmentHeat,combinedChangeEUR:apartmentHeat.householdReductionEUR===null?null:apartmentElectricity.deltaEUR.total-apartmentHeat.householdReductionEUR},
  electricHome:{electricity:homeElectricity,heat:electricHomeHeat,combinedChangeEUR:homeElectricity.deltaEUR.total},
  recordedHeatContext:{year:2024,scope:observed.scope,residentialUseGWh:observed.residentialUseGWh,source:data.heat.cells.find(c=>c.id==='residentialUse'),recoveredHeatDeliveredToHomesGWh:null},
  scope:'These are editable illustrative homes, not averages, measured addresses or contract offers. The apartment electricity account excludes separately allocated district heat. The electric-home electricity input includes its heating and has no district-heat connection. Combined values are changes across two separate charges, not complete household bills. Historical electricity prices and local 2024 heat are not joined to estimate a causal effect.'};
}
export function finnishInspection(data,{month,annualKWh,windowId,index,additionalMW,heatYear,comparison},manifestSHA,provenance=null){return{schema:'moth-gravel/finland-inspection@2',methodVersion:FINLAND_METHOD_VERSION,extractSHA256:manifestSHA,retrieved:data.retrieved,signed:false,provenance,household:householdAccount(data,month,annualKWh),householdComparison:comparison?householdComparison(data,month,comparison):null,grid:gridAccount(data,windowId,index,additionalMW),heat:heatAccount(data,heatYear),methods:data.methods,attribution:{prices:'Source: Statistics Finland, energy prices, table 13rb / CC BY 4.0. https://creativecommons.org/licenses/by/4.0/ Bounded extract and annualised calculations by Moth & Gravel.',gridAndHeat:'Source: Energiateollisuus ry / bounded factual extracts, source workbook sheet and cell references retained.',heat2025:'Source: Nivos Vesi ja Lämpö Oy, 2025 annual report, PDF page 3, and central Mäntsälä origin disclosure. Different scopes kept separate.'}};}
