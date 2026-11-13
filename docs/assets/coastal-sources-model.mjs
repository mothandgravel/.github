const finite = value => typeof value === 'number' && Number.isFinite(value);
export function readSources(payload) {
  if (payload?.format !== 'mg.coastal-environment-archive.v1' || payload.timezone !== 'Europe/Helsinki') throw Error('Unrecognised source record');
  const start=Date.parse(payload.windowStartUtc),end=Date.parse(payload.windowEndUtcExclusive);
  if (!finite(start)||!finite(end)||end-start!==86400000||payload.dateLocal!=='2026-11-11'||start!==Date.parse('2026-11-10T22:00:00Z')||!Array.isArray(payload.series)||!payload.series.length) throw Error('Invalid study window');
  const ids=new Set();
  for(const s of payload.series){
    if(ids.has(s.id)||!s.id||!s.station||!s.parameter||!s.unit||!finite(s.latitude)||!finite(s.longitude)||!Array.isArray(s.points)||s.points.length!==24) throw Error('Invalid measured channel');
    ids.add(s.id);let prior=-Infinity;
    for(const [index,p] of s.points.entries()){
      const t=Date.parse(p.observedAt);
      if(!finite(t)||t<start||t>=end||t<=prior||t!==start+index*3600000||typeof p.rawValue!=='string'||!p.rawValue.trim()||(p.value!==null&&!finite(p.value))) throw Error('Invalid or unordered sample');
      if((p.value===null&&Number.isFinite(Number(p.rawValue)))||(p.value!==null&&Number(p.rawValue)!==p.value)) throw Error('Value differs from original');
      prior=t;
    }
  }
  return payload;
}
export function sampleAt(series, utc) {
  return series.points.find(p=>Date.parse(p.observedAt)===Date.parse(utc))??null;
}
export function segments(points){
  const out=[];let run=[];
  for(const p of points){
    if(p.value===null){if(run.length)out.push(run);run=[];}else run.push(p);
  }
  if(run.length)out.push(run);
  return out;
}
export const localHour=utc=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Helsinki',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(utc));
export const exact=value=>value===null?'Missing':new Intl.NumberFormat('en-GB',{maximumFractionDigits:6}).format(value);
export const sampledRange=series=>{
  const values=series.points.filter(p=>p.value!==null).map(p=>p.value);
  return values.length?{min:Math.min(...values),max:Math.max(...values),numeric:values.length,missing:series.points.length-values.length}:null;
};
