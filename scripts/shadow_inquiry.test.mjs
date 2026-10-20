import test from "node:test";
import assert from "node:assert/strict";
import {
  INQUIRY,
  inquirySnapshot,
} from "../docs/assets/shadow-inquiry-model.mjs";
test("knowledge is causal and relay does not create another original or family", () => {
  const start = inquirySnapshot(),
    relay = inquirySnapshot({ step: 1 });
  assert.deepEqual(start.counts, { deliveries: 2, originals: 2, families: 1 });
  assert.deepEqual(relay.counts, { deliveries: 3, originals: 2, families: 1 });
  assert.equal(relay.comparison, null);
  assert(!relay.reports.some((r) => r.id === "R-17"));
  assert.equal(start.coverage, "unknown");
  assert.equal(start.classification, "not assessed");
});
test("uncertainty changes compatibility, not raw reports or identity", () => {
  const raw = structuredClone(INQUIRY);
  const narrow = inquirySnapshot({ step: 2 });
  const broad = inquirySnapshot({ step: 3, uncertainty: 12 });
  assert.equal(narrow.comparison.radius, 71);
  assert(Math.abs(narrow.comparison.separation - Math.hypot(180, 70)) < 1e-10);
  assert(narrow.comparison.gap > 0);
  assert.equal(broad.comparison.gap, 0);
  assert.equal(broad.identity, "unresolved");
  assert.deepEqual(narrow.reports, broad.reports);
  assert.deepEqual(INQUIRY, raw);
});
test("clock correction is explicit and bounds include velocity uncertainty during clock uncertainty", () => {
  const r = inquirySnapshot({ step: 2, offset: -20, uncertainty: 10 });
  assert.equal(r.comparison.dt, 10);
  assert.equal(r.comparison.projected.x, 80);
  assert.equal(r.comparison.radius, 139);
  assert.equal(r.reports.at(-1).observed, 30);
  for (const args of [
    { step: 9 },
    { offset: 4 },
    { offset: NaN },
    { uncertainty: -1 },
  ])
    assert.throws(() => inquirySnapshot(args), RangeError);
});
