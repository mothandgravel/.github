import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createTntStudy, tntSnapshot, exportTntPrefix, elapsedLabel } from '../docs/assets/maintenance-tnt-model.mjs';
const bytes = await readFile(new URL('../docs/assets/maintenance-tnt.json', import.meta.url));
const data = JSON.parse(bytes), study = createTntStudy(data);
const provenance = JSON.parse(await readFile(new URL('../docs/design/maintenance-tnt-provenance.json', import.meta.url)));
test('derived data and unchanged public source CSVs retain their pinned hashes', async () => {
  assert.equal(createHash('sha256').update(bytes).digest('hex'), provenance.datasetSha256);
  for (const item of Object.values(data.source.files)) {
    const raw = await readFile(new URL('../docs/assets/' + item.file, import.meta.url));
    assert.equal(createHash('sha256').update(raw).digest('hex'), item.sha256);
  }
  const licence = await readFile(new URL('../docs/assets/tnt/LICENSE.txt', import.meta.url));
  assert.equal(createHash('sha1').update(Buffer.from(`blob ${licence.length}\0`)).update(licence).digest('hex'), 'f288702d2fa16d3cdf0035b15a9fcbc552cd88e7');
});
test('full capture reproduces the published counts and recorded delay', () => {
  const full = tntSnapshot(study, data.endUs);
  assert.deepEqual(full.counts, { sent: 1000, received: 927, awaiting: 0, notObserved: 73 });
  const received = study.records.filter((r) => r.receivedUs !== null);
  const mean = received.reduce((sum, r) => sum + r.delayUs, 0) / received.length / 1e6;
  assert.ok(Math.abs(mean - Number(data.publishedSummary.avg_latency_s)) < 1e-6);
  assert.equal(data.summary.lossPercent, Number(data.publishedSummary.packet_dropped_pct));
});
test('a packet with no receive row stays awaiting until the observed capture ends', () => {
  const missing = study.records.find((r) => r.receivedUs === null);
  assert.equal(tntSnapshot(study, missing.sentUs, missing.ordinal).selected.state, 'awaiting');
  assert.equal(tntSnapshot(study, data.endUs - 1, missing.ordinal).selected.state, 'awaiting');
  assert.equal(tntSnapshot(study, data.endUs, missing.ordinal).selected.state, 'not-observed');
});
test('receiver evidence appears only when its recorded event arrives', () => {
  const packet = study.records.find((r) => r.delayUs === Math.max(...study.records.map((r) => r.delayUs || 0)));
  const before = tntSnapshot(study, packet.receivedUs - 1, packet.ordinal).selected;
  assert.equal(before.receiver, null); assert.equal(before.delayUs, null); assert.equal(before.sourceRows.receiver, null);
  assert.equal(tntSnapshot(study, packet.receivedUs, packet.ordinal).selected.receiver.packet_id, packet.packetId);
});
test('exports exclude future receiver evidence and are bounded to the selected prefix', () => {
  const packet = study.records.find((r) => r.receivedUs !== null);
  const exported = exportTntPrefix(study, packet.sentUs, packet.ordinal);
  assert.equal(exported.selected.receiver, null);
  assert.equal(exported.events.some((event) => event.atUs > packet.sentUs), false);
  assert.equal(exported.events.some((event) => event.ordinal === packet.ordinal && event.kind === 'received'), false);
});
test('reused IPv4 IDs remain separate occurrences with nonnegative recorded delay', () => {
  assert.equal(data.failedControl.uniqueSenderKeys, 994);
  assert.equal(data.failedControl.negativeDelayCount, 5);
  assert.equal(study.records.filter((r) => r.occurrence > 1).length, 6);
  assert.ok(study.records.every((r) => r.delayUs === null || r.delayUs >= 0));
});
test('replay has recorded bounds and explicit evidence limits', () => {
  assert.equal(tntSnapshot(study, -10).cursorUs, 0);
  assert.equal(tntSnapshot(study, Infinity).cursorUs, 0);
  assert.equal(tntSnapshot(study, data.endUs * 2).cursorUs, data.endUs);
  assert.equal(elapsedLabel(335_835_865, true), '00:05:35.836');
  assert.ok(data.limits.some((text) => text.includes('No application acknowledgement')));
});
