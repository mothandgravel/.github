import { maintenanceProjection, maintenanceEvidence, exportMaintenancePrefix } from './maintenance-acceptance-model.mjs';
const $ = (id) => document.getElementById(id);
const names = { create: 'Prepared', approve: 'Approved', dispatch: 'Execution observed', 'dispatch-pending': 'Dispatch intent saved', reconcile: 'Account reopened', recover: 'Receipt recovered', verify: 'Acceptance checked', 'changed-input': 'Changed-input guard check' };
let bundle, record, cursor = 0, kind = 'receiver', timer = null, local = false, activeRun = null, busy = false;
const say = (text, error = false) => { $('ma-status').textContent = text; $('ma-status').dataset.error = String(error); };
const timestamp = (value) => value ? new Date(value).toISOString().replace('T', ' ').replace('.000Z', ' UTC').replace('Z', ' UTC') : '—';
const stop = () => { clearInterval(timer); timer = null; $('ma-play').textContent = 'Play the account'; $('ma-play').setAttribute('aria-pressed', 'false'); };
function selected() { return record?.history?.[cursor]?.snapshot; }
function render() {
  if (!record) return;
  const s = selected(), p = maintenanceProjection(s), evidence = maintenanceEvidence(s, kind);
  const serviceMode = (text) => String(text || '').match(/service_mode = ([a-z]+)/)?.[1] || 'unknown';
  const currentMode = serviceMode(s.bench.document), targetMode = serviceMode(s.bench.payload.content);
  $('ma-config-current').textContent = currentMode === 'active' ? 'Active' : currentMode === 'maintenance' ? 'Maintenance' : 'Unknown';
  $('ma-config-target').textContent = targetMode === 'active' ? 'Active' : targetMode === 'maintenance' ? 'Maintenance' : 'Unknown';
  $('ma-change-note').textContent = targetMode === 'maintenance' ? 'This proposal leaves maintenance mode enabled. A successful write can still leave the station waiting.' : 'This proposal enables station responses. The running service still needs its own check.';
  $('ma-bench').dataset.phase = p.phase;
  $('ma-operation').textContent = p.operationId ?? 'Not dispatched';
  $('ma-starts').textContent = p.starts;
  $('ma-queries').textContent = p.queries;
  $('ma-writes').textContent = p.writes;
  $('ma-accepted').textContent = p.accepted === null ? 'Not checked' : p.accepted ? 'Accepted' : s.bench.verification?.loadedApprovedConfiguration && s.bench.verification?.httpStatus === 503 ? 'Held' : 'Open';
  const verification = s.bench.verification;
  $('ma-station').dataset.result = verification ? verification.accepted ? 'accepted' : 'held' : 'unchecked';
  $('ma-http-code').textContent = verification?.httpStatus ? `HTTP ${verification.httpStatus}` : verification ? 'Unavailable' : '—';
  const heldMaintenance = verification?.httpStatus === 503 && verification.loadedApprovedConfiguration && verification.response?.status === 'maintenance';
  $('ma-http-state').textContent = verification ? verification.accepted ? 'The station can resume.' : heldMaintenance ? 'Still in maintenance.' : 'Acceptance stays open.' : 'The station is waiting.';
  $('ma-http-copy').textContent = verification ? verification.httpStatus ? `A separate client received a real ${verification.httpStatus} response from the running relay. ${verification.accepted ? 'The reviewed configuration is loaded.' : heldMaintenance ? 'The reviewed configuration still enables maintenance.' : 'The response has not met every acceptance condition. Inspect its loaded digest and the disk readback.'}` : 'The local relay did not respond. Acceptance remains open; this does not undo the recovered file-operation receipt.' : 'Recover the original receipt, then make the station’s request. No readiness result is assumed.';
  $('ma-loaded').textContent = verification ? verification.loadedApprovedConfiguration ? 'Reviewed revision' : 'Different / unknown' : 'Not observed';
  $('ma-latency').textContent = verification ? `${verification.elapsedMs} ms · ${verification.attempts?.length || 1} request(s)` : 'Not measured';
  $('ma-operator-state').textContent = p.operator;
  $('ma-mobile-operator').textContent = p.operator; $('ma-mobile-receiver').textContent = p.receiverLabel;
  $('ma-operator-detail').textContent = ['interrupted', 'dispatching'].includes(p.phase) ? 'reply unresolved' : ['prepared', 'refused'].includes(p.phase) ? 'not started' : p.phase === 'approved' ? 'input reviewed' : 'receipt recovered';
  $('ma-receiver-state').textContent = p.receiverLabel;
  $('ma-receiver-detail').textContent = p.starts ? `${p.starts} start · ${p.queries} q` : 'not started';
  $('ma-link-text').textContent = p.phase === 'interrupted' ? 'NO REPLY' : p.queries ? 'QUERIED' : p.starts ? 'SENT' : 'WAITING';
  $('ma-acceptance-text').textContent = p.accepted === null ? 'STATION / NOT CHECKED' : verification.httpStatus ? `STATION / HTTP ${verification.httpStatus}` : 'STATION / UNAVAILABLE';
  $('ma-diagram-desc').textContent = `Operator ${p.operator}; receiver ${p.receiverLabel}. ${p.starts} starts, ${p.queries} queries, ${p.writes} replacements. Station ${verification ? `HTTP ${verification.httpStatus}; acceptance ${p.accepted ? 'accepted' : 'held'}` : 'not checked'}.`;
  $('ma-phase-title').textContent = p.title;
  $('ma-phase-copy').textContent = p.copy;
  $('ma-phase-index').textContent = `${String(cursor + 1).padStart(2, '0')} / ${names[record.history[cursor].action] || p.phase}`;
  $('ma-evidence-note').textContent = evidence.note;
  $('ma-json').textContent = JSON.stringify(evidence.value, null, 2);
  $('ma-evidence-age').textContent = `Snapshot ${timestamp(record.history[cursor].at)}`;
  $('ma-capture').textContent = `${activeRun ? 'Received' : 'Captured'} ${timestamp(record.capturedAt)}`;
  $('ma-mode-label').textContent = activeRun ? 'Local runtime / real file operation' : 'Recorded runtime evidence';
  $('ma-view-label').textContent = `${activeRun ? 'Local' : 'Recorded'} step ${cursor + 1} of ${record.history.length}`;
  $('ma-cursor-label').textContent = `Step ${cursor + 1} / ${record.history.length} · ${names[record.history[cursor].action]}`;
  $('ma-cursor').max = record.history.length - 1;
  $('ma-cursor').value = cursor;
  $('ma-prev').disabled = cursor === 0;
  $('ma-next').disabled = cursor === record.history.length - 1;
  $('ma-export').disabled = false;
  $('ma-current').hidden = !activeRun || cursor === record.history.length - 1;
  $('ma-actions').hidden = !activeRun;
  $('ma-new').hidden = !local;
  $('ma-new').disabled = busy;
  const current = cursor === record.history.length - 1 && !busy && !timer;
  $('ma-approve').disabled = !current || !['prepared', 'approved'].includes(s.phase);
  $('ma-dispatch').disabled = !current || s.phase !== 'approved';
  $('ma-changed').disabled = !current || s.phase !== 'approved';
  $('ma-recover').disabled = !current || s.phase !== 'interrupted';
  $('ma-verify').disabled = !current || !['recovered', 'held', 'accepted'].includes(s.phase);
  $('ma-refresh').disabled = busy;
  $('ma-scenario').disabled = busy;
  $('ma-steps').replaceChildren(...record.history.map((entry, i) => {
    const li = document.createElement('li'), button = document.createElement('button');
    button.type = 'button'; button.textContent = `${String(i + 1).padStart(2, '0')} / ${names[entry.action] || entry.action}`;
    if (i === cursor) button.setAttribute('aria-current', 'step');
    button.addEventListener('click', () => { stop(); cursor = i; render(); }); li.append(button); return li;
  }));
}
function loadRecorded() {
  stop(); activeRun = null;
  record = bundle.cases.find((c) => c.scenario === $('ma-scenario').value).record;
  cursor = Math.max(0, record.history.findIndex((entry) => entry.action === 'dispatch')); render();
  say('Captured runtime evidence. Replay changes only your view; it sends no actions.');
}
async function action(action) {
  if (busy || !local) return;
  stop(); busy = true; render(); say('Waiting for the local runtime. Evidence will appear when the action settles.');
  try {
    const response = await fetch('/api/maintenance/action', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-MG-Workbench': '1' }, body: JSON.stringify({ action, runId: activeRun, scenario: $('ma-scenario').value }) });
    const body = await response.json(); if (!response.ok) throw Error(body.error || `HTTP ${response.status}`);
    record = body; activeRun = body.runId; cursor = record.history.length - 1;
    try { sessionStorage.setItem('mg-maintenance-run-v2', activeRun); } catch { /* Export remains available. */ }
    kind = action === 'changed-input' ? 'guard' : action === 'verify' ? 'verification' : kind;
    const guard = record.guardEvents.at(-1)?.result;
    say(['dispatch', 'changed-input'].includes(action) && guard?.decision !== 'allow' ? `Raivari RPC did not permit execution: ${guard?.receipt?.reason || guard?.decision}. Ajo was not invoked.` : action === 'changed-input' ? 'Guard probe complete. No execution action was sent. Inspect the original result.' : action === 'dispatch' && record.phase === 'interrupted' ? 'The execution account is interrupted. Query the original operation to recover its result.' : 'Local evidence received. Open the records or continue the account.');
  } catch (error) {
    if (activeRun) { try { await refreshAccount(false); } catch { /* Explicit reopen stays available. */ } }
    say(`The request did not complete: ${error.message}. The saved account was reopened where available; inspect it before continuing.`, true);
  }
  finally { busy = false; updateTabs(); render(); }
}
async function refreshAccount(announce = true) {
  if (!activeRun) return;
  const response = await fetch('/api/maintenance/run/' + activeRun);
  const body = await response.json(); if (!response.ok) throw Error(body.error || 'Account unavailable');
  record = body; cursor = record.history.length - 1;
  if (announce) { stop(); say('Reopened the native journal and receiver account. This sent no execution action.'); render(); }
}
$('ma-refresh').addEventListener('click', () => refreshAccount().catch((error) => say(error.message, true)));
function updateTabs() { document.querySelectorAll('[data-evidence]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.evidence === kind))); }
for (const button of document.querySelectorAll('[data-evidence]')) button.addEventListener('click', () => { kind = button.dataset.evidence; $('ma-evidence-drawer').open = true; updateTabs(); render(); });
$('ma-prev').addEventListener('click', () => { stop(); cursor = Math.max(0, cursor - 1); render(); });
$('ma-next').addEventListener('click', () => { stop(); cursor = Math.min(record.history.length - 1, cursor + 1); render(); });
$('ma-cursor').addEventListener('input', () => { stop(); cursor = Number($('ma-cursor').value); render(); });
$('ma-current').addEventListener('click', () => { stop(); cursor = record.history.length - 1; render(); });
$('ma-play').addEventListener('click', () => {
  if (timer) { stop(); render(); return; }
  if (!record) return;
  if (cursor === record.history.length - 1) cursor = 0;
  $('ma-play').textContent = 'Pause the account'; $('ma-play').setAttribute('aria-pressed', 'true');
  timer = setInterval(() => { if (cursor >= record.history.length - 1) stop(); else cursor++; render(); }, 2200); render();
});
$('ma-scenario').addEventListener('change', () => { if (!activeRun) loadRecorded(); else say('Scenario selected for the next local run. The current run and its evidence stay intact.'); });
$('ma-export').addEventListener('click', () => {
  const value = exportMaintenancePrefix(record, cursor);
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = `maintenance-${record.runId}-step-${cursor + 1}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('ma-connect').addEventListener('click', () => { if (local) { $('ma-new').focus(); say('Local runtime ready. Start a new run to make a fresh, isolated file change.'); } else { $('ma-local-instructions').open = true; $('ma-local-instructions').scrollIntoView({ block: 'start' }); } });
for (const [id, command] of [['new', 'create'], ['approve', 'approve'], ['dispatch', 'dispatch'], ['recover', 'recover'], ['verify', 'verify'], ['changed', 'changed-input']]) $('ma-' + id).addEventListener('click', () => action(command));
document.addEventListener('visibilitychange', () => { if (document.hidden) { stop(); render(); } });
try {
  const response = await fetch('../../assets/maintenance-acceptance-recordings.json');
  if (!response.ok) throw Error(`recordings HTTP ${response.status}`);
  bundle = await response.json(); loadRecorded();
  if (new URLSearchParams(location.search).get('mode') === 'live') {
    const health = await fetch('/api/maintenance/health');
    if (!health.ok || (await health.json()).service !== 'maintenance-acceptance') throw Error('local runtime is unavailable');
    local = true; $('ma-connect').textContent = 'Local runtime connected'; $('ma-new').hidden = false;
    let saved; try { saved = sessionStorage.getItem('mg-maintenance-run-v2'); } catch { /* No saved run. */ }
    if (/^[a-f0-9]{32}$/.test(saved || '')) {
      const restored = await fetch('/api/maintenance/run/' + saved);
      if (restored.ok) { record = await restored.json(); activeRun = saved; cursor = record.history.length - 1; $('ma-scenario').value = record.scenario; }
    }
    say(activeRun ? 'Reopened the saved local account. Page reload has sent no action.' : 'Local runtime connected. The diagram still shows a captured run. Start a new local run to create fresh evidence.'); render();
  }
} catch (error) { say(`Could not open the requested evidence: ${error.message}. The records are not replaced with synthetic outcomes.`, true); }
