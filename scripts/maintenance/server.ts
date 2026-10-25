/** Loopback-only specimen host. No arbitrary tools, paths or shell from requests. */
import { createHash, randomUUID } from 'node:crypto';
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { planSha256, phaseFromBench, appendSnapshot, applyReconciliation, mayDispatch } from './state.mjs';

const root = resolve(import.meta.dir, '../..');
const data = resolve(root, 'artifacts/maintenance/accounts');
const rpcRoot = process.env.MAINTENANCE_RPC_ROOT || resolve(root, 'artifacts/maintenance/vendor/raivari-rpc');
const provenance = JSON.parse(await readFile(resolve(root, 'docs/design/maintenance-acceptance-provenance.json'), 'utf8'));
async function checkedRpc() {
  const observed = await Promise.all(provenance.files.filter((item: any) => item.repo === 'raivari-rpc').map(async (item: any) => ({ ...item, sha256: createHash('sha256').update(await readFile(resolve(rpcRoot, item.path))).digest('hex') })));
  if (JSON.stringify(observed) !== JSON.stringify(provenance.files.filter((item: any) => item.repo === 'raivari-rpc'))) throw Error('RPC runtime source differs from the pinned file hashes');
  return observed;
}
const rpcFiles = await checkedRpc();
const { evaluateToolExecutionGuard, fingerprintToolExecutionInput } = await import(resolve(rpcRoot, 'packages/rpc/src/guard.ts'));
const port = Number(process.env.MAINTENANCE_PORT || 8796);
const ajoRoot = process.env.MAINTENANCE_AJO_ROOT || '/tmp/mg-maintenance-20261025/ajo';
const hosts = process.env.MAINTENANCE_HOSTS || '/tmp/mg-maintenance-20261025/hosts';
const runtimeRoot = process.env.MAINTENANCE_DATA_ROOT || '/tmp/mg-maintenance-20261025/runs';
const script = root.replaceAll('\\', '/').replace(/^([A-Za-z]):/, (_, drive) => '/mnt/' + drive.toLowerCase()) + '/scripts/maintenance/runtime.py';
const bridgeUrl = 'http://127.0.0.1:8797';
const adapterHash = createHash('sha256').update(Buffer.concat(await Promise.all(['bridge.py', 'runtime.py', 'relay.py', 'contracts.py'].map((name) => readFile(resolve(import.meta.dir, name)))))).digest('hex');
const configurationHash = createHash('sha256').update(JSON.stringify([ajoRoot, hosts, runtimeRoot])).digest('hex');
function checkedBridge(identity: any) {
  if (identity.service !== 'mg-maintenance-bridge' || identity.adapterSha256 !== adapterHash || identity.configurationSha256 !== configurationHash || JSON.stringify(identity.files) !== JSON.stringify(provenance.files.filter((item: any) => item.repo === 'ajo'))) throw Error('A different, stale or unpinned adapter owns port 8797. Stop that owned adapter before starting this version.');
  return identity;
}
await mkdir(data, { recursive: true });
let bridgeAvailable = false;
let bridgeIdentity: any = null;
try { bridgeIdentity = await (await fetch(bridgeUrl + '/health')).json(); } catch { /* Start the owned local bridge below. */ }
if (bridgeIdentity) checkedBridge(bridgeIdentity);
bridgeAvailable = Boolean(bridgeIdentity);
if (!bridgeAvailable) {
  const bridgeArgs = ['python3', script.replace(/runtime\.py$/, 'bridge.py'), '--ajo-root', ajoRoot, '--hosts', hosts, '--data-root', runtimeRoot, '--manifest', script.replace(/scripts\/maintenance\/runtime.py$/, 'docs/design/maintenance-acceptance-provenance.json')];
  Bun.spawn(process.platform === 'win32' ? ['wsl.exe', '-d', 'Ubuntu', '--', ...bridgeArgs] : bridgeArgs, { stdin: 'ignore', stdout: 'ignore', stderr: 'inherit' });
}
const sha = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const catalog = 'mg.maintenance.config.v1';
const manifestHash = sha({ catalog, tool: 'fs-replace@1', path: 'document.txt', acceptance: 'http-station-response-v1' });
let busy = false;
async function runtime(run: string, command: string, scenario = 'lost-reply', approvedPlanSha256?: string) {
  const response = await fetch(bridgeUrl + '/action', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-MG-Bridge': '1' }, body: JSON.stringify({ run, command, scenario, approvedPlanSha256 }), signal: AbortSignal.timeout(45_000) });
  const body = await response.json();
  if (!response.ok) throw Error('Ajo adapter failed: ' + body.error);
  return body;
}
async function save(state: any) {
  const target = resolve(data, state.runId + '.json');
  const temporary = target + '.tmp';
  await writeFile(temporary, JSON.stringify(state, null, 2));
  await rename(temporary, target);
}
async function account(run: string) { return JSON.parse(await readFile(resolve(data, run + '.json'), 'utf8')); }
async function reconcile(state: any) {
  if (applyReconciliation(state, await runtime(state.runId, 'snapshot'))) await save(state);
  return state;
}
function envelope(state: any) { return { format: 'mg.maintenance-acceptance.v1', capturedAt: Date.now(), evidenceMode: 'live-local', ...state }; }
async function act(body: any) {
  const allowed = ['create', 'approve', 'dispatch', 'recover', 'verify', 'changed-input'];
  if (!allowed.includes(body.action)) throw Error('unknown action');
  let state: any;
  if (body.action === 'create') {
    const runId = randomUUID().replaceAll('-', '');
    const scenario = body.scenario === 'acceptance-held' ? 'acceptance-held' : 'lost-reply';
    const bench = await runtime(runId, 'create', scenario);
    const identity = checkedBridge(await (await fetch(bridgeUrl + '/health')).json());
    state = { runId, scenario, phase: 'prepared', bench, guardEvents: [], approval: null, history: [], sources: provenance.sources, runtimeIdentity: { adapterSha256: adapterHash, files: [...identity.files, ...rpcFiles], binarySha256: identity.binarySha256, ocamlVersion: identity.ocamlVersion }, };
    state.bench = await runtime(runId, 'check');
  } else {
    if (!/^[a-f0-9]{32}$/.test(body.runId || '')) throw Error('invalid run');
    state = await reconcile(await account(body.runId));
    const operationId = state.bench.session + ':apply';
    if (body.action === 'approve') {
      if (!['prepared', 'approved'].includes(state.phase)) throw Error('approval belongs to an undispatched run');
      state.approval = { evidenceId: randomUUID(), source: 'operator-review', operationId, toolCatalogId: catalog, reviewedManifestHash: manifestHash, inputFingerprint: fingerprintToolExecutionInput(state.bench.payload), planSha256: planSha256(state.bench.plan), outcome: 'approved', reviewedAt: new Date().toISOString(), expiresAt: new Date(Date.now() + 10 * 60_000).toISOString(), toolName: 'fs-replace@1', subject: 'local-bench-operator' };
      state.phase = 'approved';
    } else if (body.action === 'dispatch' || body.action === 'changed-input') {
      if (state.phase !== 'approved') throw Error('approve this exact change before dispatch');
      const input = body.action === 'changed-input' ? { ...state.bench.payload, content: state.bench.payload.content + '# changed after approval\n' } : state.bench.payload;
      await checkedRpc();
      const result = await evaluateToolExecutionGuard({ operationId, protocol: 'direct', subject: 'local-bench-operator', strictEvidenceBinding: true, inputFingerprint: fingerprintToolExecutionInput(input), descriptor: { toolName: 'fs-replace@1', toolCatalogId: catalog, manifestHash, reviewedManifestHash: manifestHash, manifestState: 'verified', allowlistState: 'allowed', revocationState: 'active', reviewOutcome: 'approved', reviewedAt: state.approval.reviewedAt, staleAfterDays: 1, dangerous: true, requiresReview: true, isolated: false }, authorizationProvider: { authorize: () => ({ approval: state.approval }) } });
      state.guardEvents.push({ at: Date.now(), component: '@navivra/rpc/guard', operationId, result });
      if (mayDispatch(body.action, result)) {
        state.phase = 'dispatching';
        appendSnapshot(state, 'dispatch-pending');
        await save(state);
        try { state.bench = await runtime(state.runId, 'dispatch', state.scenario, state.approval.planSha256); }
        catch (error) { try { await reconcile(state); } catch { /* Persisted dispatch intent prevents a blind repeat. */ } throw error; }
        state.phase = phaseFromBench(state.bench, 'dispatching');
      }
    } else if (body.action === 'recover') {
      if (state.phase !== 'interrupted') throw Error('no interrupted action to recover');
      state.bench = await runtime(state.runId, 'recover');
      state.phase = state.bench.journal?.status === 'SUCCEEDED' ? 'recovered' : 'interrupted';
    } else if (body.action === 'verify') {
      if (!['recovered', 'held', 'accepted'].includes(state.phase)) throw Error('recover the original result before acceptance');
      state.bench = await runtime(state.runId, 'verify');
      state.phase = state.bench.verification.accepted ? 'accepted' : 'held';
    }
  }
  appendSnapshot(state, body.action);
  await save(state);
  return envelope(state);
}
const mime: Record<string, string> = { '.html': 'text/html', '.css': 'text/css', '.mjs': 'text/javascript', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.woff2': 'font/woff2' };
const server = Bun.serve({ hostname: '127.0.0.1', port, async fetch(req) {
  const url = new URL(req.url);
  try {
    if (url.hostname !== '127.0.0.1' && url.hostname !== 'localhost') return new Response('Loopback only', { status: 403 });
    if (url.pathname === '/api/maintenance/health') {
      const bridge = await (await fetch(bridgeUrl + '/health', { signal: AbortSignal.timeout(3000) })).json();
      checkedBridge(bridge); await checkedRpc();
      return Response.json({ service: 'maintenance-acceptance', version: 1 });
    }
    if (url.pathname === '/api/maintenance/action') {
      if (req.method !== 'POST' || req.headers.get('X-MG-Workbench') !== '1' || (req.headers.get('Origin') && req.headers.get('Origin') !== url.origin)) return new Response('Same-origin workbench requests only', { status: 403 });
      if (busy) return Response.json({ error: 'Another bench action is in progress.' }, { status: 409 });
      busy = true;
      try { const text = await req.text(); if (text.length > 4096) throw Error('request too large'); return Response.json(await act(JSON.parse(text)), { headers: { 'Cache-Control': 'no-store' } }); }
      finally { busy = false; }
    }
    if (url.pathname.startsWith('/api/maintenance/run/')) {
      const id = url.pathname.split('/').at(-1)!;
      if (!/^[a-f0-9]{32}$/.test(id)) return new Response('Invalid run', { status: 400 });
      if (busy) return Response.json({ error: 'An action is still settling. Reopen after it finishes.' }, { status: 409 });
      busy = true;
      try { return Response.json(envelope(await reconcile(await account(id))), { headers: { 'Cache-Control': 'no-store' } }); }
      finally { busy = false; }
    }
    let relative = decodeURIComponent(url.pathname);
    if (relative.endsWith('/')) relative += 'index.html';
    const site = resolve(root, 'docs');
    const path = resolve(site, '.' + relative);
    if (!path.startsWith(site + sep)) return new Response('Not found', { status: 404 });
    const file = Bun.file(path);
    if (!(await file.exists())) return new Response('Not found', { status: 404 });
    return new Response(file, { headers: { 'Content-Type': mime[path.slice(path.lastIndexOf('.'))] || 'application/octet-stream', 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-cache' } });
  } catch (error) { return Response.json({ error: String(error) }, { status: 400 }); }
} });
console.log(`Maintenance acceptance: http://127.0.0.1:${server.port}/specimens/maintenance-acceptance/?mode=live`);
