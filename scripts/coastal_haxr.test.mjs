import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createHaxrStudy, exportHaxrView } from "../docs/assets/coastal-haxr-model.mjs";
import { parseHaxr, selectHaxrAis, haxrPixels, pairRadarFrames, compareStationContinuity } from "../docs/assets/coastal-haxr-core.mjs";

const read = path => readFileSync(new URL(`../${path}`, import.meta.url));
const data = ["reiherstieg", "hohe-schaar"].map(id => JSON.parse(read(`docs/data/haxr/${id}.json`)));
const study = createHaxrStudy(data);
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
test("published extracts and browser core match pinned integrity references", () => {
  const manifest = JSON.parse(read("docs/design/coastal-haxr-provenance.json"));
  for (const asset of manifest.extracts) {
    const bytes = read(`docs/${asset.path}`);
    assert.equal(bytes.length, asset.bytes);
    assert.equal(hash(bytes), asset.sha256);
    const recording = JSON.parse(bytes);
    assert.equal(recording.frames.length, asset.frames);
    assert.equal(recording.ais.reports.length, asset.aisReports);
    const radar = manifest.sourceFiles.find(f => f.file === recording.file);
    const ais = manifest.sourceFiles.find(f => f.file === recording.ais.file);
    assert.equal(recording.sha256, radar.sha256);
    assert.equal(recording.sourceMd5, radar.md5.slice(4));
    assert.equal(recording.ais.sha256, ais.sha256);
    assert.equal(recording.ais.sourceMd5, ais.md5.slice(4));
  }
  const core = JSON.parse(read("docs/design/coastal-haxr-core.json"));
  assert.equal(hash(read("docs/assets/coastal-haxr-core.mjs").toString().replaceAll("\r\n", "\n")), core.bundleSha256);
});
test("actual recordings respond to endpoint bounds without changing returns", () => {
  const before = hash(JSON.stringify(study.recordings));
  for (const [tolerance, count] of [[.5, 0], [1, 10], [2, 16]]) {
    const v = study.view({ tolerance });
    assert.equal(v.pairing.pairs.length, count);
    assert.deepEqual(v.pairing, pairRadarFrames(parseHaxr(data[0]), parseHaxr(data[1]), tolerance));
  }
  assert.equal(hash(JSON.stringify(study.recordings)), before);
  assert(Object.isFrozen(study.recordings.reiherstieg.frames[0].pixels));
});
test("an ineligible nearest comparison never becomes a selected pair", () => {
  const v = study.view({ tolerance: 1 });
  assert.equal(v.selectedPair, null);
  assert.equal(v.preview.role, "nearest comparison only");
  assert.equal(v.preview.endpointSkew, 1.109375);
  assert.equal(v.unmatchedReason, "outside-skew-limit");
  const eligible = study.view({ tolerance: 2 });
  assert.equal(eligible.preview.role, "eligible pair");
  assert(eligible.selectedPair);
  assert.deepEqual(v.stations, eligible.stations);
});
test("both stations reuse the AIS policy and retain one shared family", () => {
  const v = study.view();
  assert.equal(v.sourceFamilies, 1);
  assert.equal(v.sharedIds, 10);
  for (const [id, s] of Object.entries(v.stations))
    assert.deepEqual(s.ais, selectHaxrAis(study.recordings[id].ais.reports, s.frame.endTod));
  const shared = v.contacts.find(c => Object.values(c.reports).every(Boolean));
  assert(shared);
  assert.notEqual(shared.reports.reiherstieg.rangeMeters, shared.reports.hohe_schaar.rangeMeters);
});
test("switching anchor uses the existing directional pairing and covers all frames", () => {
  for (const anchor of ["reiherstieg", "hohe_schaar"]) {
    for (let index = 0; index < 16; index++) {
      const v = study.view({ anchor, index, tolerance: 2 });
      assert.equal(v.stations[anchor].index, index);
      assert.equal(v.pairing.pairs.length, 16);
      assert.equal(new Set(v.pairing.pairs.map(p => p.right.index)).size, 16);
    }
  }
});
test("missing, zero and positive radar bins remain distinct in original amplitude mapping", () => {
  assert.deepEqual([...haxrPixels([null, 0, 10], 10)], [0, 0, 0, 0, 0, 0, 0, 255, 255, 190, 70, 255]);
});
test("core excludes future, stale and conflicting latest AIS instead of fabricating positions", () => {
  const report = (uid, tod, rangeMeters = 10) => ({ uid, tod, rangeMeters, azimuthDegrees: 90 });
  const result = selectHaxrAis([report("future", 21), report("stale", 9), report("conflict", 20), report("conflict", 20, 11), report("good", 10)], 20);
  assert.equal(result.futureReports, 1);
  assert.equal(result.staleTargets, 1);
  assert.equal(result.conflictingTargets, 1);
  assert.deepEqual(result.selected.map(r => r.uid), ["good"]);
  assert.equal(result.selected[0].ageSeconds, 10);
});
test("export retains actual frame, exclusions, selected UID and explicit limits without raster payload", () => {
  const uid = study.view().contacts.find(c => Object.values(c.reports).every(Boolean)).uid;
  const result = exportHaxrView(study, { anchor: "reiherstieg", index: 0, tolerance: 1 }, uid);
  assert.equal(result.signed, false);
  assert.equal(result.comparison.selectedPair, null);
  assert.equal(result.sourceLineage.family, "one shared AIS stream");
  for (const [id, station] of Object.entries(result.stations)) {
    assert.equal(station.selectedReport.uid, uid);
    assert.equal(station.source.sha256, study.recordings[id].sha256);
    assert.equal(station.frame.pixels, undefined);
    assert.equal(station.source.ais.reports, undefined);
  }
  assert.match(result.limits.join(" "), /not calibrated clock uncertainty/);
  assert(JSON.stringify(result).length < 50000);
});
test("invalid selections and mismatched or incomplete recordings fail closed", () => {
  for (const settings of [{ index: 16 }, { index: -1 }, { index: .1 }, { tolerance: NaN }, { tolerance: -1 }, { tolerance: 4 }, { anchor: "__proto__" }])
    assert.throws(() => study.view(settings));
  assert.throws(() => createHaxrStudy([data[0]]));
  assert.throws(() => createHaxrStudy([data[0], data[0]]));
  assert.throws(() => createHaxrStudy([{ ...data[0], station: "hohe_schaar" }, data[1]]));
  assert.throws(() => createHaxrStudy([{ ...data[0], ais: undefined }, data[1]]));
});

