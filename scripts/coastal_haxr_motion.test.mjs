import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { followRadarReturn } from "../docs/assets/coastal-haxr-motion.mjs";
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
