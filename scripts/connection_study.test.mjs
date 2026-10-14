import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { getQualityMeasurementStatus } from '../docs/assets/specimens/measurement-status.mjs';
import { inspectReading } from '../docs/assets/connection-study-model.mjs';

const now = Date.parse('2026-01-01T12:00:00Z');
const complete = { hasDelta: true, source: 'inbound', updatedAt: new Date(now).toISOString() };
test('source helper preserves the exact freshness boundary', () => {
  assert.equal(getQualityMeasurementStatus(complete, now), 'current');
  assert.equal(getQualityMeasurementStatus(complete, now + 15000), 'current');
  assert.equal(getQualityMeasurementStatus(complete, now + 15001), 'stale');
});
test('missing, incomplete and untrustworthy dates stay unavailable', () => {
  for (const diagnostics of [undefined, { ...complete, hasDelta: false },
    { ...complete, source: 'unknown' }, { ...complete, unavailableMetrics: ['rtt'] },
    { ...complete, updatedAt: 'bad-date' }, { ...complete, updatedAt: new Date(now + 1).toISOString() }]) {
    assert.equal(getQualityMeasurementStatus(diagnostics, now), 'unavailable');
  }
  assert.equal(getQualityMeasurementStatus({ ...complete, unavailableMetrics: [] }, now), 'current');
});
test('freshness is independent of the measured rate', () => {
  assert.equal(getQualityMeasurementStatus({ ...complete, frameRate: 0 }, now), 'current');
  assert.equal(getQualityMeasurementStatus({ ...complete, frameRate: undefined }, now), 'current');
});
test('the published source fixtures replay to their declared outcomes', async () => {
  const provenance = JSON.parse(await readFile(new URL('../docs/design/connection-study-provenance.json', import.meta.url), 'utf8'));
  for (const fixture of provenance.fixtures) {
    const result = inspectReading(fixture.kind, fixture.ageSeconds ?? 2);
    assert.equal(result.measurement, fixture.expectedMeasurement);
    assert.equal(result.connection, fixture.connection);
    assert.equal(result.age, fixture.ageSeconds);
    assert.equal(result.frameRate, fixture.frameRate);
  }
});
test('advancing the inspection clock never changes or refreshes the sample', () => {
  for (let age = 0; age <= 30; age++) {
    const result = inspectReading('measured', age);
    assert.equal(result.connection, 'connected');
    assert.equal(result.frameRate, 24);
    assert.equal(result.measurement, age <= 15 ? 'current' : 'stale');
    assert.equal(inspectReading('missing', age).frameRate, null);
    assert.equal(inspectReading('missing', age).measurement, 'unavailable');
  }
});
test('the inspection accepts only declared fixtures and bounded clock positions', () => {
  for (const kind of ['', 'live', '<script>']) assert.throws(() => inspectReading(kind, 2));
  for (const age of [-1, 31, NaN, Infinity, 1.5, '2']) assert.throws(() => inspectReading('measured', age));
});