test("recorded ID history distinguishes held reports, unequal expiry and later recovery", () => {
  const first = study.follow("1b1e4", { index: 0 });
  assert.equal(first.comparison.aisRelation, "same-source-time");
  assert.equal(first.current.reiherstieg.state, "new");
  assert.equal(study.follow("1b1e4", { index: 1 }).current.reiherstieg.state, "held");
  const boundary = study.follow("1b1e4", { index: 3 });
  assert.equal(boundary.current.reiherstieg.state, "held");
  assert.equal(boundary.current.hohe_schaar.state, "stale");
  assert.equal(boundary.comparison.aisRelation, "one-sided");
  const gap = study.follow("1b1e4", { index: 4 });
  assert.equal(gap.comparison.aisRelation, "neither-eligible");
  assert.equal(gap.current.reiherstieg.report, null);
  assert(gap.current.reiherstieg.latestAgeSeconds > 10);
  assert(gap.current.reiherstieg.trail.some(r => r.tod === 29101));
  const recovered = study.follow("1b1e4", { index: 10 });
  assert.equal(recovered.current.reiherstieg.state, "new");
  assert.equal(recovered.current.reiherstieg.report.tod, 29132);
  assert.equal(recovered.current.hohe_schaar.report.tod, 29132);
  assert.equal(recovered.sourceFamilies, 1);
});

test("history admission matches the original selector at every station frame", () => {
  for (const uid of ["1b1e4", "7baba"]) {
    const h = study.follow(uid, {});
    for (const [id, station] of Object.entries(h.stations)) {
      for (const f of station.frames) {
        const expected = selectHaxrAis(study.recordings[id].ais.reports, f.endTod).selected.find(r => r.uid === uid) ?? null;
        assert.deepEqual(f.report, expected);
      }
    }
    const a = study.recordings.reiherstieg.ais, b = study.recordings.hohe_schaar.ais;
    assert.deepEqual(h.continuity, compareStationContinuity({ ...a, reports: a.reports.filter(r => r.uid === uid) }, { ...b, reports: b.reports.filter(r => r.uid === uid) }, h.continuity.startTod, h.continuity.endTod));
  }
});

