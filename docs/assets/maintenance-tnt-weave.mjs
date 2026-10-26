import { elapsedLabel } from './maintenance-tnt-model.mjs';

/** One fixed curve between recorded timestamps. No route, signal strength or future link. */
export function drawTntWeave(canvas, window) {
  const box = canvas.getBoundingClientRect(), width = box.width, height = width < 540 ? 310 : 340;
  if (!width) return [];
  canvas.style.height = height + 'px';
  const dpr = Math.min(devicePixelRatio || 1, 2);
  canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
  const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const style = getComputedStyle(canvas), gold = style.getPropertyValue('--gold-bright').trim(), muted = style.getPropertyValue('--muted').trim(), line = style.getPropertyValue('--line-soft').trim();
  const left = 32, right = width - 32, top = 65, bottom = height - 68;
  const x = (time) => left + (time - window.startUs) / Math.max(1, window.endUs - window.startUs) * (right - left);
  ctx.font = '10px ' + getComputedStyle(document.documentElement).getPropertyValue('--mono').trim(); ctx.fillStyle = muted;
  ctx.fillText('SENDER / RECORDED SEND', left, 25); ctx.fillText('RECEIVER / RECORDED RECEIVE', left, height - 18);
  ctx.lineWidth = 1; ctx.strokeStyle = line;
  for (const y of [top, bottom]) { ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke(); }
  const tickCount = width < 380 ? 1 : width < 620 ? 2 : 6;
  for (let i = 0; i <= tickCount; i++) {
    const time = window.startUs + (window.endUs - window.startUs) * i / tickCount, px = x(time);
    ctx.strokeStyle = line; ctx.beginPath(); ctx.moveTo(px, top - 8); ctx.lineTo(px, bottom + 8); ctx.stroke();
    ctx.textAlign = i === 0 ? 'left' : i === tickCount ? 'right' : 'center'; ctx.fillStyle = muted;
    ctx.fillText('+' + elapsedLabel(time), px, height - 39);
  }
  ctx.textAlign = 'left';
  if (window.cursorUs < window.endUs) {
    const at = Math.max(left, x(window.cursorUs)); ctx.fillStyle = line; ctx.globalAlpha = .6; ctx.fillRect(at, top, right - at, bottom - top); ctx.globalAlpha = 1;
    ctx.save(); ctx.beginPath(); ctx.rect(at, top, right - at, bottom - top); ctx.clip(); ctx.strokeStyle = line; ctx.lineWidth = .7;
    for (let h = at - (bottom - top); h < right; h += 13) { ctx.beginPath(); ctx.moveTo(h, bottom); ctx.lineTo(h + bottom - top, top); ctx.stroke(); }
    ctx.restore();
  }
  const hits = [];
  const visible = window.observations.filter((r) => r.sentUs <= window.endUs && (r.receivedUs ?? r.sentUs) >= window.startUs);
  const ordered = [...visible.filter((r) => r.ordinal !== window.ordinal), ...visible.filter((r) => r.ordinal === window.ordinal)];
  ctx.save(); ctx.beginPath(); ctx.rect(left - 9, top - 10, right - left + 18, bottom - top + 20); ctx.clip();
  for (const r of ordered) {
    const selected = r.ordinal === window.ordinal, sx = x(r.sentUs), rx = r.receivedUs === null ? null : x(r.receivedUs);
    ctx.strokeStyle = gold; ctx.fillStyle = gold; ctx.globalAlpha = selected ? 1 : window.scope === 'capture' ? .14 : .38; ctx.lineWidth = selected ? 2 : .8;
    if (rx !== null) {
      ctx.beginPath(); ctx.moveTo(sx, top); ctx.bezierCurveTo(sx, top + (bottom - top) * .42, rx, bottom - (bottom - top) * .42, rx, bottom); ctx.stroke();
      ctx.globalAlpha = selected ? 1 : .5; ctx.beginPath(); ctx.arc(rx, bottom, selected ? 4.5 : 2.1, 0, Math.PI * 2); ctx.fill();
      if (rx >= left && rx <= right) hits.push({ x: rx, y: bottom, ordinal: r.ordinal });
    } else {
      ctx.globalAlpha = selected ? 1 : .5; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(sx, top + 9); ctx.lineTo(sx, top + 33); ctx.stroke(); ctx.setLineDash([]);
      if (r.state === 'not-observed') { ctx.beginPath(); ctx.moveTo(sx - 5, top + 38); ctx.lineTo(sx + 5, top + 28); ctx.stroke(); }
    }
    ctx.globalAlpha = selected ? 1 : .65; ctx.beginPath(); ctx.arc(sx, top, selected ? 5 : 2.3, 0, Math.PI * 2); ctx.fillStyle = style.backgroundColor; ctx.fill(); ctx.stroke();
    if (sx >= left && sx <= right) hits.push({ x: sx, y: top, ordinal: r.ordinal });
  }
  ctx.restore(); ctx.globalAlpha = 1; ctx.setLineDash([]);
  const earlier = window.observations.filter((r) => r.sentUs < window.startUs && ['awaiting', 'not-observed'].includes(r.state));
  if (earlier.length) {
    const awaiting = earlier.filter((r) => r.state === 'awaiting').length;
    const label = `${awaiting ? awaiting + ' awaiting' : earlier.length + ' without receive rows'} / sent before window`;
    ctx.fillStyle = style.backgroundColor; ctx.fillRect(left, top + 42, ctx.measureText(label).width + 16, 24);
    ctx.fillStyle = muted; ctx.fillText(label, left + 7, top + 58);
  }
  if (window.cursorUs >= window.startUs && window.cursorUs <= window.endUs) {
    const at = x(window.cursorUs); ctx.strokeStyle = gold; ctx.lineWidth = 1; ctx.setLineDash([2, 5]); ctx.beginPath(); ctx.moveTo(at, top - 15); ctx.lineTo(at, bottom + 15); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = gold; ctx.textAlign = at > width / 2 ? 'right' : 'left'; ctx.fillText('REPLAY POINT', at + (at > width / 2 ? -7 : 7), 45);
  }
  const joined = visible.filter((r) => r.receivedUs !== null).length;
  canvas.setAttribute('aria-label', `Recorded time weave from ${elapsedLabel(window.startUs)} to ${elapsedLabel(window.endUs)}. ${joined} visible send-receive pairs. ${earlier.length} unjoined sends are earlier than this window. Only observations through ${elapsedLabel(window.cursorUs, true)} are included. Packet ${window.ordinal} selected. Use the labelled packet controls for keyboard inspection.`);
  return hits;
}
