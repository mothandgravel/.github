import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const origin = process.env.MAINTENANCE_URL || 'http://127.0.0.1:8796';
const root = resolve(import.meta.dirname, '../..');
async function action(action, runId, scenario) {
  const r = await fetch(origin + '/api/maintenance/action', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-MG-Workbench': '1' }, body: JSON.stringify({ action, runId, scenario }) });
  const body = await r.json(); assert.equal(r.ok, true, JSON.stringify(body)); return body;
}
const cases = [];
for (const scenario of ['lost-reply', 'acceptance-held']) {
  let state = await action('create', null, scenario);
  assert.equal(state.bench.actions.at(-1).result.ok, true, 'native checker accepts the plan');
  state = await action('approve', state.runId);
  if (scenario === 'lost-reply') {
    state = await action('changed-input', state.runId);
    assert.equal(state.guardEvents.at(-1).result.receipt.reason, 'approval-binding-mismatch');
    assert.equal(state.bench.journal, null, 'blocked input never reaches Ajo execution');
    assert.equal(state.bench.physicalWrites.length, 0);
  }
  state = await action('dispatch', state.runId);
  const operation = () => state.bench.receiver.operations[state.bench.session + ':apply'];
  assert.equal(state.phase, 'interrupted');
  assert.equal(state.bench.actions.at(-1).result.crashed, true, 'actual evaluator subprocess exits at the injected boundary');
  assert.equal(state.bench.journal.ops.apply.state, 'IN_FLIGHT');
  assert.equal(operation().starts, 1);
  assert.equal(operation().queries, 0);
  assert.equal(operation().receipt.status, 'SUCCEEDED');
  assert.equal(state.bench.physicalWrites.length, 1, 'receiver records an actual file replacement');
  state = await action('recover', state.runId);
  assert.equal(state.phase, 'recovered');
  assert.equal(state.bench.journal.status, 'SUCCEEDED');
  assert.equal(operation().starts, 1, 'recovery must not repeat the original start');
  assert.equal(operation().queries, 1, 'recovery queries the original receiver operation');
  assert.equal(state.bench.physicalWrites.length, 1);
  state = await action('verify', state.runId);
  assert.equal(state.bench.verification.matchesApprovedBytes, true);
  assert.equal(state.bench.verification.loadedApprovedConfiguration, true);
  assert.equal(state.bench.verification.httpStatus, scenario === 'lost-reply' ? 200 : 503);
  assert.equal(state.bench.verification.accepted, scenario === 'lost-reply');
  assert.equal(state.phase, scenario === 'lost-reply' ? 'accepted' : 'held');
  const reopened = await (await fetch(origin + '/api/maintenance/run/' + state.runId)).json();
  assert.equal(reopened.phase, state.phase);
  assert.equal(reopened.bench.session, state.bench.session);
  cases.push({ scenario, record: { ...state, evidenceMode: 'recorded-runtime' } });
}
const bundle = { format: 'mg.maintenance-acceptance.capture.v1', capturedAt: Date.now(), method: 'HTTP actions against the local Ajo OCaml/filesystem receiver and unchanged Raivari RPC guard; no model requests.', cases };
const bytes = JSON.stringify(bundle, null, 2) + '\n';
await writeFile(resolve(root, 'docs/assets/maintenance-acceptance-recordings.json'), bytes);
const identity = cases[0].record.runtimeIdentity;
const hashes = identity.files;
const provenance = { format: 'mg.maintenance-acceptance.provenance.v1', capturedAt: bundle.capturedAt, captureSha256: createHash('sha256').update(bytes).digest('hex'), sources: cases[0].record.sources, files: hashes, runtime: { ajo: 'unchanged OCaml evaluator and POSIX filesystem receiver', ocaml: identity.ocamlVersion, nativeBinarySha256: identity.binarySha256, adapterSha256: identity.adapterSha256, rpc: 'unchanged Raivari RPC execution guard, Bun host', interruption: 'injected evaluator exit after receiver commit', acceptance: 'separate-process HTTP station request and file readback' }, limits: ['Real local HTTP relay and file operation; no physical equipment or deployed-site validation.', 'Controlled process exit does not establish power-loss durability.', 'Same-host evidence is not independent attestation.', 'RPC allowed decision is a preflight result, not a signature or atomic lease.', 'Only captured runtime evidence is bundled; private runtime source stays outside the public site.'], runs: cases.map(({ scenario, record }) => ({ scenario, runId: record.runId, phase: record.phase, originalStarts: record.bench.receiver.operations[record.bench.session + ':apply'].starts, receiverQueries: record.bench.receiver.operations[record.bench.session + ':apply'].queries, fileReplacements: record.bench.physicalWrites.length })) };
await writeFile(resolve(root, 'docs/design/maintenance-acceptance-provenance.json'), JSON.stringify(provenance, null, 2) + '\n');
console.log(JSON.stringify({ verifiedCases: cases.length, sha256: provenance.captureSha256, bytes: bytes.length, runs: provenance.runs }, null, 2));
