import { parseHaxr, selectHaxrAis, pairRadarFrames, HAXR_AIS_POLICY } from "./coastal-haxr-core.mjs";
export { HAXR_AIS_POLICY };
export const STATIONS = Object.freeze({ reiherstieg: "Reiherstieg", hohe_schaar: "Hohe Schaar" });
export const endpointSkew = (a, b) => Math.max(Math.abs(a.startTod - b.startTod), Math.abs(a.endTod - b.endTod));
const frozen = value => {
  if (value && typeof value === "object") { Object.values(value).forEach(frozen); Object.freeze(value); }
  return value;
};
export function createHaxrStudy(inputs) {
  if (!Array.isArray(inputs) || inputs.length !== 2) throw Error("Two recorded stations are required");
  const parsed = inputs.map(parseHaxr);
  if (new Set(parsed.map(r => r.station)).size !== 2 || parsed.some(r => !r.ais)) throw Error("Both station recordings and their AIS extracts are required");
  const recordings = frozen(Object.fromEntries(parsed.map(r => [r.station, r])));
  const maxima = Object.fromEntries(parsed.map(r => [r.station, r.frames.reduce((max, f) => f.pixels.reduce((m, p) => Math.max(m, p ?? 0), max), 0)]));
  let cacheKey = "", cachedPairing;
  function view({ anchor = "reiherstieg", index = 0, tolerance = 1 } = {}) {
    if (!Object.hasOwn(recordings, anchor) || !Number.isInteger(index) || index < 0 || index >= recordings[anchor].frames.length || !Number.isFinite(tolerance) || tolerance < 0 || tolerance > 3)
      throw Error("Invalid replay selection");
    const other = anchor === "reiherstieg" ? "hohe_schaar" : "reiherstieg";
    const left = recordings[anchor], right = recordings[other], frame = left.frames[index];
    const key = `${anchor}:${tolerance}`;
    if (key !== cacheKey) {
      cachedPairing = frozen(pairRadarFrames(left, right, tolerance));
      cacheKey = key;
    }
    const pairing = cachedPairing;
    const match = pairing.pairs.find(p => p.left.index === index);
    const nearest = right.frames.map((f, i) => ({ index: i, skew: endpointSkew(frame, f) })).sort((a, b) => a.skew - b.skew || a.index - b.index)[0];
    const rightIndex = match?.right.index ?? nearest.index;
    const indexes = { [anchor]: index, [other]: rightIndex };
    const stations = Object.fromEntries(Object.keys(STATIONS).map(id => {
      const recording = recordings[id], frameIndex = indexes[id], f = recording.frames[frameIndex];
      return [id, { frame: f, index: frameIndex, ais: selectHaxrAis(recording.ais.reports, f.endTod), max: maxima[id] }];
    }));
    const ids = [...new Set(Object.values(stations).flatMap(s => s.ais.selected.map(r => r.uid)))].sort((a, b) => a.localeCompare(b));
    const contacts = ids.map(uid => ({
      uid,
      reports: Object.fromEntries(Object.entries(stations).map(([id, s]) => [id, s.ais.selected.find(r => r.uid === uid) ?? null])),
      sourceFamily: "HAXR shared AIS stream",
    }));
    return {
      anchor, other, index, tolerance, pairing, stations, contacts,
      selectedPair: match ?? null,
      preview: { otherIndex: rightIndex, endpointSkew: endpointSkew(frame, right.frames[rightIndex]), role: match ? "eligible pair" : "nearest comparison only" },
      unmatchedReason: pairing.unmatchedLeft.find(p => p.frame.index === index)?.reason ?? null,
      sharedIds: contacts.filter(c => Object.values(c.reports).every(Boolean)).length,
      sourceFamilies: 1,
    };
  }
  return Object.freeze({ recordings, view });
}
export function exportHaxrView(study, settings, uid = null) {
  const v = study.view(settings);
  return {
    schema: "coastal-haxr-inquiry-v1",
    evidence: "recorded HAXR radar and shared AIS; modified downsampled extracts",
    signed: false,
    selection: { ...settings, uid },
    comparison: { preview: v.preview, selectedPair: v.selectedPair, unmatchedReason: v.unmatchedReason },
    pairing: v.pairing,
    stations: Object.fromEntries(Object.entries(v.stations).map(([id, s]) => [id, {
      frame: { ...s.frame, pixels: undefined },
      comparison: s.ais,
      selectedReport: s.ais.selected.find(r => r.uid === uid) ?? null,
      source: { ...study.recordings[id], frames: undefined, ais: { ...study.recordings[id].ais, reports: undefined } },
    }])),
    sourceLineage: { family: "one shared AIS stream", stationFiles: Object.values(study.recordings).map(r => r.ais.file) },
    limits: [
      "Offline directional pairing may use a later frame; not a causal live tracker.",
      "Tolerance describes endpoint eligibility, not calibrated clock uncertainty.",
      "Station coordinates are local; no common geometric frame or radar target association.",
      "Pseudonymous AIS IDs do not establish real MMSI, IMO or hull identity.",
      "Blank raster bins mean no selected cell, not verified empty water.",
      "Source hashes identify upstream artifacts; exports are unsigned.",
    ],
  };
}
