import test from "node:test";
import assert from "node:assert/strict";
import {
  RECORDS,
  recordDependencies,
  identitySnapshot,
  reviseIdentity,
  assessment,
  identityExport,
  readTransportSnapshot,
  transportIdentities,
} from "../docs/assets/coastal-identity-model.mjs";

test("receipt boundaries exclude later evidence and preserve the late document's effective time", () => {
  assert.deepEqual(
    identitySnapshot().records.map((r) => r.id),
    ["A-00"],
  );
  const before = identitySnapshot({ step: 3 }),
    after = identitySnapshot({ step: 4 });
  assert(!before.records.some((r) => r.id === "P-02"));
  assert.equal(after.records.at(-1).observed, -600);
  assert.equal(after.records.at(-1).received, 45);
});
test("copies and separate instruments do not multiply position origins", () => {
  const copied = identitySnapshot({ step: 1 }),
    bridge = identitySnapshot({ step: 2 }),
    radar = identitySnapshot({ step: 3 });
  assert.equal(copied.counts.deliveries, 3);
  assert.equal(copied.counts.originals, 2);
  assert.equal(copied.counts.positions, 2);
  assert.deepEqual(copied.roots, ["gnss"]);
  assert.equal(bridge.counts.positions, 3);
  assert.deepEqual(bridge.roots, ["gnss"]);
  assert.deepEqual(radar.roots, ["gnss", "radar"]);
});
test("position provenance never becomes evidence for identity-only records", () => {
  assert(!recordDependencies(RECORDS[0]).includes("gnss"));
  assert(recordDependencies(RECORDS[1]).includes("gnss"));
  assert(!identitySnapshot().sources.includes("gnss"));
});
test("shared correction moves every descendant together and never changes raw evidence or radar", () => {
  const original = JSON.stringify(RECORDS);
  const initial = identitySnapshot({ step: 3 });
  const moved = identitySnapshot({ step: 3, correction: 180 });
  assert(initial.comparison.gap > 0);
  assert.equal(moved.comparison.gap, 0);
  assert.equal(moved.comparison.association, "unverified");
  assert(moved.positions.filter((p) => p.shared).every((p) => p.x === 120));
  assert.deepEqual(
    moved.positions.find((p) => p.id === "R-17"),
    initial.positions.find((p) => p.id === "R-17"),
  );
  assert.equal(JSON.stringify(RECORDS), original);
  assert.equal(
    identitySnapshot({ step: 1, correction: 180 }).positions[0].x,
    300,
  );
});
test("identity revisions are reversible, append-only, and causal during rewind", () => {
  const original = JSON.stringify(RECORDS);
  const first = reviseIdentity([], "ember", 1);
  const other = reviseIdentity(first, "other", 4);
  const withdrawn = reviseIdentity(other, "unresolved", 4);
  assert.equal(first.length, 1);
  assert.equal(withdrawn.length, 3);
  assert.equal(assessment(other, 2), "ember");
  assert.equal(assessment(other, 4), "other");
  assert.equal(assessment(withdrawn, 4), "unresolved");
  assert.equal(assessment(withdrawn, 0), "unresolved");
  assert.equal(JSON.stringify(RECORDS), original);
  assert.throws(() => reviseIdentity([], "other", 3));
  assert.throws(() => reviseIdentity([], "ember", 0));
});
test("a withdrawal after rewind compares the visible assessment, not a later decision", () => {
  const linked = reviseIdentity([], "ember", 1);
  const futureWithdrawal = reviseIdentity(linked, "unresolved", 4);
  assert.equal(assessment(futureWithdrawal, 2), "ember");
  const pastWithdrawal = reviseIdentity(futureWithdrawal, "unresolved", 2);
  assert.equal(pastWithdrawal.length, 3);
  assert.equal(pastWithdrawal.at(-1).previous, "ember");
  assert.equal(assessment(pastWithdrawal, 2), "unresolved");
  assert.equal(futureWithdrawal.length, 2);
  assert.strictEqual(
    reviseIdentity(pastWithdrawal, "unresolved", 2),
    pastWithdrawal,
  );
});
test("export separates historical view, complete fixture and session revision history", () => {
  const journal = reviseIdentity([], "other", 4);
  const out = identityExport(
    { step: 1, correction: 0, allowance: 35 },
    journal,
  );
  assert.equal(out.signed, false);
  assert.equal(out.assessment, "unresolved");
  assert.equal(out.view.records.length, 3);
  assert.equal(out.fixture.records.length, 6);
  assert.equal(out.sessionRevisions.length, 1);
  assert.match(out.revisionMeaning, /later/);
});
test("invalid comparison settings are rejected", () => {
  for (const settings of [
    { step: -1 },
    { step: 5 },
    { step: 1.5 },
    { correction: Infinity },
    { correction: 241 },
    { allowance: -1 },
  ])
    assert.throws(() => identitySnapshot(settings));
});
const fixture = () => ({
  runId: "test",
  serverTime: 5000,
  observations: [
    {
      id: "old",
      origin: "south",
      evidence: "public-ais",
      observedAt: 1000,
      queuedAt: 1100,
      lat: 60,
      lon: 24,
      source: { mmsi: 990000001, provider: "Fixture source" },
    },
    {
      id: "new",
      origin: "south",
      evidence: "public-ais",
      observedAt: 2000,
      queuedAt: 2100,
      lat: 61,
      lon: 25,
      source: { mmsi: 990000001, provider: "Fixture source" },
    },
    {
      id: "sim",
      origin: "north",
      evidence: "synthetic-position",
      observedAt: 500,
      queuedAt: 600,
      lat: 60,
      lon: 24,
    },
  ],
  accepted: [
    { station: "north", observation_id: "new", first_received_at: 3000 },
    { station: "north", observation_id: "old", first_received_at: 4000 },
  ],
  receipts: [
    {
      id: 1,
      station: "north",
      observation_id: "new",
      received_at: 3000,
      outcome: "accepted-response-failed",
    },
    {
      id: 2,
      station: "north",
      observation_id: "new",
      received_at: 3500,
      outcome: "duplicate",
    },
    {
      id: 3,
      station: "north",
      observation_id: "old",
      received_at: 4000,
      outcome: "accepted",
    },
  ],
});
test("real transport projection retains newer source position despite late arrival and duplicate receipt", () => {
  const parsed = readTransportSnapshot({
    payload: fixture(),
    integrity: { signed: false },
  });
  const [north] = transportIdentities(parsed, "north");
  assert.equal(north.latest.id, "new");
  assert.equal(north.records.length, 2);
  assert.equal(north.receipts.length, 3);
  assert.match(north.identity, /unverified/);
  assert.match(north.dependencies, /unavailable/);
  assert.equal(
    transportIdentities({ ...parsed, serverTime: 3200 }, "north")[0].receipts
      .length,
    1,
  );
  assert.equal(
    transportIdentities({ ...parsed, serverTime: 2500 }, "north").length,
    0,
  );
});
test("invalid import fails atomically, bounds records and does not invent missing identity fields", () => {
  for (const mutate of [
    (s) => {
      s.observations[0].lat = 91;
    },
    (s) => {
      s.observations[0].source.mmsi = 12;
    },
    (s) => {
      s.observations.push(s.observations[0]);
    },
    (s) => {
      s.accepted.push(s.accepted[0]);
    },
    (s) => {
      s.receipts[0].id = null;
    },
    (s) => {
      s.accepted[0].first_received_at = -1;
    },
    (s) => {
      s.observations = Array(201).fill(s.observations[0]);
    },
    (s) => {
      s.observations[0].evidence = "radar";
    },
  ]) {
    const data = fixture();
    mutate(data);
    assert.throws(() => readTransportSnapshot(data));
  }
  const parsed = readTransportSnapshot(fixture());
  assert.equal(parsed.observations[0].name, undefined);
  assert.equal(parsed.observations[0].source.imo, undefined);
});
