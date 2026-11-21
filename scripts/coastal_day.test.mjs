import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {readDay, at, aisAt, metarAt} from '../docs/assets/coastal-day-model.mjs';
const data = readDay(JSON.parse(await readFile(new URL('../docs/data/coastal-days/2026-11-21/notebook.json', import.meta.url), 'utf8')));
const series = id => data.series.find(s => s.id === id);
test('source values and units remain exact at the morning label',()=>{
  assert.equal(at(data,series('101039:ws_10min'),32400).point.raw,'8.6');
  assert.equal(at(data,series('108495:WaveHs'),32400).point.raw,'0.8');
  assert.equal(at(data,series('134254:WLEVN2K_PT1S_INSTANT'),32400).point.raw,'595.0');
  assert.equal(series('134254:WLEVN2K_PT1S_INSTANT').unit,'mm');
});
test('a later Gulf sample never substitutes for a missing Orrengrund sample',()=>{
  const a=at(data,series('108495:WaveHs'),34200), b=at(data,series('134221:WaveHs'),34200);
  assert.equal(a.kind,'missing');assert.equal(a.point.raw,'NaN');assert.equal(a.point.value,null);
  assert.equal(b.kind,'reading');assert.equal(b.point.value,1);assert.equal(a.point.time,b.point.time);
});
test('query cutoff is inclusive, uncollected evening is distinct from NaN',()=>{
  assert.ok(at(data,series('108495:WaveHs'),68400).point);
  assert.equal(at(data,series('108495:WaveHs'),68401).kind,'uncollected');
  assert.equal(at(data,series('108495:WaveHs'),72000).point,null);
});
test('AIS is withheld before its source time and never projected',()=>{
  assert.equal(aisAt(data,32502).kind,'before');assert.equal(aisAt(data,32503).kind,'saved');
  assert.deepEqual(aisAt(data,60000).fix.geometry.coordinates,aisAt(data,32503).fix.geometry.coordinates);
  assert.equal(aisAt(data,60000).fix.properties.timestampExternal,1795244502644);
  assert.equal(aisAt(data,72000).kind,'uncollected');
});
test('METAR selection cannot pull a later observation into an earlier picture',()=>{
  for(const t of [0,10000,32400,32503,34200,60000,68400]) {
    const report=metarAt(data,'EETN',t);if(report)assert.ok(Date.parse(report.time)<=Date.parse(data.startUtc)+t*1000);
  }
  assert.equal(metarAt(data,'EETN',72000),null);
});
test('corrupted raw values and changed source dates are rejected',()=>{
  const bad=structuredClone(data);bad.series[0].points[0].value=999;assert.throws(()=>readDay(bad));
  const other=structuredClone(data);other.dateLocal='2026-11-11';assert.throws(()=>readDay(other));
});
test('a bare builder run refuses to replace a frozen snapshot or its inventory',async()=>{
  const files=['../docs/data/coastal-days/2026-11-21/notebook.json','../docs/design/coastal-day-20261121-provenance.json'].map(f=>new URL(f,import.meta.url));
  const before=await Promise.all(files.map(f=>readFile(f)));
  const result=spawnSync(process.platform==='win32'?'python':'python3',['scripts/build_coastal_day.py'],{cwd:fileURLToPath(new URL('..',import.meta.url)),encoding:'utf8'});
  assert.equal(result.status,1);assert.match(result.stderr,/Frozen snapshot already exists/);
  const after=await Promise.all(files.map(f=>readFile(f)));assert.deepEqual(after,before);
});
