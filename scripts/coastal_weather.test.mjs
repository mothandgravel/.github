import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {readWeather,utcAtSecond,secondAtUtc,cloudAt,radarAt,buoyAt,radarCell,radarGridAt,radarCellLocation,waveDirectionFrom,mapBearingVector,inspectWeather} from '../docs/assets/coastal-weather-model.mjs';
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
test('radar selection respects product-interval end labels and saved boundaries',()=>{
  const first=data.radar[0],last=data.radar.at(-1);
  assert.equal(radarAt(data,secondAtUtc(first.intervalEndUtc)-1),null);
  assert.equal(radarAt(data,secondAtUtc(first.intervalEndUtc)),first);
  assert.equal(radarAt(data,secondAtUtc(last.intervalEndUtc)),last);
  assert.equal(radarAt(data,secondAtUtc(last.intervalEndUtc)+1),null);
  for(const second of [44103,45003,45903])assert.equal(radarAt(data,second),null);
  for(let second=0;second<86400;second+=13){const f=radarAt(data,second);if(f)assert.ok(secondAtUtc(f.intervalEndUtc)<=second);}
});
test('native float32 pixels retain missing, below-detection and quantitative values',async()=>{
  const f=data.radar[0],bytes=gunzipSync(await readFile(new URL(f.pixels,root)));
  assert.equal(bytes.length,f.pixelsUncompressedBytes);assert.equal(createHash('sha256').update(bytes).digest('hex'),f.pixelsUncompressedSha256);
  const counts={missing:0,'below detection':0,quantitative:0};let positive;
  for(let i=0;i<bytes.length;i+=4){const v=bytes.readFloatLE(i),cell=radarCell(f,v);counts[cell.kind]++;if(cell.kind==='quantitative')positive=cell;else assert.equal(cell.value,null);}
  assert.equal(counts.missing,f.cellCounts.missing);assert.equal(counts['below detection'],f.cellCounts.belowDetection);assert.equal(counts.quantitative,f.cellCounts.quantitative);
  assert.equal(positive.value,positive.rawValue*f.gain+f.offset);assert.equal(radarCell(f,0).value,null);assert.equal(radarCell(f,65535).value,null);
  assert.equal(f.georeferencing.verified,false);assert.equal(f.georeferencing.method,'mg.corner-mercator.v1');
  assert.equal(f.underlyingSweepAcquisitionUtc,null);assert.equal(f.perPixelAcquisitionUtc,null);
});

test('corner registration matches independent Pyproj controls with explicit unknown accuracy',()=>{
  for(const f of data.radar){
    assert.equal(f.georeferencing.metadataReconciled,false);assert.equal(f.georeferencing.providerConfirmed,false);assert.equal(f.georeferencing.surveyValidated,false);
    for(const p of f.georeferencing.controlPoints){
      const c=radarCellLocation(f,p.column,p.row);
      assert.ok(Math.abs(c.longitude-p.longitude)<1e-9);assert.ok(Math.abs(c.latitude-p.latitude)<1e-9);assert.ok(Math.abs(c.agencyLatitude-p.agencyLatitude)<1e-9);
      assert.deepEqual(radarGridAt(f,c.longitude,c.latitude),{column:p.column,row:p.row});assert.equal(c.accuracyMetres,null);assert.equal(c.approximate,true);
    }
    assert.equal(radarGridAt(f,0,0),null);assert.equal(radarGridAt(f,24,90),null);assert.equal(radarGridAt(f,NaN,60),null);assert.throws(()=>radarCellLocation(f,720,0));
    const g=f.georeferencing;assert.ok(g.footprintChecks.cornerMercator.p90AbsoluteRangeResidualMetres<2000);
    assert.ok(g.footprintChecks.literalMetreScales.medianAbsoluteRangeResidualMetres>50000);
  }
});

test('registration rejects a changed projection contract instead of silently locating cells',()=>{
  for(const mutate of [d=>{d.radar[0].georeferencing.method='unknown';},d=>{d.radar[0].georeferencing.metadataReconciled=true;},d=>{d.radar[0].georeferencing.projectedBoundsMetres[0]=NaN;},d=>{d.radar[0].mapImage='../unsafe.png';},d=>{d.radar[0].where.projdef='+proj=longlat';},d=>{d.radar[0].georeferencing.projectedBoundsMetres[0]+=100;}]){
    const changed=structuredClone(data);mutate(changed);assert.throws(()=>readWeather(changed));
  }
});

test('wave bearings follow the equal-degree map tangent instead of raw compass screen angles',()=>{
  const v=mapBearingVector(208,59.965);
  // Independent WGS84 Pyproj Geod forward: 10 m from 25.235 E,59.965 N at 208 degrees.
  assert.ok(Math.abs(v.dx-(-.7275556800939953))<2e-6);assert.ok(Math.abs(v.dy-.6860486370243468)<2e-6);
  assert.ok(Math.abs(v.dx-Math.sin(208*Math.PI/180))>.2);
  assert.ok(Math.abs(mapBearingVector(0,60).dx)<1e-12);assert.equal(mapBearingVector(0,60).dy,-1);
  assert.ok(Math.abs(mapBearingVector(90,60).dx-1)<1e-12);assert.equal(mapBearingVector(null,60),null);
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
