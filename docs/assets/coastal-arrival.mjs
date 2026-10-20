import {
  transportArrival,
  shortObservation,
  transportClock,
} from "./coastal-transport-model.mjs";

const $ = (id) => document.getElementById(id);
const title = (s) => (s === "north" ? "North" : "South");
const duration = (ms) => {
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
};
const add = (tag, text, parent, cls) => {
  const el = document.createElement(tag);
  el.textContent = text;
  if (cls) el.className = cls;
  parent.append(el);
  return el;
};

export function createArrivalInspector({ select, inspect }) {
  let signature = "",
    pickerSignature = "",
    arrivals = [];
  $("ct-late-reports").addEventListener("change", (e) => {
    const a = arrivals.find((a) => a.observation.id === e.target.value);
    if (a) select(a.observation.id, a.station);
  });
  return function update(state, selected) {
    arrivals = state.observations.map((o) => transportArrival(state, o.id));
    const late = arrivals.filter((a) => a.status === "late");
    const ids = JSON.stringify(late.map((a) => a.observation.id));
    if (ids !== pickerSignature) {
      pickerSignature = ids;
      const picker = $("ct-late-reports");
      picker.replaceChildren();
      add(
        "option",
        late.length
          ? `Choose an arrival · ${late.length} recorded`
          : "No out-of-order arrivals recorded",
        picker,
      ).value = "";
      for (const a of [...late].reverse())
        add(
          "option",
          `${shortObservation(a.observation)} · received ${transportClock(a.receivedAt)}`,
          picker,
        ).value = a.observation.id;
      picker.disabled = !late.length;
    }
    const id =
      selected ||
      [...state.observations].reverse().find((o) => !o.acked)?.id ||
      state.observations.at(-1)?.id;
    $("ct-late-reports").value = late.some((a) => a.observation.id === id)
      ? id
      : "";
    const a = arrivals.find((a) => a.observation.id === id);
    const sig = JSON.stringify(a);
    if (sig === signature) return;
    signature = sig;
    const panel = $("ct-arrival-comparison");
    panel.dataset.arrival = a?.status || "empty";
    $("ct-arrival-heading").textContent =
      a?.status === "late"
        ? "History grows. The position stays."
        : a?.status === "pending"
          ? "Still at the first shore."
          : "One report. Two times.";
    const grid = $("ct-arrival-clocks");
    grid.replaceChildren();
    const card = (label, time, detail) => {
      const el = add("div", "", grid, "ct-time-card");
      add("span", label, el, "cw-label");
      const t = add("time", time == null ? "—" : transportClock(time), el);
      if (time != null) t.dateTime = new Date(time).toISOString();
      add(
        "small",
        time == null
          ? detail
          : `${new Date(time).toISOString().slice(0, 10)} UTC · ${detail}`,
        el,
      );
      return el;
    };
    card(
      "01 / Observed",
      a?.observation.observedAt,
      a?.observation.evidence === "public-ais"
        ? "Source timestampExternal"
        : "Synthetic sample time",
    );
    card(
      `02 / First received${a ? " at " + title(a.station) : ""}`,
      a?.receivedAt,
      a?.receivedAt != null
        ? `${duration(a.sourceAgeMs)} after source time · ${duration(a.queueDelayMs)} since queued`
        : "No acceptance recorded",
    );
    const retained = a?.retained;
    const third = card(
      "03 / Already known at arrival",
      a?.previous?.observedAt,
      a?.previous
        ? retained
          ? "Newer source time · kept on the chart"
          : "Earlier or equal source time"
        : "No prior report established for this contact",
    );
    if (retained) {
      const b = add(
        "button",
        "Inspect the retained report ↗",
        third,
        "ct-text-button",
      );
      b.type = "button";
      b.addEventListener("click", () => select(retained.id, a.station));
    }
    $("ct-arrival-explanation").textContent = !a
      ? "Choose a report to compare its source time with its first acceptance."
      : a.status === "late"
        ? `${title(a.station)} already held a report observed ${duration(retained.observedAt - a.observation.observedAt)} later for this contact and origin. This arrival adds a historical position; it does not move the latest mark backwards.${a.current?.id !== retained.id ? " Another, newer report is now latest." : ""}`
        : a.status === "pending"
          ? "A queue entry is not an arrival. The destination has no acceptance for this report yet."
          : "This report was not established as out of order at first acceptance. A long delay alone does not make an arrival out of order.";
    const action = $("ct-arrival-receipt");
    action.hidden = !a?.receipt;
    action.textContent = a?.receipt
      ? `Inspect first receipt #${a.receipt.id} ↗`
      : "";
    action.onclick = () => {
      if (a?.receipt) inspect(a.observation.id, a.station, a.receipt);
    };
  };
}
