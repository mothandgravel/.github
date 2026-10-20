import {
  CHAPTERS,
  SOURCES,
  ancestors,
  recordDependencies,
  identitySnapshot,
  reviseIdentity,
  assessment,
  identityExport,
  readTransportSnapshot,
  transportIdentities,
} from "./coastal-identity-model.mjs";
const $ = (id) => document.getElementById(id);
const add = (tag, text, parent, className) => {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  parent.append(el);
  return el;
};
const stamp = (sec) =>
  new Date(Date.UTC(2026, 0, 1, 12, 0, sec)).toISOString().slice(11, 19);
const date = (ms) => new Date(ms).toISOString();
let settings = { step: 0, correction: 0, allowance: 35 };
let journal = [],
  selected = "A-00",
  source = "south",
  transport = null,
  ledgerKey = "";
let transportSelection = "";
const sourceButtons = new Map(),
  chapterButtons = [],
  recordButtons = new Map();
function svg(tag, attrs, text = "") {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  el.textContent = text;
  $("il-marks").append(el);
  return el;
}
function plot(view) {
  $("il-marks").replaceChildren();
  const x = (n) => (n + 200) * 0.95,
    y = (n) => 180 - n * 0.95;
  svg("path", {
    d: "M35 45V25H55 M665 25H685V45 M35 305V325H55 M665 325H685V305",
    fill: "none",
    stroke: "var(--line)",
  });
  svg("text", { x: 50, y: 55, class: "il-fine" }, "N ↑ / LOCAL METRES");
  svg("path", {
    d: "M555 310H650 M555 305V315 M650 305V315",
    stroke: "var(--secondary)",
  });
  svg("text", { x: 565, y: 340 }, "100 m");
  const shared = view.positions.find((p) => p.shared);
  if (shared) {
    svg("circle", {
      cx: x(300),
      cy: y(0),
      r: 7,
      class: "il-raw-mark",
      "data-mark": "raw",
    });
    if (view.comparison?.correction)
      svg("path", {
        d: `M${x(300)} ${y(0)}H${x(shared.x)}`,
        fill: "none",
        stroke: "var(--gold)",
        "stroke-dasharray": "4 5",
      });
    svg("circle", {
      cx: x(shared.x),
      cy: y(shared.y),
      r: settings.allowance * 0.95,
      class: "il-shared-mark",
      "data-mark": "shared-bound",
    });
    svg("circle", {
      cx: x(shared.x),
      cy: y(shared.y),
      r: 6,
      fill: "var(--gold-bright)",
      "data-mark": "shared",
      "data-position": shared.x,
    });
    svg("text", { x: x(shared.x) - 50, y: 255 }, "GNSS K");
    svg(
      "text",
      { x: x(shared.x) - 50, y: 277, class: "il-fine" },
      `${view.positions.filter((p) => p.shared).length} accounts / shared origin`,
    );
  } else svg("text", { x: 105, y: 180 }, "No current position received.");
  const radar = view.positions.find((p) => !p.shared);
  if (radar) {
    svg("circle", {
      cx: x(radar.x),
      cy: y(radar.y),
      r: 35 * 0.95,
      class: "il-radar-mark",
    });
    svg("path", {
      d: `M${x(radar.x)} ${y(radar.y) - 7}l7 7 -7 7 -7 -7Z`,
      fill: "var(--ink)",
      "data-mark": "radar",
    });
    svg("text", { x: x(radar.x) - 40, y: 72 }, "RADAR N");
    svg("path", {
      d: `M${x(shared.x)} ${y(shared.y)}L${x(radar.x)} ${y(radar.y)}`,
      stroke: "var(--secondary)",
      "stroke-dasharray": "2 4",
    });
  }
  $("il-plot-desc").textContent = radar
    ? `GNSS descendants at ${shared.x} east, 0 north; radar at 120 east, 40 north. ${view.comparison.separation.toFixed(1)} metres apart. Source records remain unchanged; association is unverified.`
    : shared
      ? "All current position accounts share GNSS K."
      : "No current position record is available at this boundary.";
}
function render() {
  const view = identitySnapshot(settings);
  if (!view.records.some((r) => r.id === selected))
    selected = view.records.at(-1).id;
  if (!view.sources.includes(source)) source = view.records.at(-1).source;
  chapterButtons.forEach((b, i) =>
    b.setAttribute("aria-pressed", String(i === settings.step)),
  );
  $("il-progress").textContent =
    `${String(settings.step + 1).padStart(2, "0")} / 05`;
  $("il-prev").disabled = settings.step === 0;
  $("il-next").disabled = settings.step === 4;
  $("il-time").textContent = `${stamp(view.chapter.time)} UTC`;
  $("il-time").dateTime = `2026-01-01T${stamp(view.chapter.time)}Z`;
  $("il-title").textContent = view.chapter.title;
  $("il-story").textContent = view.chapter.text;
  $("il-current").hidden = settings.step < 1;
  $("il-other").hidden = settings.step < 4;
  $("il-awaiting").textContent =
    settings.step === 0
      ? "The new account has not arrived."
      : settings.step < 4
        ? "No second identity document has arrived."
        : "All identifiers here are fictional. A name match is not an identity match.";
  $("il-accounts").textContent = String(view.counts.positions).padStart(2, "0");
  $("il-roots").textContent = String(view.counts.positionRoots).padStart(
    2,
    "0",
  );
  $("il-assumptions").disabled = settings.step < 3;
  $("il-correction").value = view.comparison?.correction ?? 0;
  $("il-correction-value").textContent =
    `${view.comparison?.correction ?? 0} m`;
  $("il-allowance").value = settings.allowance;
  $("il-allowance-value").textContent = `${settings.allowance} m`;
  $("il-result").textContent = !view.comparison
    ? settings.step < 1
      ? "The position question is still empty."
      : "Agreement within one position family."
    : view.comparison.gap > 0
      ? "Separated under these assumptions."
      : "Compatible bounds. Identity still open.";
  $("il-distance").textContent = view.comparison
    ? `${view.comparison.separation.toFixed(1)} m between centres · ${view.comparison.gap.toFixed(1)} m between bounds · radar association unverified`
    : "Copies and shared inputs cannot exclude a common position error.";
  plot(view);
  for (const [id, button] of sourceButtons) {
    button.hidden = !view.sources.includes(id);
    button.setAttribute("aria-pressed", String(id === source));
    button.dataset.linked = String(ancestors(id).includes(source));
  }
  $("il-source-note").textContent = SOURCES[source].detail;
  $("il-path").textContent =
    `Selected: ${SOURCES[source].label}. ${source === "gnss" ? "Only position-bearing records are highlighted. GNSS supplies no name or IMO evidence." : "Highlighted records pass through this source."}`;
  const key = view.records.map((r) => r.id).join();
  if (key !== ledgerKey) {
    ledgerKey = key;
    $("il-records").replaceChildren();
    recordButtons.clear();
    for (const r of view.records) {
      const row = add("tr", "", $("il-records"));
      const button = add("button", r.id, add("td", "", row));
      button.type = "button";
      button.onclick = () => {
        selected = r.id;
        render();
      };
      recordButtons.set(r.id, { button, row });
      add("td", SOURCES[r.source].label, row);
      add("td", stamp(r.observed), row);
      add("td", stamp(r.received), row);
      add("td", r.name ?? "Not reported", row);
    }
  }
  for (const r of view.records) {
    const { button, row } = recordButtons.get(r.id);
    button.setAttribute("aria-pressed", String(r.id === selected));
    row.dataset.selected = String(r.id === selected);
    row.dataset.linked = String(recordDependencies(r).includes(source));
  }
  $("il-ledger-count").textContent =
    `${view.counts.deliveries} stored accounts · ${view.counts.originals} original records · receipt time gates this view`;
  const record = view.records.find((r) => r.id === selected);
  $("il-record-title").textContent = record.id;
  $("il-record-note").textContent = record.note;
  $("il-raw").textContent = JSON.stringify(record, null, 2);
  const link = assessment(journal, settings.step);
  document.querySelectorAll("[data-il-link]").forEach((button) => {
    button.disabled =
      settings.step < 1 ||
      (button.dataset.ilLink === "other" && settings.step < 4);
    button.setAttribute("aria-pressed", String(button.dataset.ilLink === link));
  });
  $("il-current").classList.toggle("chosen", link !== "unresolved");
  $("il-assessment").textContent =
    link === "ember"
      ? "Hypothesis: A-01 belongs to candidate A. Reported identifiers agree; independent hull verification is still absent."
      : link === "other"
        ? "Hypothesis: A-01 belongs to candidate B. Name agrees, but MMSI, IMO and callsign conflict. The conflict remains in the account."
        : "A-01 remains unassociated with a verified hull. Position agreement cannot settle this question.";
  $("il-journal").replaceChildren();
  if (!journal.length)
    add(
      "li",
      "No identity decisions recorded in this session.",
      $("il-journal"),
    );
  for (const j of journal)
    add(
      "li",
      `Revision ${j.revision} / boundary ${j.step + 1}: ${j.statement}${j.step > settings.step ? " [Later than this view; excluded.]" : ""}`,
      $("il-journal"),
      j.step > settings.step ? "future" : "",
    );
}
function setStep(step) {
  settings.step = step;
  selected = identitySnapshot(settings).records.at(-1).id;
  render();
}
CHAPTERS.forEach((chapter, i) => {
  const b = add("button", "", document.querySelector(".il-chapters"));
  b.type = "button";
  add("span", `0${i + 1} / ${stamp(chapter.time)}`, b);
  add("strong", chapter.label, b);
  b.onclick = () => setStep(i);
  chapterButtons.push(b);
});
for (const [id, node] of Object.entries(SOURCES)) {
  const b = add(
    "button",
    "",
    $("il-sources"),
    node.parents.length ? "" : "root",
  );
  b.type = "button";
  b.dataset.source = id;
  add("span", node.kind, b);
  add("strong", node.label, b);
  add(
    "small",
    node.parents.length
      ? `← ${node.parents.map((p) => SOURCES[p].label).join(", ")}`
      : "Origin in this fixture",
    b,
  );
  b.onclick = () => {
    source = id;
    render();
  };
  sourceButtons.set(id, b);
}
$("il-prev").onclick = () => setStep(settings.step - 1);
$("il-next").onclick = () => setStep(settings.step + 1);
for (const key of ["correction", "allowance"])
  $(`il-${key}`).oninput = (e) => {
    settings[key] = Number(e.target.value);
    render();
  };
