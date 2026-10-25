import { createTntStudy, tntSnapshot, exportTntPrefix, elapsedLabel } from './maintenance-tnt-model.mjs';
const $ = (id) => document.getElementById(id);
let study, cursorUs = 0, ordinal = 1, evidenceKind = 'sender', playing = false, stopUs = null, frame = null, previousTime = null, lastRender = 0, evidenceKey = '';
const say = (message, error = false) => { $('tn-status').textContent = message; $('tn-status').dataset.error = String(error); };
const seconds = (us) => (us / 1e6).toFixed(3) + ' s';
function pause() { playing = false; cancelAnimationFrame(frame); previousTime = null; $('tn-play').textContent = 'Play the capture'; $('tn-play').setAttribute('aria-pressed', 'false'); }

function drawAtlas(snapshot) {
  const canvas = $('tn-atlas'), box = canvas.getBoundingClientRect();
  if (!box.width || !box.height) return;
  const dpr = Math.min(devicePixelRatio || 1, 2), width = Math.round(box.width * dpr), height = Math.round(box.height * dpr);
  if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, box.width, box.height);
  const styles = getComputedStyle(document.documentElement), gold = styles.getPropertyValue('--gold-bright').trim(), muted = styles.getPropertyValue('--muted').trim(), line = styles.getPropertyValue('--line').trim();
  const columns = box.width < 550 ? 25 : 50, rows = Math.ceil(study.records.length / columns), pad = 12, cellW = (box.width - pad * 2) / columns, cellH = (box.height - pad * 2) / rows, size = Math.max(3, Math.min(cellW, cellH) * .53);
  snapshot.states.forEach((state, index) => {
    const x = pad + (index % columns + .5) * cellW, y = pad + (Math.floor(index / columns) + .5) * cellH;
    ctx.globalAlpha = state === 'unsent' ? .5 : 1; ctx.lineWidth = 1; ctx.strokeStyle = state === 'unsent' ? line : state === 'not-observed' ? muted : gold; ctx.fillStyle = gold;
    if (state === 'received') ctx.fillRect(x - size / 2, y - size / 2, size, size);
    else if (state === 'awaiting') { ctx.beginPath(); ctx.moveTo(x, y - size / 2); ctx.lineTo(x + size / 2, y); ctx.lineTo(x, y + size / 2); ctx.lineTo(x - size / 2, y); ctx.closePath(); ctx.stroke(); }
    else if (state === 'not-observed') { ctx.beginPath(); ctx.moveTo(x - size / 2, y + size / 2); ctx.lineTo(x + size / 2, y - size / 2); ctx.stroke(); }
    else ctx.strokeRect(x - size / 2, y - size / 2, size, size);
    if (index + 1 === ordinal) { ctx.globalAlpha = 1; ctx.lineWidth = 1.5; ctx.strokeStyle = gold; ctx.strokeRect(x - cellW * .43, y - cellH * .43, cellW * .86, cellH * .86); }
  });
  ctx.globalAlpha = 1;
  canvas.setAttribute('aria-label', `Recorded packet overview at ${elapsedLabel(snapshot.cursorUs)}. ${snapshot.counts.sent} sent, ${snapshot.counts.received} received, ${snapshot.counts.awaiting} awaiting, ${snapshot.counts.notObserved} not observed by the capture end. Packet ${ordinal} selected. Use the packet controls below to inspect each row.`);
}

