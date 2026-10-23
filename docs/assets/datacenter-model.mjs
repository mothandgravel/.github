export const COMPONENTS = Object.freeze([
  { id:'it_power_kw', name:'Computing equipment', short:'IT', color:'#c8ad7d' },
  { id:'cooling_kw', name:'Outdoor cooling', short:'Cooling', color:'#a8c7cc' },
  { id:'pump_kw', name:'Water-loop pumps', short:'Pumps', color:'#a2b39b' },
  { id:'hvac_kw', name:'Room air systems', short:'HVAC', color:'#b1acbd' },
  { id:'plug_and_light_kw', name:'Lights & utility plugs', short:'Other', color:'#dbbea6' },
].map(Object.freeze));
export const METHODS = Object.freeze({ maxGapSeconds:90, weatherMaxAgeSeconds:90, energy:'trapezoidal / piecewise-linear power', time:'source clock; timezone unspecified', periodPUE:'facility kWh / IT kWh over shared valid coverage', samplingAssumption:'Reported power is treated as point samples; publisher does not specify sensor averaging windows', validity:'All five power components finite and nonnegative at both interval endpoints; gaps over 90 s excluded; no zero filling or extrapolation', weather:'Earlier-only source-clock observation within 90 s; Fahrenheit to Celsius; clock alignment unverified' });

/** Integer microseconds on a naive calendar axis. UTC functions perform calendar
 * arithmetic only; this never assigns a timezone to the publisher's readings. */
export function clockUs(text) {
  const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?$/.exec(text);
  if(!m)throw Error('Invalid source clock');
  const [y,mo,d,h,mi,s]=m.slice(1,7).map(Number);
  const base=Date.UTC(y,mo-1,d), check=new Date(base);
  if(y<1900||y>2100||check.getUTCFullYear()!==y||check.getUTCMonth()!==mo-1||check.getUTCDate()!==d||h>23||mi>59||s>59)throw Error('Invalid source calendar');
  return base*1000+(h*3600+mi*60+s)*1e6+Number((m[7]??'').padEnd(6,'0'));
}
export function sourceClock(us, seconds=false) { return new Date(us/1000).toISOString().slice(0,seconds?19:16).replace('T',' '); }
const total = r => COMPONENTS.reduce((s,c)=>s+r[c.id],0);
const valid = r => COMPONENTS.every(c=>Number.isFinite(r[c.id])&&r[c.id]>=0);

export function prepareDataset(payload) {
  if(payload.schema!=='mg-esif-1'||typeof payload.licenseNotice!=='string'||!payload.licenseNotice.includes('USE OR PERFORMANCE OF THE DATA.'))throw Error('Missing dataset schema or publisher notice');
  const expected=['sourceRow','sourceClock',...COMPONENTS.map(c=>c.id),'pue','energy_reuse','ere'];
  if(JSON.stringify(payload.columns)!==JSON.stringify(expected))throw Error('Unexpected source columns');
  let previous=-Infinity;
  const records=payload.rows.map(row=>{
    if(row.length!==expected.length||!Number.isInteger(row[0])||row[0]<0)throw Error('Invalid source row');
    const r=Object.fromEntries(expected.map((key,i)=>[key,row[i]]));
    r.us=clockUs(r.sourceClock);
    if(r.us<=previous)throw Error('Source clocks must be strictly increasing');previous=r.us;
    for(const key of expected.slice(2))if(r[key]!==null&&!Number.isFinite(r[key]))throw Error('Nonfinite source value');
    r.validPower=valid(r);r.totalKW=r.validPower?total(r):null;
    r.closureKW=r.validPower&&Number.isFinite(r.pue)?r.pue*r.it_power_kw-r.totalKW:null;
    return Object.freeze(r);
  });
  const start=clockUs(payload.time.start),end=clockUs(payload.time.endExclusive);
  if(end<=start||!records.length||records[0].us>start||records.at(-1).us<end)throw Error('Window is not bracketed');
  previous=-Infinity;
  const weather=payload.weatherRows.map(row=>{
    if(row.length!==3||row.slice(1).some(x=>x!==null&&!Number.isFinite(x)))throw Error('Invalid weather record');
    const us=clockUs(row[0]);if(us<=previous)throw Error('Weather clocks must increase');previous=us;
    return Object.freeze({sourceClock:row[0],us,tempF:row[1],humidity:row[2]});
  });
  return Object.freeze({payload,records:Object.freeze(records),weather:Object.freeze(weather),start,end,window:Object.freeze(records.filter(r=>r.us>=start&&r.us<end))});
}

