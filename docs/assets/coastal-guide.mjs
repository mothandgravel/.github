import { createGuidedRun, guideBlocker } from "./coastal-guide-model.mjs";
import { transportClock } from "./coastal-transport-model.mjs";

export function createGuide({
  getState,
  command,
  select,
  inspect,
  availability,
  replay,
}) {
  const $ = (id) => document.getElementById(id);
  const stages = [
    "First capture",
    "Interrupted",
    "Newer report",
    "Burst sync",
    "Position retained",
  ];
  const phaseIndex = {
    idle: -1,
    capturing: 0,
    held: 1,
    waiting: 2,
    ready: 2,
    sending: 3,
    complete: 4,
  };
  let connected = false,
    busy = false;
  const guide = createGuidedRun({
    getState,
    command,
    change(run) {
      render();
      availability();
      const id = run.pair?.older.id ?? run.olderIds?.[0];
      if (id)
        select(
          id,
          run.phase === "held" ||
            run.phase === "waiting" ||
            run.phase === "ready"
            ? "south"
            : "north",
        );
    },
  });
  function render() {
    const run = guide.state,
      state = getState();
    const index = phaseIndex[run.phase] ?? -1;
    $("ct-guide").dataset.phase = run.phase;
    $("ct-guide-progress").textContent =
      run.phase === "complete"
        ? "05 / Evidence recorded"
        : run.active
          ? `${String(Math.max(1, index + 1)).padStart(2, "0")} / Live run`
          : "Guided run / Live AIS";
    $("ct-guide-note").textContent =
      run.note ||
      "Let one report wait. Let a newer one pass. Then ask the receiver what changed.";
    for (const [i, el] of [...$("ct-guide-steps").children].entries()) {
      el.dataset.state = i < index ? "done" : i === index ? "current" : "next";
      if (i === index) el.setAttribute("aria-current", "step");
      else el.removeAttribute("aria-current");
      el.textContent = `${String(i + 1).padStart(2, "0")} / ${stages[i]}`;
    }
    const action = $("ct-guide-action");
    action.textContent =
      run.phase === "held"
        ? "Wait for a newer report ↗"
        : run.phase === "ready"
          ? "Restore link & burst ↗"
          : run.phase === "complete"
            ? "Run again ↗"
            : "Begin with live AIS ↗";
    action.hidden = run.active && !["held", "ready"].includes(run.phase);
    const blocker = !connected
      ? "Connect to the local service to begin."
      : guideBlocker(state);
    action.disabled = busy || run.working || (!run.active && Boolean(blocker));
    $("ct-guide-requirement").textContent =
      !run.active && blocker
        ? blocker
        : "South → North · Up to 40 reports · Three newer captures maximum · No timestamps rewritten";
    $("ct-guide-stop").hidden = !run.active;
    $("ct-guide-stop").disabled = !run.active;
    $("ct-guide-inspect").hidden = run.phase !== "complete";
    $("ct-guide-retry").hidden = run.phase !== "complete";
    $("ct-guide-replay").hidden = run.phase !== "complete";
    $("ct-guide-pair").hidden = !run.pair;
    if (run.pair) {
      $("ct-guide-older").textContent = transportClock(
        run.pair.older.observedAt,
      );
      $("ct-guide-newer").textContent = transportClock(
        run.arrival?.retained?.observedAt ?? run.pair.newer.observedAt,
      );
      $("ct-guide-vessel").textContent =
        `MMSI ${run.pair.older.source.mmsi} / Source times UTC`;
    }
  }
  $("ct-guide-action").addEventListener("click", () => {
    const run = guide.state;
    if (run.phase === "held") void guide.findNewer();
    else if (run.phase === "ready") void guide.release();
    else void guide.begin();
  });
  $("ct-guide-stop").addEventListener("click", () => void guide.stop());
  $("ct-guide-inspect").addEventListener("click", () => {
    const a = guide.state.arrival;
    if (a) inspect(a.observation.id, "north", a.receipt);
  });
  $("ct-guide-retry").addEventListener("click", () => {
    const r = guide.state.retry;
    if (r) inspect(r.observation_id, "north", r);
  });
  $("ct-guide-replay").addEventListener("click", () => {
    if (guide.state.arrival) replay(guide.state.arrival.observation.id);
  });
  window.addEventListener("beforeunload", (event) => {
    if (guide.state.active) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  return {
    get active() {
      return guide.state.active;
    },
    update(connection, working) {
      connected = connection;
      busy = working;
      render();
    },
  };
}
