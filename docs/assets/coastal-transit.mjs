import {
  transportJourney,
  shortObservation,
  transportClock,
} from "./coastal-transport-model.mjs";

const $ = (id) => document.getElementById(id);
const title = (s) => (s === "south" ? "South" : "North");
const phases = {
  empty: "Waiting for a report",
  queued: "Held in the queue",
  interrupted: "Link interrupted",
  sending: "POST started",
  received: "Received · acknowledgement separate",
  acknowledged: "Sender acknowledged",
  retrying: "Response failed · retry pending",
  refused: "Delivery refused",
  unknown: "Unfinished attempt · outcome unknown",
};
const add = (tag, text, parent, cls) => {
  const el = document.createElement(tag);
  el.textContent = text;
  if (cls) el.className = cls;
  parent.append(el);
  return el;
};

export function createTransportTransit({ select, inspect }) {
  let state,
    selected,
    connected = false,
    busy = false,
    origin = "south";
  let currentId = null,
    signature = "",
    pickerSignature = "",
    eventFocus = null;
  let replay = null,
    replayTimer = null;
  const journey = () => transportJourney(state, currentId);
  function stop() {
    clearTimeout(replayTimer);
    replayTimer = null;
    replay = null;
    if (state) draw();
  }
  function eventDescription(e) {
    if (e.receipt)
      return `Receipt #${e.receipt.id} · ${title(e.receipt.station)} · ${e.receipt.outcome.replaceAll("-", " ")} · HTTP ${e.receipt.status}. ${e.attempt ? `POST ${e.attempt.attempt} in burst ${e.attempt.cycle_id}.` : "No matching sender attempt in this snapshot."}`;
    if (e.attempt)
      return `Burst ${e.attempt.cycle_id} · POST ${e.attempt.attempt} · ${e.kind === "attempt" ? "started" : `${e.attempt.status ?? "No HTTP response"} · ${e.attempt.error || "acknowledged"}`}. Attempt ${e.attempt.id}.`;
    return "Written to the originating SQLite queue. This is not a receiver receipt.";
  }
  function draw() {
    const j = journey();
    const events = replay?.events || j?.events || [];
    const current = replay ? events[replay.index] : null;
    const seen = replay ? events.slice(0, replay.index + 1) : events;
    const receipts = replay
      ? seen.filter((e) => e.receipt).map((e) => e.receipt)
      : j?.receipts || [];
    const accepted = receipts.some((r) => r.outcome !== "rejected");
    const phase = current?.phase || j?.phase || "empty";
    const from = j?.observation.origin || origin,
      to = from === "south" ? "north" : "south";
    $("ct-crossing").dataset.phase = phase;
    $("ct-crossing").dataset.replay = String(Boolean(replay));
    $("ct-from").textContent = title(from);
    $("ct-to").textContent = title(to);
    $("ct-from-state").textContent = j
      ? (
          replay
            ? seen.some((e) => e.phase === "acknowledged")
            : j.observation.acked
        )
        ? "Acknowledgement recorded"
        : "Report retained locally"
      : "No report selected";
    $("ct-to-state").textContent =
      accepted || (!replay && j?.accepted)
        ? "Observation stored"
        : "No acceptance recorded";
    $("ct-link-count").textContent =
      `${state.queues[from].pending} waiting now`;
    $("ct-receipt-count").textContent =
      `${receipts.length} ${replay ? "replayed " : ""}${receipts.length === 1 ? "receipt" : "receipts"}`;
    $("ct-link-state").textContent =
      (!connected && !replay ? "Last snapshot · " : "") + phases[phase];
    const runningBurst =
      (busy || state.busy) &&
      state.cycles?.at(-1)?.finished_at === null &&
      state.aisCapture?.status !== "fetching";
    $("ct-transit-mode").textContent = replay
      ? `Recorded replay / ${replay.index + 1} of ${events.length}`
      : runningBurst
        ? "Burst in progress / live snapshots"
        : busy || state.busy
          ? "Request in progress / live snapshots"
          : connected
            ? "Live evidence / latest snapshot"
            : "Disconnected / retained snapshot";
    $("ct-crossing-caption").textContent = current
      ? `${transportClock(current.time)} UTC · ${eventDescription(current)}`
      : j
        ? `${shortObservation(j.observation)} · ${j.attempts.length} POST attempts · ${j.receipts.length} receiver receipts. ${phase === "interrupted" ? "The report remains at its origin; no crossing is implied." : phase === "received" ? "Acceptance is recorded even if the sender is still waiting." : "Choose an event below to inspect its record."}`
        : "Capture public AIS, interrupt the link, then send. The queue keeps what the other shore has not received.";
    $("ct-replay-journey").textContent = replay
      ? "Return to live evidence ↗"
      : "Replay recorded journey ↗";
    $("ct-replay-journey").disabled =
      !j || j.events.length < 2 || busy || state.busy;
    const cycle = state.cycles?.at(-1);
    const burst = $("ct-burst-strip");
    burst.textContent = cycle
      ? `Latest burst ${cycle.id} / ${transportClock(cycle.started_at)} UTC · ${cycle.finished_at === null ? (state.busy ? "In progress" : "Unfinished / outcome unknown") : `${state.attempts.filter((a) => a.cycle_id === cycle.id).length} POST attempts recorded · ${[cycle.result?.north?.error, cycle.result?.south?.error].filter(Boolean).join(" / ") || "finished"}`}`
      : "No burst has run yet. Capturing a report does not send it.";
    const sig = JSON.stringify([currentId, events, eventFocus, replay?.index]);
    if (sig !== signature) {
      signature = sig;
      const focused = document.activeElement?.dataset?.transitEvent;
      const lane = $("ct-transit-events");
      const scrollLeft = lane.scrollLeft;
      lane.replaceChildren();
      for (const e of events) {
        const b = add("button", "", lane, "ct-transit-event");
        b.type = "button";
        b.dataset.transitEvent = e.id;
        b.dataset.kind = e.kind;
        b.setAttribute(
          "aria-pressed",
          String((current?.id || eventFocus) === e.id),
        );
        b.dataset.future = String(Boolean(replay && !seen.includes(e)));
        add(
          "span",
          e.attempt
            ? `BURST ${e.attempt.cycle_id} / ${e.kind === "receipt" ? "RECEIPT #" + e.receipt.id : "POST " + e.attempt.attempt}`
            : e.kind === "queue"
              ? "ORIGIN / SQLITE"
              : "RECEIPT #" + e.receipt.id,
          b,
          "cw-label",
        );
        add("strong", e.label, b);
        add("time", transportClock(e.time), b).dateTime = new Date(
          e.time,
        ).toISOString();
        b.addEventListener("click", () => {
          clearTimeout(replayTimer);
          replay = null;
          eventFocus = e.id;
          $("ct-event-detail").textContent =
            `${transportClock(e.time)} UTC · ${eventDescription(e)}`;
          inspect(currentId, to, e);
          draw();
        });
      }
      lane.scrollLeft = scrollLeft;
      if (focused)
        [...lane.children]
          .find((el) => el.dataset.transitEvent === focused)
          ?.focus({ preventScroll: true });
      if (current) {
        const target = [...lane.children].find(
          (el) => el.dataset.transitEvent === current.id,
        );
        if (target) lane.scrollLeft = target.offsetLeft - lane.offsetLeft;
      }
    }
  }
  function tick() {
    if (!replay) return;
    draw();
    if (replay.index < replay.events.length - 1)
      replayTimer = setTimeout(() => {
        replay.index++;
        tick();
      }, 1100);
  }
  $("ct-replay-journey").addEventListener("click", () => {
    if (replay) return stop();
    const j = journey();
    if (!j || busy || state.busy) return;
    eventFocus = null;
    $("ct-event-detail").textContent =
      "Choose an event to inspect its evidence.";
    replay = { events: structuredClone(j.events), index: 0 };
    tick();
  });
  $("ct-follow").addEventListener("change", (e) => {
    stop();
    eventFocus = null;
    const o = state.observations.find((o) => o.id === e.target.value);
    if (o) select(o.id, o.origin === "south" ? "north" : "south");
  });
  return {
    stop,
    update(next, options) {
      state = next;
      ({ selected, connected, busy, origin } = options);
      const id =
        selected ||
        [...state.observations].reverse().find((o) => !o.acked)?.id ||
        state.observations.at(-1)?.id ||
        null;
      if (id !== currentId || busy || state.busy) {
        clearTimeout(replayTimer);
        replay = null;
        if (id !== currentId) {
          eventFocus = null;
          $("ct-transit-events").scrollLeft = 0;
          $("ct-event-detail").textContent =
            "Choose an event to inspect its evidence.";
        }
      }
      currentId = id;
      const ids = JSON.stringify(state.observations.map((o) => o.id));
      if (ids !== pickerSignature) {
        pickerSignature = ids;
        const picker = $("ct-follow");
        picker.replaceChildren();
        if (!state.observations.length)
          add("option", "Capture a report to begin", picker).value = "";
        for (const o of [...state.observations].reverse())
          add(
            "option",
            `${shortObservation(o)} · ${transportClock(o.observedAt)}`,
            picker,
          ).value = o.id;
      }
      $("ct-follow").value = currentId || "";
      $("ct-follow").disabled = !currentId;
      // Keep the shore charts aligned with the selected report's direction.
      const from = journey()?.observation.origin || origin;
      for (const s of ["north", "south"])
        $(`ct-${s}-map`).closest(".cw-station").style.order =
          s === from ? "0" : "1";
      draw();
    },
  };
}
