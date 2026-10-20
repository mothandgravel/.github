import { transportArrival } from "./coastal-transport-model.mjs";

const clearControls = { paused: false, reject: false, failResponseOnce: false };
export function guideBlocker(state) {
  if (!state || state.busy) return "Connect to an idle local service to begin.";
  if (Object.values(state.controls).some(Boolean))
    return "Clear the journey conditions before starting a guided run.";
  if (state.queues.north.pending || state.queues.south.pending)
    return "Finish the existing queue first. This run starts with both queues empty.";
  if (state.observations.length > 160)
    return "This run needs room for up to 40 reports. Export and use a new service data directory.";
  if (state.serverTime - (state.aisCapture?.startedAt ?? 0) < 15000)
    return "The AIS source needs 15 seconds between captures. Try again shortly.";
  return "";
}

export function guidePair(state, olderIds, newerIds) {
  const older = state.observations.filter((o) => olderIds.includes(o.id));
  for (const next of state.observations.filter((o) =>
    newerIds.includes(o.id),
  )) {
    const previous = older.find(
      (o) =>
        o.evidence === "public-ais" &&
        next.evidence === "public-ais" &&
        o.origin === next.origin &&
        o.source.mmsi === next.source.mmsi &&
        o.observedAt < next.observedAt,
    );
    if (previous) return { older: previous, newer: next };
  }
  return null;
}

// A guide drives the existing command API. Its progress is never transport evidence.
// Commands remain serial, including cancellation: an in-flight POST is not undone.
export function createGuidedRun({
  getState,
  command,
  change,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}) {
  let run = { phase: "idle", active: false, working: false, note: "" };
  let stopRequested = false;
  const publish = (patch) => {
    run = { ...run, ...patch };
    change(run);
  };
  const check = () => {
    if (stopRequested) throw Error("Stopped. Captured reports remain queued.");
    if (getState().runId !== run.runId)
      throw Error(
        "The service record changed. Reconnect and inspect its queue.",
      );
  };
  const send = async (body) => {
    check();
    const state = await command(body);
    check();
    return state;
  };
  const restore = async () => {
    // Do not alter a replacement service or silently retry an uncertain command.
    if (getState()?.runId !== run.runId)
      throw Error("The service record changed.");
    await command({ action: "controls", controls: clearControls });
  };
  async function perform(work) {
    if (run.working) return;
    publish({ working: true });
    try {
      await work();
    } catch (error) {
      let note = error.message;
      try {
        await restore();
        note += " Link restored; no additional reports sent.";
      } catch {
        note +=
          " Reconnect and check the link conditions; the last command may have completed.";
      }
      publish({
        phase: stopRequested ? "stopped" : "incomplete",
        active: false,
        note,
      });
    } finally {
      publish({ working: false });
    }
  }
  async function capture(priority) {
    const before = new Set(getState().observations.map((o) => o.id));
    const state = await send({
      action: "capture-ais",
      station: "south",
      priority,
    });
    if (state.aisCapture?.status !== "complete")
      throw Error(state.aisCapture?.error || "AIS capture did not complete.");
    return state.observations
      .filter((o) => !before.has(o.id) && o.origin === "south")
      .map((o) => o.id);
  }
  return {
    get state() {
      return run;
    },
    async begin() {
      if (run.active || run.working) return;
      const state = getState(),
        reason = guideBlocker(state);
      if (reason) {
        publish({ note: reason });
        return;
      }
      stopRequested = false;
      publish({
        phase: "capturing",
        active: true,
        runId: state.runId,
        olderIds: [],
        newerIds: [],
        pair: null,
        arrival: null,
        retry: null,
        note: "Closing South’s link and capturing the first live reports.",
      });
      await perform(async () => {
        await send({
          action: "controls",
          controls: { ...clearControls, paused: true },
        });
        const olderIds = await capture("low");
        publish({ olderIds });
        if (!olderIds.length)
          throw Error(
            "No new AIS reports were available. No late arrival was staged.",
          );
        const state = await send({ action: "sync" });
        const cycle = state.cycles.at(-1);
        if (
          cycle?.result?.south?.success !== false ||
          state.accepted.some((r) => olderIds.includes(r.observation_id))
        )
          throw Error(
            "The interrupted burst did not prove these reports were held.",
          );
        publish({
          phase: "held",
          interruption: cycle.id,
          note: `${olderIds.length} live reports held at South. Burst #${cycle.id} could not cross the interrupted link.`,
        });
      });
    },
    async findNewer() {
      if (run.phase !== "held") return;
      await perform(async () => {
        publish({
          phase: "waiting",
          note: "Waiting for the source clock to advance. Up to three captures, 20 seconds apart.",
        });
        for (let attempt = 1; attempt <= 3; attempt++) {
          // Short slices let Stop take effect while respecting the provider interval.
          for (let i = 0; i < 20; i++) {
            await sleep(1000);
            check();
          }
          const newerIds = [...run.newerIds, ...(await capture("high"))];
          const pair = guidePair(getState(), run.olderIds, newerIds);
          publish({
            newerIds,
            pair,
            note: `Capture ${attempt}/3: ${newerIds.length} later captures queued. ${pair ? "A newer source report matches the same vessel." : "No strictly newer report for the same vessel yet."}`,
          });
          if (pair) {
            publish({
              phase: "ready",
              note: `MMSI ${pair.older.source.mmsi} now has two source times. Restore the link to send the high-priority reports first, then the older reports.`,
            });
            return;
          }
        }
        throw Error(
          "No matching newer source report arrived within three captures. This run is inconclusive; timestamps were not changed.",
        );
      });
    },
    async release() {
      if (run.phase !== "ready") return;
      await perform(async () => {
        publish({
          phase: "sending",
          note: "Restoring the link. One acceptance returns 503 so the queue must retry. Follow the actual burst below.",
        });
        await send({
          action: "controls",
          controls: { ...clearControls, failResponseOnce: true },
        });
        const state = await send({ action: "sync" });
        const arrival = transportArrival(state, run.pair.older.id, "north");
        const failedResponse = state.receipts.find(
          (r) =>
            run.newerIds.includes(r.observation_id) &&
            r.station === "north" &&
            r.outcome === "accepted-response-failed",
        );
        const retry =
          failedResponse &&
          state.receipts.find(
            (r) =>
              r.observation_id === failedResponse.observation_id &&
              r.station === "north" &&
              r.outcome === "duplicate" &&
              r.id > failedResponse.id,
          );
        if (
          arrival?.status !== "late" ||
          !run.newerIds.includes(arrival.retained?.id) ||
          arrival.current?.id !== arrival.retained?.id ||
          !arrival.receipt ||
          !retry ||
          state.journalError ||
          run.olderIds
            .concat(run.newerIds)
            .some((id) => !state.observations.find((o) => o.id === id)?.acked)
        )
          throw Error(
            "The burst ended without a complete late-arrival proof. Inspect the receipts before sending again.",
          );
        await restore();
        publish({
          phase: "complete",
          active: false,
          arrival,
          retry,
          burst: state.cycles.at(-1)?.id,
          note: `Receipt #${arrival.receipt.id} accepted the older report. The newer position stayed current. Retry receipt #${retry.id} kept its original observation identity.`,
        });
      });
    },
    async stop() {
      if (!run.active) return;
      stopRequested = true;
      if (run.working) {
        publish({
          note: "Stopping after the current request. An in-flight burst may finish; its receipts are kept.",
        });
      } else {
        await perform(async () => {
          throw Error("Stopped. Captured reports remain queued.");
        });
      }
    },
  };
}
