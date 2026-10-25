import { createHash } from 'node:crypto';
export function planSha256(plan) {
  const sorted = (value) => Array.isArray(value) ? value.map(sorted) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, sorted(value[key])])) : value;
  return createHash('sha256').update(JSON.stringify(sorted(plan))).digest('hex');
}
export function phaseFromBench(bench, fallback) {
  if (bench.journal?.status === 'SUCCEEDED') return bench.verification ? bench.verification.accepted ? 'accepted' : 'held' : 'recovered';
  if (bench.journal) return 'interrupted';
  if (bench.actions?.at(-1)?.action === 'dispatch-refused' && !Object.keys(bench.receiver?.operations || {}).length && !bench.physicalWrites?.length) return 'refused';
  return fallback;
}
export function appendSnapshot(state, action) {
  const snapshot = structuredClone(state);
  delete snapshot.history;
  state.history.push({ action, at: Date.now(), snapshot });
}
export function applyReconciliation(state, bench) {
  const phase = phaseFromBench(bench, state.phase);
  const changed = phase !== state.phase || JSON.stringify(bench) !== JSON.stringify(state.bench);
  state.bench = bench; state.phase = phase;
  if (changed) appendSnapshot(state, 'reconcile');
  return changed;
}
export function mayDispatch(action, guardResult) { return action === 'dispatch' && guardResult.decision === 'allow'; }
