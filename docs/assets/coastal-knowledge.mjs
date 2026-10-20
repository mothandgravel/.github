import {
  knowledgeRuns,
  knowledgeSnapshot,
} from "./coastal-knowledge-model.mjs";
import {
  transportPicture,
  transportClock,
} from "./coastal-transport-model.mjs";

export function createKnowledgeReplay({ redraw, select, inspect, onStart }) {
  const $ = (id) => document.getElementById(id);
  let state,
    frozen,
    runs = [],
    run = null,
    index = 0,
    timer,
    playing = false,
    locked = false,
    signature = "";
  const pause = () => {
    clearTimeout(timer);
    playing = false;
  };
  function draw() {
    $("ct-knowledge").dataset.replaying = String(Boolean(run));
    $("ct-knowledge-controls").hidden = !run;
    $("ct-knowledge-start").disabled = !runs.length || locked;
    $("ct-knowledge-start").hidden = Boolean(run);
    $("ct-knowledge-runs").disabled = !runs.length || locked;
    $("ct-knowledge-state").textContent = run
      ? "Recorded knowledge / vessel focus"
      : "Replay the evidence / two shores";
    $("ct-history").disabled = Boolean(run);
    if (!run) {
      $("ct-knowledge-heading").textContent = "What did each shore know?";
      $("ct-knowledge-note").textContent = runs.length
        ? "Open a recorded crossing. Step through what was available at each shore, then return to the live picture."
        : "Complete a late-arrival run to build a replay from its queue records and receipts.";
      $("ct-knowledge-clock").textContent = "—";
      $("ct-knowledge-stations").replaceChildren();
      return;
    }
    const step = run.steps[index],
      snapshot = knowledgeSnapshot(frozen, run, index);
    $("ct-knowledge-heading").textContent = step.title;
    $("ct-knowledge-note").textContent = step.note;
    $("ct-knowledge-clock").textContent =
      `${new Date(step.time).toISOString().slice(0, 10)} / ${transportClock(step.time)} UTC`;
    $("ct-knowledge-position").textContent =
      `${index + 1} / ${run.steps.length}`;
    $("ct-knowledge-prev").disabled = index === 0;
    $("ct-knowledge-next").disabled = index === run.steps.length - 1;
    $("ct-knowledge-play").textContent = playing
      ? "Pause replay"
      : index === run.steps.length - 1
        ? "Play again ↗"
        : "Play steps ↗";
    $("ct-knowledge-play").setAttribute("aria-pressed", String(playing));
    $("ct-knowledge-receipt").hidden = !step.receipt;
    $("ct-knowledge-receipt").textContent = step.receipt
      ? `Inspect receipt #${step.receipt.id} ↗`
      : "";
    const target = $("ct-knowledge-stations");
    target.replaceChildren();
    for (const station of ["south", "north"]) {
      const picture = transportPicture(snapshot, station),
        latest = picture.latest[0];
      const card = document.createElement("div");
      const label = document.createElement("span");
      label.className = "cw-label";
      label.textContent = `${station} / ${picture.records.length} reports known`;
      const time = document.createElement("strong");
      time.textContent = latest
        ? transportClock(latest.observedAt)
        : "Not yet known";
      const detail = document.createElement("small");
      detail.textContent = latest
        ? `Latest source time · ${latest.lon.toFixed(6)}° E, ${latest.lat.toFixed(6)}° N`
        : "No accepted report for this vessel at this boundary.";
      card.append(label, time, detail);
      target.append(card);
    }
  }
  function move(next) {
    index = Math.max(0, Math.min(run.steps.length - 1, next));
    draw();
    const step = run.steps[index];
    select(
      step.kind === "newer" || step.kind === "retry"
        ? run.newer.id
        : run.older.id,
      ["held", "interrupted", "captured"].includes(step.kind)
        ? "south"
        : "north",
    );
  }
  function tick() {
    timer = setTimeout(() => {
      if (!playing || !run) return;
      move(index + 1);
      if (index === run.steps.length - 1) {
        pause();
        draw();
      } else tick();
    }, 2400);
  }
  function start(id) {
    if (locked) return;
    const found = runs.find((r) => r.id === id) ?? runs[0];
    if (!found) return;
    onStart?.();
    pause();
    frozen = structuredClone(state);
    run = structuredClone(found);
    index = 0;
    $("ct-knowledge-runs").value = run.id;
    move(0);
  }
  function stop() {
    pause();
    run = null;
    frozen = null;
    draw();
    redraw();
  }
  $("ct-knowledge-start").addEventListener("click", () =>
    start($("ct-knowledge-runs").value),
  );
  $("ct-knowledge-runs").addEventListener("change", () => {
    if (run) start($("ct-knowledge-runs").value);
  });
  $("ct-knowledge-prev").addEventListener("click", () => {
    pause();
    move(index - 1);
  });
  $("ct-knowledge-next").addEventListener("click", () => {
    pause();
    move(index + 1);
  });
  $("ct-knowledge-live").addEventListener("click", stop);
  $("ct-knowledge-play").addEventListener("click", () => {
    if (playing) {
      pause();
      draw();
      return;
    }
    if (index === run.steps.length - 1) move(0);
    playing = true;
    draw();
    tick();
  });
  $("ct-knowledge-receipt").addEventListener("click", () => {
    pause();
    draw();
    const receipt = run.steps[index].receipt;
    if (receipt) inspect(receipt.observation_id, "north", receipt);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      pause();
      draw();
    }
  });
  return {
    get active() {
      return Boolean(run);
    },
    get snapshot() {
      return run ? knowledgeSnapshot(frozen, run, index) : null;
    },
    get label() {
      return run
        ? `Recorded step ${index + 1}/${run.steps.length} · MMSI ${run.older.source.mmsi} only · both plots show knowledge then. Journey, ledger and record inspectors below use the latest snapshot.`
        : "";
    },
    start,
    stop,
    update(next, unavailable) {
      state = next;
      locked = unavailable;
      if (run && state.runId !== frozen.runId) {
        pause();
        run = null;
        frozen = null;
      }
      // Keep an active replay frozen while live polling continues.
      runs = knowledgeRuns(state);
      const nextSignature = JSON.stringify(runs.map((r) => [r.id, r.burst]));
      if (signature !== nextSignature) {
        signature = nextSignature;
        const picker = $("ct-knowledge-runs"),
          previous = picker.value;
        picker.replaceChildren();
        for (const r of runs) {
          const option = document.createElement("option");
          option.value = r.id;
          option.textContent = `Burst #${r.burst} / MMSI ${r.older.source.mmsi} / receipt #${r.steps.at(-1).receipt.id}`;
          picker.append(option);
        }
        if (!runs.length) {
          const option = document.createElement("option");
          option.textContent = "No recorded crossing yet";
          picker.append(option);
        } else if (runs.some((r) => r.id === previous)) picker.value = previous;
      }
      draw();
    },
  };
}
