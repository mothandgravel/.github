import { createHaxrStudy, exportHaxrView, STATIONS } from "./coastal-haxr-model.mjs";
import { haxrPixels } from "./coastal-haxr-core.mjs";

const $ = id => document.getElementById(`hx-${id}`);
const settings = { anchor: "reiherstieg", index: 0, tolerance: 1 };
let study, view, selectedUid = null, timer, bin = { station: "reiherstieg", col: 64, row: 64 };
const svgNS = "http://www.w3.org/2000/svg";
const fmt = (n, places = 2) => n.toFixed(places);
const time = n => {
  const ms = Math.round(n * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, "0")}:${String(Math.floor(ms / 60000) % 60).padStart(2, "0")}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}.${String(ms % 1000).padStart(3, "0")}`;
};
function svg(tag, attributes = {}, text) {
  const el = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attributes)) el.setAttribute(key, value);
  if (text !== undefined) el.textContent = text;
  return el;
}
function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function facts(entries) {
  const dl = element("dl");
  for (const [key, value] of entries) {
    const row = element("div");
    row.append(element("dt", key), element("dd", value));
    dl.append(row);
  }
  return dl;
}
function stop() {
  clearInterval(timer); timer = null;
  $("play").textContent = "Play frames";
  $("play").setAttribute("aria-pressed", "false");
}
async function boundedText(url, limit) {
  const response = await fetch(url, { cache: "no-cache", signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw Error(`Recording request failed (${response.status})`);
  if (Number(response.headers.get("content-length")) > limit) throw Error("Recording exceeds the size bound");
  const reader = response.body.getReader(), chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw Error("Recording exceeds the size bound");
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}
const digest = async bytes => [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(v => v.toString(16).padStart(2, "0")).join("");
$("load").addEventListener("click", async () => {
  $("load").disabled = true;
  $("load-status").textContent = "Reading both extracts and checking their published SHA-256 hashes…";
  try {
    const base = new URL("../", import.meta.url);
    const provenance = JSON.parse(new TextDecoder().decode(await boundedText(new URL("design/coastal-haxr-provenance.json", base), 50000)));
    const records = await Promise.all(["reiherstieg", "hohe_schaar"].map(async station => {
      const asset = provenance.extracts.find(e => e.station === station);
      const path = station === "reiherstieg" ? "data/haxr/reiherstieg.json" : "data/haxr/hohe-schaar.json";
      if (!asset || asset.path !== path) throw Error("Recording manifest does not match this desk");
      const bytes = await boundedText(new URL(path, base), 2000000);
      if (await digest(bytes) !== asset.sha256) throw Error(`${STATIONS[station]} extract does not match its published hash`);
      return JSON.parse(new TextDecoder().decode(bytes));
    }));
    study = createHaxrStudy(records);
    const first = study.view(settings);
    selectedUid = first.contacts.find(c => Object.values(c.reports).every(r => r && Math.abs(r.east) < 1900 && Math.abs(r.north) < 1900))?.uid
      ?? first.contacts.find(c => Object.values(c.reports).every(Boolean))?.uid ?? first.contacts[0]?.uid ?? null;
    const uids = [...new Set(records.flatMap(r => r.ais.reports.map(a => a.uid)))].sort();
    $("contact").replaceChildren(...uids.map(uid => new Option(uid, uid)));
    if (selectedUid) $("contact").value = selectedUid;
    $("load-panel").hidden = true;
    $("workspace").hidden = false;
    render();
    $("anchor").focus({ preventScroll: true });
  } catch (error) {
    $("load-status").textContent = `The recordings could not be opened. ${error.message}. You can retry.`;
    $("load").disabled = false;
  }
});
function drawStation(id) {
  const station = view.stations[id], frame = station.frame;
  const canvas = $(`${id}-canvas`);
  canvas.getContext("2d").putImageData(new ImageData(haxrPixels(frame.pixels, station.max), 128, 128), 0, 0);
  const overlay = $(`${id}-overlay`);
  overlay.replaceChildren();
  overlay.append(svg("title", {}, `${STATIONS[id]} frame ${station.index + 1}; recorded AIS rings are not radar detections`));
  for (const r of [64, 128, 192, 256]) overlay.append(svg("circle", { cx: 256, cy: 256, r, class: "hx-grid" }));
  overlay.append(svg("path", { d: "M256 0V512M0 256H512M75 75L437 437M75 437L437 75", class: "hx-grid" }));
  overlay.append(svg("path", { d: "M250 256H262M256 250V262", class: "hx-origin" }));
  for (const [x, y, label] of [[256, 18, "N / LOCAL"], [256, 500, "S"], [24, 260, "W"], [490, 260, "E"], [303, 249, "0.5 km"], [430, 249, "1.5 km"]])
    overlay.append(svg("text", { x, y, fill: "currentColor", "text-anchor": "middle", "paint-order": "stroke", stroke: "#101719", "stroke-width": 3 }, label));
  let onChart = 0;
  if ($("ais").checked) {
    for (const report of station.ais.selected) {
      const x = 256 + report.east * .128, y = 256 - report.north * .128;
      if (x < 0 || x > 512 || y < 0 || y > 512) continue;
      onChart++;
      const selected = report.uid === selectedUid;
      if (selected) overlay.append(svg("circle", { cx: x, cy: y, r: 13, class: "hx-ais-halo" }));
      const mark = svg("circle", { cx: x, cy: y, r: selected ? 5 : 3.5, class: "hx-ais-mark", "data-selected": selected });
      mark.append(svg("title", {}, `AIS ${report.uid} · ${fmt(report.ageSeconds)} s old · select using the reported ID control below`));
      mark.addEventListener("click", event => {
        event.stopPropagation(); selectedUid = report.uid; $("contact").value = selectedUid; render();
      });
      overlay.append(mark);
      if (selected) overlay.append(svg("text", {
        x: x > 430 ? x - 20 : x + 20, y: y < 25 ? y + 22 : y - 12,
        fill: "#c8f0e9", "text-anchor": x > 430 ? "end" : "start",
        "paint-order": "stroke", stroke: "#101719", "stroke-width": 3,
        "pointer-events": "none",
      }, `AIS ${report.uid}`));
    }
  }
  if (bin.station === id) overlay.append(svg("rect", { x: bin.col * 4, y: bin.row * 4, width: 4, height: 4, class: "hx-bin" }));
  const role = $(`${id}-role`);
  role.textContent = id === settings.anchor ? "Anchor station" : view.selectedPair ? "Eligible time pair" : "Nearest / not paired";
  role.dataset.eligible = String(Boolean(view.selectedPair));
  $(`${id}-time`).textContent = `${time(frame.startTod)} – ${time(frame.endTod)} UTC`;
  $(`${id}-stats`).textContent = `Frame ${String(station.index + 1).padStart(2, "0")} · ${fmt(frame.endTod - frame.startTod, 3)} s acquisition · ${station.ais.selected.length} eligible AIS IDs${$("ais").checked ? ` / ${onChart} on chart` : " / overlay hidden"}`;
}
function drawTiming() {
  const a = view.stations[view.anchor].frame, b = view.stations[view.other].frame;
  const start = Math.min(a.startTod, b.startTod), end = Math.max(a.endTod, b.endTod), span = Math.max(.001, end - start);
  const x = t => 105 + (t - start) / span * 515;
  const group = $("time-marks"); group.replaceChildren();
  for (let i = 0; i < 5; i++) {
    const px = 105 + i / 4 * 515;
    group.append(svg("line", { x1: px, y1: 25, x2: px, y2: 112, class: "hx-time-axis" }));
    group.append(svg("text", { x: px, y: 140, fill: "currentColor", "text-anchor": i === 4 ? "end" : i === 0 ? "start" : "middle" }, `+${fmt(span * i / 4, 1)}s`));
  }
  for (const [f, y, label, other] of [[a, 42, view.anchor === "reiherstieg" ? "R / anchor" : "H / anchor", false], [b, 87, view.other === "reiherstieg" ? "R / other" : "H / other", true]]) {
    group.append(svg("text", { x: 0, y: y + 4, fill: "currentColor" }, label));
    group.append(svg("rect", { x: x(f.startTod), y: y - 7, width: Math.max(1, x(f.endTod) - x(f.startTod)), height: 14, class: `hx-time-bar${other ? " hx-other" : ""}` }));
  }
  $("timeline-desc").textContent = `Offsets from ${time(start)} UTC. Anchor interval ${fmt(a.endTod - a.startTod, 3)} seconds; other interval ${fmt(b.endTod - b.startTod, 3)} seconds. Maximum endpoint difference ${fmt(view.preview.endpointSkew, 3)} seconds.`;
  const status = $("pair-status");
  status.replaceChildren(element("strong", view.selectedPair ? "Within the chosen bound." : "No eligible pair for this frame."));
  status.append(document.createTextNode(view.selectedPair ? "Eligible in time. Geometry remains unaligned." : `Nearest frame stays visible for comparison. ${view.unmatchedReason === "eligible-counterpart-consumed" ? "Its eligible counterpart was assigned elsewhere." : "Its endpoints exceed the chosen bound."}`));
  $("timing").replaceChildren(...facts([
    ["Start difference", `${fmt(Math.abs(a.startTod - b.startTod), 3)} s`],
    ["End difference", `${fmt(Math.abs(a.endTod - b.endTod), 3)} s`],
    ["Maximum endpoint difference", `${fmt(view.preview.endpointSkew, 3)} s`],
    ["Spatial alignment", "Not established"],
  ]).children);
  const pairs = new Set(view.pairing.pairs.map(p => p.left.index));
  $("pair-strip").replaceChildren(...study.recordings[settings.anchor].frames.map((_, i) => {
    const button = element("button", String(i + 1).padStart(2, "0"));
    button.type = "button"; button.dataset.eligible = String(pairs.has(i));
    button.setAttribute("aria-pressed", String(i === settings.index));
    button.setAttribute("aria-label", `Frame ${i + 1}, ${pairs.has(i) ? "eligible time pair" : "no eligible pair"}`);
    button.addEventListener("click", () => { stop(); settings.index = i; render(); $("pair-strip").children[i].focus({ preventScroll: true }); });
    return button;
  }));
  $("pair-summary").textContent = `${pairs.size} / 16 anchor frames have an eligible counterpart at ${fmt(settings.tolerance)} s. Brass ticks mark eligible pairs.`;
}
function drawContact() {
  $("contact-count").textContent = `${view.contacts.length} IDs eligible across these frames · ${view.sharedIds} in both · 1 upstream AIS family`;
  const container = $("contact-detail"); container.replaceChildren();
  for (const [id, station] of Object.entries(view.stations)) {
    const report = station.ais.selected.find(r => r.uid === selectedUid);
    const card = element("article", undefined, "hx-contact-card");
    card.append(element("h3", STATIONS[id]));
    if (report) {
      const inside = Math.abs(report.east) <= 2000 && Math.abs(report.north) <= 2000;
      card.append(facts([
        ["Reported at", `${time(report.tod)} UTC`],
        ["Age at frame end", `${fmt(report.ageSeconds, 3)} s`],
        ["Local range / bearing", `${fmt(report.rangeMeters, 0)} m / ${fmt(report.azimuthDegrees, 1)}°`],
        ["Local east / north", `${fmt(report.east, 0)} / ${fmt(report.north, 0)} m`],
        ["Raster extent", inside ? "Inside this square" : "Outside this square"],
        ["Source family", "Same HAXR AIS stream"],
      ]));
    } else card.append(element("p", "No eligible report for this ID at this frame end. It remains selected; no position is invented.", "hx-small"));
    container.append(card);
  }
  $("ais-summary").textContent = Object.entries(view.stations).map(([id, s]) => `${STATIONS[id]}: ${s.ais.futureReports} future reports, ${s.ais.staleTargets} stale IDs and ${s.ais.conflictingTargets} conflicting IDs excluded.`).join(" ") + " Latest report at or before frame end; maximum age 10 s. No prediction or interpolation.";
}
function inspectBin() {
  const s = view.stations[bin.station], f = s.frame, amplitude = f.pixels[bin.row * 128 + bin.col];
  const east = -2000 + bin.col * 31.25, north = 2000 - bin.row * 31.25;
  $("cell-result").textContent = `${STATIONS[bin.station]}, column ${bin.col}, row ${bin.row}: ${amplitude === null ? "no selected cell (null). This does not establish empty water." : `recorded maximum amplitude ${amplitude}. ${amplitude === 0 ? "Measured zero is distinct from a missing cell." : "This value is not calibrated power."}`} East ${fmt(east)} to ${fmt(east + 31.25)} m; north ${fmt(north - 31.25)} to ${fmt(north)} m.`;
  $("raw").textContent = JSON.stringify({
    station: bin.station, sourceFile: study.recordings[bin.station].file,
    sourceSha256: study.recordings[bin.station].sha256,
    frame: { ...f, pixels: undefined },
    bin: { column: bin.col, row: bin.row, amplitude, eastMin: east, eastMax: east + 31.25, northMin: north - 31.25, northMax: north },
    note: "Acquisition times describe the frame; no per-bin instant is inferred.",
  }, null, 2);
}
function render() {
  view = study.view(settings);
  $("frame").value = settings.index; $("frame-value").textContent = `${String(settings.index + 1).padStart(2, "0")} / 16`;
  $("prev").disabled = settings.index === 0; $("next").disabled = settings.index === 15;
  $("tolerance-value").textContent = `${fmt(settings.tolerance)} s`;
  for (const id of Object.keys(STATIONS)) drawStation(id);
  drawTiming(); drawContact(); inspectBin();
}
$("anchor").addEventListener("change", () => { stop(); settings.anchor = $("anchor").value; render(); });
$("frame").addEventListener("input", () => { stop(); settings.index = Number($("frame").value); render(); });
$("tolerance").addEventListener("input", () => { stop(); settings.tolerance = Number($("tolerance").value); render(); });
$("prev").addEventListener("click", () => { stop(); settings.index = Math.max(0, settings.index - 1); render(); });
$("next").addEventListener("click", () => { stop(); settings.index = Math.min(15, settings.index + 1); render(); });
$("play").addEventListener("click", () => {
  if (timer) return stop();
  if (settings.index === 15) { settings.index = 0; render(); }
  $("play").textContent = "Pause frames"; $("play").setAttribute("aria-pressed", "true");
  timer = setInterval(() => {
    settings.index++; render();
    if (settings.index >= 15) stop();
  }, 1200);
});
document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
window.addEventListener("pagehide", stop);
$("ais").addEventListener("change", render);
$("contact").addEventListener("change", () => { selectedUid = $("contact").value; render(); });
$("inspect").addEventListener("click", () => {
  const col = Number($("col").value), row = Number($("row").value);
  if (!$("col").value || !$("row").value || !Number.isInteger(col) || !Number.isInteger(row) || col < 0 || col > 127 || row < 0 || row > 127) {
    $("cell-result").textContent = "Choose a whole-number column and row from 0 to 127."; return;
  }
  bin = { station: $("cell-station").value, col, row }; render();
});
for (const id of Object.keys(STATIONS)) $(`${id}-scope`).addEventListener("click", event => {
  const rect = event.currentTarget.getBoundingClientRect();
  bin = { station: id, col: Math.min(127, Math.max(0, Math.floor((event.clientX - rect.left) / rect.width * 128))), row: Math.min(127, Math.max(0, Math.floor((event.clientY - rect.top) / rect.height * 128))) };
  $("cell-station").value = id; $("col").value = bin.col; $("row").value = bin.row; render();
});
$("export").addEventListener("click", () => {
  const record = exportHaxrView(study, settings, selectedUid);
  record.selectedBin = JSON.parse($("raw").textContent);
  const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }));
  const link = element("a"); link.href = url; link.download = `coastal-haxr-${settings.anchor}-${settings.index + 1}.json`;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("export-status").textContent = "Comparison exported with frame times, AIS exclusions, bin value and source hashes. Unsigned; recorded data, not a live receipt.";
});
