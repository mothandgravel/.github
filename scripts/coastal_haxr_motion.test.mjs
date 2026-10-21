import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { followRadarReturn, createRadarHypotheses, MAX_HYPOTHESES } from "../docs/assets/coastal-haxr-motion.mjs";
import { createHaxrStudy } from "../docs/assets/coastal-haxr-model.mjs";
const pattern = [3, 41, 7, 90, 22, 51, 1, 72, 15, 32, 8, 63, 100, 4, 81, 37, 16, 92, 26, 58, 70, 11, 45, 2, 33];
const frame = (i, fill = 0) => ({ startTod: 100 + i * 3, endTod: 102 + i * 3, pixels: Array(16384).fill(fill) });
const stamp = (f, col, row) => { pattern.forEach((v, i) => { f.pixels[(row + Math.floor(i / 5) - 2) * 128 + col + i % 5 - 2] = v; }); return f; };
const record = frames => ({ station: "reiherstieg", frames, ais: { reports: [{ uid: "test", tod: 101, rangeMeters: 200, azimuthDegrees: 90 }] } });
const seed = { index: 0, col: 64, row: 64 };
test("fixed template follows translated texture without AIS steering", () => {
  const r = record([stamp(frame(0), 64, 64), stamp(frame(1), 65, 64), stamp(frame(2), 66, 63)]);
  const h = followRadarReturn(r, "test", seed);
  assert.deepEqual(h.steps.map(s => s.state), ["seed", "matched", "matched"]);
  assert.deepEqual(h.steps[2].radarDisplacement, { east: 62.5, north: 31.25 });
  const changed = structuredClone(r); changed.ais.reports = [{ uid: "test", tod: 101, rangeMeters: 1500, azimuthDegrees: 180 }];
  assert.deepEqual(followRadarReturn(changed, "test", seed).steps.map(s => s.accepted), h.steps.map(s => s.accepted));
  assert.equal(h.steps[2].aisDisplacement.east, 0);
});
test("stationary texture remains a fixed-bin hypothesis, not a shore classification", () => {
  const h = followRadarReturn(record([0, 1, 2].map(i => stamp(frame(i), 64, 64))), "test", seed);
  assert(h.steps.every(s => s.accepted.col === 64 && s.accepted.row === 64));
  assert.match(h.limits.join(" "), /moored vessel/);
  assert.equal(h.sourceFamilies, 1);
});
test("equal competing patches stop the chain and never silently reacquire", () => {
  const ambiguous = stamp(stamp(frame(1), 61, 64), 67, 64);
  const h = followRadarReturn(record([stamp(frame(0), 64, 64), ambiguous, stamp(frame(2), 64, 64)]), "test", seed, { searchBins: 4 });
  assert.equal(h.steps[1].state, "ambiguous"); assert.equal(h.steps[1].accepted, null);
  assert.equal(h.steps[1].margin, 0); assert.equal(h.steps[1].candidates.length, 2);
  assert.equal(h.steps[2].state, "stopped"); assert.equal(h.steps[2].accepted, null);
});
test("missing and flat patches cannot match; a fixed-bin zero remains measured", () => {
  const missing = frame(1, null); missing.pixels[64 * 128 + 64] = 0;
  const h = followRadarReturn(record([stamp(frame(0), 64, 64), missing]), "test", seed);
  assert.equal(h.steps[1].state, "insufficient"); assert.equal(h.steps[1].fixedBinAmplitude, 0);
  const flat = record([frame(0, 20), frame(1, 20)]);
  assert.equal(followRadarReturn(flat, "test", seed).steps[0].state, "unusable-seed");
  assert.equal(followRadarReturn(flat, "test", seed).steps[1].state, "stopped");
});
test("future radar cannot alter earlier hypotheses and before-seed steps stay untracked", () => {
  const r = record([0, 1, 2, 3].map(i => stamp(frame(i), 64, 64)));
  const h = followRadarReturn(r, "test", { ...seed, index: 1 });
  assert.equal(h.steps[0].state, "before-seed"); assert.equal(h.steps[0].accepted, null);
  r.frames[3].pixels.fill(null);
  assert.deepEqual(followRadarReturn(r, "test", { ...seed, index: 1 }).steps.slice(0, 3), h.steps.slice(0, 3));
});
test("search bounds, edge coverage and seed validity fail explicitly", () => {
  const r = record([stamp(frame(0), 64, 64), stamp(frame(1), 70, 64)]);
  assert.notEqual(followRadarReturn(r, "test", seed, { searchBins: 1 }).steps[1].state, "matched");
  for (const s of [{ ...seed, col: -1 }, { ...seed, row: 128 }, { ...seed, index: 9 }, { ...seed, col: 1.5 }]) assert.throws(() => followRadarReturn(r, "test", s));
  assert.throws(() => followRadarReturn(r, "test", seed, { searchBins: 9 }));
  assert.throws(() => followRadarReturn(r, "test", { ...seed, col: 0 }));
  const edge = frame(0, null); edge.pixels[0] = 5;
  assert.equal(followRadarReturn(record([edge]), "test", { index: 0, col: 0, row: 0 }).steps[0].state, "unusable-seed");
});
test("weak texture and inadequate common coverage stop without a fabricated position", () => {
  const weak = frame(1);
  pattern.toReversed().forEach((v, i) => { weak.pixels[(62 + Math.floor(i / 5)) * 128 + 62 + i % 5] = v; });
  const h = followRadarReturn(record([stamp(frame(0), 64, 64), weak]), "test", seed);
  assert.equal(h.steps[1].state, "weak"); assert.equal(h.steps[1].accepted, null);
  const missing = frame(1, null); missing.pixels[64 * 128 + 64] = 100;
  assert.equal(followRadarReturn(record([stamp(frame(0), 64, 64), missing]), "test", seed).steps[1].state, "insufficient");
});
test("recorded fixed-bin texture persists through AIS expiry without inventing a position", () => {
  const s = createHaxrStudy(["reiherstieg", "hohe-schaar"].map(id => JSON.parse(readFileSync(new URL(`../docs/data/haxr/${id}.json`, import.meta.url)))));
  const h = followRadarReturn(s.recordings.reiherstieg, "1b1e4", { index: 0, col: 62, row: 77 });
  assert(h.steps.every(step => step.accepted?.col === 62 && step.accepted?.row === 77));
  assert.equal(h.steps[4].ais, null); assert.equal(h.steps[4].displacementDifference, null);
  assert(h.steps[10].ais); assert(h.steps[10].displacementDifference < 31.25);
  assert.equal(h.steps[0].ais.ageSeconds, .7109375);
});

