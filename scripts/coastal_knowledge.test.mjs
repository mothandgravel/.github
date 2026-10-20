import test from "node:test";
import assert from "node:assert/strict";
import {
  knowledgeRuns,
  knowledgeSnapshot,
} from "../docs/assets/coastal-knowledge-model.mjs";
import { transportPicture } from "../docs/assets/coastal-transport-model.mjs";

export function crossingFixture() {
  const observation = (id, observedAt, queuedAt, lon) => ({
    id,
    observedAt,
    queuedAt,
    lon,
    lat: 60.1,
    origin: "south",
    evidence: "public-ais",
    source: { mmsi: 230123456 },
  });
  return {
    runId: "knowledge-test",
    serverTime: 20000,
    observations: [
      observation("old", 1000, 2000, 24.8),
      observation("new", 4000, 5000, 24.9),
    ],
    accepted: [
      { observation_id: "new", station: "north", first_received_at: 7000 },
      { observation_id: "old", station: "north", first_received_at: 7000 },
    ],
    receipts: [
      {
        id: 1,
        observation_id: "new",
        station: "north",
        received_at: 7000,
        outcome: "accepted-response-failed",
        attempt_id: "a1",
      },
      {
        id: 2,
        observation_id: "new",
        station: "north",
        received_at: 7000,
        outcome: "duplicate",
        attempt_id: "a2",
      },
      {
        id: 3,
        observation_id: "old",
        station: "north",
        received_at: 7000,
        outcome: "accepted",
        attempt_id: "a3",
      },
    ],
    attempts: [
      { id: "a1", cycle_id: 2 },
      { id: "a2", cycle_id: 2 },
      { id: "a3", cycle_id: 2 },
    ],
    cycles: [
      {
        id: 1,
        started_at: 3000,
        finished_at: 3100,
        result: { south: { success: false, error: "No connection" } },
      },
      { id: 2, started_at: 6000, finished_at: 8000 },
    ],
  };
}
test("recorded replay changes both shores at queue and receipt boundaries without future knowledge", () => {
  const state = crossingFixture(),
    before = structuredClone(state);
  const run = knowledgeRuns(state)[0];
  assert.deepEqual(
    run.steps.map((s) => s.kind),
    ["held", "interrupted", "captured", "burst", "newer", "retry", "late"],
  );
  const counts = run.steps.map((step, i) => {
    const snapshot = knowledgeSnapshot(state, run, i);
    return ["south", "north"].map(
      (station) => transportPicture(snapshot, station).records.length,
    );
  });
  assert.deepEqual(counts, [
    [1, 0],
    [1, 0],
    [2, 0],
    [2, 0],
    [2, 1],
    [2, 1],
    [2, 2],
  ]);
  const newer = transportPicture(knowledgeSnapshot(state, run, 4), "north")
    .latest[0];
  const late = transportPicture(knowledgeSnapshot(state, run, 6), "north")
    .latest[0];
  assert.equal(newer.id, late.id);
  assert.equal(newer.lon, late.lon);
  assert.equal(
    transportPicture(knowledgeSnapshot(state, run, 1), "north").records.length,
    0,
    "rewinding removes later knowledge",
  );
  assert.deepEqual(state, before, "read-only replay leaves evidence unchanged");
});
test("same-millisecond receipt order prevents a later acceptance leaking into the newer or retry step", () => {
  const state = crossingFixture(),
    run = knowledgeRuns(state)[0];
  assert.deepEqual(
    knowledgeSnapshot(state, run, 4).receipts.map((r) => r.id),
    [1],
  );
  assert.deepEqual(
    knowledgeSnapshot(state, run, 5).receipts.map((r) => r.id),
    [1, 2],
  );
  assert.deepEqual(
    knowledgeSnapshot(state, run, 6).receipts.map((r) => r.id),
    [1, 2, 3],
  );
  state.receipts.find((r) => r.id === 3).id = 0;
  assert.equal(knowledgeRuns(state).length, 0);
});
test("incomplete evidence does not invent a burst, connection failure or first acceptance", () => {
  const state = crossingFixture();
  state.cycles.shift();
  assert(!knowledgeRuns(state)[0].steps.some((s) => s.kind === "interrupted"));
  state.attempts = [];
  assert.equal(knowledgeRuns(state).length, 0);
  const missing = crossingFixture();
  missing.receipts.shift();
  assert.equal(knowledgeRuns(missing).length, 0);
});
test("replay preserves prior knowledge for the focused vessel and excludes other contacts", () => {
  const state = crossingFixture();
  const previous = {
    ...state.observations[0],
    id: "previous",
    observedAt: 100,
    queuedAt: 200,
  };
  state.observations.push(previous, {
    ...previous,
    id: "other",
    source: { mmsi: 230999999 },
  });
  state.accepted.push({
    observation_id: "previous",
    station: "north",
    first_received_at: 300,
  });
  state.receipts.unshift({
    id: 0,
    observation_id: "previous",
    station: "north",
    received_at: 300,
    outcome: "accepted",
  });
  const run = knowledgeRuns(state).find((r) => r.id === "old");
  assert.deepEqual(
    transportPicture(knowledgeSnapshot(state, run, 0), "north").records.map(
      (o) => o.id,
    ),
    ["previous"],
  );
  assert(
    !knowledgeSnapshot(state, run, 6).observations.some(
      (o) => o.id === "other",
    ),
  );
});
