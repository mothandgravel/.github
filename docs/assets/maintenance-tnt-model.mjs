/** Historical observations only. Replay never produces a network or application receipt. */
export function createTntStudy(data) {
  if (data?.format !== 'mg.maintenance-tnt.v1' || !Array.isArray(data.records) || !data.records.length || !data.source?.files || typeof data.source.clock !== 'string' || typeof data.source.matching !== 'string' || !Array.isArray(data.limits)) throw Error('Unsupported TNT record');
  const records = data.records;
  for (const [index, record] of records.entries()) {
    const sourceRow = (value) => Number.isSafeInteger(value) && value >= 2;
    if (record.ordinal !== index + 1 || !Number.isSafeInteger(record.sentUs) || record.sentUs < 0 || (index && record.sentUs < records[index - 1].sentUs) || !record.sender || record.packetId !== record.sender.packet_id || !Number.isSafeInteger(record.occurrence) || record.occurrence < 1 || !sourceRow(record.sourceRows?.sender) || (record.receivedUs === null ? record.delayUs !== null || record.receiver !== null || record.sourceRows?.receiver !== null : !Number.isSafeInteger(record.receivedUs) || record.receivedUs < record.sentUs || record.delayUs !== record.receivedUs - record.sentUs || !record.receiver || !sourceRow(record.sourceRows?.receiver))) throw Error('Invalid recorded event');
  }
  const events = records.flatMap((record) => [{ kind: 'sent', atUs: record.sentUs, ordinal: record.ordinal }, ...(record.receivedUs === null ? [] : [{ kind: 'received', atUs: record.receivedUs, ordinal: record.ordinal }])]).sort((a, b) => a.atUs - b.atUs || (a.kind === b.kind ? a.ordinal - b.ordinal : a.kind === 'sent' ? -1 : 1));
  if (!Number.isSafeInteger(data.endUs) || data.endUs !== events.at(-1).atUs) throw Error('Invalid capture end');
  return { data, records, events };
}

export function packetState(record, cursorUs, endUs) {
  if (record.sentUs > cursorUs) return 'unsent';
  if (record.receivedUs !== null && record.receivedUs <= cursorUs) return 'received';
  if (record.receivedUs === null && cursorUs >= endUs) return 'not-observed';
  return 'awaiting';
}

export function tntSnapshot(study, requestedUs, ordinal = 1) {
  const cursorUs = Math.round(Math.max(0, Math.min(study.data.endUs, Number.isFinite(requestedUs) ? requestedUs : 0)));
  const record = study.records[Math.max(0, Math.min(study.records.length - 1, Number.isFinite(ordinal) ? Math.trunc(ordinal) - 1 : 0))];
  const states = study.records.map((r) => packetState(r, cursorUs, study.data.endUs));
  const counts = { sent: states.filter((s) => s !== 'unsent').length, received: states.filter((s) => s === 'received').length, awaiting: states.filter((s) => s === 'awaiting').length, notObserved: states.filter((s) => s === 'not-observed').length };
  const state = packetState(record, cursorUs, study.data.endUs);
  const sent = state !== 'unsent', arrived = state === 'received';
  const selected = { ordinal: record.ordinal, packetId: sent ? record.packetId : null, occurrence: sent ? record.occurrence : null, state, sentUs: sent ? record.sentUs : null, receivedUs: arrived ? record.receivedUs : null, delayUs: arrived ? record.delayUs : null, waitingUs: sent ? (arrived ? record.delayUs : cursorUs - record.sentUs) : null, sender: sent ? record.sender : null, receiver: arrived ? record.receiver : null, sourceRows: { sender: sent ? record.sourceRows.sender : null, receiver: arrived ? record.sourceRows.receiver : null } };
  return { cursorUs, ended: cursorUs === study.data.endUs, counts, states, selected, recentEvents: study.events.filter((event) => event.atUs <= cursorUs).slice(-5) };
}

export function exportTntPrefix(study, cursorUs, ordinal) {
  const snapshot = tntSnapshot(study, cursorUs, ordinal);
  return { format: 'mg.maintenance-tnt.export.v1', evidence: 'recorded-radio-bench', revision: study.data.source.revision, sourceFiles: study.data.source.files, clock: study.data.source.clock, matching: study.data.source.matching, cursorUs: snapshot.cursorUs, counts: snapshot.counts, selected: snapshot.selected, events: study.events.filter((event) => event.atUs <= snapshot.cursorUs), limits: study.data.limits };
}

export function elapsedLabel(us, precise = false) {
  if (us === null || us === undefined) return '—';
  const totalMs = precise ? Math.round(Math.max(0, us) / 1000) : Math.floor(Math.max(0, us) / 1_000_000) * 1000;
  const seconds = Math.floor(totalMs / 1000);
  const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds / 60) % 60;
  const tail = String(seconds % 60).padStart(2, '0') + (precise ? '.' + String(totalMs % 1000).padStart(3, '0') : '');
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${tail}`;
}

/** Plot geometry uses a fixed time window, never the selected packet's future receive. */
export function tntTimeWindow(study, cursorUs, ordinal, scope = 'packet') {
  const snapshot = tntSnapshot(study, cursorUs, ordinal);
  const spanUs = 480_000_000;
  const anchorUs = scope === 'replay' ? snapshot.cursorUs - 300_000_000 : (snapshot.selected.sentUs ?? snapshot.cursorUs);
  const startUs = scope === 'capture' ? 0 : Math.max(0, Math.min(study.data.endUs - spanUs, anchorUs - 60_000_000));
  const endUs = scope === 'capture' ? study.data.endUs : Math.min(study.data.endUs, startUs + spanUs);
  const observations = study.records.filter((record) => record.sentUs <= snapshot.cursorUs).map((record) => {
    const receivedUs = record.receivedUs !== null && record.receivedUs <= snapshot.cursorUs ? record.receivedUs : null;
    return { ordinal: record.ordinal, sentUs: record.sentUs, receivedUs, state: packetState(record, snapshot.cursorUs, study.data.endUs) };
  });
  const anchor = scope === 'capture' ? 'whole-record-axis' : scope === 'replay' ? 'replay-clock' : snapshot.selected.sentUs === null ? 'replay-before-send' : 'visible-send';
  return { scope: ['capture', 'replay'].includes(scope) ? scope : 'packet', anchor, startUs, endUs, cursorUs: snapshot.cursorUs, ordinal: snapshot.selected.ordinal, observations };
}