const forks = () => record([stamp(frame(0), 64, 64), ...[1, 2, 3].map(i => stamp(stamp(frame(i), 61, 64), 67, 64))]);
test("manual branches preserve the ambiguous parent, siblings and shared-source uncertainty", () => {
  const ledger = createRadarHypotheses(forks(), "test", seed, { searchBins: 4 });
  const before = structuredClone(ledger.get("H01"));
  const a = ledger.branch("H01", 1, 0), b = ledger.branch("H01", 1, 1);
  assert.deepEqual(ledger.get("H01"), before);
  assert.equal(a.id, "H02"); assert.equal(b.id, "H03");
  assert.equal(a.follow.steps[0].state, "before-seed");
  assert.equal(a.follow.seed.col, 61); assert.equal(b.follow.seed.col, 67);
  assert.equal(a.follow.steps[2].accepted.col, 61); assert.equal(b.follow.steps[2].accepted.col, 67);
  assert.equal(before.follow.steps[2].accepted, null);
  assert.equal(a.decision.parentState, "ambiguous"); assert.equal(a.decision.parentMargin, 0);
  assert.equal(a.decision.rank, 0); assert.equal(a.decision.kind, "manual-candidate-choice");
  assert.deepEqual(a.follow.policy, before.follow.policy);
  assert.match(a.decision.template, /Fresh 5x5/);
  assert.throws(() => { a.follow.steps[1].accepted.col = 80; }, TypeError);
  assert.throws(() => { a.decision.retainedCandidates[0].correlation = 1; }, TypeError);
  assert.equal(ledger.branch("H01", 1, 0), a, "Repeated choice reopens the same hypothesis");
  const exported = ledger.export(b.id, 2);
  assert.equal(exported.sourceFamilies, 1); assert.equal(exported.association, "unestablished");
  assert.equal(exported.entries.length, 3);
  assert.equal(exported.entries[0].follow.steps[1].accepted, null);
  assert.equal(ledger.export(a.id, 0).entries[1].follow.steps[0].accepted, null);
  assert.equal(ledger.export(a.id, 1).entries[0].follow.steps[1].state, "ambiguous");
  exported.entries.pop(); assert.equal(ledger.entries().length, 3);
});

test("branch selection rejects invented candidates, non-stop frames and bad cutoffs", () => {
  const ledger = createRadarHypotheses(forks(), "test", seed, { searchBins: 4 });
  for (const args of [["H99", 1, 0], ["H01", 0, 0], ["H01", 2, 0], ["H01", 1, -1], ["H01", 1, 2], ["H01", 1, .5], ["H01", "1", 0]]) assert.throws(() => ledger.branch(...args));
  for (const cutoff of [-1, 999, .5, "1"]) assert.throws(() => ledger.export("H01", cutoff));
  assert.equal(ledger.entries().length, 1);
});

test("recorded branch uses the candidate's stop-frame template, not the parent's seed texture", () => {
  const s = createHaxrStudy(["reiherstieg", "hohe-schaar"].map(id => JSON.parse(readFileSync(new URL(`../docs/data/haxr/${id}.json`, import.meta.url)))));
  const r = s.recordings.reiherstieg, ledger = createRadarHypotheses(r, "1b1e4", { index: 0, col: 46, row: 40 });
  const parent = ledger.get("H01"); assert.equal(parent.follow.steps[1].state, "ambiguous");
  const child = ledger.branch("H01", 1, 1);
  assert.equal(child.follow.seed.col, 45); assert.equal(child.follow.seed.index, 1);
  assert.deepEqual(child.follow, followRadarReturn(r, "1b1e4", { index: 1, col: 45, row: 40 }, { searchBins: 2 }));
  assert.equal(child.decision.parentMargin, parent.follow.steps[1].margin);
  assert.equal(parent.follow.steps[2].state, "stopped");
});

test("a branch can stop again, branch again, and remains bounded", () => {
  // Repeated identical textures leave many competing candidate centres.
  const frames = Array.from({ length: 20 }, (_, i) => {
    const f = frame(i); for (let y = 35; y < 94; y++) for (let x = 35; x < 94; x++) f.pixels[y * 128 + x] = (x + y) % 2 ? 20 : 100; return f;
  });
  const ledger = createRadarHypotheses(record(frames), "test", seed);
  let parent = ledger.get("H01");
  for (let i = 1; i < MAX_HYPOTHESES; i++) { parent = ledger.branch(parent.id, i, 0); assert.equal(parent.decision.parentState, "ambiguous"); }
  assert.equal(ledger.entries().length, MAX_HYPOTHESES);
  assert.throws(() => ledger.branch(parent.id, MAX_HYPOTHESES, 0), /at most 16/);
  assert.equal(ledger.branch("H01", 1, 0).id, "H02", "Existing choices still open at capacity");
});
