export function maintenanceProjection(snapshot) {
  const bench = snapshot?.bench;
  const operationId = bench ? `${bench.session}:apply` : null;
  const receiver = bench?.receiver?.operations?.[operationId] ?? null;
  const journalOperation = bench?.journal?.ops?.apply ?? null;
  const phase = snapshot?.phase ?? 'prepared';
  const v = bench?.verification;
  const heldMaintenance = v?.httpStatus === 503 && v.loadedApprovedConfiguration && v.response?.status === 'maintenance';
  const descriptions = {
    prepared: ['A change, still on the desk.', 'The plan has been checked by Ajo. No operation has started. Permission to execute this exact input is still missing.'],
    approved: ['Permission is not an effect.', 'The operator record names this operation and this input. Nothing has changed at the receiver. A changed input must pass a new approval check.'],
    interrupted: ['The receiver kept its part.', 'The file replacement happened. Then the evaluator stopped before saving its acknowledgement. The operator’s journal is still in flight; its outcome must be treated as unknown. The receiver has a different account.'],
    recovered: ['The original result comes back.', 'Ajo resumed the original execution and queried the same operation. It recovered the receiver’s result without starting the file change again. Acceptance has its own check.'],
    accepted: ['The station gets its answer.', 'The original change is confirmed. A separate client requested the running status relay: HTTP 200, with the reviewed configuration digest. The station’s side of this laboratory handback now passes.'],
    held: heldMaintenance ? ['The relay is still in maintenance.', 'The receiver performed the approved change. But the running relay responds HTTP 503: its approved configuration still enables maintenance mode. The station cannot resume. Acceptance stays held.'] : ['Acceptance stays open.', 'The station check has not established a serving response with the approved bytes loaded. Inspect the observed response and configuration before checking again.'],
    dispatching: ['The reply is still unresolved.', 'Dispatch intent was saved. Reopen the receiver account to inspect what happened before attempting any further action. No second dispatch is available.'],
  };
  if (phase === 'interrupted' && receiver?.receipt?.status !== 'SUCCEEDED') descriptions.interrupted = ['The outcome is still unknown.', 'An execution journal exists, but this snapshot has no successful receiver receipt. Query the original operation; do not assume the change landed.'];
  return {
    phase, operationId, receiver, journalOperation,
    starts: receiver?.starts ?? 0,
    queries: receiver?.queries ?? 0,
    writes: bench?.physicalWrites?.length ?? 0,
    accepted: bench?.verification?.accepted ?? null,
    title: descriptions[phase]?.[0] ?? 'An account to inspect.',
    copy: descriptions[phase]?.[1] ?? 'Inspect the underlying record before drawing a conclusion.',
    operator: ['interrupted', 'dispatching'].includes(phase) ? 'UNKNOWN' : ['recovered', 'accepted', 'held'].includes(phase) ? 'CONFIRMED' : phase === 'approved' ? 'APPROVED' : 'PREPARED',
    receiverLabel: receiver?.receipt?.status === 'SUCCEEDED' ? 'APPLIED' : 'UNCHANGED',
  };
}

export function maintenanceEvidence(snapshot, kind) {
  const p = maintenanceProjection(snapshot);
  if (kind === 'receiver') return { note: 'Original Ajo filesystem-receiver record. Starts and queries are separate. A receiver receipt is not an acceptance decision.', value: p.receiver ?? { state: 'not-started', operationId: p.operationId } };
  if (kind === 'journal') return { note: 'Decoded Ajo journal, as saved at this step. IN_FLIGHT after the injected evaluator exit leaves the outcome unknown.', value: snapshot?.bench?.journal ?? { state: 'no-execution-journal' } };
  if (kind === 'guard') return { note: 'Host-owned operator approval and unchanged Raivari RPC guard results. An allowed preflight decision is not a signature or a runtime receipt.', value: { operatorApproval: snapshot?.approval ?? null, guardEvaluations: snapshot?.guardEvents ?? [] } };
  if (kind === 'verification') return { note: 'Actual HTTP station request to a separate running relay process, plus file readback. This is local service evidence, not deployed equipment validation.', value: snapshot?.bench?.verification ?? { state: 'not-checked', accepted: null } };
  return { note: 'The exact plan submitted to Ajo. The file path and effects are fixed by the local host, not selected by a page visitor.', value: snapshot?.bench?.plan ?? null };
}

export function exportMaintenancePrefix(record, cursor) {
  const index = Math.max(0, Math.min(record.history.length - 1, cursor));
  return { format: 'mg.maintenance-acceptance.export.v1', evidenceMode: record.evidenceMode, capturedAt: record.capturedAt, selectedStep: index, snapshot: record.history[index].snapshot, history: record.history.slice(0, index + 1) };
}
