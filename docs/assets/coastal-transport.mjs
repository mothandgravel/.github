import { createTransportTransit } from "./coastal-transit.mjs";
import {
  transportPicture,
  shortObservation,
  transportClock as clock,
} from "./coastal-transport-model.mjs";
const $ = (id) => document.getElementById(id);
const add = (tag, text, parent, className) => {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  parent.append(el);
  return el;
};
const svg = (tag, attrs, parent) => {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  parent.append(el);
  return el;
};
const point = (lon, lat) => [(lon - 24.55) * 857.143, (60.19 - lat) * 1714.286];
const title = (value) => value[0].toUpperCase() + value.slice(1);
const date = (time) => new Date(time).toISOString();
const signatures = new Map();
function changed(key, value) {
  const signature = JSON.stringify(value);
  if (signatures.get(key) === signature) return false;
  signatures.set(key, signature);
  return true;
}
let state = null,
  selected = null,
  station = "north",
  live = false,
  connected = false,
  busy = false,
  timer = null,
  requestVersion = 0;
let earlier = false,
  filtered = false;
function announce(text, tone = "normal") {
  $("ct-status").textContent = text;
  $("ct-status").dataset.tone = tone;
}
function schedule() {
  clearTimeout(timer);
  if (live && connected && !document.hidden)
    timer = setTimeout(() => refresh(false), busy || state?.busy ? 200 : 1500);
}
function availability() {
  const disabled = !connected || busy || Boolean(state?.busy);
  for (const el of document.querySelectorAll(
    "#ct-controls input,#ct-controls select,#ct-controls button,.ct-conditions input,#ct-observe",
  ))
    el.disabled = disabled;
  $("ct-controls").setAttribute("aria-busy", String(busy));
  $("ct-refresh").disabled = busy;
  $("ct-export").disabled = !state;
  $("ct-filter").disabled = !selected;
  if (!selected) {
    filtered = false;
    $("ct-filter").checked = false;
  }
  $("ct-start").hidden = connected;
  $("ct-connection").dataset.connected = String(connected);
  $("ct-connection").textContent = connected
    ? "Local service connected"
    : "Service disconnected";
  $("ct-panel").dataset.busy = String(busy);
}
function select(id, s) {
  if (!state?.observations.some((o) => o.id === id)) return;
  selected = id;
  station = s;
  $("ct-station").value = s;
  render();
  $("ct-selection-status").textContent =
    `${shortObservation(state.observations.find((o) => o.id === id))} selected. Its record is open below the plots.`;
}
function setEvidence(view) {
  for (const kind of ["receipts", "attempts"]) {
    $(`ct-${kind}-pane`).hidden = view !== kind;
    $(`ct-${kind}-tab`).setAttribute("aria-pressed", String(view === kind));
  }
}
function renderCharts() {
  const focused = document.activeElement?.dataset?.transportFocus;
  for (const s of ["north", "south"]) {
    const picture = transportPicture(state, s),
      layer = $(`ct-${s}-marks`);
    // Avoid rebuilding focused marks on every poll; age changes only alter freshness class.
    const visible = earlier
      ? picture.records
      : picture.records.filter(
          (o) => picture.latest.some((l) => l.id === o.id) || o.id === selected,
        );
    if (
      changed(`map-${s}`, [
        visible.map((o) => [o.id, o.age > 120]),
        selected,
        station,
        earlier,
      ])
    ) {
      layer.replaceChildren();
      for (const o of visible) {
        const [x, y] = point(o.lon, o.lat),
          latest = picture.latest.some((l) => l.id === o.id),
          isSelected = selected === o.id && station === s;
        const g = svg(
          "g",
          {
            role: "button",
            tabindex: "0",
            "aria-label": `Inspect ${shortObservation(o)} at ${s} station`,
          },
          layer,
        );
        g.dataset.transportFocus = `${s}-${o.id}`;
        svg("title", {}, g).textContent = shortObservation(o);
        svg("circle", { cx: x, cy: y, r: 16, class: "hit" }, g);
        const classes = `mark ${o.origin} ${o.age > 120 ? "old" : ""} ${!latest ? "history-mark" : ""} ${isSelected ? "selected" : ""}`;
        if (isSelected)
          svg("circle", { cx: x, cy: y, r: 15, class: "selection-ring" }, g);
        if (o.origin === "north")
          svg(
            "path",
            { d: `M${x} ${y - 5} l5 5 -5 5 -5 -5Z`, class: classes },
            g,
          );
        else
          svg("circle", { cx: x, cy: y, r: latest ? 5 : 3, class: classes }, g);
        g.addEventListener("click", () => select(o.id, s));
        g.addEventListener("keydown", (e) => {
          if (["Enter", " "].includes(e.key)) {
            e.preventDefault();
            select(o.id, s);
          }
        });
      }
      const o = visible.find((o) => o.id === selected);
      if (o && s === station) {
        const [x, y] = point(o.lon, o.lat),
          label =
            o.evidence === "public-ais"
              ? `AIS / ${o.source.mmsi}`
              : "SYNTHETIC SAMPLE",
          lx = Math.min(445, Math.max(10, x + 18)),
          ly = Math.min(333, Math.max(15, y - 24));
        const g = svg(
          "g",
          { "aria-hidden": "true", "pointer-events": "none" },
          layer,
        );
        svg(
          "rect",
          {
            x: lx - 6,
            y: ly - 12,
            width: 145,
            height: 22,
            rx: 1,
            class: "selection-label-bg",
          },
          g,
        );
        svg(
          "text",
          { x: lx, y: ly + 2, class: "selection-label" },
          g,
        ).textContent = label;
      }
    }
    const known = picture.records.length,
      ais = picture.latest.filter((o) => o.evidence === "public-ais").length;
    $(`ct-${s}-count`).textContent = String(known).padStart(2, "0");
    const summary = $(`ct-${s}-summary`);
    if (changed(`summary-${s}`, [known, ais, state.queues[s].pending])) {
      summary.replaceChildren();
      add("span", `${ais} AIS contact records · ${known} reports`, summary);
      add("strong", `${state.queues[s].pending} waiting`, summary);
    }
  }
  if (focused)
    document
      .querySelector(`[data-transport-focus="${focused}"]`)
      ?.focus({ preventScroll: true });
}
function renderRecord() {
  const observations = state.observations;
  if (
    changed(
      "picker",
      observations.map((o) => o.id),
    )
  ) {
    const picker = $("ct-observation");
    picker.replaceChildren();
    add("option", "Choose a record", picker).value = "";
    for (const o of [...observations].reverse()) {
      const option = add(
        "option",
        `${shortObservation(o)} · ${clock(o.observedAt)}`,
        picker,
      );
      option.value = o.id;
    }
  }
  $("ct-observation").value = selected ?? "";
  const o = observations.find((o) => o.id === selected);
  const receipt = state.accepted.find(
    (r) => r.station === station && r.observation_id === selected,
  );
  if (!changed("record", [o, station, receipt])) return;
  const record = $("ct-record");
  record.replaceChildren();
  if (!o) {
    add(
      "p",
      "Choose a mark on either shore, or open a report from the receipt ledger.",
      record,
    );
    add(
      "p",
      "Its source, queue entry and arrival will stay together here.",
      record,
      "cw-muted",
    );
    return;
  }
  const isAis = o.evidence === "public-ais",
    local = o.origin === station;
  const kicker = add("div", "", record, "ct-record-kicker");
  add(
    "span",
    isAis ? "Public AIS / Digitraffic" : "Synthetic / sample",
    kicker,
  );
  add("span", `${title(o.origin)} origin`, kicker);
  add("h3", isAis ? String(o.source.mmsi) : "Sample observation", record);
  add(
    "p",
    `${o.lat.toFixed(6)}° N / ${o.lon.toFixed(6)}° E`,
    record,
    "ct-record-position",
  );
  if (isAis) {
    const stats = add("div", "", record, "ct-source-stats");
    for (const [k, v] of [
      ["Speed", o.source.sog === null ? "—" : `${o.source.sog.toFixed(1)} kn`],
      ["Course", o.source.cog === null ? "—" : `${o.source.cog.toFixed(1)}°`],
      ["Heading", o.source.heading === null ? "—" : `${o.source.heading}°`],
    ]) {
      const item = add("span", k, stats);
      add("strong", v, item);
    }
  }
  const steps = add("ol", "", record, "ct-journey");
  const journey = [
    [isAis ? "Source timestampExternal" : "Sample observed", o.observedAt],
    ...(isAis ? [["Fetched from Digitraffic", o.source.fetchedAt]] : []),
    [`Queued at ${title(o.origin)}`, o.queuedAt],
    ...(local
      ? []
      : [[`Accepted at ${title(station)}`, receipt?.first_received_at]]),
  ];
  for (const [label, time] of journey) {
    const li = add("li", "", steps);
    li.dataset.pending = String(!time);
    add("strong", label, li);
    const t = add(
      "time",
      time ? `${clock(time)} UTC` : "Not received at this shore",
      li,
    );
    if (time) t.dateTime = date(time);
  }
  add(
    "p",
    o.acked
      ? "Sender acknowledged. The receiver’s record remains separate."
      : "Waiting for sender acknowledgement.",
    record,
    "cw-muted",
  );
  const details = add("details", "", record, "ct-record-ids");
  add("summary", "Identity & provenance", details);
  const dl = add("dl", "", details);
  for (const [k, v] of [
    ["Observation ID", o.id],
    ["Queue message ID", o.messageId],
    ["Source date / UTC", date(o.observedAt)],
    ["Priority", o.priority],
    ["Failed batches", String(o.failedBatches)],
    ...(isAis ? [["Timestamp meaning", o.source.timestampMeaning]] : []),
  ]) {
    add("dt", k, dl);
    add("dd", v, dl);
  }
  const copy = add("button", "Copy observation ID", details);
  copy.type = "button";
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(o.id);
      copy.textContent = "Copied";
    } catch {
      announce(
        "Clipboard unavailable. The observation ID is available in Identity & provenance.",
        "error",
      );
    }
  });
}
function renderLedgers() {
  const focused = document.activeElement?.dataset?.transportFocus;
  const observation = state.observations.find((o) => o.id === selected);
  const receipts = state.receipts.filter(
    (r) => !filtered || r.observation_id === selected,
  );
  if (changed("receipts", [receipts, selected])) {
    const target = $("ct-receipts");
    target.replaceChildren();
    for (const r of [...receipts].reverse()) {
      const o = state.observations.find((o) => o.id === r.observation_id),
        tr = add("tr", "", target);
      tr.dataset.selected = String(selected === r.observation_id);
      add("td", `#${r.id} / ${title(r.station)}`, tr);
      const button = add(
        "button",
        o?.evidence === "public-ais"
          ? String(o.source.mmsi)
          : o
            ? shortObservation(o)
            : r.observation_id,
        add("td", "", tr),
      );
      button.type = "button";
      button.dataset.transportFocus = `receipt-${r.id}`;
      button.setAttribute(
        "aria-label",
        `Open ${o ? shortObservation(o) : r.observation_id}, receipt ${r.id}`,
      );
      button.addEventListener("click", () =>
        select(r.observation_id, r.station),
      );
      add("td", clock(r.received_at), tr);
      const cell = add("td", "", tr),
        label = add("span", r.outcome.replaceAll("-", " "), cell, "ct-result");
      label.dataset.kind = r.outcome;
      add("span", `HTTP ${r.status}`, cell, "ct-receipt-outcome");
    }
    if (!receipts.length) {
      const cell = add(
        "td",
        filtered
          ? "No receipts for this observation."
          : "No arrivals yet. Send a queued report to begin the record.",
        add("tr", "", target),
      );
      cell.colSpan = 4;
    }
  }
  const attempts = state.attempts.filter(
    (a) => !filtered || a.message_id === observation?.messageId,
  );
  if (changed("attempts", attempts)) {
    const open = new Set(
      [...document.querySelectorAll("#ct-attempts details[open]")].map(
        (el) => el.dataset.attempt,
      ),
    );
    const target = $("ct-attempts");
    target.replaceChildren();
    for (const a of [...attempts].reverse()) {
      const tr = add("tr", "", target);
      add("td", `${a.cycle_id} / ${a.origin} / ${a.attempt}`, tr);
      add("td", clock(a.started_at), tr);
      add("td", clock(a.finished_at), tr);
      add(
        "td",
        a.finished_at === null
          ? "Unfinished / unknown"
          : a.error
            ? `${a.status ?? "Network error"} · ${a.error}`
            : `${a.status} · acknowledged`,
        tr,
      );
      const details = add("details", "", add("td", "", tr));
      details.dataset.attempt = a.id;
      details.open = open.has(a.id);
      add("summary", "IDs", details);
      add("p", `Attempt: ${a.id}`, details);
      add("p", `Queue: ${a.message_id}`, details);
    }
    if (!attempts.length) {
      const cell = add(
        "td",
        filtered
          ? "No attempts for this observation."
          : "No POST attempts. An interrupted link can keep a report in its queue.",
        add("tr", "", target),
      );
      cell.colSpan = 5;
    }
  }
  if (changed("cycles", state.cycles)) {
    const cycles = $("ct-cycles");
    cycles.replaceChildren();
    for (const c of [...state.cycles].reverse().slice(0, 8))
      add(
        "p",
        c.result
          ? `Burst ${c.id} · North: ${c.result.north.messagesSent} sent, ${c.result.north.error ?? "complete"} · South: ${c.result.south.messagesSent} sent, ${c.result.south.error ?? "complete"}`
          : `Burst ${c.id} · unfinished / outcome unknown`,
        cycles,
      );
    if (!state.cycles.length) add("p", "No bursts yet.", cycles);
  }
  if (focused)
    document
      .querySelector(`[data-transport-focus="${focused}"]`)
      ?.focus({ preventScroll: true });
}
function render() {
  if (!state) return;
  if (!selected) {
    filtered = false;
    $("ct-filter").checked = false;
  }
  $("ct-run").textContent =
    `Run ${state.runId} · snapshot ${date(state.serverTime)}`;
  $("ct-snapshot-clock").textContent = clock(state.serverTime).slice(0, 8);
  $("ct-snapshot-clock").dateTime = date(state.serverTime);
  $("ct-snapshot-date").textContent = date(state.serverTime).slice(0, 10);
  $("ct-paused").checked = state.controls.paused;
  $("ct-reject").checked = state.controls.reject;
  $("ct-response").checked = state.controls.failResponseOnce;
  const pending = state.queues.north.pending + state.queues.south.pending;
  for (const [id, value] of [
    ["observations", state.observations.length],
    ["pending", pending],
    ["receipts", state.receipts.length],
    ["attempts", state.attempts.length],
  ])
    $(`ct-metric-${id}`).textContent = String(value).padStart(2, "0");
  $("ct-summary").textContent =
    `${state.observations.length} original observations · ${state.receipts.length} HTTP receipts · ${state.attempts.length} POST attempts · ${state.accepted.length} accepted station records`;
  $("ct-journal-warning").textContent = state.journalError || "";
  const capture = state.aisCapture;
  if (changed("capture", capture))
    $("ct-ais-status").textContent = !capture
      ? "No public AIS captured yet."
      : capture.status === "complete"
        ? `Captured ${date(capture.fetchedAt)}: ${capture.added} queued, ${capture.duplicates} already known, ${capture.excluded} outside the extent, older than 10 minutes, future-dated or invalid, ${capture.limited} beyond this capture’s limit.`
        : capture.status === "failed"
          ? `AIS capture failed: ${capture.error}. Existing records remain; no synthetic replacement was added.`
          : "Fetching public AIS…";
  transit.update(state, {
    selected,
    connected,
    busy,
    origin: $("ct-origin").value,
  });
  renderCharts();
  renderRecord();
  renderLedgers();
  availability();
}
async function refresh(manual = true) {
  if (manual && busy) return;
  const version = ++requestVersion,
    wasConnected = connected;
  try {
    const response = await fetch("/api/coastal/state", {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw Error("Local transport endpoint unavailable");
    const next = await response.json();
    if (next.format !== "raivari.coastal-transport.v1")
      throw Error("Unexpected transport service");
    if (version !== requestVersion) return;
    state = next;
    connected = true;
    $("ct-workbench").hidden = false;
    render();
    if (!wasConnected || manual)
      announce(
        "Connected to Raivari. Capture a report, change its journey, then send it across.",
      );
  } catch {
    if (version !== requestVersion) return;
    connected = false;
    if (state)
      transit.update(state, {
        selected,
        connected,
        busy,
        origin: $("ct-origin").value,
      });
    availability();
    announce(
      state
        ? "Disconnected. Showing the last received snapshot. Reconnect to continue."
        : "Start the local service below. This static server has no queue or receiver.",
      "error",
    );
  }
  schedule();
}
async function command(body) {
  if (!connected || busy) return;
  busy = true;
  transit.stop();
  availability();
  clearTimeout(timer);
  ++requestVersion;
  schedule();
  if (state)
    transit.update(state, {
      selected,
      connected,
      busy,
      origin: $("ct-origin").value,
    });
  announce(
    body.action === "capture-ais"
      ? "Capturing public AIS from Digitraffic…"
      : body.action === "sync"
        ? "Sending the queued reports. Waiting for the receiver…"
        : "Saving the change…",
  );
  try {
    const response = await fetch("/api/coastal/command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Coastal-Workbench": "1",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(120000),
    });
    if (!response.ok) throw Error(await response.text());
    const next = await response.json();
    ++requestVersion;
    clearTimeout(timer);
    connected = true;
    state = next;
    if (body.action === "observe" || body.action === "capture-ais")
      selected = state.observations
        .filter((o) => o.origin === body.station)
        .at(-1)?.id;
    render();
    if (body.action === "capture-ais")
      announce(
        state.aisCapture?.status === "failed"
          ? `AIS capture failed: ${state.aisCapture.error}`
          : `${state.aisCapture?.added ?? 0} new AIS reports queued at ${title(body.station)}. Send when you are ready.`,
        state.aisCapture?.status === "failed" ? "error" : "normal",
      );
    else
      announce(
        body.action === "sync"
          ? "Burst finished. The receiver receipts and sender attempts are ready to inspect."
          : "Saved. The next delivery will use these conditions.",
      );
  } catch (error) {
    ++requestVersion;
    clearTimeout(timer);
    announce(
      `Request did not complete: ${error.message}. Refresh before retrying; the server may have stored it.`,
      "error",
    );
    connected = false;
  } finally {
    busy = false;
    if (state) render();
    availability();
    schedule();
  }
}
function mode(value) {
  live = value;
  document.body.classList.toggle("ct-active", live);
  $("ct-panel").hidden = !live;
  $("cw-desk").hidden = live;
  $("ct-live").setAttribute("aria-pressed", String(live));
  $("ct-authored").setAttribute("aria-pressed", String(!live));
  if ($("cw-play").getAttribute("aria-pressed") === "true")
    $("cw-play").click();
  if (live) void refresh(!busy);
  else {
    clearTimeout(timer);
    transit.stop();
  }
}
for (const s of ["north", "south"]) {
  const original = document.querySelector(`#cw-${s}-marks`).closest("svg"),
    map = original.cloneNode(true);
  map.setAttribute(
    "aria-label",
    `${s} station, actual transport availability of labelled observations`,
  );
  map
    .querySelectorAll("[id]")
    .forEach(
      (el) =>
        (el.id = el.id
          .replace("cw-", "ct-")
          .replace(`${s}-grid`, `ct-${s}-grid`)),
    );
  map.querySelector("rect").setAttribute("fill", `url(#ct-${s}-grid)`);
  map.querySelector(".cw-land").replaceChildren();
  map.querySelector(`#ct-${s}-marks`).replaceChildren();
  $(`ct-${s}-map`).append(map);
}
fetch(new URL("./coastal-replay-land.json", import.meta.url))
  .then((r) => {
    if (!r.ok) throw Error();
    return r.json();
  })
  .then((land) => {
    for (const layer of document.querySelectorAll("#ct-panel .cw-land"))
      for (const polygon of land.polygons)
        svg(
          "path",
          {
            class: "land",
            d: polygon
              .map(
                (ring) =>
                  ring
                    .map(([lon, lat], i) => {
                      const [x, y] = point(lon, lat);
                      return `${i ? "L" : "M"}${x} ${y}`;
                    })
                    .join(" ") + "Z",
              )
              .join(" "),
          },
          layer,
        );
  })
  .catch(() => {
    $("ct-map-note").textContent =
      "Coastline unavailable. Queue and receipt inspection remains available.";
  });
const transit = createTransportTransit({
  select,
  inspect(id, destination, event) {
    filtered = true;
    $("ct-filter").checked = true;
    select(id, destination);
    setEvidence(event.receipt ? "receipts" : "attempts");
    if (event.attempt) {
      const details = [
        ...document.querySelectorAll("#ct-attempts details"),
      ].find((el) => el.dataset.attempt === event.attempt.id);
      if (details) details.open = true;
    }
  },
});
$("ct-origin").addEventListener("change", () => {
  if (state) render();
});
$("ct-live").addEventListener("click", () => mode(true));
$("ct-authored").addEventListener("click", () => mode(false));
$("ct-refresh").addEventListener("click", () => refresh());
$("ct-observe").addEventListener("click", () =>
  command({
    action: "observe",
    station: $("ct-origin").value,
    priority: $("ct-priority").value,
  }),
);
$("ct-ais").addEventListener("click", () =>
  command({
    action: "capture-ais",
    station: $("ct-origin").value,
    priority: $("ct-priority").value,
  }),
);
$("ct-sync").addEventListener("click", () => command({ action: "sync" }));
for (const id of ["ct-paused", "ct-reject", "ct-response"])
  $(id).addEventListener("change", () =>
    command({
      action: "controls",
      controls: {
        paused: $("ct-paused").checked,
        reject: $("ct-reject").checked,
        failResponseOnce: $("ct-response").checked,
      },
    }),
  );
$("ct-observation").addEventListener("change", (e) => {
  selected = e.target.value || null;
  render();
});
$("ct-station").addEventListener("change", (e) => {
  station = e.target.value;
  render();
});
$("ct-history").addEventListener("change", (e) => {
  earlier = e.target.checked;
  renderCharts();
});
$("ct-filter").addEventListener("change", (e) => {
  filtered = e.target.checked;
  renderLedgers();
});
for (const view of ["receipts", "attempts"])
  $(`ct-${view}-tab`).addEventListener("click", () => setEvidence(view));
$("ct-export").addEventListener("click", async () => {
  if (!state) return;
  const payload = structuredClone(state),
    digest = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(JSON.stringify(payload)),
    );
  const blob = new Blob(
    [
      JSON.stringify(
        {
          integrity: {
            algorithm: "SHA-256",
            encoding: "UTF-8 JSON.stringify(payload)",
            digest: Array.from(new Uint8Array(digest), (b) =>
              b.toString(16).padStart(2, "0"),
            ).join(""),
            signed: false,
          },
          payload,
        },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = url;
  link.download = `coastal-transport-${state.runId}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  announce(
    "Exported this snapshot. Source provenance, queue records and receipts are included. Unsigned.",
  );
});
document.addEventListener("visibilitychange", () => {
  clearTimeout(timer);
  if (!document.hidden && live && connected) void refresh(false);
  if (document.hidden) transit.stop();
});
document.querySelector(".ct-mode").hidden = false;
availability();
if (new URL(location.href).searchParams.get("transport") === "live") mode(true);
