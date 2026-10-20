import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createHaxrStudy, exportHaxrView } from "../docs/assets/coastal-haxr-model.mjs";
import { parseHaxr, selectHaxrAis, haxrPixels, pairRadarFrames } from "../docs/assets/coastal-haxr-core.mjs";

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
