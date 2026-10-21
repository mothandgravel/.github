import { selectHaxrAis, compareStationContinuity, HAXR_AIS_POLICY } from "./coastal-haxr-core.mjs?v=branches-1";

// This is report history in each station's local frame, never a radar track.
export function selectedHistory(recordings, uid) {
  if (typeof uid !== "string" || !uid || uid.length > 80) throw Error("Choose a valid recorded AIS ID");
  const stations = Object.fromEntries(Object.entries(recordings).map(([id, recording]) => {
    const reports = recording.ais.reports.filter(r => r.uid === uid);
    const groups = new Map();
    for (const report of reports) {
      if (!groups.has(report.tod)) groups.set(report.tod, []);
      groups.get(report.tod).push(report);
    }
    const events = [...groups].sort(([a], [b]) => a - b).map(([tod, rows]) => {
      const selected = selectHaxrAis(rows, tod).selected[0] ?? null;
      return { tod, sourceRows: rows.length, kind: selected ? "report" : "conflict", report: selected };
    });
    const frames = recording.frames.map((f, index) => {
      const selection = selectHaxrAis(reports, f.endTod);
      const report = selection.selected[0] ?? null;
      const last = events.filter(e => e.tod <= f.endTod).at(-1);
      const previousEnd = index ? recording.frames[index - 1].endTod : f.startTod;
      const state = report ? (report.tod > previousEnd || (!index && report.tod === previousEnd) ? "new" : "held")
        : selection.staleTargets ? "stale" : selection.conflictingTargets ? "conflict" : "unseen";
      return {
        index, startTod: f.startTod, endTod: f.endTod, state, report,
        latestReportTod: last?.tod ?? null,
        latestAgeSeconds: last ? f.endTod - last.tod : null,
      };
    });
    const totals = { new: 0, held: 0, stale: 0, conflict: 0, unseen: 0 };
    frames.forEach(f => totals[f.state]++);
    return [id, { events, frames, totals, eligibleFrames: totals.new + totals.held }];
  }));
  const a = recordings.reiherstieg, b = recordings.hohe_schaar;
  const start = Math.max(a.frames[0].startTod, b.frames[0].startTod);
  const end = Math.min(a.frames.at(-1).endTod, b.frames.at(-1).endTod);
  // Native continuity has an explicit common-window contract. Do not extend a
  // recording or invent samples when a valid pair of extracts has no overlap.
  const continuity = end > start ? compareStationContinuity(
    { ...a.ais, reports: a.ais.reports.filter(r => r.uid === uid) },
    { ...b.ais, reports: b.ais.reports.filter(r => r.uid === uid) }, start, end,
  ) : null;
  return {
    schema: "coastal-haxr-selected-history-v1", uid,
    scope: "Retrospective full extracted window. Current positions and breadcrumbs use each displayed frame's own end time.",
    sourceFamily: "one shared HAXR AIS stream", sourceFamilies: 1,
    policy: HAXR_AIS_POLICY, stations, continuity,
    limits: [
      "New and held describe AIS selection at radar-frame ends, not radar detections or receipt times.",
      "Stale, conflicting or unseen reports do not establish vessel absence or a station outage.",
      "Breadcrumbs are separate recorded positions; no interpolation, prediction or radar association.",
      "Equal AIS timestamps do not establish independent sources or an identical upstream packet.",
      "The five-second continuity grid may miss shorter changes and omits a final partial interval.",
    ],
  };
}

export function historyAtView(history, view) {
  const current = Object.fromEntries(Object.entries(view.stations).map(([id, station]) => {
    const h = history.stations[id], frame = h.frames[station.index];
    const visible = h.events.filter(e => e.tod <= frame.endTod);
    return [id, {
      ...frame,
      // Conflicts never become points; repeated source rows never create extra breadcrumbs.
      trail: visible.filter(e => e.report && e.tod !== frame.report?.tod).map(e => e.report),
      visibleEvents: visible,
    }];
  }));
  const reports = Object.values(current).map(s => s.report);
  const eligibleStations = reports.filter(Boolean).length;
  const sameTime = eligibleStations === 2 && reports[0].tod === reports[1].tod;
  return {
    ...history, current,
    comparison: {
      eligibleStations, sourceFamilies: 1,
      aisRelation: eligibleStations === 2 ? (sameTime ? "same-source-time" : "different-source-times") : eligibleStations === 1 ? "one-sided" : "neither-eligible",
      reportTimeDifference: eligibleStations === 2 ? Math.abs(reports[0].tod - reports[1].tod) : null,
      radarTimePairEligible: Boolean(view.selectedPair),
      endpointDifference: view.preview.endpointSkew,
      geometry: "not aligned", radarAssociation: "not established",
    },
  };
}
