import test from "node:test";
import assert from "node:assert/strict";
import {
  createGuidedRun,
  guideBlocker,
  guidePair,
} from "../docs/assets/coastal-guide-model.mjs";

function harness({
  unchanged = false,
  failSync = false,
  sleep,
  afterCommand,
} = {}) {
  let now = 100000,
    captures = 0;
  const commands = [],
    updates = [];
  const state = {
    runId: "test",
    serverTime: now,
    controls: { paused: false, reject: false, failResponseOnce: false },
    observations: [],
    accepted: [],
    receipts: [],
    cycles: [],
    queues: { north: { pending: 0 }, south: { pending: 0 } },
  };
  const command = async (body) => {
    commands.push(body);
    now += 100;
    state.serverTime = now;
    if (body.action === "controls") state.controls = { ...body.controls };
    if (body.action === "capture-ais") {
      captures++;
      state.observations.push({
        id: `o${captures}`,
        origin: "south",
        evidence: "public-ais",
        source: { mmsi: 230123456 },
        observedAt: unchanged ? 1000 : captures * 1000,
        queuedAt: now,
        priority: body.priority,
        lon: 24.9 + captures / 100,
        lat: 60.1,
        acked: false,
      });
      state.aisCapture = { status: "complete", startedAt: now };
      state.queues.south.pending++;
    }
    if (body.action === "sync") {
      if (failSync && !state.controls.paused)
        throw Error("Uncertain network outcome");
      state.cycles.push({
        id: state.cycles.length + 1,
        result: { south: { success: !state.controls.paused } },
      });
      if (!state.controls.paused) {
        for (const o of [...state.observations].sort(
          (a, b) => b.observedAt - a.observedAt,
        )) {
          o.acked = true;
          state.accepted.push({
            station: "north",
            observation_id: o.id,
            first_received_at: now,
          });
          state.receipts.push({
            id: state.receipts.length + 1,
            station: "north",
            observation_id: o.id,
            received_at: now,
            outcome: "accepted",
          });
          if (state.controls.failResponseOnce) {
            state.receipts.at(-1).outcome = "accepted-response-failed";
            state.receipts.push({
              id: state.receipts.length + 1,
              station: "north",
              observation_id: o.id,
              received_at: now,
              outcome: "duplicate",
            });
            state.controls.failResponseOnce = false;
          }
        }
        state.queues.south.pending = 0;
      }
    }
    await afterCommand?.(body);
    return state;
  };
  const guide = createGuidedRun({
    getState: () => state,
    command,
    change: (r) => updates.push(r),
    sleep:
      sleep ??
      (async () => {
        now += 1000;
        state.serverTime = now;
      }),
  });
  return { state, commands, updates, guide };
}

test("guided run proves interruption, strictly newer source time and retained receiver position", async () => {
  const { guide, state, commands } = harness();
  await guide.begin();
  assert.equal(guide.state.phase, "held");
  assert.equal(state.receipts.length, 0);
  assert.equal(state.controls.paused, true);
  await guide.findNewer();
  assert.equal(guide.state.phase, "ready");
  assert.equal(
    state.receipts.length,
    0,
    "no delivery before deliberate release",
  );
  await guide.release();
  assert.equal(guide.state.phase, "complete");
  assert.equal(guide.state.arrival.retained.id, "o2");
  assert.equal(guide.state.arrival.receipt.id, 3);
  assert.equal(guide.state.retry.id, 2);
  assert.equal(state.controls.paused, false);
  assert.equal(state.controls.failResponseOnce, false);
  assert.deepEqual(
    commands.filter((c) => c.action === "capture-ais").map((c) => c.priority),
    ["low", "high"],
  );
});

test("unchanged timestamps exhaust the bounded search without claiming success or sending reports", async () => {
  const { guide, state, commands } = harness({ unchanged: true });
  await guide.begin();
  await guide.findNewer();
  assert.equal(guide.state.phase, "incomplete");
  assert.match(guide.state.note, /inconclusive/);
  assert.equal(state.observations.length, 4);
  assert.equal(state.receipts.length, 0);
  assert.equal(commands.filter((c) => c.action === "sync").length, 1);
  assert.equal(state.controls.paused, false);
});

test("stop while waiting restores conditions and preserves the captured report", async () => {
  let continueSleep;
  const { guide, state } = harness({
    sleep: () =>
      new Promise((resolve) => {
        continueSleep = resolve;
      }),
  });
  await guide.begin();
  const waiting = guide.findNewer();
  await guide.stop();
  continueSleep();
  await waiting;
  assert.equal(guide.state.phase, "stopped");
  assert.equal(state.controls.paused, false);
  assert.equal(state.observations.length, 1);
  assert.equal(state.receipts.length, 0);
});

test("uncertain burst is never automatically retried or called complete", async () => {
  const { guide, commands } = harness({ failSync: true });
  await guide.begin();
  await guide.findNewer();
  await guide.release();
  assert.equal(guide.state.phase, "incomplete");
  assert.match(guide.state.note, /Uncertain network outcome/);
  assert.equal(commands.filter((c) => c.action === "sync").length, 2);
});

test("stopping an in-flight burst keeps its completed receipts without claiming reports are still queued", async () => {
  let finish;
  let delivered;
  const inFlight = new Promise((resolve) => {
    delivered = resolve;
  });
  const { guide, state } = harness({
    afterCommand: async (body) => {
      if (body.action === "sync" && !state.controls.paused) {
        delivered();
        await new Promise((resolve) => {
          finish = resolve;
        });
      }
    },
  });
  await guide.begin();
  await guide.findNewer();
  const sending = guide.release();
  await inFlight;
  await guide.stop();
  finish();
  await sending;
  assert.equal(guide.state.phase, "stopped");
  assert.equal(state.queues.south.pending, 0);
  assert.equal(state.receipts.length, 3);
  assert.doesNotMatch(guide.state.note, /remain queued/);
  assert.equal(state.controls.paused, false);
});

test("preflight protects existing queues, journey conditions, capacity and capture cooldown", () => {
  const { state } = harness();
  assert.equal(guideBlocker(state), "");
  state.queues.north.pending = 1;
  assert.match(guideBlocker(state), /existing queue/);
  state.queues.north.pending = 0;
  state.controls.reject = true;
  assert.match(guideBlocker(state), /conditions/);
  state.controls.reject = false;
  state.observations = Array(161).fill({});
  assert.match(guideBlocker(state), /40 reports/);
  state.observations = [];
  state.aisCapture = { startedAt: state.serverTime - 14999 };
  assert.match(guideBlocker(state), /15 seconds/);
});

test("a different vessel, origin, or equal source time cannot supply the newer report", async () => {
  const { guide, state } = harness();
  await guide.begin();
  await guide.findNewer();
  const next = state.observations[1];
  next.source = { mmsi: 230999999 };
  assert.equal(guidePair(state, ["o1"], ["o2"]), null);
  next.source.mmsi = 230123456;
  next.origin = "north";
  assert.equal(guidePair(state, ["o1"], ["o2"]), null);
  next.origin = "south";
  next.observedAt = 1000;
  assert.equal(guidePair(state, ["o1"], ["o2"]), null);
});
