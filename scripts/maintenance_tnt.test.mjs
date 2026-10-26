import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createTntStudy, tntSnapshot, exportTntPrefix, elapsedLabel, tntTimeWindow, tntCarryInLabel } from '../docs/assets/maintenance-tnt-model.mjs';
const bytes = await readFile(new URL('../docs/assets/maintenance-tnt.json', import.meta.url));
const data = JSON.parse(bytes), study = createTntStudy(data);
const provenance = JSON.parse(await readFile(new URL('../docs/design/maintenance-tnt-provenance.json', import.meta.url)));
test('earlier sends retain their awaiting versus absent meaning outside the canvas', () => {
  const endWindow = tntTimeWindow(study, data.endUs, 1000);
  assert.equal(tntCarryInLabel(endWindow), 'Sent before this window: 73 without receive rows at capture end.');
  const beforeEnd = tntTimeWindow(study, data.endUs - 1, 1000);
  assert.match(tntCarryInLabel(beforeEnd), /73 awaiting a receive observation/);
  assert.doesNotMatch(tntCarryInLabel(beforeEnd), /capture end/);
  assert.equal(tntCarryInLabel(tntTimeWindow(study, 0, 1)), '');
});
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
test('a selected unsent packet exports no future source identity or row', () => {
  const packet = study.records[500];
  const exported = exportTntPrefix(study, packet.sentUs - 1, packet.ordinal);
  assert.equal(exported.selected.packetId, null);
  assert.equal(exported.selected.occurrence, null);
  assert.equal(exported.selected.sender, null);
  assert.deepEqual(exported.selected.sourceRows, { sender: null, receiver: null });
});
test('matching is unique within the declared published-delay bound and intervals differ explicitly', () => {
  assert.ok(data.source.matchingCheck.shortestReuseGapUs > data.source.matchingCheck.maximumDelayUs);
  assert.equal(data.source.matchingCheck.candidatesWithinBoundPerReceiver, 1);
  assert.ok(Math.abs(data.source.interval.publishedReceiveSpanUs / 1e6 - Number(data.publishedSummary.total_time_s)) < 1e-6);
  assert.ok(data.endUs > data.source.interval.publishedReceiveSpanUs);
});
test('malformed source rows, missing-delay states and send ordering fail during load', () => {
  const invalidMissing = structuredClone(data);
  invalidMissing.records.find((r) => r.receivedUs === null).delayUs = 10;
  assert.throws(() => createTntStudy(invalidMissing));
  const invalidOrder = structuredClone(data); invalidOrder.records[10].sentUs = 0;
  assert.throws(() => createTntStudy(invalidOrder));
  const invalidRow = structuredClone(data); invalidRow.records[0].sourceRows.sender = null;
  assert.throws(() => createTntStudy(invalidRow));
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
  assert.equal(elapsedLabel(59_999_999, true), '00:01:00.000');
  assert.equal(elapsedLabel(3_599_999_999, true), '01:00:00.000');
  assert.ok(data.limits.some((text) => text.includes('No application acknowledgement')));
});

test('time weave exposes exactly the sent prefix and no future receiver endpoints', () => {
  const packet = study.records.find((r) => r.delayUs === Math.max(...study.records.map((r) => r.delayUs || 0)));
  for (const at of [0, packet.sentUs, packet.receivedUs - 1, packet.receivedUs, data.endUs]) {
    const window = tntTimeWindow(study, at, packet.ordinal), snapshot = tntSnapshot(study, at, packet.ordinal);
    assert.equal(window.observations.length, snapshot.counts.sent);
    assert.equal(window.observations.filter((r) => r.receivedUs !== null).length, snapshot.counts.received);
    assert.equal(window.observations.filter((r) => r.state === 'awaiting').length, snapshot.counts.awaiting);
    assert.equal(window.observations.filter((r) => r.state === 'not-observed').length, snapshot.counts.notObserved);
    assert.ok(window.observations.every((r) => r.sentUs <= at && (r.receivedUs === null || r.receivedUs <= at)));
  }
});
test('around-packet window never uses a future send or future receive to position its axis', () => {
  const packet = study.records[500], at = packet.sentUs - 1;
  const hidden = tntTimeWindow(study, at, packet.ordinal);
  const altered = structuredClone(data); altered.records[500].receivedUs += 10_000_000; altered.records[500].delayUs += 10_000_000;
  const changed = tntTimeWindow(createTntStudy(altered), at, packet.ordinal);
  assert.deepEqual(hidden, changed);
  assert.equal(hidden.endUs - hidden.startUs, 480_000_000);
  assert.equal(hidden.anchor, 'replay-before-send');
  assert.equal(tntTimeWindow(study, packet.sentUs, packet.ordinal).anchor, 'visible-send');
  assert.equal(hidden.observations.some((r) => r.ordinal === packet.ordinal), false);
});
test('whole time axis preserves the same evidence prefix and holds missing rows until the end', () => {
  const at = Math.floor(data.endUs / 2);
  const fullAxis = tntTimeWindow(study, at, 1, 'capture'), packetAxis = tntTimeWindow(study, at, 1);
  assert.equal(fullAxis.startUs, 0); assert.equal(fullAxis.endUs, data.endUs);
  assert.deepEqual(fullAxis.observations, packetAxis.observations);
  assert.equal(fullAxis.observations.some((r) => r.state === 'not-observed'), false);
  assert.equal(tntTimeWindow(study, data.endUs, 1).observations.filter((r) => r.state === 'not-observed').length, 73);
});

test('following the replay clock keeps its line in the window after the selected send leaves view', () => {
  const at = 1_200_000_000;
  const window = tntTimeWindow(study, at, 1, 'replay');
  assert.ok(window.startUs <= at && window.endUs >= at);
  assert.ok(window.startUs > study.records[0].sentUs);
  assert.deepEqual(window.observations, tntTimeWindow(study, at, 1, 'packet').observations);
});
