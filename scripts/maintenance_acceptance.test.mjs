import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { maintenanceProjection, maintenanceEvidence, exportMaintenancePrefix } from '../docs/assets/maintenance-acceptance-model.mjs';
import { applyReconciliation, mayDispatch, planSha256 } from './maintenance/state.mjs';
const bytes = await readFile(new URL('../docs/assets/maintenance-acceptance-recordings.json', import.meta.url));
const bundle = JSON.parse(bytes);
const provenance = JSON.parse(await readFile(new URL('../docs/design/maintenance-acceptance-provenance.json', import.meta.url)));
test('recordings match their captured provenance and declared component revisions', () => {
  assert.equal(createHash('sha256').update(bytes).digest('hex'), provenance.captureSha256);
  assert.equal(provenance.sources.ajo, 'ec205b9925add515b2b7408cbc8ee73737fcec55');
  assert.equal(provenance.sources.rpc, '80ca8c6cc28440e5eab7abccbece7282ecbb56ab');
  assert.equal(bundle.cases.length, 2);
});
test('public evidence has no nested adapter context', () => assert.equal(bytes.includes('adapter_context'), false));
test('captures retain runtime-observed source hashes and approved plan binding', () => {
  for (const { record } of bundle.cases) {
    assert.deepEqual(record.runtimeIdentity.files, provenance.files);
    assert.match(record.runtimeIdentity.binarySha256, /^[a-f0-9]{64}$/);
    assert.equal(record.runtimeIdentity.ocamlVersion, provenance.runtime.ocaml);
    const approved = record.history.find((h) => h.action === 'approve').snapshot;
    assert.equal(approved.approval.planSha256, planSha256(approved.bench.plan));
  }
});
test('lost host reply reopens the committed native account without another dispatch', () => {
  const r = bundle.cases[0].record;
  const state = structuredClone(r.history.find((h) => h.action === 'approve').snapshot);
  state.history = []; state.phase = 'dispatching';
  const committed = r.history.find((h) => h.action === 'dispatch').snapshot.bench;
  assert.equal(applyReconciliation(state, committed), true);
  assert.equal(state.phase, 'interrupted');
  assert.equal(maintenanceProjection(state).starts, 1);
  const recovered = r.history.find((h) => h.action === 'recover').snapshot.bench;
  applyReconciliation(state, recovered);
  assert.equal(state.phase, 'recovered');
  assert.equal(maintenanceProjection(state).writes, 1);
});
test('a changed-input guard probe can never dispatch even if a guard returns allow', () => {
  assert.equal(mayDispatch('changed-input', { decision: 'allow' }), false);
  assert.equal(mayDispatch('dispatch', { decision: 'block' }), false);
  assert.equal(mayDispatch('dispatch', { decision: 'allow' }), true);
});
test('approved plan digest is stable across property order but binds actual effects', () => {
  assert.equal(planSha256({ b: 2, a: 1 }), planSha256({ a: 1, b: 2 }));
  assert.notEqual(planSha256({ content: 'reviewed' }), planSha256({ content: 'changed' }));
});
test('a lagging relay does not claim the approved configuration enables maintenance', () => {
  const snapshot = structuredClone(bundle.cases[1].record.history.at(-1).snapshot);
  snapshot.bench.verification.loadedApprovedConfiguration = false;
  const p = maintenanceProjection(snapshot);
  assert.equal(p.title, 'Acceptance stays open.');
  assert.equal(p.copy.includes('still enables maintenance'), false);
});
test('receiver success does not clear operator uncertainty or imply acceptance', () => {
  const record = bundle.cases[0].record;
  const s = record.history.find((h) => h.action === 'dispatch').snapshot;
  const p = maintenanceProjection(s);
  assert.equal(s.bench.actions.at(-1).result.crashed, true);
  assert.equal(p.journalOperation.state, 'IN_FLIGHT');
  assert.equal(p.receiver.receipt.status, 'SUCCEEDED');
  assert.equal(p.operator, 'UNKNOWN');
  assert.equal(p.accepted, null);
  assert.equal(p.starts, 1); assert.equal(p.writes, 1); assert.equal(p.queries, 0);
});
test('captured recovery retains original operation identity and one file replacement', () => {
  for (const { record } of bundle.cases) {
    const before = maintenanceProjection(record.history.find((h) => h.action === 'dispatch').snapshot);
    const after = maintenanceProjection(record.history.find((h) => h.action === 'recover').snapshot);
    assert.equal(before.operationId, after.operationId);
    assert.equal(after.starts, 1); assert.equal(after.writes, 1); assert.equal(after.queries, 1);
    assert.equal(after.operator, 'CONFIRMED'); assert.equal(after.accepted, null);
  }
});
test('a real successful receipt can coexist with held acceptance', () => {
  const record = bundle.cases[1].record;
  const s = record.history.at(-1).snapshot;
  assert.equal(maintenanceProjection(s).receiver.receipt.status, 'SUCCEEDED');
  assert.equal(s.bench.verification.matchesApprovedBytes, true);
  assert.equal(maintenanceProjection(s).accepted, false);
  assert.equal(s.bench.verification.httpStatus, 503);
  assert.equal(s.bench.verification.response.status, 'maintenance');
  assert.equal(s.bench.verification.loadedApprovedConfiguration, true);
});
test('accepted handback includes a real HTTP response from the loaded relay', () => {
  const verification = bundle.cases[0].record.history.at(-1).snapshot.bench.verification;
  assert.equal(verification.httpStatus, 200);
  assert.equal(verification.response.service, 'site-status-relay');
  assert.equal(verification.response.status, 'serving');
  assert.equal(verification.response.configurationSha256, verification.sha256);
  assert.match(verification.response.requestId, /^[a-f0-9-]{36}$/);
  assert.equal(verification.loadedApprovedConfiguration, true);
});
test('changed-input RPC refusal precedes all evaluator effects', () => {
  const s = bundle.cases[0].record.history.find((h) => h.action === 'changed-input').snapshot;
  const refusal = s.guardEvents.at(-1).result;
  assert.equal(refusal.receipt.schemaVersion, 'raivari.tool-execution-guard-receipt.v1');
  assert.equal(refusal.receipt.executionState, 'not-invoked');
  assert.equal(refusal.receipt.reason, 'approval-binding-mismatch');
  assert.equal(s.bench.journal, null); assert.equal(maintenanceProjection(s).writes, 0);
});
test('export and evidence inspection at an interruption do not include later recovery', () => {
  const record = bundle.cases[0].record;
  const cursor = record.history.findIndex((h) => h.action === 'dispatch');
  const exported = exportMaintenancePrefix(record, cursor);
  assert.equal(exported.history.length, cursor + 1);
  assert.equal(exported.snapshot.phase, 'interrupted');
  assert.equal(exported.snapshot.bench.verification, null);
  assert.equal(maintenanceEvidence(exported.snapshot, 'verification').value.accepted, null);
  assert.equal(exported.history.some((h) => h.action === 'recover'), false);
});
