import { haxrPixels } from "./coastal-haxr-core.mjs?v=branches-1";
import { BIN_METERS } from "./coastal-haxr-returns.mjs?v=branches-1";
const labels = { nearby: "Returns inside the aperture", "below-floor": "No bins above this floor", missing: "No sampled bins here", "no-ais": "No eligible AIS position", outside: "AIS outside this raster" };
const marks = { nearby: "+", "below-floor": "·", missing: "?", "no-ais": "—", outside: "↗" };
export function createReturnsPanel({ selectFrame, selectUid, inspectBin, followBin, stop, redraw, time }) {
  const $ = id => document.getElementById(`hx-${id}`);
  const options = { radius: 125, floor: 60 };
  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
  for (const field of ["radius", "floor"]) $(`returns-${field}`).addEventListener("input", () => {
    stop(); options[field] = Number($(`returns-${field}`).value); redraw();
  });
  $("returns-id").addEventListener("change", () => selectUid($("returns-id").value));
  $("returns-play").addEventListener("click", () => $("play").click());
  function draw({ study, view, uid, settings, names }) {
    const inquiry = study.inspect(uid, settings, options);
    if (!$("returns-id").options.length) $("returns-id").replaceChildren(...[...$("follow-id").options].map(o => new Option(o.text, o.value)));
    $("returns-id").value = uid;
    $("returns-selected").textContent = `AIS ${uid} / 01 shared source family`;
    $("returns-floor-value").textContent = `${options.floor}%`;
    $("returns-play").textContent = $("play").getAttribute("aria-pressed") === "true" ? "Pause frames" : "Play frames";
    $("returns-play").setAttribute("aria-pressed", $("play").getAttribute("aria-pressed"));
    const panels = $("returns-panels"); panels.replaceChildren();
    for (const [id, current] of Object.entries(inquiry.current)) {
      const panel = el("article", undefined, "hx-return-station");
      panel.append(el("p", `${names[id]} / FRAME ${String(current.index + 1).padStart(2, "0")}`, "hx-label"), el("h3", labels[current.state]));
      const scope = el("div", undefined, "hx-return-scope"); scope.dataset.state = current.state;
      const canvas = el("canvas"); canvas.width = 480; canvas.height = 480;
      canvas.setAttribute("role", "img"); canvas.setAttribute("aria-label", `${names[id]} local radar aperture. ${labels[current.state]}. Details follow.`);
      scope.append(canvas); panel.append(scope);
      const ctx = canvas.getContext("2d"); ctx.fillStyle = "#101719"; ctx.fillRect(0, 0, 480, 480);
      if (current.report && current.state !== "outside") {
        const report = current.report, half = options.radius * 1.5, scale = 480 / (half * 2);
        const source = document.createElement("canvas"); source.width = source.height = 128;
        source.getContext("2d").putImageData(new ImageData(haxrPixels(view.stations[id].frame.pixels, view.stations[id].max), 128, 128), 0, 0);
        // Render the original pixel grid, including its null/zero distinction; no smoothing.
        ctx.strokeStyle = "#263a3c"; ctx.lineWidth = 1;
        for (let p = 0; p < 480; p += 16) { ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, 480); ctx.moveTo(0, p); ctx.lineTo(480, p); ctx.stroke(); }
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(source, 240 + (-2000 - report.east) * scale, 240 + (report.north - 2000) * scale, 4000 * scale, 4000 * scale);
        ctx.strokeStyle = "#c9ad72"; ctx.setLineDash([5, 5]); ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(240, 240, options.radius * scale, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
        if (current.nearest) {
          const n = current.nearest;
          const x = 240 + (n.east - report.east) * scale, y = 240 - (n.north - report.north) * scale;
          ctx.strokeStyle = "#fff4d1"; ctx.lineWidth = 2;
          ctx.strokeRect(x - BIN_METERS * scale / 2, y - BIN_METERS * scale / 2, BIN_METERS * scale, BIN_METERS * scale);
        }
        ctx.strokeStyle = "#91ddd4"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(226, 240); ctx.lineTo(254, 240); ctx.moveTo(240, 226); ctx.lineTo(240, 254); ctx.stroke();
        ctx.fillStyle = "#dce8e2"; ctx.font = "12px monospace";
        ctx.fillText(`N ↑   ${options.radius} m radius`, 16, 24);
        ctx.fillText(`${half * 2} m across / local frame`, 16, 462);
        canvas.addEventListener("click", event => {
          const rect = canvas.getBoundingClientRect();
          const east = report.east + ((event.clientX - rect.left) / rect.width * 480 - 240) / scale;
          const north = report.north - ((event.clientY - rect.top) / rect.height * 480 - 240) / scale;
          const col = Math.floor((east + 2000) / BIN_METERS), row = Math.floor((2000 - north) / BIN_METERS);
          if (col >= 0 && col < 128 && row >= 0 && row < 128) inspectBin(id, col, row);
        });
      } else {
        const message = el("p", current.state === "outside" ? "The reported position falls outside the recorded square." : "The aperture waits for an eligible report. No stale position is carried forward.", "hx-return-empty"); scope.append(message);
      }
      const details = el("dl");
      const facts = current.report && current.state !== "outside" ? [
        ["Positive bins ≥ display floor", `${current.aboveFloorBins} / ${current.sampledBins} sampled`],
        ["Missing / measured zero", `${current.missingBins} / ${current.zeroBins}`],
        ["Nearest qualifying bin centre", current.nearest ? `${current.nearest.distanceMeters.toFixed(1)} m from AIS` : "None at this floor"],
        ["Other eligible AIS IDs in radius", current.nearbyAisIds.length ? current.nearbyAisIds.join(", ") : "None in this extract"],
        ["AIS / age at frame end", `${time(current.report.tod)} / ${current.reportAgeAtEnd.toFixed(3)} s`],
      ] : [
        ["Positive bins ≥ display floor", "Not sampled"],
        ["Missing / measured zero", "Not sampled"],
        ["Nearest qualifying bin centre", "Unavailable"],
        ["Other eligible AIS IDs in radius", "Not compared"],
        ["AIS / age at frame end", current.report ? `${time(current.report.tod)} / outside raster` : "No eligible report"],
      ];
      for (const [k, v] of facts) { const row = el("div"); row.append(el("dt", k), el("dd", v)); details.append(row); }
      panel.append(details);
      panel.append(el("p", `${time(current.startTod)}–${time(current.endTod)} UTC acquisition. ${current.reportTiming === "within-frame" ? "AIS falls within this interval and may be later than individual radar cells." : current.reportTiming === "before-frame" ? "AIS predates this acquisition interval; motion is not compensated." : "No current position comparison."}${current.clipped ? " The inspection circle is clipped by the raster edge." : ""}`, "hx-small"));
      const nearest = el("button", "Inspect nearest qualifying bin ↗"); nearest.type = "button"; nearest.disabled = !current.nearest;
      nearest.addEventListener("click", () => inspectBin(id, current.nearest.col, current.nearest.row)); panel.append(nearest);
      const follow = el("button", "Follow this return over time ↓"); follow.type = "button"; follow.className = "hx-follow-return"; follow.disabled = !current.nearest;
      follow.addEventListener("click", () => followBin(id, current.nearest.col, current.nearest.row)); panel.append(follow);
      panel.append(el("p", "THROUGH THIS RECORDING / FULL WINDOW", "hx-label hx-return-through"));
      const strip = el("div", undefined, "hx-history-strip hx-return-strip"); strip.setAttribute("role", "group"); strip.setAttribute("aria-label", `${names[id]} local return history`);
      for (const item of inquiry.stations[id]) {
        const button = el("button", String(item.index + 1).padStart(2, "0")); button.type = "button";
        button.id = `hx-return-${id}-${item.index}`; button.dataset.state = item.state;
        button.setAttribute("aria-pressed", String(item.index === current.index));
        button.setAttribute("aria-label", `${names[id]} frame ${item.index + 1}: ${labels[item.state]}, ${item.aboveFloorBins} bins above floor`);
        const mark = el("span", marks[item.state]); mark.setAttribute("aria-hidden", "true"); button.append(mark);
        const move = index => { selectFrame(id, index); $(`return-${id}-${index}`).focus({ preventScroll: true }); };
        button.addEventListener("click", () => move(item.index));
        button.addEventListener("keydown", event => {
          const index = event.key === "Home" ? 0 : event.key === "End" ? 15 : event.key === "ArrowRight" ? Math.min(15, item.index + 1) : event.key === "ArrowLeft" ? Math.max(0, item.index - 1) : null;
          if (index !== null) { event.preventDefault(); move(index); }
        });
        strip.append(button);
      }
      panel.append(strip); panels.append(panel);
    }
    $("returns-comparison").textContent = `${view.selectedPair ? "Frames meet the selected time bound." : "These frames are not an eligible time pair."} Nearby returns can support a local proximity check, but cannot identify this vessel. Station geometry is uncalibrated, bin times are unavailable, and shore, clutter or other vessels may contribute. Both AIS positions come from one shared stream.`;
  }
  return { draw, options };
}
