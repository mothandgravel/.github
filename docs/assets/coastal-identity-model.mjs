import { transportPicture } from "./coastal-transport-model.mjs";

const freeze = (value) => {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};
export const IDENTITY_VERSION = "coastal-identity-v1";
export const SOURCES = freeze({
  gnss: {
    label: "GNSS K",
    parents: [],
    kind: "Position origin",
    detail:
      "One fictional position receiver supplies two instruments. Agreement between its descendants cannot exclude a shared error.",
  },
  ais: {
    label: "AIS transmitter",
    parents: ["gnss"],
    kind: "Report",
    detail:
      "Reported identity is entered separately from position. This instrument uses GNSS K for position.",
  },
  south: {
    label: "South receiver",
    parents: ["ais"],
    kind: "Delivery",
    detail:
      "Receives the AIS report. A receiving station does not create a new position measurement.",
  },
  north: {
    label: "North relay",
    parents: ["south"],
    kind: "Copy",
    detail:
      "Carries the same A-01 report to another station, with its original identity and timestamp.",
  },
  bridge: {
    label: "Bridge recorder",
    parents: ["gnss"],
    kind: "Recorded display",
    detail:
      "A separate record of a display, but its position still comes from GNSS K.",
  },
  radar: {
    label: "Radar N",
    parents: [],
    kind: "Position origin",
    detail:
      "Fictional shore radar in a fixed local coordinate frame. Its association with this vessel remains unverified.",
  },
  document: {
    label: "Port document",
    parents: [],
    kind: "Identity assertion",
    detail:
      "A fictional dated document. It describes another candidate with the same name; it contains no position measurement.",
  },
});
export const RECORDS = freeze([
  {
    id: "A-00",
    source: "south",
    original: "A-00",
    observed: -3600,
    received: 0,
    name: "EMBER",
    mmsi: 990000001,
    imo: 9900001,
    callSign: "DEMO-A",
    position: null,
    note: "Earlier identity report. All identifiers in this rehearsal are invented.",
  },
  {
    id: "A-01",
    source: "south",
    original: "A-01",
    observed: 10,
    received: 12,
    name: "VEIL",
    mmsi: 990000001,
    imo: 9900001,
    callSign: "DEMO-A",
    position: [300, 0],
    note: "A new name, with the same reported MMSI, IMO and callsign. This supports a question about continuity; it does not verify a hull.",
  },
  {
    id: "A-01-copy",
    source: "north",
    original: "A-01",
    observed: 10,
    received: 18,
    name: "VEIL",
    mmsi: 990000001,
    imo: 9900001,
    callSign: "DEMO-A",
    position: [300, 0],
    note: "A relay copy of A-01, not another identity or position observation.",
  },
  {
    id: "B-04",
    source: "bridge",
    original: "B-04",
    observed: 10,
    received: 25,
    name: null,
    mmsi: null,
    imo: null,
    callSign: null,
    position: [300, 0],
    note: "A separately recorded bridge position uses the same GNSS K input. It contains no independent identity claim.",
  },
  {
    id: "R-17",
    source: "radar",
    original: "R-17",
    observed: 10,
    received: 35,
    name: null,
    mmsi: null,
    imo: null,
    callSign: null,
    position: [120, 40],
    note: "A different position origin. No MMSI, name or IMO is measured by this radar; association remains a hypothesis.",
  },
  {
    id: "P-02",
    source: "document",
    original: "P-02",
    observed: -600,
    received: 45,
    name: "VEIL",
    mmsi: 990000002,
    imo: 9900002,
    callSign: "DEMO-B",
    position: null,
    note: "Late-arriving document, earlier effective time. Same name as A-01, different reported identifiers. Keep both accounts.",
  },
]);
export const CHAPTERS = freeze([
  {
    time: 0,
    title: "A name on the water.",
    label: "An earlier account",
    text: "EMBER appears in an earlier AIS report. The identifiers describe a claim made by that source. No hull identity has been independently established.",
  },
  {
    time: 18,
    title: "The name changes.",
    label: "The copied name",
    text: "The next report says VEIL. Its other identifiers remain the same. North receives a copy. Two deliveries still carry one new identity assertion.",
  },
  {
    time: 25,
    title: "Agreement has a parent.",
    label: "A shared origin",
    text: "A bridge record agrees with AIS. Follow both paths: they meet at GNSS K. Separate instruments can inherit the same error.",
  },
  {
    time: 35,
    title: "Move the assumption.",
    label: "Another instrument",
    text: "A radar mark sits elsewhere. Try a shared westward correction to GNSS K. Its descendants move together; the stored reports and radar mark stay untouched.",
  },
  {
    time: 45,
    title: "One name. Two accounts.",
    label: "The late document",
    text: "A document arrives with the name VEIL and different identifiers. Try linking the new AIS account to either candidate, then withdraw the link. A changed interpretation must not rewrite a source.",
  },
]);
export function ancestors(source, seen = new Set()) {
  if (!Object.hasOwn(SOURCES, source)) throw Error("Unknown source");
  if (seen.has(source)) return [...seen];
  seen.add(source);
  for (const parent of SOURCES[source].parents) ancestors(parent, seen);
  return [...seen];
}
export function recordDependencies(record) {
  // GNSS supplies position, never a name or an IMO assertion.
  return ancestors(record.source).filter(
    (id) => id !== "gnss" || record.position !== null,
  );
}
export function identitySnapshot({
  step = 0,
  correction = 0,
  allowance = 35,
} = {}) {
  if (
    !Number.isInteger(step) ||
    step < 0 ||
    step >= CHAPTERS.length ||
    !Number.isFinite(correction) ||
    correction < 0 ||
    correction > 240 ||
    !Number.isFinite(allowance) ||
    allowance < 0 ||
    allowance > 120
  )
    throw Error("Invalid inquiry setting");
  const chapter = CHAPTERS[step];
  const records = RECORDS.filter((r) => r.received <= chapter.time);
  const positioned = records.filter((r) => r.position);
  const effectiveCorrection = step >= 3 ? correction : 0;
  const positions = positioned.map((r) => ({
    id: r.id,
    source: r.source,
    original: r.original,
    shared: ancestors(r.source).includes("gnss"),
    x:
      r.position[0] -
      (ancestors(r.source).includes("gnss") ? effectiveCorrection : 0),
    y: r.position[1],
  }));
  const roots = [
    ...new Set(
      positioned.flatMap((r) =>
        ancestors(r.source).filter((s) => !SOURCES[s].parents.length),
      ),
    ),
  ];
  const separation =
    step >= 3 ? Math.hypot(180 - effectiveCorrection, 40) : null;
  return {
    chapter,
    step,
    records,
    positions,
    roots,
    sources: [...new Set(records.flatMap(recordDependencies))],
    counts: {
      deliveries: records.length,
      originals: new Set(records.map((r) => r.original)).size,
      positions: positioned.length,
      positionRoots: roots.length,
    },
    comparison:
      separation === null
        ? null
        : {
            separation,
            correction: effectiveCorrection,
            allowance,
            radarBound: 35,
            gap: Math.max(0, separation - allowance - 35),
            association: "unverified",
          },
  };
}
export function reviseIdentity(journal, link, step) {
  if (
    !["unresolved", "ember", "other"].includes(link) ||
    !Number.isInteger(step) ||
    step < 1 ||
    step > 4 ||
    (link === "other" && step < 4)
  )
    throw Error("Candidate is not available at this boundary");
  if (!Array.isArray(journal) || journal.length >= 100)
    throw Error("Export this session before adding more than 100 revisions");
  const previous = assessment(journal, step);
  if (previous === link) return journal;
  return [
    ...journal,
    {
      revision: journal.length + 1,
      step,
      link,
      previous,
      record: "A-01",
      kind: "analyst hypothesis",
      statement:
        link === "ember"
          ? "Associate A-01 with the earlier EMBER candidate."
          : link === "other"
            ? "Associate A-01 with the document candidate; identifier conflicts remain."
            : "Withdraw the association. Keep A-01 unresolved.",
    },
  ];
}
export function assessment(journal, step) {
  // Session revision order is distinct from the source clock. Future-boundary
  // decisions are excluded during rewind; a later revision at this step can supersede them.
  return journal.filter((j) => j.step <= step).at(-1)?.link ?? "unresolved";
}
export function identityExport(settings, journal) {
  return {
    schema: IDENTITY_VERSION,
    evidence: "authored synthetic rehearsal",
    signed: false,
    view: identitySnapshot(settings),
    assessment: assessment(journal, settings.step),
    sessionRevisions: structuredClone(journal),
    revisionMeaning:
      "All session revisions, including decisions made at boundaries later than the selected view.",
    fixture: {
      meaning: "Complete authored fixture, including not-yet-received records.",
      records: RECORDS,
      sources: SOURCES,
    },
    limits: [
      "No real vessel or sanctions finding.",
      "Bounds are illustrative, not calibrated confidence.",
      "A position match does not verify identity.",
      "Different roots do not prove statistical independence.",
    ],
  };
}

