// A single, deterministic performance. Coordinates are local to the quiet stage.
export const DURATION = 4800;

const clamp = (n, a, b) => Math.min(b, Math.max(a, n));
const mix = (a, b, t) => a + (b - a) * t;
const ease = t => t * t * (3 - 2 * t);
const progress = (t, from, to) => clamp((t - from) / (to - from), 0, 1);
const turn = a => ((a + 180) % 360 + 360) % 360 - 180;
const turnBetween = (a, b, t) => a + turn(b - a) * t;

function cubic(a, b, c, d, t) {
  const s = 1 - t;
  return {
    x: s * s * s * a.x + 3 * s * s * t * b.x + 3 * s * t * t * c.x + t * t * t * d.x,
    y: s * s * s * a.y + 3 * s * s * t * b.y + 3 * s * t * t * c.y + t * t * t * d.y,
  };
}

function geometry(layout) {
  const { source, perch, width, height } = layout;
  if (![source.x, source.y, source.size, perch.x, perch.y, perch.size, width, height].every(Number.isFinite)
      || Math.min(source.size, perch.size, width, height) <= 0) {
    throw new TypeError('The moth stage needs finite, positive measured geometry.');
  }
  const flyingWidth = Math.min(102, Math.max(source.size, perch.size) * 1.3, width * .26, height * .36);
  // Root measures source and perch outside the question hit area. Intermediate
  // handles stay in the stage; fixed endpoints continue to meet their marks.
  const inset = Math.min(28 + flyingWidth / 2, width / 2, height / 2);
  const point = (x, y) => ({ x: clamp(x, inset, width - inset), y: clamp(y, inset, height - inset) });
  const dx = perch.x - source.x;
  const direction = dx < 0 ? -1 : 1;
  const lifted = point(source.x + dx * .13, source.y - 28);
  const inspecting = point(perch.x - direction * 32, perch.y - 30);
  const approach = point(perch.x - direction * 12, perch.y + 17);
  const departed = point(source.x + (perch.x - source.x) * .45, Math.min(source.y + 20, height * .32));
  const lift = [source, point(source.x, source.y - 22), point(lifted.x - direction * 8, lifted.y + 2), lifted];
  const travel = [lifted, point(lifted.x + dx * .24, lifted.y - 18), point(inspecting.x - dx * .18, inspecting.y - height * .2), inspecting];
  const inspection = [inspecting, point(inspecting.x + direction * 6, inspecting.y + 12), point(approach.x - direction * 10, approach.y + 12), approach];
  // Final tangent points upward. The body can settle almost upright rather than
  // making a conspicuous half-turn at the instant it touches the perch.
  const landing = [approach, point(approach.x + direction * 14, approach.y - 15), point(perch.x, perch.y + 10), perch];
  const leaving = [perch, point(perch.x + direction * 7, perch.y - 22), point(departed.x + direction * 36, departed.y + 16), departed];
  return { source, perch, width, height, flyingWidth, lift, travel, inspection, landing, leaving };
}

function route(t, g) {
  if (t < 360) return { x: g.source.x, y: g.source.y };
  if (t < 920) return cubic(...g.lift, ease(progress(t, 360, 920)));
  if (t < 2300) return cubic(...g.travel, progress(t, 920, 2300));
  if (t < 2750) return cubic(...g.inspection, progress(t, 2300, 2750));
  if (t < 3250) return cubic(...g.landing, ease(progress(t, 2750, 3250)));
  if (t < 4010) return { x: g.perch.x, y: g.perch.y };
  return cubic(...g.leaving, ease(progress(t, 4010, 4760)));
}

function wing(phase, amplitude, resting, sign, weight = 1) {
  const compression = resting - amplitude * (.5 + .5 * Math.sin(phase));
  return {
    compression: clamp(compression, .28, 1),
    shear: sign * Math.cos(phase) * amplitude * .15 * weight,
  };
}

/**
 * Layout uses visible-moth widths, not the original emblem's square whitespace.
 * Scale multiplies a rig whose base width is layout.source.size. Heading is in
 * degrees with zero pointing upward. Wing outputs are pivoted affine inputs.
 * This function holds no clock, DOM state, random seed or animation resources.
 */
