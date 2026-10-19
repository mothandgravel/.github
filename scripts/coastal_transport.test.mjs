import test from "node:test";
import assert from "node:assert/strict";
import {
  transportPicture,
  transportJourney,
} from "../docs/assets/coastal-transport-model.mjs";
const observation = (id, observedAt, mmsi = 230123456) => ({
  id,
  origin: "south",
  evidence: "public-ais",
  source: { mmsi },
  observedAt,
  queuedAt: observedAt + 100,
});

const crossing = () => ({
  serverTime: 10000,
  busy: false,
  controls: { paused: false, reject: false },
  cycles: [],
  observations: [
    { ...observation("report", 1000), messageId: "message", acked: false },
  ],
  attempts: [],
  receipts: [],
  accepted: [],
});
test("an interrupted link holds a report without inventing a POST or arrival", () => {
  const s = crossing();
  s.controls.paused = true;
  const j = transportJourney(s, "report");
  assert.equal(j.phase, "interrupted");
  assert.equal(j.events.length, 1);
  assert.equal(j.accepted, undefined);
  assert.equal(j.attempts.length, 0);
  s.observations[0].origin = "north";
  assert.equal(transportJourney(s, "report").phase, "queued");
});
test("acceptance survives a lost response and later interruption; duplicate receipt joins the exact retry", () => {
  const s = crossing();
  s.controls.paused = true;
  s.attempts = [
    {
      id: "first",
      message_id: "message",
      cycle_id: 1,
      attempt: 1,
      started_at: 2000,
      finished_at: 2100,
      status: 503,
      error: "failed",
    },
    {
      id: "retry",
      message_id: "message",
      cycle_id: 1,
      attempt: 2,
      started_at: 2600,
      finished_at: 2700,
      status: 200,
      error: null,
    },
    {
      id: "unrelated",
      message_id: "other",
      cycle_id: 1,
      attempt: 1,
      started_at: 2600,
      finished_at: 2700,
      status: 200,
      error: null,
    },
  ];
  s.receipts = [
    {
      id: 1,
      attempt_id: "first",
      observation_id: "report",
      station: "north",
      received_at: 2050,
      outcome: "accepted-response-failed",
      status: 503,
    },
    {
      id: 2,
      attempt_id: "retry",
      observation_id: "report",
      station: "north",
      received_at: 2650,
      outcome: "duplicate",
      status: 200,
    },
  ];
  s.accepted = [
    { observation_id: "report", station: "north", first_received_at: 2050 },
  ];
  let j = transportJourney(s, "report");
  assert.equal(j.phase, "received");
  assert.equal(j.attempts.length, 2);
  assert.equal(j.events.find((e) => e.receipt?.id === 2).attempt.id, "retry");
  assert.equal(j.events.filter((e) => e.kind === "queue").length, 1);
  s.observations[0].acked = true;
  j = transportJourney(s, "report");
  assert.equal(j.phase, "acknowledged");
  assert.equal(j.accepted.first_received_at, 2050);
});
test("an unfinished attempt is unknown after a burst ends, and rejection never becomes acceptance", () => {
  const s = crossing();
  s.attempts = [
    {
      id: "a",
      message_id: "message",
      cycle_id: 1,
      attempt: 1,
      started_at: 2000,
      finished_at: null,
      status: null,
      error: null,
    },
  ];
  assert.equal(transportJourney(s, "report").phase, "unknown");
  s.busy = true;
  s.cycles = [{ id: 1, finished_at: null }];
  assert.equal(transportJourney(s, "report").phase, "sending");
  s.busy = false;
  s.controls.reject = true;
  s.attempts[0].finished_at = 2100;
  s.attempts[0].status = 503;
  s.attempts[0].error = "failed";
  s.receipts = [
    {
      id: 1,
      attempt_id: "a",
      observation_id: "report",
      station: "north",
      received_at: 2050,
      outcome: "rejected",
      status: 503,
    },
  ];
  const j = transportJourney(s, "report");
  assert.equal(j.phase, "refused");
  assert.equal(j.accepted, undefined);
  assert.equal(j.events.find((e) => e.kind === "receipt").phase, "refused");
});
test("unreceived or rejected reports stay absent; a retry does not reset freshness", () => {
  const o = observation("a", 1000);
  const s = {
    serverTime: 10000,
    observations: [o],
    accepted: [],
    receipts: [
      {
        observation_id: "a",
        station: "north",
        outcome: "rejected",
        received_at: 4000,
      },
    ],
  };
  assert.equal(transportPicture(s, "north").records.length, 0);
  s.accepted.push({
    observation_id: "a",
    station: "north",
    first_received_at: 5000,
  });
  s.receipts.push({
    observation_id: "a",
    station: "north",
    outcome: "duplicate",
    received_at: 9000,
  });
  const p = transportPicture(s, "north");
  assert.equal(p.records.length, 1);
  assert.equal(p.records[0].availableAt, 5000);
  assert.equal(p.records[0].age, 9);
});
test("late arrival retains history without replacing a newer report; vessels stay distinct", () => {
  const s = {
    serverTime: 10000,
    observations: [
      observation("old", 1000),
      observation("new", 3000),
      observation("other", 2000, 230123457),
    ],
    accepted: [
      { observation_id: "old", station: "north", first_received_at: 9000 },
      { observation_id: "new", station: "north", first_received_at: 4000 },
      { observation_id: "other", station: "north", first_received_at: 5000 },
    ],
  };
  const p = transportPicture(s, "north");
  assert.equal(p.records.length, 3);
  assert.deepEqual(p.latest.map((o) => o.id).sort(), ["new", "other"]);
});
test("one upstream at two stations remains two source records without a corroboration claim", () => {
  const south = observation("s", 1000),
    north = { ...observation("n", 1000), origin: "north" };
  const s = {
    serverTime: 10000,
    observations: [south, north],
    accepted: [
      { observation_id: "s", station: "north", first_received_at: 5000 },
    ],
  };
  assert.equal(transportPicture(s, "north").latest.length, 2);
});
test("future source timestamps and future receipts cannot enter the current picture", () => {
  const s = {
    serverTime: 5000,
    observations: [observation("future", 6000), observation("late", 1000)],
    accepted: [
      { observation_id: "future", station: "north", first_received_at: 4000 },
      { observation_id: "late", station: "north", first_received_at: 6000 },
    ],
  };
  assert.deepEqual(transportPicture(s, "north").records, []);
});

test("equal timestamps retain POST, receipt and response ordering across retries", () => {
  const s = crossing();
  s.attempts = [
    {
      id: "z-first",
      message_id: "message",
      cycle_id: 1,
      attempt: 1,
      started_at: 2000,
      finished_at: 2000,
      status: 503,
      error: "failed",
    },
    {
      id: "a-second",
      message_id: "message",
      cycle_id: 1,
      attempt: 2,
      started_at: 2000,
      finished_at: 2000,
      status: 200,
      error: null,
    },
  ];
  s.receipts = [
    {
      id: 1,
      attempt_id: "z-first",
      observation_id: "report",
      station: "north",
      received_at: 2000,
      outcome: "accepted-response-failed",
      status: 503,
    },
    {
      id: 2,
      attempt_id: "a-second",
      observation_id: "report",
      station: "north",
      received_at: 2000,
      outcome: "duplicate",
      status: 200,
    },
  ];
  assert.deepEqual(
    transportJourney(s, "report").events.map((e) => e.id),
    [
      "queue-report",
      "start-z-first",
      "receipt-1",
      "end-z-first",
      "start-a-second",
      "receipt-2",
      "end-a-second",
    ],
  );
});