/** No extrapolation or zero filling. All channels share the same validity mask. */
export function integrate(records,start,end,maxGapSeconds=METHODS.maxGapSeconds) {
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||end<=start||!(maxGapSeconds>0&&Number.isFinite(maxGapSeconds)))throw Error('Invalid integration interval');
  const energy=Object.fromEntries(COMPONENTS.map(c=>[c.id,0]));
  let coveredUs=0,segments=0;
  for(let i=1;i<records.length;i++){
    const a=records[i-1],b=records[i];
    if(b.us<=start||a.us>=end)continue;
    const dt=b.us-a.us;
    if(dt<=0||dt>maxGapSeconds*1e6||!a.validPower||!b.validPower)continue;
    const lo=Math.max(start,a.us),hi=Math.min(end,b.us),left=(lo-a.us)/dt,right=(hi-a.us)/dt;
    if(hi<=lo)continue;
    for(const c of COMPONENTS){const delta=b[c.id]-a[c.id];energy[c.id]+=((a[c.id]+left*delta)+(a[c.id]+right*delta))/2*(hi-lo)/3.6e9;}
    coveredUs+=hi-lo;segments++;
  }
  const totalKWh=COMPONENTS.reduce((s,c)=>s+energy[c.id],0),requestedSeconds=(end-start)/1e6,coveredSeconds=coveredUs/1e6;
  return {start,end,energy,totalKWh,ITKWh:energy.it_power_kw,PUE:energy.it_power_kw>0?totalKWh/energy.it_power_kw:null,coveredSeconds,requestedSeconds,uncoveredSeconds:requestedSeconds-coveredSeconds,coverage:coveredSeconds/requestedSeconds,segments,method:METHODS.energy};
}
export function hourAccount(data,hour) {
  const start=clockUs(`${hour}:00:00`),end=start+3600e6;
  if(start<data.start||end>data.end)throw Error('Hour outside replay');
  const account=integrate(data.records,start,end);
  const samples=data.window.filter(r=>r.us>=start&&r.us<end);
  const pue=samples.map(r=>r.pue).filter(Number.isFinite);
  return {...account,hour,samples:samples.length,samplePUEArithmeticMean:pue.length?pue.reduce((a,b)=>a+b,0)/pue.length:null,
    meanKW:account.coveredSeconds?account.totalKWh/(account.coveredSeconds/3600):null,
    maxClosureKW:Math.max(0,...samples.map(r=>r.closureKW===null?0:Math.abs(r.closureKW)))};
}
export function precedingWeather(data,us) {
  let lo=0,hi=data.weather.length-1,index=-1;
  while(lo<=hi){const mid=(lo+hi)>>1;if(data.weather[mid].us<=us){index=mid;lo=mid+1;}else hi=mid-1;}
  if(index<0)return null;
  const r=data.weather[index],ageSeconds=(us-r.us)/1e6;
  if(ageSeconds>METHODS.weatherMaxAgeSeconds||!Number.isFinite(r.tempF)||!Number.isFinite(r.humidity)||r.humidity<0||r.humidity>100)return null;
  return {...r,ageSeconds,tempC:(r.tempF-32)*5/9,alignment:'source-clock comparison; alignment not verified'};
}
export function comparison(data,a,b) {
  const left=hourAccount(data,a),right=hourAccount(data,b);
  return {left,right,powerChangePercent:left.meanKW===null||right.meanKW===null?null:(right.meanKW/left.meanKW-1)*100,pueChange:left.PUE===null||right.PUE===null?null:right.PUE-left.PUE};
}

/** An isolated capacity rehearsal: recorded facility demand, authored supply.
 * Fixed grid cap; battery covers the remainder. No load rescheduling, thermal
 * response, generator startup, electrical transients or useful-work prediction. */
export function capacityRehearsal(records,start,end,{gridKW=2500,batteryKWh=500,initialFraction=.8,reserveFraction=.1,outputKW=1000,efficiency=.92}={}) {
  if([gridKW,batteryKWh,outputKW].some(x=>!Number.isFinite(x)||x<0)||!(efficiency>0&&efficiency<=1)||!(initialFraction>=reserveFraction&&initialFraction<=1&&reserveFraction>=0))throw Error('Invalid rehearsal assumptions');
  const baseline=integrate(records,start,end);
  let energy=batteryKWh*initialFraction,unmetKWh=0,deliveredKWh=0,gridKWh=0,lossKWh=0;
  const reserve=batteryKWh*reserveFraction,steps=[];
  // Integrate in one-second intervals on the same recorded linear power curve.
  // Crossings of the grid cap are therefore numerical approximations, labelled in UI/export.
  for(let i=1;i<records.length;i++){
    const a=records[i-1],b=records[i],dt=b.us-a.us;
    if(b.us<=start||a.us>=end||!a.validPower||!b.validPower||dt<=0||dt>90e6)continue;
    for(let lo=Math.max(start,a.us),hiEnd=Math.min(end,b.us);lo<hiEnd;){
      const hi=Math.min(lo+1e6,hiEnd),fraction=((lo+hi)/2-a.us)/dt;
      const demand=a.totalKW+(b.totalKW-a.totalKW)*fraction,hours=(hi-lo)/3.6e9,deficit=Math.max(0,demand-gridKW);
      const delivered=Math.min(deficit,outputKW,hours?Math.max(0,energy-reserve)*efficiency/hours:0)*hours;
      energy-=delivered/efficiency;deliveredKWh+=delivered;lossKWh+=delivered/efficiency-delivered;
      gridKWh+=Math.min(demand,gridKW)*hours;unmetKWh+=deficit*hours-delivered;lo=hi;
    }
    steps.push({us:Math.min(end,b.us),storedKWh:energy});
  }
  return {baseline,assumptions:{gridKW,batteryKWh,initialFraction,reserveFraction,outputKW,efficiency,stepSeconds:1},storedKWh:energy,reserveKWh:reserve,deliveredKWh,gridKWh,unmetKWh,lossKWh,steps,kind:'counterfactual capacity arithmetic; no equipment control'};
}
export function exportInspection(data,index,a,b,rehearsal=null) {
  const record=data.window[index];if(!record)throw Error('Invalid inspected record');
  return {specimen:'Where the power goes',version:1,licenseNotice:data.payload.licenseNotice,source:data.payload.source,methods:METHODS,
    record,weather:precedingWeather(data,record.us),comparison:comparison(data,a,b),rehearsal,
    interpretation:{geometry:'Authored, not a survey of ESIF; no per-rack measurements',energy:'Numerical estimate from power samples',uncertainty:'No calibration uncertainty supplied. Missing coverage is not a confidence interval.',time:METHODS.time},signed:false};
}
