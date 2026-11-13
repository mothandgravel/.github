import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {readSources,sampleAt,segments,localHour,sampledRange} from '../docs/assets/coastal-sources-model.mjs';
const saved=JSON.parse(readFileSync(new URL('../docs/data/coastal-sources/2026-11-11/selected.json',import.meta.url),'utf8'));
test('Helsinki calendar day starts on the previous UTC date',()=>{
  const data=readSources(saved);
  assert.equal(localHour(data.series[0].points[0].observedAt),'00:00');
  assert.equal(localHour(data.series[0].points[23].observedAt),'23:00');
  assert.equal(data.windowStartUtc,'2026-11-10T22:00:00Z');
  assert.equal(data.windowEndUtcExclusive,'2026-11-11T22:00:00Z');
});
test('Loviisa keeps nineteen gaps and never bridges a missing sample',()=>{
  const s=readSources(saved).series[4],range=sampledRange(s);
  assert.equal(range.numeric,5);assert.equal(range.missing,19);
  assert.equal(segments(s.points).flat().length,5);
  for(const run of segments(s.points))for(let i=1;i<run.length;i++)assert.equal(Date.parse(run[i].observedAt)-Date.parse(run[i-1].observedAt),3600000);
  assert.equal(sampleAt(s,'2026-11-10T22:30:00Z'),null);
});
test('theoretical mean water and N2000 remain separate channels',()=>{
  const data=readSources(saved),n2000=data.series[5],mean=data.series[6];
  assert.equal(n2000.unit,'mm');assert.equal(mean.unit,'mm');
  assert.notEqual(n2000.parameter,mean.parameter);
  for(let i=0;i<24;i++)assert.equal(n2000.points[i].value-mean.points[i].value,211);
});
test('missing values cannot be replaced with zero or fabricated numeric values',()=>{
  const changed=structuredClone(saved),p=changed.series[4].points.find(p=>p.value===null);p.value=0;
  assert.throws(()=>readSources(changed),/original/);
  p.value=NaN;assert.throws(()=>readSources(changed),/sample/);
});
test('duplicates, reversed times and out-of-day samples are refused',()=>{
  for(const change of [p=>p.series.push(p.series[0]),p=>p.series[0].points.reverse(),p=>p.series[0].points[23].observedAt=p.windowEndUtcExclusive]){
    const data=structuredClone(saved);change(data);assert.throws(()=>readSources(data));
  }
});
test('one isolated numeric sample stays a point, and an empty series has no invented range',()=>{
  assert.deepEqual(segments([{value:null},{value:0},{value:null}]),[[{value:0}]]);
  assert.equal(sampledRange({points:[{value:null}]}),null);
});