export function sampleScene(elapsed, layout) {
  const t = clamp(Number.isFinite(elapsed) ? elapsed : 0, 0, DURATION);
  const g = geometry(layout);
  const p = route(t, g);
  const seconds = t / 1000;
  const flight = progress(t, 360, 600) * (1 - progress(t, 2900, 3250));
  const departure = progress(t, 4010, 4190);
  const moving = Math.max(flight, departure);
  const bob = Math.sin(seconds * 11.7) * 2 * moving;
  const drift = Math.sin(seconds * 4.1 + .4) * Math.sin(seconds * 7.3) * 5
    * progress(t, 920, 1150) * (1 - progress(t, 2450, 2750));

  let size = g.source.size;
  let phase = 'emerge';
  if (t >= 360 && t < 920) {
    phase = 'lift';
    size = mix(g.source.size, g.flyingWidth, ease(progress(t, 360, 920)));
  } else if (t >= 920 && t < 2300) {
    phase = 'travel'; size = g.flyingWidth;
  } else if (t >= 2300 && t < 2750) {
    phase = 'inspect'; size = g.flyingWidth;
  } else if (t >= 2750 && t < 3250) {
    phase = 'land'; size = mix(g.flyingWidth, g.perch.size, ease(progress(t, 2750, 3250)));
  } else if (t >= 3250 && t < 4010) {
    phase = 'settle'; size = g.perch.size;
  } else if (t >= 4010 && t < 4760) {
    phase = 'depart'; size = mix(g.perch.size, g.flyingWidth * .65, ease(progress(t, 4010, 4760)));
  } else if (t >= 4760) {
    phase = 'finished'; size = g.flyingWidth * .65;
  }

  // A short look-behind/look-ahead suggests the body's turn inertia, including
  // the course correction, without retaining state or snapping at path joins.
  const before = route(Math.max(360, t - 100), g);
  const after = route(Math.min(4760, t + 100), g);
  const tangent = turn(Math.atan2(after.y - before.y, after.x - before.x) * 180 / Math.PI + 90);
  let heading = tangent;
  if (t < 540) heading = turnBetween(-4, tangent, ease(progress(t, 340, 540)));
  if (t >= 2950 && t < 3250) heading = turnBetween(tangent, 15, ease(progress(t, 2950, 3250)));
  if (t >= 3250 && t < 4010) heading = 15;
  if (t >= 4010 && t < 4170) heading = turnBetween(15, tangent, ease(progress(t, 4010, 4170)));

  const beat = (seconds * 7.8 + .035 * Math.sin(seconds * 6)) * Math.PI * 2;
  let amplitude = .18 + .53 * moving;
  let resting = 1;
  if (t >= 2750 && t < 3250) {
    const landing = ease(progress(t, 2750, 3250));
    amplitude = .42 * (1 - landing);
    resting = mix(1, .8, landing);
  }
  if (t >= 3250 && t < 4010) { amplitude = 0; resting = .8; }
  if (t >= 4010) {
    amplitude = .65 * departure;
    resting = mix(.8, 1, departure);
  }
  if (t >= 4760) { amplitude = 0; resting = .8; }
  const compressionLag = .32;
  const stoneLag = .04 * 7.8 * Math.PI * 2;
  const wingSoftFore = wing(beat, amplitude, resting, -1);
  const wingSoftHind = wing(beat - compressionLag, amplitude * .83, resting, -1);
  const wingStoneFore = wing(beat - stoneLag, amplitude * .82, resting, 1, .7);
  const wingStoneHind = wing(beat - stoneLag - compressionLag, amplitude * .69, resting, 1, .7);
  const settleAdjustment = Math.sin(progress(t, 3250, 3420) * Math.PI) * (t < 3420 ? 1 : 0);
  const opacity = ease(progress(t, 0, 120)) * (1 - ease(progress(t, 4510, 4760)));

  return {
    x: p.x + drift,
    y: p.y + bob,
    heading: turn(heading),
    scale: size / g.source.size,
    opacity,
    phase,
    softFore: wingSoftFore,
    softHind: wingSoftHind,
    stoneFore: wingStoneFore,
    stoneHind: wingStoneHind,
    bodyPitch: Math.sin(beat - .35) * 2.1 * moving + settleAdjustment * 1.5,
    antennaAngle: Math.sin(seconds * 5.2) * 3 * moving + settleAdjustment * 6,
    shadow: {
      opacity: opacity * (.07 + .09 * ease(progress(t, 2750, 3250)) * (1 - progress(t, 4010, 4230))),
      scale: mix(.62, .94, ease(progress(t, 2750, 3250))) * (1 - .2 * departure),
    },
  };
}
