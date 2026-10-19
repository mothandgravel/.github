import test from 'node:test';
import assert from 'node:assert/strict';
import { scenario, picture, settings, evidence, END } from '../docs/assets/coastal-replay-model.mjs';
test('a local observation exists at South while North has not received it', () => {
  const s = scenario();
  assert.ok(picture(s, 'south', 420).records.some(o => o.id === 'S-300'));
  assert.ok(!picture(s, 'north', 420).records.some(o => o.id === 'S-300'));
});
test('late receipt is inclusive, keeps event time, and never rolls latest position back', () => {
  const s = scenario();
  assert.ok(!picture(s, 'north', 579).records.some(o => o.id === 'S-300'));
  const late = picture(s, 'north', 580);
  assert.equal(late.records.find(o => o.id === 'S-300').age, 280);
  assert.equal(late.latest.find(o => o.origin === 'south').id, 'S-500');
});
test('hindsight adds only historically observed records and does not mutate a then-view', () => {
  const s = scenario(), before = picture(s, 'north', 420);
  const later = picture(s, 'north', 420, 'later');
  assert.equal(later.historicalAdditions, 3);
  assert.ok(later.records.every(o => o.observedAt <= 420));
  assert.deepEqual(picture(s, 'north', 420), before);
  assert.equal(picture(s, 'north', 0).records.length, 0);
});
test('retry adds a receipt but never a second observation or source', () => {
  const s = scenario(), before = picture(s, 'north', 580), after = picture(s, 'north', 584);
  assert.equal(after.records.length, before.records.length);
  assert.equal(after.duplicates, 1);
  assert.equal(after.records.filter(o => o.id === 'S-300').length, 1);
});
test('freshness uses observation age, not a recent delivery', () => {
  const p = picture(scenario(), 'north', 580);
  assert.equal(p.records.find(o => o.id === 'S-300').fresh, false);
  assert.equal(picture(scenario(), 'north', 220).records.find(o => o.id === 'S-100').fresh, true);
  assert.equal(picture(scenario(), 'north', 221).records.find(o => o.id === 'S-100').fresh, false);
});
test('baseline and delayed runs preserve observations, vary only delivery', () => {
  const s = scenario(), baseline = scenario({ interrupted: false });
  assert.deepEqual(s.observations, baseline.observations);
  assert.ok(picture(baseline, 'north', 420).records.some(o => o.id === 'S-300'));
  assert.equal(scenario({ delay: 340 }).receipts.find(r => r.station === 'north' && r.observationId === 'S-300').receivedAt, 640);
});
test('all snapshots remain causal across all seconds and all supported delays', () => {
  for (const delay of [220, 280, 340]) for (const interrupted of [true, false]) {
    const s = scenario({ delay, interrupted });
    for (let t = 0; t <= END; t++) for (const station of ['north', 'south']) {
      const p = picture(s, station, t);
      assert.ok(p.records.every(o => o.observedAt <= t && o.receipt.receivedAt <= t));
      assert.equal(new Set(p.records.map(o => o.id)).size, p.records.length);
    }
  }
});
test('invalid inputs fail explicitly; export separates full fixture and filtered snapshots', () => {
  for (const x of [{delay: NaN}, {delay: 400}, {freshness: 0}, {interrupted: 'false'}]) assert.throws(() => settings(x));
  assert.throws(() => picture(scenario(), 'unknown', 0));
  assert.throws(() => picture(scenario(), 'north', Infinity));
  assert.throws(() => picture(scenario(), 'north', 0, 'truth'));
  const out = evidence(scenario(), 420, 'then', 'north', 'S-300');
  assert.equal(out.synthetic, true);
  assert.ok(out.scenario.observations.some(o => o.observedAt > 420));
  assert.ok(out.snapshots.every(p => p.records.every(o => o.observedAt <= 420)));
});
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

test('published provenance binds the reused map and exposes the working entry point', () => {
  const read = path => readFileSync(new URL('../docs/' + path, import.meta.url));
  const record = JSON.parse(read('design/coastal-two-stations-provenance.json'));
  const asset = record.implementation.reusedGeometry;
  assert.equal(createHash('sha256').update(read(asset.file)).digest('hex'), asset.sha256);
  assert.equal(createHash('sha256').update(read(record.capture.path)).digest('hex'), record.capture.sha256);
  assert.match(read('specimens/coastal-watch/index.html').toString(), /href="\.\/two-stations\/"/);
  assert.match(read('sitemap.xml').toString(), /https:\/\/mothandgravel.com\/specimens\/coastal-watch\/two-stations\//);
  assert.equal(record.raivariReview.pieces.length, 9);
});