test("rewind removes future breadcrumbs while the labelled full-window history remains retrospective", () => {
  const later = study.follow("1b1e4", { index: 15 });
  assert(later.current.reiherstieg.trail.some(r => r.tod === 29132));
  const early = study.follow("1b1e4", { index: 0 });
  for (const s of Object.values(early.current)) {
    assert(s.visibleEvents.every(e => e.tod <= s.endTod));
    assert(s.trail.every(r => r.tod <= s.endTod && r.tod !== s.report?.tod));
    assert(!s.trail.some(r => r.tod === 29132));
  }
  assert(early.stations.reiherstieg.events.some(e => e.tod === 29132));
  assert.match(early.scope, /Retrospective full extracted window/);
});

test("changing anchor or timing tolerance cannot rewrite a report history or multiply its sources", () => {
  const first = study.follow("1b1e4", { tolerance: .5 });
  const second = study.follow("1b1e4", { anchor: "hohe_schaar", tolerance: 3, index: 10 });
  assert.deepEqual(first.stations, second.stations);
  assert.deepEqual(first.continuity, second.continuity);
  assert.equal(first.comparison.sourceFamilies, 1);
  assert.equal(second.comparison.sourceFamilies, 1);
  assert.equal(first.comparison.radarTimePairEligible, false);
  assert.equal(second.comparison.radarTimePairEligible, true);
  assert.equal(second.comparison.radarAssociation, "not established");
});

test("controlled duplicate and conflicting timestamps do not become extra or arbitrarily selected points", () => {
  const report = { uid: "controlled", tod: 29101, rangeMeters: 100, azimuthDegrees: 90 };
  const inputs = structuredClone(data);
  inputs[0].ais.reports = [report, { ...report }, { ...report, tod: 29104, rangeMeters: 110 }, { ...report, tod: 29104, rangeMeters: 120 }, { ...report, tod: 29107, rangeMeters: 130 }];
  inputs[1].ais.reports = [{ ...report, tod: 29100 }];
  const controlled = createHaxrStudy(inputs);
  const initial = controlled.follow("controlled", { index: 0 });
  assert.equal(initial.stations.reiherstieg.events[0].sourceRows, 2);
  assert.equal(initial.stations.reiherstieg.events.length, 3);
  assert.equal(initial.comparison.aisRelation, "different-source-times");
  assert.equal(initial.comparison.reportTimeDifference, 1);
  const conflicted = controlled.follow("controlled", { index: 1 });
  assert.equal(conflicted.current.reiherstieg.state, "conflict");
  assert.equal(conflicted.current.reiherstieg.report, null);
  assert.deepEqual(conflicted.current.reiherstieg.trail.map(r => r.tod), [29101]);
  const recovered = controlled.follow("controlled", { index: 2 });
  assert.equal(recovered.current.reiherstieg.report.tod, 29107);
  assert(!recovered.current.reiherstieg.trail.some(r => r.tod === 29104));
});

test("unknown and future-only IDs never appear as current points or proven outages", () => {
  const missing = study.follow("not-in-recordings", {});
  assert(Object.values(missing.current).every(s => s.state === "unseen" && s.latestReportTod === null && s.trail.length === 0));
  assert(missing.continuity.samples.every(s => s.both + s.aOnly + s.bOnly + s.neither === 0));
  const inputs = structuredClone(data);
  inputs.forEach(r => { r.ais.reports = [{ uid: "later", tod: 29140, rangeMeters: 200, azimuthDegrees: 0 }]; });
  const future = createHaxrStudy(inputs).follow("later", {});
  assert(Object.values(future.current).every(s => s.state === "unseen" && s.visibleEvents.length === 0));
  assert.equal(future.continuity.samples[0].neither, 0);
  for (const id of ["", null, "x".repeat(81)]) assert.throws(() => study.follow(id, {}));
});

test("history export preserves current cutoffs and the full recorded window with explicit scope", () => {
  const result = exportHaxrView(study, { anchor: "reiherstieg", index: 4, tolerance: 1 }, "1b1e4");
  assert.equal(result.selectedHistory.uid, "1b1e4");
  assert.equal(result.selectedHistory.current.reiherstieg.report, null);
  assert.equal(result.selectedHistory.comparison.aisRelation, "neither-eligible");
  assert.equal(result.selectedHistory.stations.reiherstieg.frames.length, 16);
  assert.match(result.selectedHistory.limits.join(" "), /not radar detections/);
  assert.equal(result.selectedHistory.sourceFamilies, 1);
});


