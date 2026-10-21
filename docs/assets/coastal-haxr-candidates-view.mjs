import { haxrPixels } from "./coastal-haxr-core.mjs?v=branches-1";
import { MAX_HYPOTHESES } from "./coastal-haxr-motion.mjs?v=branches-1";

const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
const $ = id => document.getElementById(`hx-${id}`);
const state = s => ({ ambiguous: "Competing patches", weak: "Texture changed", stopped: "Stopped", seed: "Selected seed", matched: "Texture match retained", "before-seed": "Before seed", insufficient: "Insufficient texture", "unusable-seed": "Unusable seed" })[s];

// Both the thumbnail and numeric table read the original raster, including nulls.
function patchCard(frame, point, max, title, subtitle) {
  const card = el("article", undefined, "hx-patch-card");
  card.append(el("p", subtitle, "hx-label"), el("h4", title));
  const canvas = el("canvas"); canvas.width = canvas.height = 200;
  canvas.setAttribute("role", "img"); canvas.setAttribute("aria-label", `5 by 5 patch at column ${point.col}, row ${point.row}. Original amplitudes in the expandable table below.`);
  const ctx = canvas.getContext("2d"), colors = haxrPixels(frame.pixels, max), values = [];
  for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) {
    const col = point.col + x - 2, row = point.row + y - 2;
    const offset = row * 128 + col, inside = col >= 0 && col < 128 && row >= 0 && row < 128;
    const value = inside ? frame.pixels[offset] : null; values.push(value);
    ctx.fillStyle = value === null ? "#1e3033" : `rgb(${colors[offset * 4]},${colors[offset * 4 + 1]},${colors[offset * 4 + 2]})`;
    ctx.fillRect(x * 40, y * 40, 40, 40);
    ctx.strokeStyle = "#3b4d4c"; ctx.lineWidth = 1; ctx.strokeRect(x * 40, y * 40, 40, 40);
    if (value === null) { ctx.beginPath(); ctx.moveTo(x * 40, y * 40 + 40); ctx.lineTo(x * 40 + 40, y * 40); ctx.stroke(); }
  }
  ctx.strokeStyle = "#fff4d1"; ctx.lineWidth = 2; ctx.strokeRect(81, 81, 38, 38);
  card.append(canvas, el("p", `Bin ${point.col} / ${point.row} · ${values.filter(v => v !== null).length}/25 measured`, "hx-small"));
  const details = el("details"), table = el("table"), body = el("tbody");
  details.append(el("summary", "Inspect raw amplitudes"));
  table.append(el("caption", `Rows ${point.row - 2}–${point.row + 2}, columns ${point.col - 2}–${point.col + 2}. — = missing or outside raster; 0 = measured zero.`));
  for (let y = 0; y < 5; y++) { const row = el("tr"); for (let x = 0; x < 5; x++) row.append(el("td", values[y * 5 + x] === null ? "—" : String(values[y * 5 + x]))); body.append(row); }
  table.append(body); details.append(table); card.append(details);
  return card;
}

