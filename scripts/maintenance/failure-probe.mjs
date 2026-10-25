/** Destructive fault injection only into newly-created, isolated laboratory runs. */
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const exec = promisify(execFile);
const root = resolve(import.meta.dirname, '../..');
const origin = process.env.MAINTENANCE_URL || 'http://127.0.0.1:8796';
async function action(action, runId, ok = true) {
  const r = await fetch(origin + '/api/maintenance/action', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-MG-Workbench': '1' }, body: JSON.stringify({ action, runId }) });
  const body = await r.json(); assert.equal(r.ok, ok, JSON.stringify(body)); return body;
}
let state = await action('create');
state = await action('approve', state.runId);
const preReply = structuredClone(state);
delete preReply.format; delete preReply.capturedAt; delete preReply.evidenceMode;
state = await action('dispatch', state.runId);
assert.equal(state.bench.physicalWrites.length, 1);
// Emulate host death after the native commit but before its account checkpoint.
await writeFile(resolve(root, 'artifacts/maintenance/accounts', state.runId + '.json'), JSON.stringify(preReply));
state = await (await fetch(origin + '/api/maintenance/run/' + state.runId)).json();
assert.equal(state.phase, 'interrupted');
state = await action('recover', state.runId);
assert.equal(state.phase, 'recovered');
assert.equal(state.bench.receiver.operations[state.bench.session + ':apply'].starts, 1);
assert.equal(state.bench.physicalWrites.length, 1);
const recoveredRun = state.runId;
// A different native plan after approval must be refused before the evaluator starts.
state = await action('create'); state = await action('approve', state.runId);
const nativeRoot = process.env.MAINTENANCE_DATA_ROOT || '/tmp/mg-maintenance-20261025/runs';
const mutate = "import json,sys; from pathlib import Path; p=Path(sys.argv[1])/sys.argv[2]/'bench.json'; r=json.loads(p.read_text()); r['plan']['tree']['children'][0]['payload']['literal']['content'] += '# unreviewed change\\n'; p.write_text(json.dumps(r))";
const args = ['python3', '-c', mutate, nativeRoot, state.runId];
await exec(process.platform === 'win32' ? 'wsl.exe' : 'python3', process.platform === 'win32' ? ['-d', 'Ubuntu', '--', ...args] : args.slice(1));
await action('dispatch', state.runId, false);
state = await (await fetch(origin + '/api/maintenance/run/' + state.runId)).json();
assert.equal(state.bench.journal, null);
assert.equal(state.bench.physicalWrites.length, 0);
const mutatedPlanRun = state.runId;
state = await action('create'); state = await action('approve', state.runId);
const accountPath = resolve(root, 'artifacts/maintenance/accounts', state.runId + '.json');
const expired = JSON.parse(await readFile(accountPath, 'utf8'));
expired.approval.expiresAt = '2020-01-01T00:00:00.000Z';
await writeFile(accountPath, JSON.stringify(expired));
state = await action('dispatch', state.runId);
assert.equal(state.guardEvents.at(-1).result.decision, 'block');
assert.equal(state.bench.journal, null);
state = await action('approve', state.runId);
state = await action('dispatch', state.runId);
assert.equal(state.phase, 'interrupted');
assert.equal(state.bench.physicalWrites.length, 1);
const result = { observedAt: Date.now(), recoveredRun, mutatedPlanRun, renewedApprovalRun: state.runId, lostHostCheckpointRecovered: true, originalStarts: 1, fileReplacements: 1, changedNativePlanRefusedBeforeExecution: true, expiredApprovalBlockedThenRenewed: true };
await mkdir(resolve(root, 'artifacts/maintenance'), { recursive: true });
await writeFile(resolve(root, 'artifacts/maintenance/failure-probe.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
