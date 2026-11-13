import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {readArchives, utcAtMinute, minuteAtUtc, gaugeAt, reportAt, resolveReport, frameAt, levelEH2000, radarValue, reportFields} from '../docs/assets/coastal-archives-model.mjs';
const saved = JSON.parse(readFileSync(new URL('../docs/data/coastal-archives/2026-11-11/notebook.json', import.meta.url), 'utf8'));

test('preserved archives retain their distinct clocks and complete requested collections', () => {
  const data = readArchives(saved);
  assert.equal(data.gauges.flatMap(s => s.points).length, 144);
  assert.equal(data.reports.filter(r => r.station === 'EETN').length, 48);
  assert.equal(utcAtMinute(0), '2026-11-10T22:00:00Z');
  assert.equal(utcAtMinute(1439), '2026-11-11T21:59:00Z');
  assert.equal(minuteAtUtc('2026-11-11T10:00:00Z'), 720);
  assert.throws(() => utcAtMinute(1440)); assert.throws(() => utcAtMinute(.5));
});

test('hourly mean labels are selected without inventing an interval edge or interpolating values', () => {
  const s = saved.gauges[0];
  assert.equal(gaugeAt(s, utcAtMinute(35)), s.points[0]);
  assert.equal(gaugeAt(s, utcAtMinute(60)), s.points[1]);
  assert.equal(s.intervalEdge, null);
  const changed = structuredClone(s); changed.points[0].value = null; changed.points[0].rawValue = null;
  assert.equal(gaugeAt(changed, utcAtMinute(35)).value, null);
  assert.equal(gaugeAt(s, '2026-11-11T22:00:00Z'), null);
});

test('gauge conversion uses the documented minus-five-metre EH2000 zero, preserving real zeros and missing values', () => {
  assert.equal(levelEH2000(522.380), .2238);
  assert.equal(levelEH2000(522.381), .22381);
  assert.equal(levelEH2000(500), 0);
  assert.equal(levelEH2000(null), null);
  assert.equal(saved.gauges.find(s => s.parameter === 'WL avg').gaugeZeroMetresEH2000, -5);
});

test('no future report leaks into the before-first-message state', () => {
  assert.equal(reportAt(saved.reports, 'EFHK', utcAtMinute(19)), null);
  assert.equal(reportAt(saved.reports, 'EFHK', utcAtMinute(20)).observedAt, '2026-11-10T22:20:00Z');
  assert.equal(reportAt(saved.reports, 'EFHK', utcAtMinute(49)).observedAt, '2026-11-10T22:20:00Z');
  assert.equal(reportAt(saved.reports, 'EFHK', utcAtMinute(50)).observedAt, '2026-11-10T22:50:00Z');
});

test('reports remain intact and timestamp ties preserve separate messages, including corrections', () => {
  const r = saved.reports[0], corrected = {...r, id: 'correction', raw: r.raw + ' COR'};
  const list = [corrected, {...r, observedAt: utcAtMinute(50)}, r];
  assert.equal(reportAt(list, r.station, utcAtMinute(20)), r);
  assert.equal(resolveReport(list, r.station, utcAtMinute(20), corrected.id), corrected);
  assert.equal(resolveReport(list, r.station, utcAtMinute(20), r.id), r);
  assert.equal(resolveReport(list, r.station, utcAtMinute(19), corrected.id), null);
  assert.equal(list.length, 3);
});

test('radar strip has exact boundaries and never freezes its last frame across the rest of the day', () => {
  assert.equal(frameAt(saved.frames, utcAtMinute(719)), null);
  assert.equal(frameAt(saved.frames, utcAtMinute(720)), saved.frames[0]);
  assert.equal(frameAt(saved.frames, utcAtMinute(724)), saved.frames[0]);
  assert.equal(frameAt(saved.frames, utcAtMinute(725)), saved.frames[1]);
  assert.equal(frameAt(saved.frames, utcAtMinute(735)), saved.frames[3]);
  assert.equal(frameAt(saved.frames, utcAtMinute(736)), null);
  assert.equal(frameAt(saved.frames, utcAtMinute(1439)), null);
});

test('provider-masked radar zero has no physical reflectivity value', () => {
  assert.equal(radarValue(0), null);
  assert.equal(radarValue(64), 0);
  assert.equal(radarValue(100), 18);
  for (const code of [255, -1, .5, NaN]) assert.throws(() => radarValue(code));
});

test('METAR reading preserves bounds, variable winds, gusts and negative temperatures', () => {
  const decoded = reportFields('EETN 111020Z VRB05G12KT 9999 BKN020 M02/M04 Q1007');
  assert.equal(decoded.visibility, '≥10 km');
  assert.equal(decoded.wind, 'Variable / 5 kt · gust 12');
  assert.equal(decoded.temperature, '-2 °C');
  assert.equal(decoded.pressure, '1007 hPa');
  assert.equal(decoded.clouds, 'BKN020');
  const cavok = reportFields('EFHK 111020Z 20005MPS CAVOK 05/03 Q1007');
  assert.match(cavok.visibility, /≥10 km/); assert.match(cavok.clouds, /not zero cloud/);
  assert.match(cavok.wind, /m\/s/);
});

test('NASA date products cannot acquire a made-up acquisition or publication time', () => {
  for (const field of ['acquiredAt', 'publishedAt']) {
    const bad = structuredClone(saved); bad.images[0][field] = utcAtMinute(720);
    assert.throws(() => readArchives(bad), /daily image clock/);
  }
  assert.equal(saved.images[0].acquiredAt, null);
  assert.equal(saved.images[0].productDateUtc, '2026-11-11');
});

test('source-clock, datum, mask, raw-value and receipt corruption is refused', () => {
  for (const change of [
    d => { d.gauges[0].points[0].value = 0; },
    d => { d.gauges[0].intervalEdge = 'end'; },
    d => { d.gauges[0].gaugeZeroMetresEH2000 = 0; },
    d => { d.reports[0].observedAt = utcAtMinute(50); },
    d => { d.frames[0].noDataCode = 255; },
    d => { d.frames[0].observedAt = utcAtMinute(0); },
    d => { d.receipts[d.frames[0].sourceFile].sha256 = 'unknown'; },
    d => { d.receipts[d.frames[0].sourceFile].completedAt = '2020-01-01T00:00:00Z'; },
  ]) { const bad = structuredClone(saved); change(bad); assert.throws(() => readArchives(bad)); }
});