$("il-reset-assumptions").onclick = () => {
  settings.correction = 0;
  settings.allowance = 35;
  render();
};
document.querySelectorAll("[data-il-link]").forEach(
  (b) =>
    (b.onclick = () => {
      try {
        journal = reviseIdentity(journal, b.dataset.ilLink, settings.step);
        render();
      } catch (error) {
        $("il-assessment").textContent = error.message;
      }
    }),
);
$("il-export").onclick = () => {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(identityExport(settings, journal), null, 2)], {
      type: "application/json",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "coastal-identity-inquiry.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("il-export-status").textContent =
    "Exported the selected view, session revisions and separately labelled full fixture. Unsigned.";
};
function renderTransport() {
  if (!transport) return;
  const station = $("il-station").value;
  const groups = transportIdentities(transport, station).sort(
    (a, b) => b.latest.observedAt - a.latest.observedAt,
  );
  const key = (g) => `${g.latest.origin}:${g.latest.source.mmsi}`;
  if (!groups.some((g) => key(g) === transportSelection))
    transportSelection = groups[0] ? key(groups[0]) : "";
  const picker = $("il-contact");
  picker.replaceChildren();
  for (const group of groups) {
    const option = add(
      "option",
      `${group.latest.source.mmsi} / ${group.latest.origin}`,
      picker,
    );
    option.value = key(group);
  }
  picker.value = transportSelection;
  $("il-contact-label").hidden = !groups.length;
  $("il-imported").replaceChildren();
  $("il-import-raw").hidden = true;
  if (!groups.length)
    add(
      "p",
      "No public AIS records were known at this station in the snapshot. No vessel absence is inferred.",
      $("il-imported"),
    );
  for (const group of groups.filter((g) => key(g) === transportSelection)) {
    const card = add("article", "", $("il-imported"), "il-import-card");
    add("h3", `Reported MMSI ${group.latest.source.mmsi}`, card);
    add(
      "p",
      `${group.latest.source.provider} · origin ${group.latest.origin} · ${group.records.length} known reports · ${group.receipts.length} receipts`,
      card,
    );
    add(
      "p",
      `Retained position: ${group.latest.lat.toFixed(5)}, ${group.latest.lon.toFixed(5)} · observed ${date(group.latest.observedAt)}`,
      card,
    );
    add("p", `${group.identity}. ${group.dependencies}.`, card);
    const details = add("details", "", card);
    add("summary", "Inspect known reports and receipts", details);
    for (const r of group.records) {
      const b = add(
        "button",
        `${r.id === group.latest.id ? "Retained" : "History"} · ${date(r.observedAt)}`,
        details,
      );
      b.type = "button";
      b.onclick = () => {
        $("il-import-raw").hidden = false;
        $("il-import-raw").textContent = JSON.stringify(
          {
            record: r,
            receipts: group.receipts.filter(
              (receipt) => receipt.observation_id === r.id,
            ),
            note: "Projection of imported transport fields; unsigned and unverified.",
          },
          null,
          2,
        );
      };
    }
  }
}
function loadSnapshot(input, label) {
  const next = readTransportSnapshot(input);
  transport = next;
  $("il-import-status").textContent =
    `${label} · run ${next.runId} · snapshot ${date(next.serverTime)}. Read-only, unsigned, authenticity unverified.`;
  renderTransport();
}
const contactLabel = add(
  "label",
  "Reported contact ",
  $("il-station").parentElement.parentElement,
);
contactLabel.id = "il-contact-label";
contactLabel.hidden = true;
const contactPicker = add("select", "", contactLabel);
contactPicker.id = "il-contact";
$("il-station").onchange = renderTransport;
$("il-contact").onchange = (event) => {
  transportSelection = event.target.value;
  renderTransport();
};
$("il-import").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    if (file.size > 2_000_000)
      throw Error("Choose a transport export smaller than 2 MB");
    loadSnapshot(JSON.parse(await file.text()), "Imported transport snapshot");
  } catch (error) {
    $("il-import-status").textContent =
      `Could not import: ${error.message}. Previous snapshot, if any, is unchanged.`;
  }
};
const local = ["127.0.0.1", "localhost", "[::1]"].includes(location.hostname);
$("il-load-local").disabled = !local;
$("il-load-local").title = local
  ? "Read one snapshot from the local transport service"
  : "Available when this page is served by the local Raivari workbench. Use a JSON export here.";