export function drawCandidates({ ledger, activeId, index, recording, max, choose, visit, time }) {
  const active = ledger.get(activeId), h = active.follow, entries = ledger.entries();
  const select = $("motion-account"); select.replaceChildren();
  for (const e of entries) { const o = el("option", `${e.id} · ${e.parentId ? `from ${e.parentId}, candidate ${e.decision.rank + 1}` : "original follow"} · seed ${e.follow.seed.index + 1}`); o.value = e.id; select.append(o); }
  select.value = activeId;
  $("motion-account-count").textContent = `${entries.length} / ${MAX_HYPOTHESES} hypotheses · 01 shared AIS family · no association established`;
  const ancestry = $("motion-ancestry"); ancestry.replaceChildren();
  let ancestor = active;
  while (ancestor.parentId) {
    const child = ancestor, parent = ledger.get(child.parentId), d = child.decision;
    const block = el("div", undefined, "hx-choice-receipt");
    block.append(el("p", `${parent.id} → ${child.id} / MANUAL CHOICE`, "hx-label"));
    block.append(el("p", index < d.frameIndex ? `This choice belongs to frame ${d.frameIndex + 1}, beyond the cursor. No branch position is shown before its seed.` : `At frame ${d.frameIndex + 1}, ${parent.id} stopped: ${state(d.parentState).toLowerCase()}. You chose candidate ${d.rank + 1} for a fresh template. The parent still has no accepted position at that stop.`, "hx-small"));
    block.append(el("p", `Original correlation ${d.candidate.correlation.toFixed(3)} · margin ${d.parentMargin === null ? "no runner-up" : d.parentMargin.toFixed(3)} · ${d.candidate.pairedBins}/25 measured pairs. The choice adds a hypothesis, not a witness.`, "hx-small"));
    const button = el("button", `Inspect ${parent.id} at its stop ↑`); button.type = "button"; button.addEventListener("click", () => visit(parent.id, d.frameIndex)); block.append(button); ancestry.append(block);
    ancestor = parent;
  }
  const comparison = $("motion-account-comparison"); comparison.replaceChildren();
  for (const e of entries) {
    const step = e.follow.steps[index], row = el("div");
    row.dataset.active = String(e.id === activeId);
    row.append(el("dt", `${e.id} · ${state(step.state)}`), el("dd", step.accepted ? `${step.accepted.east.toFixed(1)} E / ${step.accepted.north.toFixed(1)} N m` : "No retained position")); comparison.append(row);
  }
  $("motion-comparison-time").textContent = `Same station, frame ${index + 1} / ${time(h.steps[index].endTod)} UTC frame end. Positions use station-local coordinates; each hypothesis has its own displacement origin. Full-window account choices remain listed when you rewind.`;
  const section = $("motion-candidates"), cards = $("motion-candidate-cards"); cards.replaceChildren();
  const stopStep = h.steps.find(s => s.index <= index && ["ambiguous", "weak", "insufficient", "unusable-seed"].includes(s.state));
  section.hidden = !stopStep;
  if (!stopStep) return;
  $("motion-stop-detail").textContent = `${activeId} / frame ${stopStep.index + 1} / ${time(stopStep.startTod)}–${time(stopStep.endTod)} UTC. ${state(stopStep.state)}. No accepted radar position. ${index > stopStep.index ? `Replay is now at frame ${index + 1}; these patches remain frozen at the earlier stop.` : ""}`;
  const jump = $("motion-stop-jump"); jump.hidden = index === stopStep.index; jump.onclick = () => visit(activeId, stopStep.index);
  $("motion-candidate-summary").textContent = stopStep.candidates.length ? `Top ${stopStep.candidates.length} of ${stopStep.candidateCount} scored candidates. Required correlation ≥ ${h.policy.minCorrelation.toFixed(2)}; lead ≥ ${h.policy.minMargin.toFixed(2)}. Actual lead: ${stopStep.margin === null ? "no runner-up" : stopStep.margin.toFixed(3)}. Correlation is texture similarity, not probability.` : "There is no scored candidate to continue from. Missing or flat texture cannot supply a branch. You can inspect another measured bin to start a new account.";
  cards.append(patchCard(recording.frames[h.seed.index], h.seed, max, "Original template", `${activeId} / SEED FRAME ${h.seed.index + 1}`));
  stopStep.candidates.forEach((candidate, rank) => {
    const card = patchCard(recording.frames[stopStep.index], candidate, max, `Candidate ${rank + 1}`, `STOP FRAME ${stopStep.index + 1} / RANK ${rank + 1}`);
    const metric = el("p", candidate.correlation.toFixed(3), "hx-patch-score"); metric.append(el("span", "texture correlation")); card.append(metric);
    card.append(el("p", `${candidate.pairedBins}/25 common measured bins · centre amplitude ${candidate.amplitude} · ${Math.hypot(candidate.east - stopStep.searchCentre.east, candidate.north - stopStep.searchCentre.north).toFixed(1)} m from last retained centre`, "hx-small"));
    const existing = entries.find(e => e.parentId === activeId && e.decision.frameIndex === stopStep.index && e.decision.rank === rank);
    const button = el("button", existing ? `Open ${existing.id} from candidate ${rank + 1} →` : `Branch from candidate ${rank + 1} →`); button.type = "button"; button.dataset.candidate = rank;
    button.disabled = !existing && entries.length >= MAX_HYPOTHESES;
    button.addEventListener("click", () => choose(stopStep.index, rank)); card.append(button);
    if (button.disabled) card.append(el("p", "Account limit reached. Export before clearing or starting another seed.", "hx-small"));
    cards.append(card);
  });
}
