import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {readWeather,utcAtSecond,secondAtUtc,cloudAt,radarAt,buoyAt,radarCell,waveDirectionFrom,inspectWeather} from '../docs/assets/coastal-weather-model.mjs';
const root=new URL('../docs/data/coastal-weather/2026-11-11/',import.meta.url);
const data=readWeather(JSON.parse(await readFile(new URL('notebook.json',root),'utf8')));

test('civil day has 144 product slots, separate from retrieval and per-pixel acquisition',()=>{
  assert.equal(utcAtSecond(0),'2026-11-10T22:00:00Z');assert.equal(utcAtSecond(86399),'2026-11-11T21:59:59Z');
  assert.equal(cloudAt(data,0).productTimeUtc,utcAtSecond(0));
  assert.equal(cloudAt(data,599).productTimeUtc,utcAtSecond(0));
  assert.equal(cloudAt(data,600).productTimeUtc,utcAtSecond(600));
  assert.equal(cloudAt(data,86399).perPixelAcquisitionUtc,null);
  assert.throws(()=>utcAtSecond(86400));assert.throws(()=>utcAtSecond(1.5));
  const changed=structuredClone(data);changed.clouds[1].productTimeUtc=changed.clouds[0].productTimeUtc;assert.throws(()=>readWeather(changed));
});
test('a missing cloud slot never acquires a previous or future image',()=>{
  const changed=structuredClone(data);changed.clouds[1].available=false;
  assert.equal(cloudAt(changed,600),null);assert.equal(cloudAt(changed,1199),null);
  assert.equal(cloudAt(changed,1200).productTimeUtc,utcAtSecond(1200));
});
test('radar selection waits for completed scans and stops at the saved boundaries',()=>{
  const first=data.radar[0],last=data.radar.at(-1);
  assert.equal(radarAt(data,secondAtUtc(first.scanEndUtc)-1),null);
  assert.equal(radarAt(data,secondAtUtc(first.scanEndUtc)),first);
  assert.equal(radarAt(data,secondAtUtc(last.scanEndUtc)),last);
  assert.equal(radarAt(data,secondAtUtc(last.scanEndUtc)+1),null);
  for(let second=0;second<86400;second+=13){const f=radarAt(data,second);if(f)assert.ok(secondAtUtc(f.scanEndUtc)<=second);}
});
test('native float32 pixels retain missing, below-detection and quantitative values',async()=>{
  const f=data.radar[0],bytes=gunzipSync(await readFile(new URL(f.pixels,root)));
  assert.equal(bytes.length,f.pixelsUncompressedBytes);assert.equal(createHash('sha256').update(bytes).digest('hex'),f.pixelsUncompressedSha256);
  const counts={missing:0,'below detection':0,quantitative:0};let positive;
  for(let i=0;i<bytes.length;i+=4){const v=bytes.readFloatLE(i),cell=radarCell(f,v);counts[cell.kind]++;if(cell.kind==='quantitative')positive=cell;else assert.equal(cell.value,null);}
  assert.equal(counts.missing,f.cellCounts.missing);assert.equal(counts['below detection'],f.cellCounts.belowDetection);assert.equal(counts.quantitative,f.cellCounts.quantitative);
  assert.equal(positive.value,positive.rawValue*f.gain+f.offset);assert.equal(radarCell(f,0).value,null);assert.equal(radarCell(f,65535).value,null);
  assert.equal(f.georeferencing.verified,false);assert.equal(f.georeferencing.presentation,'native grid only');
});
test('Orrengrund gaps remain missing instead of retaining an earlier valid sample',()=>{
  const station=data.buoys.find(b=>b.id==='108495'),series=station.series.find(s=>s.parameter==='WaveHs'),gap=series.points.find(p=>p.value===null);
  const result=buoyAt(data,station.id,secondAtUtc(gap.observedAt)+3599);
  assert.equal(result.points.WaveHs.value,null);assert.equal(result.points.WaveHs.rawValue,'NaN');assert.equal(result.points.WaveHs.observedAt,gap.observedAt);
  assert.equal(series.points.filter(p=>p.value!==null).length,5);
  const changed=structuredClone(data);changed.buoys[0].series[0].points[0].rawValue='123';assert.throws(()=>readWeather(changed));
});
test('direction glyph expresses from bearing, with a separate travel direction',()=>{
  assert.deepEqual(waveDirectionFrom(90,20),{fromDegrees:90,travellingTowardsDegrees:270,spreadDegrees:20,cardinal:'E'});
  assert.equal(waveDirectionFrom(360).fromDegrees,0);assert.equal(waveDirectionFrom(0).cardinal,'N');assert.equal(waveDirectionFrom(null),null);
  assert.equal(waveDirectionFrom(-1),null);
});
test('inspection preserves all source clocks without promoting retrieval into publication',()=>{
  const result=inspectWeather(data,43806,'134221');assert.equal(result.clouds.ageSeconds,6);assert.equal(result.radar.ageSeconds,5);
  assert.equal(result.firstPublicationUtc,null);assert.equal(result.originalReceiverTimeUtc,null);assert.equal(result.clouds.record.perPixelAcquisitionUtc,null);
  assert.match(result.clouds.httpReceipt.completedAt,/^2026-11-14/);assert.equal(result.buoy.sourceRecords[0].completedAt,null);
  assert.equal(result.buoy.points.WaveHs.observedAt,'2026-11-11T10:00:00Z');
});
