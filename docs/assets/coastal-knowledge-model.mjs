import { transportArrival } from "./coastal-transport-model.mjs";

/** Reconstruct crossings from persisted evidence, not from a remembered UI animation. */
export function knowledgeRuns(state) {
  if (!state) return [];
  return state.observations
    .flatMap((o) => {
      if (o.evidence !== "public-ais" || o.origin !== "south") return [];
      const arrival = transportArrival(state, o.id, "north");
      if (arrival?.status !== "late" || !arrival.receipt) return [];
      const first = state.receipts.find(
        (r) =>
          r.observation_id === arrival.retained.id &&
          r.station === "north" &&
          r.received_at ===
            state.accepted.find(
              (a) =>
                a.station === "north" &&
                a.observation_id === arrival.retained.id,
            )?.first_received_at &&
          ["accepted", "accepted-response-failed"].includes(r.outcome),
      );
      if (!first) return [];
      const attempt = state.attempts.find(
        (a) => a.id === arrival.receipt.attempt_id,
      );
      const burst = state.cycles.find((c) => c.id === attempt?.cycle_id);
      if (!burst) return [];
      const interruption = state.cycles
        .filter(
          (c) =>
            c.result?.south?.success === false &&
            c.result.south.error === "No connection" &&
            c.started_at >= o.queuedAt &&
            c.finished_at <= arrival.retained.queuedAt &&
            c.finished_at <= burst.started_at,
        )
        .at(-1);
      const retry = state.receipts.find(
        (r) =>
          r.station === "north" &&
          r.observation_id === first.observation_id &&
          r.outcome === "duplicate" &&
          r.id > first.id &&
          r.id < arrival.receipt.id &&
          r.received_at <= arrival.receivedAt,
      );
      const steps = [
        {
          kind: "held",
          time: o.queuedAt,
          title: "South keeps the first report.",
          note: "It exists in South’s queue. North can only show what it had received by this moment.",
        },
        ...(interruption
          ? [
              {
                kind: "interrupted",
                time: interruption.finished_at,
                title: "The link cannot carry it.",
                note: `Burst #${interruption.id} recorded “No connection”. No delivery is inferred from the attempt to connect.`,
              },
            ]
          : []),
        {
          kind: "captured",
          time: arrival.retained.queuedAt,
          title: "South has a newer observation.",
          note: "The source timestamp has advanced. South can update its picture while North still waits for this report.",
        },
        {
          kind: "burst",
          time: burst.started_at,
          title: "The burst begins.",
          note: `Burst #${burst.id} starts. A sender starting work is not yet a receiver accepting a report.`,
        },
        {
          kind: "newer",
          time: first.received_at,
          receipt: first,
          title: "The newer report arrives first.",
          note: `Receipt #${first.id} stores the newer observation at North. It becomes North’s latest source-timed report for this vessel.`,
        },
        ...(retry
          ? [
              {
                kind: "retry",
                time: retry.received_at,
                receipt: retry,
                title: "A second arrival. The same report.",
                note: `Receipt #${retry.id} records a duplicate. Receiving it again adds a receipt, not another known observation.`,
              },
            ]
          : []),
        {
          kind: "late",
          time: arrival.receivedAt,
          receipt: arrival.receipt,
          title: "The late report fills the history.",
          note: `Receipt #${arrival.receipt.id} accepts the older observation. North keeps the newer position; its history gains the report that waited.`,
        },
      ].sort(
        (a, b) =>
          a.time - b.time || (a.receipt?.id ?? -1) - (b.receipt?.id ?? -1),
      );
      // Do not build a causal story from inconsistent or incomplete evidence.
      if (
        o.queuedAt > arrival.retained.queuedAt ||
      arrival.retained.queuedAt > burst.started_at ||
        arrival.retained.queuedAt > first.received_at ||
        burst.started_at > first.received_at ||
        first.id >= arrival.receipt.id
      )
        return [];
      return [
        { id: o.id, older: o, newer: arrival.retained, burst: burst.id, steps },
      ];
    })
    .sort(
      (a, b) =>
        b.steps.at(-1).time - a.steps.at(-1).time ||
        b.steps.at(-1).receipt.id - a.steps.at(-1).receipt.id,
    );
}

/** Project this vessel at an evidence boundary. Equal-ms receipts require journal order. */
export function knowledgeSnapshot(state, run, index) {
  const step = run.steps[index];
  if (!step) throw Error("Unknown replay step");
  const limit = step.receipt?.id ?? -1;
  const observations = state.observations.filter(
    (o) =>
      o.evidence === "public-ais" &&
      o.origin === run.older.origin &&
      o.source.mmsi === run.older.source.mmsi &&
      o.queuedAt <= step.time,
  );
  const ids = new Set(observations.map((o) => o.id));
  const receipts = state.receipts.filter(
    (r) =>
      ids.has(r.observation_id) &&
      (r.received_at < step.time ||
        (r.received_at === step.time && r.id <= limit)),
  );
  const accepted = state.accepted.filter(
    (a) =>
      ids.has(a.observation_id) &&
      receipts.some(
        (r) =>
          r.station === a.station &&
          r.observation_id === a.observation_id &&
          r.received_at === a.first_received_at &&
          ["accepted", "accepted-response-failed"].includes(r.outcome),
      ),
  );
  return { ...state, serverTime: step.time, observations, receipts, accepted };
}
