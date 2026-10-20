const contactKey = (o) =>
  `${o.origin}:${o.evidence === "public-ais" ? "ais-" + o.source.mmsi : "synthetic"}`;
const sourceOrder = (a, b) =>
  a.observedAt - b.observedAt || a.id.localeCompare(b.id);

/** Project actual queue/receiver evidence. Source evidence remains attached to each observation. */
export function transportPicture(state, station) {
  if (!["north", "south"].includes(station)) throw Error("Unknown station");
  const records = state.observations
    .flatMap((o) => {
      const remote = state.accepted.find(
        (r) => r.station === station && r.observation_id === o.id,
      );
      const availableAt =
        o.origin === station ? o.queuedAt : remote?.first_received_at;
      if (
        availableAt === undefined ||
        availableAt > state.serverTime ||
        o.observedAt > state.serverTime
      )
        return [];
      return [
        {
          ...o,
          availableAt,
          age: (state.serverTime - o.observedAt) / 1000,
          local: o.origin === station,
        },
      ];
    })
    .sort(sourceOrder);
  const latest = [...new Map(records.map((r) => [contactKey(r), r])).values()];
  return { records, latest };
}

/** Compare first acceptance with knowledge already present at that shore.
 * Duplicate receipts never change arrival time. Equal host milliseconds need
 * receiver journal order; without it, do not assert an out-of-order arrival.
 */
export function transportArrival(state, id, station) {
  const observation = state.observations.find((o) => o.id === id);
  if (!observation) return null;
  station ??= observation.origin === "south" ? "north" : "south";
  const picture = transportPicture(state, station);
  const currentRecord = picture.latest.find(
    (o) => contactKey(o) === contactKey(observation),
  );
  // Return immutable source records, not age-bearing projections. Polling must
  // not rebuild a focused inspector just because the snapshot clock advanced.
  const current = state.observations.find((o) => o.id === currentRecord?.id);
  const accepted = state.accepted.find(
    (r) => r.station === station && r.observation_id === id,
  );
  const base = { observation, station, current };
  if (station === observation.origin) return { ...base, status: "local" };
  if (
    !accepted ||
    accepted.first_received_at > state.serverTime ||
    observation.observedAt > state.serverTime
  )
    return { ...base, status: "pending" };
  const receivedAt = accepted.first_received_at;
  const firstReceipt = (recordId, time) =>
    state.receipts?.find(
      (r) =>
        r.observation_id === recordId &&
        r.station === station &&
        r.received_at === time &&
        ["accepted", "accepted-response-failed"].includes(r.outcome),
    );
  const receipt = firstReceipt(id, receivedAt);
  const previousRecord = picture.records
    .filter((o) => {
      if (o.id === id || contactKey(o) !== contactKey(observation))
        return false;
      if (o.observedAt > receivedAt) return false;
      if (o.availableAt < receivedAt) return true;
      const other = firstReceipt(o.id, o.availableAt);
      return (
        o.availableAt === receivedAt &&
        receipt &&
        other &&
        other.id < receipt.id
      );
    })
    .sort(sourceOrder)
    .at(-1);
  const previous = state.observations.find((o) => o.id === previousRecord?.id);
  const late = Boolean(
    previous && previous.observedAt > observation.observedAt,
  );
  return {
    ...base,
    status: late ? "late" : "accepted",
    receivedAt,
    receipt,
    previous,
    retained: late ? previous : null,
    sourceAgeMs: receivedAt - observation.observedAt,
    queueDelayMs: receivedAt - observation.queuedAt,
  };
}
export const shortObservation = (o) =>
  `${o.evidence === "public-ais" ? "AIS " + o.source.mmsi + " / " : ""}${o.origin === "north" ? "N" : "S"}-${o.id.slice(0, 8)}`;
export const transportClock = (time) =>
  time == null ? "—" : new Date(time).toISOString().slice(11, 23);

/** Join immutable evidence by identity, never by visual proximity or timestamp. */
export function transportJourney(state, id) {
  const observation = state.observations.find((o) => o.id === id);
  if (!observation) return null;
  const destination = observation.origin === "south" ? "north" : "south";
  const attempts = (state.attempts || [])
    .filter((a) => a.message_id === observation.messageId)
    .sort(
      (a, b) =>
        a.started_at - b.started_at ||
        a.cycle_id - b.cycle_id ||
        a.attempt - b.attempt ||
        a.id.localeCompare(b.id),
    );
  const receipts = state.receipts.filter(
    (r) => r.observation_id === id && r.station === destination,
  );
  const accepted = state.accepted.find(
    (r) => r.observation_id === id && r.station === destination,
  );
  const latest = attempts.at(-1);
  const active =
    state.busy &&
    state.aisCapture?.status !== "fetching" &&
    state.cycles?.some(
      (c) => c.id === latest?.cycle_id && c.finished_at === null,
    );
  const interrupted = observation.origin === "south" && state.controls.paused;
  const refused = observation.origin === "south" && state.controls.reject;
  const phase = observation.acked
    ? "acknowledged"
    : accepted
      ? "received"
      : active && latest?.finished_at === null
        ? "sending"
        : interrupted
          ? "interrupted"
          : active && latest?.error
            ? "retrying"
            : latest?.finished_at === null
              ? "unknown"
              : refused
                ? "refused"
                : "queued";
  const events = [
    {
      id: `queue-${id}`,
      kind: "queue",
      time: observation.queuedAt,
      phase: "queued",
      label: "Queued",
      order: 0,
    },
  ];
  for (const a of attempts) {
    events.push({
      id: `start-${a.id}`,
      kind: "attempt",
      time: a.started_at,
      phase: "sending",
      label: `POST ${a.attempt}`,
      attempt: a,
      order: 1,
    });
    if (a.finished_at !== null)
      events.push({
        id: `end-${a.id}`,
        kind: "result",
        time: a.finished_at,
        phase:
          a.status >= 200 && a.status < 300 && !a.error
            ? "acknowledged"
            : "retrying",
        label:
          a.status >= 200 && a.status < 300 && !a.error
            ? "Acknowledged"
            : "Response failed",
        attempt: a,
        order: 3,
      });
  }
  for (const r of receipts)
    events.push({
      id: `receipt-${r.id}`,
      kind: "receipt",
      time: r.received_at,
      phase: r.outcome === "rejected" ? "refused" : "received",
      label:
        r.outcome === "duplicate"
          ? "Duplicate receipt"
          : r.outcome === "rejected"
            ? "Refused"
            : "Accepted",
      receipt: r,
      attempt: attempts.find((a) => a.id === r.attempt_id),
      order: 2,
    });
  events.sort(
    (a, b) =>
      a.time - b.time ||
      (a.kind === "queue"
        ? -1
        : a.attempt
          ? attempts.indexOf(a.attempt) * 4 + a.order
          : attempts.length * 4 + a.order) -
        (b.kind === "queue"
          ? -1
          : b.attempt
            ? attempts.indexOf(b.attempt) * 4 + b.order
            : attempts.length * 4 + b.order) ||
      a.id.localeCompare(b.id),
  );
  return {
    observation,
    destination,
    attempts,
    receipts,
    accepted,
    phase,
    events,
  };
}