// Controlled raster fixtures distinguish proximity from detection/identity.
const { inspectReturns, returnOptions } = await import("../docs/assets/coastal-haxr-returns.mjs");
const fixtureFrame = () => ({ startTod: 10, endTod: 12, pixels: Array(128 * 128).fill(null) });
const fixtureReport = { uid: "fixture", tod: 11, east: 15.625, north: -15.625 };
test("local aperture uses bin centres, native row orientation and raw amplitudes", () => {
  const f = fixtureFrame(); f.pixels[64 * 128 + 64] = 99; f.pixels[63 * 128 + 64] = 9;
  const r = inspectReturns(f, fixtureReport, 99, { radius: 62.5, floor: 60 });
  assert.equal(r.state, "nearby"); assert.equal(r.sampledBins, 2); assert.equal(r.aboveFloorBins, 1);
  assert.equal(r.nearest.distanceMeters, 0); assert.equal(r.nearest.col, 64); assert.equal(r.nearest.row, 64);
  assert.equal(r.nearest.north, -15.625); assert.equal(r.nearest.amplitude, 99);
  assert.equal(r.reportTiming, "within-frame"); assert.equal(r.association, "unestablished");
});
test("missing, zero and below-floor returns remain distinct; zero never qualifies", () => {
  const f = fixtureFrame();
  assert.equal(inspectReturns(f, fixtureReport, 99).state, "missing");
  f.pixels[64 * 128 + 64] = 0;
  const zero = inspectReturns(f, fixtureReport, 99, { floor: 0 });
  assert.equal(zero.state, "below-floor"); assert.equal(zero.zeroBins, 1); assert.equal(zero.nearest, null);
  f.pixels[64 * 128 + 64] = 9;
  assert.equal(inspectReturns(f, fixtureReport, 99, { floor: 60 }).aboveFloorBins, 0);
  assert.equal(inspectReturns(f, fixtureReport, 99, { floor: 40 }).aboveFloorBins, 1);
  assert.equal(f.pixels[64 * 128 + 64], 9);
});
test("edge clipping, outside positions and absent AIS do not produce an inferred aperture", () => {
  const f = fixtureFrame();
  assert.equal(inspectReturns(f, null, 99).state, "no-ais");
  assert.equal(inspectReturns(f, { ...fixtureReport, east: 2000 }, 99).state, "outside");
  assert.equal(inspectReturns(f, { ...fixtureReport, east: 1990 }, 99).clipped, true);
  for (const options of [{ radius: 0 }, { radius: Infinity }, { floor: NaN }, { floor: -1 }, { floor: 101 }]) assert.throws(() => returnOptions(options));
});
test("aperture changes retain exact radius bounds and other eligible AIS ambiguity", () => {
  const f = fixtureFrame(); f.pixels[64 * 128 + 67] = 99;
  const other = { ...fixtureReport, uid: "other", east: 80 };
  assert.equal(inspectReturns(f, fixtureReport, 99, { radius: 62.5 }, [other]).aboveFloorBins, 0);
  const wider = inspectReturns(f, fixtureReport, 99, { radius: 125 }, [fixtureReport, other]);
  assert.equal(wider.aboveFloorBins, 1); assert.deepEqual(wider.nearbyAisIds, ["other"]);
  assert.equal(wider.nearest.distanceMeters, 93.75);
});
test("real return histories use eligible positions only and keep independent station scales", () => {
  const first = study.inspect("1b1e4", { index: 0 });
  assert.equal(first.stations.reiherstieg.length, 16); assert.equal(first.sourceFamilies, 1);
  assert.equal(study.inspect("1b1e4", { index: 3 }).current.hohe_schaar.state, "no-ais");
  assert(Object.values(study.inspect("1b1e4", { index: 4 }).current).every(r => r.state === "no-ais" && r.nearest === null));
  for (const r of Object.values(first.current)) {
    assert(r.report.tod <= r.endTod); assert(r.nearest === null || r.nearest.distanceMeters <= 125);
    assert.equal(r.association, "unestablished");
  }
  const altered = study.inspect("1b1e4", { index: 0, anchor: "hohe_schaar", tolerance: 3 });
  assert.deepEqual(altered.stations, first.stations);
  const exported = exportHaxrView(study, { index: 0 }, "1b1e4", { radius: 250, floor: 80 });
  assert.deepEqual(exported.localReturns.options, { radius: 250, floor: 80 });
  assert.match(exported.localReturns.limits.join(" "), /not calibrated power/);
});
