import { selectHaxrAis } from "./coastal-haxr-core.mjs?v=branches-1";

export const RETURN_DEFAULTS = Object.freeze({ radius: 125, floor: 60 });
export const BIN_METERS = 31.25;
export function returnOptions({ radius = 125, floor = 60 } = {}) {
  if (![62.5, 125, 250].includes(radius) || !Number.isFinite(floor) || floor < 0 || floor > 100)
    throw Error("Invalid radar inspection aperture or display floor");
  return { radius, floor };
}
export const displayLevel = (amplitude, max) => max > 0 ? 100 * Math.log1p(amplitude) / Math.log1p(max) : 0;

// A spatial query of stored bin centres, not a detector or an association gate.
export function inspectReturns(frame, report, max, options = {}, others = []) {
  const { radius, floor } = returnOptions(options);
  const base = { startTod: frame.startTod, endTod: frame.endTod, report,
    radiusMeters: radius, displayFloorPercent: floor, stationScaleMaximum: max,
    association: "unestablished", binMeters: BIN_METERS };
  if (!report) return { ...base, state: "no-ais", sampledBins: 0, missingBins: 0, zeroBins: 0, aboveFloorBins: 0, nearest: null };
  const { east, north } = report;
  if (east < -2000 || east >= 2000 || north > 2000 || north <= -2000)
    return { ...base, state: "outside", sampledBins: 0, missingBins: 0, zeroBins: 0, aboveFloorBins: 0, nearest: null };
  const clipped = east - radius < -2000 || east + radius > 2000 || north - radius < -2000 || north + radius > 2000;
  let sampledBins = 0, missingBins = 0, zeroBins = 0, aboveFloorBins = 0, nearest = null, peakAmplitude = null;
  for (let row = Math.max(0, Math.floor((2000 - north - radius) / BIN_METERS)); row <= Math.min(127, Math.floor((2000 - north + radius) / BIN_METERS)); row++) {
    for (let col = Math.max(0, Math.floor((east - radius + 2000) / BIN_METERS)); col <= Math.min(127, Math.floor((east + radius + 2000) / BIN_METERS)); col++) {
      const x = -2000 + (col + .5) * BIN_METERS, y = 2000 - (row + .5) * BIN_METERS;
      const distanceMeters = Math.hypot(x - east, y - north);
      if (distanceMeters > radius) continue;
      const amplitude = frame.pixels[row * 128 + col];
      if (amplitude === null) { missingBins++; continue; }
      sampledBins++; if (amplitude === 0) zeroBins++;
      peakAmplitude = Math.max(peakAmplitude ?? 0, amplitude);
      const level = displayLevel(amplitude, max);
      if (amplitude <= 0 || level < floor) continue;
      aboveFloorBins++;
      if (!nearest || distanceMeters < nearest.distanceMeters)
        nearest = { col, row, east: x, north: y, amplitude, displayLevelPercent: level, distanceMeters };
    }
  }
  return { ...base, state: !sampledBins ? "missing" : aboveFloorBins ? "nearby" : "below-floor",
    clipped, sampledBins, missingBins, zeroBins, aboveFloorBins, nearest, peakAmplitude,
    nearbyAisIds: others.filter(r => r.uid !== report.uid && Math.hypot(r.east - east, r.north - north) <= radius).map(r => r.uid),
    reportTiming: report.tod < frame.startTod ? "before-frame" : "within-frame",
    reportAgeAtEnd: frame.endTod - report.tod,
  };
}

export function returnHistory(recordings, uid, options = {}) {
  const policy = returnOptions(options);
  return {
    schema: "coastal-haxr-local-returns-v1", uid, options: policy, sourceFamilies: 1,
    scope: "Retrospective frame history. Each aperture uses only eligible AIS at that frame end.",
    stations: Object.fromEntries(Object.entries(recordings).map(([id, r]) => {
      const max = r.frames.reduce((m, f) => f.pixels.reduce((n, p) => Math.max(n, p ?? 0), m), 0);
      return [id, r.frames.map((f, index) => {
        const selected = selectHaxrAis(r.ais.reports, f.endTod).selected;
        return { index, ...inspectReturns(f, selected.find(a => a.uid === uid) ?? null, max, policy, selected) };
      })];
    })),
    limits: [
      "Aperture radius is an inspection choice, not a measured position uncertainty or vessel footprint.",
      "Positive bins at or above the display floor are local proximity evidence only; clutter, shore and other vessels can contribute.",
      "Distance is to a raster bin centre, not a detected target or original radar-cell centre.",
      "Each bin stores a maximum over source cells. No per-bin acquisition instant is available here.",
      "Frame-end AIS selection may be later than radar cells in that frame; no motion compensation is applied.",
      "Display level is logarithmic against each station's extract maximum, not calibrated power or cross-station strength.",
      "Missing bins, below-floor bins and unavailable AIS do not establish vessel absence.",
      "Both station AIS files share one upstream source; no independent AIS corroboration is added.",
    ],
  };
}