$("il-load-local").onclick = async () => {
  $("il-load-local").disabled = true;
  $("il-import-status").textContent = "Reading one local snapshot…";
  try {
    const response = await fetch("/api/coastal/state", {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw Error(`Local service returned ${response.status}`);
    const text = await response.text();
    if (new TextEncoder().encode(text).length > 2_000_000)
      throw Error("Snapshot exceeds 2 MB");
    loadSnapshot(JSON.parse(text), "Captured from local Raivari");
  } catch (error) {
    $("il-import-status").textContent =
      `Could not read local Raivari: ${error.message}. Open this page on the transport service, or import its JSON export.`;
  } finally {
    $("il-load-local").disabled = false;
  }
};
async function datasets() {
  try {
    const response = await fetch("../../../design/coastal-datasets.json");
    if (!response.ok) throw Error("Source register unavailable");
    const register = await response.json();
    for (const item of register.datasets) {
      const card = add("article", "", $("il-dataset-list"), "il-dataset");
      add("p", `${item.region} / ${item.kind}`, card, "il-label");
      add("h3", item.title, card);
      add("p", item.use, card);
      add("p", `Access: ${item.access}`, card);
      add("p", `Rights: ${item.rights}`, card);
      add("p", item.limit, card, "il-caption");
      const link = add("a", "Open primary source ↗", card);
      link.href = item.url;
      const checked = add("details", "", card);
      add("summary", "What was checked", checked);
      add("p", item.verification, checked);
    }
  } catch {
    $("il-dataset-list").textContent =
      "The source register could not load. Its JSON download remains linked below.";
  }
}
$("il-desk").hidden = false;
render();
datasets();
