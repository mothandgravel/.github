import {
  INQUIRY,
  INQUIRY_STEPS,
  inquirySnapshot,
} from "./shadow-inquiry-model.mjs";
const $ = (id) => document.getElementById(id);
let step = 0,
  selected = "A-01";
const clock = (seconds) =>
  new Date(Date.UTC(2026, 0, 1, 12, 30) + seconds * 1000)
    .toISOString()
    .slice(11, 19);
const svg = (tag, attrs, parent) => {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs))
    el.setAttribute(key, String(value));
  parent.append(el);
  return el;
};
const point = (x, y) => [200 + x * 0.9, 260 - y * 0.9];
function render() {
  const result = inquirySnapshot({
    step,
    offset: Number($("si-offset").value),
    uncertainty: Number($("si-uncertainty").value),
  });
  const chapter = INQUIRY_STEPS[step],
    comparison = result.comparison;
  if (!result.reports.some((r) => r.id === selected)) selected = "A-01";
  $("si-title").textContent = chapter.title;
  $("si-note").textContent = chapter.note;
  $("si-question").textContent = chapter.question;
  $("si-request").textContent = chapter.request;
  $("si-clock").textContent = `${clock(result.boundary)} UTC`;
  $("si-prev").disabled = step === 0;
  $("si-next").disabled = step === INQUIRY_STEPS.length - 1;
  document
    .querySelectorAll("[data-si-step]")
    .forEach((el) =>
      el.setAttribute(
        "aria-pressed",
        String(Number(el.dataset.siStep) === step),
      ),
    );
  $("si-deliveries").textContent = String(result.counts.deliveries).padStart(
    2,
    "0",
  );
  $("si-originals").textContent = String(result.counts.originals).padStart(
    2,
    "0",
  );
  $("si-families").textContent = String(result.counts.families).padStart(
    2,
    "0",
  );
  $("si-offset-value").value =
    `${result.controls.offset > 0 ? "+" : ""}${result.controls.offset} s`;
  $("si-uncertainty-value").value = `±${result.controls.uncertainty} s`;
  $("si-assumptions").disabled = !comparison;
  $("si-result").textContent = comparison
    ? comparison.reason
    : "No second instrument available yet";
  $("si-measure").textContent = comparison
    ? `${comparison.separation.toFixed(1)} m between centres · ${comparison.gap.toFixed(1)} m between bounds`
    : "30 min between AIS reports · coverage unknown";
  $("si-formula").textContent = comparison
    ? `AIS projected ${comparison.dt} s at 8 m/s east. AIS bound ${comparison.radius.toFixed(1)} m = 35 + 1.2 × (${comparison.dt} + ${result.controls.uncertainty}) + 8 × ${result.controls.uncertainty}. Radar bound 55 m. No probability is assigned.`
    : "The gap is measured between source timestamps. It does not establish how many transmissions were missed.";
  const layer = $("si-marks");
  layer.replaceChildren();
  const [ax, ay] = point(0, 0);
  svg("circle", { cx: ax, cy: ay, r: 7, class: "si-ais" }, layer);
  svg("text", { x: ax - 75, y: ay + 35 }, layer).textContent =
    "A-01 / reported";
  if (step >= 1) {
    svg("circle", { cx: ax, cy: ay, r: 22, class: "si-copy" }, layer);
    svg("text", { x: ax - 65, y: ay + 57, class: "si-copy-label" }, layer).textContent =
      "relay / same origin";
  }
  if (comparison) {
    const [px, py] = point(comparison.projected.x, 0),
      [rx, ry] = point(420, 70);
    svg(
      "path",
      { d: `M${ax} ${ay} L${px} ${py}`, class: "si-projection" },
      layer,
    );
    svg(
      "circle",
      { cx: px, cy: py, r: comparison.radius * 0.9, class: "si-envelope" },
      layer,
    );
    svg("circle", { cx: px, cy: py, r: 5, class: "si-ais" }, layer);
    svg(
      "circle",
      { cx: rx, cy: ry, r: 55 * 0.9, class: "si-radar-bound" },
      layer,
    );
    svg(
      "path",
      { d: `M${rx} ${ry - 8} l8 8 -8 8 -8 -8Z`, class: "si-radar" },
      layer,
    );
    svg(
      "path",
      { d: `M${px} ${py} L${rx} ${ry}`, class: "si-residual" },
      layer,
    );
    svg("text", { x: rx + 22, y: ry - 64 }, layer).textContent =
      "R-17 / measured";
    svg("text", { x: 315, y: 400, class: "si-bound-label" }, layer).textContent =
      `AIS comparison envelope / ${comparison.radius.toFixed(0)} m`;
  }
  $("si-map-summary").textContent =
    `${$("si-result").textContent}. ${$("si-measure").textContent}. The dashed AIS segment is a motion assumption, not an observed path.`;
  const rows = $("si-records");
  rows.replaceChildren();
  for (const r of result.reports) {
    const row = document.createElement("tr");
    const select = document.createElement("button");
    select.type = "button";
    select.textContent = r.id;
    select.setAttribute("aria-pressed", String(selected === r.id));
    select.addEventListener("click", () => {
      selected = r.id;
      render();
    });
    const cell = document.createElement("td");
    cell.append(select);
    row.append(cell);
    for (const value of [
      clock(r.observed),
      clock(r.received),
      r.parent ?? "Original",
    ]) {
      const td = document.createElement("td");
      td.textContent = value;
      row.append(td);
    }
    rows.append(row);
  }
  const r = result.reports.find((r) => r.id === selected);
  $("si-record").textContent = JSON.stringify(r, null, 2);
  $("si-lineage").textContent = r.parent
    ? `${r.parent} → relay → ${r.id}. One original measurement. No additional witness.`
    : `${r.family} → ${r.id}. ${r.type === "Radar" ? "A separate instrument family; association with Contact K is an unverified hypothesis." : "A cooperative report. Identity and position are claims carried by the source."}`;
  $("si-copy-link").dataset.available = String(step >= 1);
  $("si-radar-link").dataset.available = String(step >= 2);
  $("si-copy-link").textContent = step >= 1 ? "A-01 → relay copy" : "Relay / no receipt yet";
  $("si-radar-link").textContent = step >= 2 ? "Radar N → R-17" : "Radar / no receipt yet";
  $("si-export").onclick = () => {
    const payload = {
      ...result,
      fullFixture: INQUIRY,
      fullFixtureIncludesFuture: true,
      review: { question: chapter.question, nextEvidence: chapter.request },
      limits:
        "Synthetic inquiry. Unsigned export. No live radar, RF, sanctions lookup, spoofing inference or operational validation.",
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `shadow-inquiry-step-${step + 1}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $("si-export-status").textContent =
      "Exported this view, its assumptions and the full labelled fixture.";
  };
}
function move(next) {
  step = next;
  $("si-offset").value = INQUIRY_STEPS[step].offset;
  $("si-uncertainty").value = INQUIRY_STEPS[step].uncertainty;
  $("si-export-status").textContent = "";
  render();
}
document
  .querySelectorAll("[data-si-step]")
  .forEach((el) =>
    el.addEventListener("click", () => move(Number(el.dataset.siStep))),
  );
$("si-prev").addEventListener("click", () => move(Math.max(0, step - 1)));
$("si-next").addEventListener("click", () =>
  move(Math.min(INQUIRY_STEPS.length - 1, step + 1)),
);
$("si-offset").addEventListener("input", render);
$("si-uncertainty").addEventListener("input", render);
$("si-reset").addEventListener("click", () => move(step));
$("si-desk").hidden = false;
$("si-fallback").hidden = true;
render();