/** Validate the subset needed by Raivari's existing causal station projection.
 * This is an untrusted, unsigned snapshot; never mix it into the fictional case.
 */
export function readTransportSnapshot(input) {
  const data = input?.payload ?? input;
  const text = (v, max = 160) =>
    typeof v === "string" && v.length > 0 && v.length <= max;
  const time = (v) => Number.isSafeInteger(v) && v > 0 && v <= 8640000000000000;
  if (
    !data ||
    !text(data.runId) ||
    !time(data.serverTime) ||
    !Array.isArray(data.observations) ||
    data.observations.length > 200 ||
    !Array.isArray(data.accepted) ||
    data.accepted.length > 400 ||
    !Array.isArray(data.receipts) ||
    data.receipts.length > 5000
  )
    throw Error("Not a bounded Coastal watch transport snapshot");
  const ids = new Set();
  const observations = data.observations.map((o) => {
    if (
      !o ||
      !text(o.id) ||
      ids.has(o.id) ||
      !["north", "south"].includes(o.origin) ||
      !["public-ais", "synthetic-position"].includes(o.evidence) ||
      !time(o.observedAt) ||
      !time(o.queuedAt) ||
      !Number.isFinite(o.lat) ||
      Math.abs(o.lat) > 90 ||
      !Number.isFinite(o.lon) ||
      Math.abs(o.lon) > 180
    )
      throw Error("Invalid or duplicate observation");
    ids.add(o.id);
    if (
      o.evidence === "public-ais" &&
      (!o.source ||
        !Number.isInteger(o.source.mmsi) ||
        o.source.mmsi < 100000000 ||
        o.source.mmsi > 999999999 ||
        !text(o.source.provider))
    )
      throw Error("Invalid AIS source");
    return {
      id: o.id,
      origin: o.origin,
      evidence: o.evidence,
      observedAt: o.observedAt,
      queuedAt: o.queuedAt,
      lat: o.lat,
      lon: o.lon,
      ...(o.evidence === "public-ais"
        ? { source: { mmsi: o.source.mmsi, provider: o.source.provider } }
        : {}),
    };
  });
  const pairs = new Set();
  const accepted = data.accepted.map((a) => {
    const key = `${a?.station}:${a?.observation_id}`;
    if (
      !a ||
      !ids.has(a.observation_id) ||
      !["north", "south"].includes(a.station) ||
      !time(a.first_received_at) ||
      pairs.has(key)
    )
      throw Error("Invalid or duplicate station acceptance");
    pairs.add(key);
    return {
      station: a.station,
      observation_id: a.observation_id,
      first_received_at: a.first_received_at,
    };
  });
  const receipts = data.receipts.map((r) => {
    if (
      !r ||
      !(Number.isSafeInteger(r.id) && r.id > 0) ||
      !["north", "south"].includes(r.station) ||
      !time(r.received_at) ||
      !text(r.outcome) ||
      (r.observation_id != null && !text(r.observation_id))
    )
      throw Error("Invalid receipt");
    return {
      id: r.id,
      station: r.station,
      received_at: r.received_at,
      outcome: r.outcome,
      observation_id: r.observation_id,
    };
  });
  return {
    runId: data.runId,
    serverTime: data.serverTime,
    observations,
    accepted,
    receipts,
  };
}
export function transportIdentities(snapshot, station) {
  const picture = transportPicture(snapshot, station);
  return picture.latest
    .filter((o) => o.evidence === "public-ais")
    .map((latest) => ({
      latest,
      records: picture.records.filter(
        (r) =>
          r.evidence === "public-ais" &&
          r.source.mmsi === latest.source.mmsi &&
          r.origin === latest.origin,
      ),
      receipts: snapshot.receipts.filter(
        (r) =>
          r.station === station &&
          r.received_at <= snapshot.serverTime &&
          picture.records.some(
            (o) =>
              o.id === r.observation_id &&
              o.evidence === "public-ais" &&
              o.source.mmsi === latest.source.mmsi &&
              o.origin === latest.origin,
          ),
      ),
      identity: "MMSI grouping only; hull identity unverified",
      dependencies: "Receiver and GNSS lineage unavailable in this export",
    }));
}
