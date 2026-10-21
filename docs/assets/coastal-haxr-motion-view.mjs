import { createRadarHypotheses } from "./coastal-haxr-motion.mjs?v=branches-1";
import { drawCandidates } from "./coastal-haxr-candidates-view.mjs?v=branches-1";
import { haxrPixels } from "./coastal-haxr-core.mjs?v=branches-1";
import { BIN_METERS } from "./coastal-haxr-returns.mjs?v=branches-1";
const labels = { seed: "Selected seed", matched: "Texture match retained", ambiguous: "Competing patches", weak: "Texture changed", insufficient: "Insufficient measured texture", stopped: "Following stopped", "unusable-seed": "Seed has too little distinct texture", "before-seed": "Before the selected seed" };
export function createMotionPanel({ stop, selectFrame, redraw, time, names }) {
  const $ = id => document.getElementById(`hx-${id}`);
  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
  let selection = null, ledger = null, activeId = "H01", hypothesis, lastContext;
  function seed(station, index, col, row, uid) {
    selection = { station, index, col, row, uid }; ledger = null; activeId = "H01";
    stop(); selectFrame(station, index);
    $("motion").scrollIntoView({ block: "start", behavior: "smooth" }); $("motion-search").focus({ preventScroll: true });
  }
  $("motion-example").addEventListener("click", () => {
    $("motion-search").value = "2";
    seed("reiherstieg", 0, 46, 40, lastContext.uid);
    selectFrame("reiherstieg", 1);
    $("motion-candidates").scrollIntoView({ block: "start", behavior: "smooth" });
    $("motion-candidate-cards").querySelector("button").focus({ preventScroll: true });
  });
  $("motion-clear").addEventListener("click", () => { stop(); selection = null; ledger = null; redraw(); });
  function visit(id, index) {
    const entry = ledger.get(id); activeId = id;
    selection = { ...entry.follow.seed, station: entry.follow.station, uid: entry.follow.uid };
    stop(); selectFrame(selection.station, index);
    $("motion-account").focus({ preventScroll: true });
  }
  $("motion-account").addEventListener("change", e => visit(e.target.value, lastContext.view.stations[selection.station].index));
  $("motion-play").addEventListener("click", () => {
    if (selection && $("play").getAttribute("aria-pressed") !== "true") {
      const currentIndex = lastContext.view.stations[selection.station].index;
      selectFrame(selection.station, currentIndex === hypothesis.steps.length - 1 ? selection.index : Math.max(selection.index, currentIndex));
    }
    $("play").click();
  });
  function draw(context) {
    lastContext = context;
    const { study, view, uid } = context;
    if (selection && selection.uid !== uid) { selection = null; ledger = null; }
    $("motion-empty").hidden = Boolean(selection); $("motion-content").hidden = !selection;
    if (!selection) { hypothesis = null; return; }
    if (!ledger) ledger = createRadarHypotheses(study.recordings[selection.station], uid, selection, { searchBins: Number($("motion-search").value) });
    hypothesis = ledger.get(activeId).follow;
    const index = view.stations[selection.station].index, current = hypothesis.steps[index];
    const past = hypothesis.steps.filter(s => s.index <= index && s.index >= selection.index);
    $("motion-selection").textContent = `${activeId} · ${names[selection.station]} · bin ${selection.col} / ${selection.row} · seed frame ${selection.index + 1} · AIS ${uid} · 01 shared AIS family · search ±${hypothesis.policy.searchHalfWidthMeters} m`;
    drawCandidates({ ledger, activeId, index, recording: study.recordings[selection.station], max: view.stations[selection.station].max, time, visit,
      choose: (frameIndex, rank) => {
        const child = ledger.branch(activeId, frameIndex, rank); visit(child.id, frameIndex);
        $("motion-accounts").scrollIntoView({ block: "start", behavior: "smooth" });
      } });
    $("motion-state").textContent = labels[current.state];
    $("motion-play").disabled = selection.index === hypothesis.steps.length - 1;
    $("motion-play").textContent = $("play").getAttribute("aria-pressed") === "true" ? "Pause frames" : "Play frames";
    $("motion-play").setAttribute("aria-pressed", $("play").getAttribute("aria-pressed"));
    const strip = $("motion-frames"); strip.replaceChildren();
    for (const step of hypothesis.steps) {
      const button = el("button", String(step.index + 1).padStart(2, "0")); button.type = "button";
      button.id = `hx-motion-frame-${step.index}`; button.dataset.state = step.state;
      button.setAttribute("aria-pressed", String(step.index === index));
      button.setAttribute("aria-label", `Frame ${step.index + 1}: ${labels[step.state]}`);
      const mark = el("span", step.accepted ? "+" : ["weak", "ambiguous", "insufficient", "unusable-seed"].includes(step.state) ? "?" : "—"); mark.setAttribute("aria-hidden", "true"); button.append(mark);
      const move = i => { selectFrame(selection.station, i); $(`motion-frame-${i}`).focus({ preventScroll: true }); };
      button.addEventListener("click", () => move(step.index));
      button.addEventListener("keydown", e => {
        const i = e.key === "Home" ? 0 : e.key === "End" ? hypothesis.steps.length - 1 : e.key === "ArrowRight" ? Math.min(hypothesis.steps.length - 1, step.index + 1) : e.key === "ArrowLeft" ? Math.max(0, step.index - 1) : null;
        if (i !== null) { e.preventDefault(); move(i); }
      }); strip.append(button);
    }
    const canvas = $("motion-canvas"), ctx = canvas.getContext("2d"), origin = hypothesis.seed;
    const span = 500, scale = 480 / span, xy = p => [240 + (p.east - origin.east) * scale, 240 - (p.north - origin.north) * scale];
    ctx.fillStyle = "#101719"; ctx.fillRect(0, 0, 480, 480);
    ctx.strokeStyle = "#263a3c"; ctx.lineWidth = 1;
    for (let x = 0; x < 480; x += 30) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 480); ctx.moveTo(0, x); ctx.lineTo(480, x); ctx.stroke(); }
    const source = document.createElement("canvas"); source.width = source.height = 128;
    source.getContext("2d").putImageData(new ImageData(haxrPixels(view.stations[selection.station].frame.pixels, view.stations[selection.station].max), 128, 128), 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(source, 240 + (-2000 - origin.east) * scale, 240 + (origin.north - 2000) * scale, 4000 * scale, 4000 * scale);
    const box = (p, color, size = 1) => { const [x, y] = xy(p); ctx.strokeStyle = color; ctx.strokeRect(x - 15 * size, y - 15 * size, 30 * size, 30 * size); };
    ctx.lineWidth = 1; ctx.setLineDash([4, 5]); box(origin, "#b8c8c3", 5); ctx.setLineDash([]);
    for (const step of past) if (step.accepted) box(step.accepted, "#c9ad72");
    if (current.accepted) { ctx.lineWidth = 3; box(current.accepted, "#fff4d1"); }
    else for (const candidate of current.candidates) { ctx.setLineDash([3, 5]); box(candidate, "#c9ad72"); ctx.setLineDash([]); }
    if (current.ais) {
      const [x, y] = xy(current.ais); ctx.strokeStyle = "#91ddd4"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(x - 12, y); ctx.lineTo(x + 12, y); ctx.moveTo(x, y - 12); ctx.lineTo(x, y + 12); ctx.stroke();
    }
    ctx.fillStyle = "#e0e9e4"; ctx.font = "12px monospace";
    ctx.fillText("N ↑ / FIXED ON THE SEED", 15, 23); ctx.fillText("500 m across / 31.25 m bins", 15, 461);
    if (current.ais && (Math.abs(current.ais.east - origin.east) > 250 || Math.abs(current.ais.north - origin.north) > 250)) ctx.fillText("AIS OUTSIDE THIS CROP", 15, 43);
    if (current.accepted && (Math.abs(current.accepted.east - origin.east) > 250 || Math.abs(current.accepted.north - origin.north) > 250)) ctx.fillText("RETAINED CENTRE OUTSIDE CROP", 15, 62);
    canvas.setAttribute("aria-label", `${names[selection.station]} frame ${index + 1}. ${labels[current.state]}. Fixed seed context; current AIS ${current.ais ? "eligible" : "unavailable"}.`);
    const vector = v => v ? `${v.east.toFixed(1)} E / ${v.north.toFixed(1)} N m` : "Unavailable";
    const facts = [
      ["Radar displacement from seed", vector(current.radarDisplacement)], ["AIS displacement from seed report", vector(current.aisDisplacement)],
      ["Difference of displacement vectors", current.displacementDifference === null ? "Unavailable" : `${current.displacementDifference.toFixed(1)} m`],
      ["Current radar–AIS separation", current.separationMeters === null ? "Unavailable" : `${current.separationMeters.toFixed(1)} m (bin centre)`],
      ["Best / next texture correlation", current.candidates.length ? current.candidates.map(c => c.correlation.toFixed(3)).join(" / ") : "No candidate comparison"],
      ["Measured pairs in best / 25", current.candidates[0] ? String(current.candidates[0].pairedBins) : "—"],
      ["Amplitude at the original fixed bin", current.fixedBinAmplitude === null ? "Missing" : String(current.fixedBinAmplitude)],
      ["AIS time / age", current.ais ? `${time(current.ais.tod)} / ${current.ais.ageSeconds.toFixed(3)} s` : "No eligible report"],
    ];
    const dl = $("motion-facts"); dl.replaceChildren();
    for (const [k, v] of facts) { const row = el("div"); row.append(el("dt", k), el("dd", v)); dl.append(row); }
    $("motion-time").textContent = `${time(current.startTod)}–${time(current.endTod)} UTC / radar acquisition interval. AIS is selected at frame end; it can postdate individual radar cells.`;
    const moved = current.radarDisplacement && Math.hypot(current.radarDisplacement.east, current.radarDisplacement.north);
    $("motion-reading").textContent = !current.accepted ? "This frame has no retained radar position. A stopped chain is not extended or silently reacquired. Inspect its candidate patches below; a manual branch keeps the original stop."
      : !current.aisDisplacement ? "The radar texture remains inspectable, but there is no eligible AIS displacement comparison. No held or predicted vessel position fills the gap."
      : moved === 0 ? "The retained texture stays in the same raster bin. That is compatible with stationary structure, clutter or a moored vessel; it does not identify shore. Motion smaller than a 31.25 m bin is unresolved here."
      : "The retained texture changes raster bins. Compare both displacement components with AIS below. Similar motion can motivate inspection, but does not establish that this is the same vessel.";
    drawPlot(past, current, hypothesis);
  }
  function drawPlot(past, current, h) {
    const ctx = $("motion-plot").getContext("2d"); ctx.clearRect(0, 0, 600, 320);
    const values = past.flatMap(s => [s.radarDisplacement, s.aisDisplacement].filter(Boolean).flatMap(v => [Math.abs(v.east), Math.abs(v.north)]));
    const bound = Math.max(31.25, ...values), first = h.steps[h.seed.index].endTod, last = h.steps.at(-1).endTod;
    const x = t => 65 + (t - first) / Math.max(.001, last - first) * 510;
    ctx.fillStyle = "#101719"; ctx.fillRect(0, 0, 600, 320); ctx.font = "12px monospace";
    for (const [component, middle, title] of [["east", 88, "EAST"], ["north", 235, "NORTH"]]) {
      ctx.strokeStyle = "#53615f"; ctx.beginPath(); ctx.moveTo(65, middle); ctx.lineTo(575, middle); ctx.stroke();
      ctx.fillStyle = "#dce8e2"; ctx.fillText(`${title} ±${bound.toFixed(1)} m`, 15, middle - 62);
      ctx.fillText("0", 38, middle + 4);
      for (const step of past) for (const [key, color, square] of [["radarDisplacement", "#f3ce86", true], ["aisDisplacement", "#91ddd4", false]]) {
        if (!step[key]) continue;
        const px = x(step.endTod), py = middle - step[key][component] / bound * 48;
        ctx.strokeStyle = color; ctx.fillStyle = color;
        if (square) ctx.fillRect(px - 4, py - 4, 8, 8);
        else { ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2); ctx.stroke(); }
      }
    }
    if (current.index >= h.seed.index) { ctx.strokeStyle = "#87978f"; ctx.setLineDash([2, 5]); ctx.beginPath(); ctx.moveTo(x(current.endTod), 36); ctx.lineTo(x(current.endTod), 291); ctx.stroke(); ctx.setLineDash([]); }
    ctx.fillStyle = "#dce8e2"; ctx.fillText("Seed", 65, 312); ctx.fillText(`+${(last - first).toFixed(1)} s`, 500, 312);
  }
  return { seed, draw, export: () => selection && hypothesis ? { ...hypothesis, displayedFrame: lastContext.view.stations[selection.station].index, current: hypothesis.steps[lastContext.view.stations[selection.station].index],
    hypothesisLedger: ledger.export(activeId, lastContext.view.stations[selection.station].index) } : null };
}