function showEvidence(snapshot) {
  const selected = snapshot.selected, key = `${ordinal}:${selected.state}:${evidenceKind}`;
  if (key === evidenceKey) return;
  evidenceKey = key;
  const source = evidenceKind === 'sender' ? selected.sender : selected.receiver;
  let value, note, row;
  if (evidenceKind === 'context') {
    value = { source: study.data.source, failedMatchingControl: study.data.failedControl, limits: study.data.limits };
    note = 'Whole-source context. The failed naive matching control is retained. Original CSV downloads contain the complete historical capture.'; row = 'SOURCE CONTEXT';
  } else if (source) {
    value = source; note = `Unchanged fields from the original ${evidenceKind} CSV row. Timestamp text is shown as recorded; its timezone is unspecified.`; row = `${evidenceKind}.csv · row ${selected.sourceRows[evidenceKind]}`;
  } else {
    value = { state: selected.state, evidence: 'No ' + evidenceKind + ' observation is present at this replay point.' };
    note = selected.state === 'not-observed' ? 'The observed capture has ended without a matching receive row. This is not an application-level failure receipt.' : 'A future observation is not included here. Advancing the replay may reveal a recorded arrival.'; row = 'NO ROW AT THIS POINT';
  }
  $('tn-json').textContent = JSON.stringify(value, null, 2); $('tn-evidence-note').textContent = note; $('tn-row').textContent = row;
  document.querySelectorAll('[data-evidence]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.evidence === evidenceKind)));
}

function render() {
  if (!study) return;
  const snapshot = tntSnapshot(study, cursorUs, ordinal), selected = snapshot.selected;
  cursorUs = snapshot.cursorUs; ordinal = selected.ordinal;
  $('tn-stage').dataset.state = selected.state;
  $('tn-at').textContent = 'Recorded clock +' + elapsedLabel(cursorUs);
  $('tn-send-state').textContent = selected.sender ? 'SENT' : 'NOT YET SENT';
  $('tn-send-time').textContent = selected.sender ? '+' + elapsedLabel(selected.sentUs, true) : 'No sender row at this point';
  $('tn-receive-state').textContent = selected.state === 'received' ? 'RECEIVED' : selected.state === 'not-observed' ? 'NOT OBSERVED' : 'WAITING';
  $('tn-receive-time').textContent = selected.receiver ? '+' + elapsedLabel(selected.receivedUs, true) : selected.state === 'not-observed' ? 'No matching receive row' : 'No receive row at this point';
  $('tn-clock-label').textContent = selected.state === 'received' ? 'RECORDED ONE-WAY DELAY' : selected.state === 'not-observed' ? 'CAPTURE ENDED / NO ARRIVAL' : selected.state === 'unsent' ? 'BEFORE THIS DEPARTURE' : 'ELAPSED SINCE SEND';
  $('tn-wait').textContent = elapsedLabel(selected.waitingUs, true);
  $('tn-state-copy').textContent = selected.state === 'received' ? 'The other end has a matching capture row.' : selected.state === 'not-observed' ? 'The capture contains no receive event for this packet.' : selected.state === 'unsent' ? 'This packet has not been sent at the selected time.' : 'A send is recorded. An arrival has not been observed yet.';
  $('tn-packet-label').textContent = `PACKET ${ordinal} / ID ${selected.packetId} / OCCURRENCE ${selected.occurrence}`;
  $('tn-count-sent').textContent = snapshot.counts.sent.toLocaleString('en'); $('tn-count-received').textContent = snapshot.counts.received.toLocaleString('en');
  $('tn-count-waiting').textContent = snapshot.ended ? snapshot.counts.notObserved : snapshot.counts.awaiting;
  $('tn-count-waiting-label').textContent = snapshot.ended ? 'not observed' : 'awaiting';
  $('tn-cursor').value = Math.round(cursorUs / study.data.endUs * 10000);
  $('tn-cursor').setAttribute('aria-valuetext', '+' + elapsedLabel(cursorUs, true));
  $('tn-cursor-label').textContent = 'Recorded elapsed time +' + elapsedLabel(cursorUs);
  $('tn-packet').value = ordinal;
  $('tn-prev').disabled = ordinal === 1; $('tn-next').disabled = ordinal === study.records.length;
  $('tn-to-receive').disabled = study.records[ordinal - 1].receivedUs === null;
  $('tn-selection').textContent = `Packet ${ordinal} of ${study.records.length}. IPv4 ID ${selected.packetId}, chronological occurrence ${selected.occurrence}. ${selected.state === 'received' ? `Recorded delay ${seconds(selected.delayUs)}.` : selected.state === 'not-observed' ? 'No receive row in the complete capture.' : selected.state === 'unsent' ? 'Its send event is later in the record.' : 'Awaiting a receive observation at this point.'}`;
  drawAtlas(snapshot); showEvidence(snapshot);
}

function tick(time) {
  if (!playing) return;
  if (previousTime === null) previousTime = time;
  cursorUs = Math.min(stopUs ?? study.data.endUs, cursorUs + (time - previousTime) * 1000 * Number($('tn-speed').value)); previousTime = time;
  if (cursorUs >= (stopUs ?? study.data.endUs)) { pause(); render(); say(stopUs === study.data.endUs ? 'The observed capture has ended. Missing receive rows are now shown separately.' : 'The selected receive event is now present. Inspect its original source row.'); return; }
  if (time - lastRender >= 80) { render(); lastRender = time; }
  frame = requestAnimationFrame(tick);
}

function play(until = study.data.endUs) { stopUs = until; playing = true; previousTime = null; $('tn-play').textContent = 'Pause the capture'; $('tn-play').setAttribute('aria-pressed', 'true'); frame = requestAnimationFrame(tick); }
function selectPacket(value, seek = false) { if (!study) return; pause(); ordinal = Math.max(1, Math.min(study.records.length, Math.trunc(Number(value)) || 1)); if (seek || cursorUs < study.records[ordinal - 1].sentUs) cursorUs = study.records[ordinal - 1].sentUs; render(); }

$('tn-play').addEventListener('click', () => { if (!study) return; if (playing) { pause(); render(); return; } if (cursorUs >= study.data.endUs) cursorUs = 0; play(); say('Playing the recorded clock. Display speed changes no source measurement.'); });
$('tn-cursor').addEventListener('input', () => { pause(); cursorUs = Number($('tn-cursor').value) / 10000 * study.data.endUs; render(); });
$('tn-packet').addEventListener('change', () => selectPacket($('tn-packet').value));
$('tn-prev').addEventListener('click', () => selectPacket(ordinal - 1)); $('tn-next').addEventListener('click', () => selectPacket(ordinal + 1));
$('tn-to-send').addEventListener('click', () => { pause(); cursorUs = study.records[ordinal - 1].sentUs; render(); say('At the selected packet’s recorded send event. No later receiver row is included.'); });
$('tn-to-receive').addEventListener('click', () => { pause(); cursorUs = study.records[ordinal - 1].receivedUs; render(); evidenceKind = 'receiver'; evidenceKey = ''; showEvidence(tntSnapshot(study, cursorUs, ordinal)); say('At the selected packet’s recorded receive event.'); });
$('tn-follow').addEventListener('click', () => {
  if (!study) return; pause();
  const packet = study.records.reduce((best, r) => (r.delayUs ?? -1) > (best.delayUs ?? -1) ? r : best);
  ordinal = packet.ordinal; cursorUs = packet.sentUs; $('tn-speed').value = '30'; evidenceKind = 'sender'; render();
  say(`Following this capture’s longest recorded wait: ${seconds(packet.delayUs)}, displayed at 30×. This is the run’s maximum, not its average.`); play(packet.receivedUs);
});
$('tn-missing').addEventListener('click', () => { if (!study) return; pause(); ordinal = study.records.find((r) => r.receivedUs === null).ordinal; cursorUs = study.data.endUs; evidenceKind = 'receiver'; render(); say('Complete-capture inspection. This sent packet has no matching receive row; no application acknowledgement is implied.'); });
$('tn-end').addEventListener('click', () => { if (!study) return; pause(); cursorUs = study.data.endUs; render(); say('Complete capture: 1,000 sent records, 927 receive records and 73 without a matching receive observation.'); });
for (const button of document.querySelectorAll('[data-evidence]')) button.addEventListener('click', () => { if (!study) return; evidenceKind = button.dataset.evidence; showEvidence(tntSnapshot(study, cursorUs, ordinal)); });
$('tn-atlas').addEventListener('click', (event) => {
  if (!study) return;
  const box = $('tn-atlas').getBoundingClientRect(), columns = box.width < 550 ? 25 : 50, rows = Math.ceil(study.records.length / columns);
  const x = event.clientX - box.left - 12, y = event.clientY - box.top - 12;
  if (x < 0 || y < 0 || x >= box.width - 24 || y >= box.height - 24) return;
  selectPacket(Math.floor(y / ((box.height - 24) / rows)) * columns + Math.floor(x / ((box.width - 24) / columns)) + 1);
});
$('tn-export').addEventListener('click', () => {
  if (!study) return;
  const result = exportTntPrefix(study, cursorUs, ordinal), url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = `tnt-packet-${ordinal}-at-${Math.round(cursorUs)}us.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
new ResizeObserver(() => { if (study) drawAtlas(tntSnapshot(study, cursorUs, ordinal)); }).observe($('tn-atlas'));
new MutationObserver(() => { if (study) drawAtlas(tntSnapshot(study, cursorUs, ordinal)); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
document.addEventListener('visibilitychange', () => { if (document.hidden) { pause(); render(); } });
try {
  const response = await fetch('../../../assets/maintenance-tnt.json'); if (!response.ok) throw Error(`HTTP ${response.status}`);
  study = createTntStudy(await response.json());
  const first = study.records[0]; ordinal = first.ordinal; cursorUs = first.sentUs;
  for (const id of ['follow', 'missing', 'end', 'play', 'export', 'prev', 'next', 'to-send', 'packet']) $('tn-' + id).disabled = false;
  $('tn-cursor').disabled = false; $('tn-cursor').max = 10000; $('tn-cursor').step = 1;
  $('tn-duration').textContent = '+' + elapsedLabel(study.data.endUs); render();
  say('Original TNT packet observations loaded. Follow the longest recorded wait, inspect a missing receive, or scrub the complete capture.');
} catch (error) { say(`The measured record could not be opened: ${error.message}. No substitute observations were generated.`, true); }
