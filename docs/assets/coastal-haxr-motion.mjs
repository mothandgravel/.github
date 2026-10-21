import { selectHaxrAis } from "./coastal-haxr-core.mjs?v=motion-1";
import { BIN_METERS } from "./coastal-haxr-returns.mjs?v=motion-1";

export const MOTION_POLICY = Object.freeze({ patchBins: 5, minPairs: 9, minCoverage: .7, minCorrelation: .7, minMargin: .1 });
const point = (col, row) => ({ col, row, east: -2000 + (col + .5) * BIN_METERS, north: 2000 - (row + .5) * BIN_METERS });
const patch = (frame, col, row) => Array.from({ length: 25 }, (_, i) => {
  const x = col + i % 5 - 2, y = row + Math.floor(i / 5) - 2;
  return x < 0 || x > 127 || y < 0 || y > 127 ? null : frame.pixels[y * 128 + x];
});
function similarity(template, target) {
  const pairs = template.flatMap((v, i) => v === null || target[i] === null ? [] : [[Math.log1p(v), Math.log1p(target[i])]]);
  const required = Math.max(MOTION_POLICY.minPairs, Math.ceil(template.filter(v => v !== null).length * MOTION_POLICY.minCoverage));
  if (pairs.length < required) return null;
  const a = pairs.reduce((s, p) => s + p[0], 0) / pairs.length, b = pairs.reduce((s, p) => s + p[1], 0) / pairs.length;
  let aa = 0, bb = 0, ab = 0;
  for (const [x, y] of pairs) { aa += (x - a) ** 2; bb += (y - b) ** 2; ab += (x - a) * (y - b); }
  if (aa < 1e-12 || bb < 1e-12) return null;
  return { correlation: Math.max(-1, Math.min(1, ab / Math.sqrt(aa * bb))), pairedBins: pairs.length };
}

// This is a bounded, fixed-template texture hypothesis. AIS never enters matching.
export function followRadarReturn(recording, uid, seed, { searchBins = 2 } = {}) {
  if (!seed || !Number.isInteger(seed.index) || seed.index < 0 || seed.index >= recording.frames.length ||
      !Number.isInteger(seed.col) || seed.col < 0 || seed.col > 127 || !Number.isInteger(seed.row) || seed.row < 0 || seed.row > 127 ||
      ![1, 2, 4].includes(searchBins) || typeof uid !== "string" || !uid || uid.length > 80) throw Error("Invalid radar-follow selection");
  const first = recording.frames[seed.index], amplitude = first.pixels[seed.row * 128 + seed.col];
  if (amplitude === null || amplitude <= 0) throw Error("Choose a positive measured radar bin");
  const origin = point(seed.col, seed.row), template = patch(first, seed.col, seed.row);
  const usable = Boolean(similarity(template, template));
  const aisOrigin = selectHaxrAis(recording.ais.reports, first.endTod).selected.find(r => r.uid === uid) ?? null;
  let last = origin, stopped = !usable;
  const steps = recording.frames.map((frame, index) => {
    const ais = selectHaxrAis(recording.ais.reports, frame.endTod).selected.find(r => r.uid === uid) ?? null;
    const base = { index, startTod: frame.startTod, endTod: frame.endTod, ais,
      fixedBinAmplitude: frame.pixels[seed.row * 128 + seed.col],
      aisDisplacement: ais && aisOrigin ? { east: ais.east - aisOrigin.east, north: ais.north - aisOrigin.north } : null };
    if (index < seed.index) return { ...base, state: "before-seed", accepted: null, candidates: [] };
    if (index === seed.index) return { ...base, state: usable ? "seed" : "unusable-seed", accepted: usable ? { ...origin, amplitude } : null, candidates: [] };
    if (stopped) return { ...base, state: "stopped", accepted: null, candidates: [] };
    const candidates = [];
    for (let row = Math.max(0, last.row - searchBins); row <= Math.min(127, last.row + searchBins); row++) {
      for (let col = Math.max(0, last.col - searchBins); col <= Math.min(127, last.col + searchBins); col++) {
        const value = frame.pixels[row * 128 + col];
        if (value === null || value <= 0) continue;
        const score = similarity(template, patch(frame, col, row));
        if (score) candidates.push({ ...point(col, row), amplitude: value, ...score });
      }
    }
    candidates.sort((a, b) => b.correlation - a.correlation || a.row - b.row || a.col - b.col);
    const best = candidates[0], runner = candidates[1];
    const margin = best && runner ? best.correlation - runner.correlation : null;
    const state = !best ? "insufficient" : best.correlation < MOTION_POLICY.minCorrelation ? "weak" : runner && margin < MOTION_POLICY.minMargin ? "ambiguous" : "matched";
    const accepted = state === "matched" ? best : null;
    const searchCentre = last;
    if (accepted) last = accepted; else stopped = true;
    return { ...base, state, accepted, searchCentre, candidateCount: candidates.length, margin, candidates: candidates.slice(0, 2) };
  }).map(step => {
    const radarDisplacement = step.accepted ? { east: step.accepted.east - origin.east, north: step.accepted.north - origin.north } : null;
    return { ...step, radarDisplacement,
      displacementDifference: radarDisplacement && step.aisDisplacement ? Math.hypot(radarDisplacement.east - step.aisDisplacement.east, radarDisplacement.north - step.aisDisplacement.north) : null,
      separationMeters: step.accepted && step.ais ? Math.hypot(step.accepted.east - step.ais.east, step.accepted.north - step.ais.north) : null };
  });
  return { schema: "coastal-haxr-patch-follow-v1", station: recording.station, uid, seed: { ...seed, ...origin, amplitude },
    policy: { ...MOTION_POLICY, searchBins, searchHalfWidthMeters: searchBins * BIN_METERS }, aisOrigin, sourceFamilies: 1, association: "unestablished", classification: "unassigned", steps,
    scope: "Full forward hypothesis from the selected seed; no backward inference. Display only steps at/before the current station frame.",
    limits: [
      "New specimen experiment, not Raivari's validated tracker or a vessel association.",
      "Fixed 5x5 seed template; mean-centred log-amplitude correlation; only positive measured candidate centres; no AIS guidance.",
      "Correlation measures texture similarity, not probability. Close competing candidates stop the chain, without automatic reacquisition.",
      "Null bins are excluded; measured zero participates in texture. Insufficient coverage or flat texture cannot support a match.",
      "Search half-width is a per-frame inspection choice, not a speed bound or calibrated uncertainty.",
      "Motion is quantized in 31.25 m bins. A fixed bin can contain different scattering sources between frames.",
      "Stationary texture can be shore, a moored vessel or clutter. Similar motion does not establish vessel identity.",
      "AIS may be held or stale; no interpolation. Frame-end time is not a per-bin radar acquisition instant.",
      "One station-local hypothesis; no cross-station fusion. AIS remains one shared source family.",
    ] };
}
