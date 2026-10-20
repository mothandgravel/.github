export const INQUIRY_VERSION = "shadow-inquiry-v1";
// Fictional measurements in a local east/north metre plane, not a real vessel.
export const INQUIRY = Object.freeze({
  id: "SI-003",
  subject: "Contact K / fictional",
  evidence: "authored synthetic fixture",
  reports: [
    {
      id: "A-00",
      family: "ais-k",
      type: "AIS",
      observed: -1800,
      received: -1798,
      x: -14400,
      y: 0,
      parent: null,
    },
    {
      id: "A-01",
      family: "ais-k",
      type: "AIS",
      observed: 0,
      received: 2,
      x: 0,
      y: 0,
      parent: null,
    },
    {
      id: "A-01-relay",
      family: "ais-k",
      type: "Relay",
      observed: 0,
      received: 8,
      x: 0,
      y: 0,
      parent: "A-01",
    },
    {
      id: "R-17",
      family: "radar-n",
      type: "Radar",
      observed: 30,
      received: 33,
      x: 420,
      y: 70,
      parent: null,
    },
  ].map(Object.freeze),
});
export const INQUIRY_STEPS = Object.freeze([
  {
    title: "A gap in the account.",
    time: 2,
    offset: 0,
    uncertainty: 0,
    note: "Thirty minutes separate the AIS source reports. Receiver coverage and transmitter state are absent from this record.",
    question: "Was the vessel silent, or was this feed unable to hear it?",
    request: "Receiver coverage and collection logs for the missing interval.",
  },
  {
    title: "Another shore. The same report.",
    time: 8,
    offset: 0,
    uncertainty: 0,
    note: "A relay delivers A-01 again. There are more deliveries, but still one AIS source family.",
    question: "Does the second account have a different origin?",
    request: "Upstream lineage before counting corroboration.",
  },
  {
    title: "A second instrument disagrees.",
    time: 33,
    offset: 0,
    uncertainty: 0,
    note: "A fictional radar measurement is now available. Compare it with an explicitly projected AIS position at the radar epoch.",
    question:
      "Position error, timing error, wrong association—or something else?",
    request:
      "Radar association evidence, sensor calibration and source-clock records.",
  },
  {
    title: "The clock changes the question.",
    time: 33,
    offset: 0,
    uncertainty: 12,
    note: "Admitting twelve seconds of relative clock uncertainty broadens the comparison. Overlap leaves the identity question open.",
    question: "How much of the disagreement depends on an unverified clock?",
    request: "A bounded clock-offset estimate from acquisition records.",
  },
]);
export function inquirySnapshot({
  step = 0,
  offset = 0,
  uncertainty = 0,
} = {}) {
  if (
    !Number.isInteger(step) ||
    step < 0 ||
    step >= INQUIRY_STEPS.length ||
    !Number.isFinite(offset) ||
    offset < -20 ||
    offset > 3 ||
    !Number.isFinite(uncertainty) ||
    uncertainty < 0 ||
    uncertainty > 20
  )
    throw new RangeError("Invalid inquiry controls");
  const boundary = INQUIRY_STEPS[step];
  const reports = INQUIRY.reports.filter((r) => r.received <= boundary.time);
  const originals = reports.filter((r) => !r.parent);
  const families = [...new Set(originals.map((r) => r.family))];
  const radar = reports.find((r) => r.id === "R-17");
  // User-selected relative clock correction. Never modify either raw timestamp.
  const dt = 30 + offset;
  const projected = { x: 8 * dt, y: 0 };
  // Illustrative deterministic bounds, not statistical confidence ellipses.
  // Triangle bound includes velocity uncertainty during the uncertain epoch.
  const radius = 35 + 1.2 * (Math.abs(dt) + uncertainty) + 8 * uncertainty;
  const separation = radar
    ? Math.hypot(radar.x - projected.x, radar.y - projected.y)
    : null;
  const gap =
    separation === null ? null : Math.max(0, separation - radius - 55);
  return {
    version: INQUIRY_VERSION,
    caseId: INQUIRY.id,
    evidence: INQUIRY.evidence,
    controls: { step, offset, uncertainty },
    boundary: boundary.time,
    reports,
    counts: {
      deliveries: reports.length,
      originals: originals.length,
      families: families.length,
    },
    sourceFamilies: families,
    gapSeconds: 1800,
    coverage: "unknown",
    identity: "unresolved",
    classification: "not assessed",
    comparison: radar
      ? {
          projected,
          radius,
          radarRadius: 55,
          separation,
          gap,
          overlap: gap === 0,
          dt,
          velocity: [8, 0],
          velocityBound: 1.2,
          reason:
            gap > 0
              ? "Separated under these assumptions"
              : "Bounds overlap; association remains unresolved",
        }
      : null,
    missing: [
      "receiver coverage",
      "RF measurements",
      "verified radar association",
      "registry and ownership evidence",
      "sanctions-list match and effective date",
    ],
  };
}
