import { clamp, rateLimit, BESS_REGISTERS, GENSET_REGISTERS, SCALE, encodeValue } from './field-power-core.mjs';

export const POLICY = Object.freeze({ minutes: 240, tripAt: 4, linkDown: 8, linkUp: 34, inspectionAt: 10,
  reserve: .1, initialSoC: .62, dischargeEfficiency: .92, chargeEfficiency: .94,
  dischargeLimit: 12, chargeLimit: 8, generatorLimit: 18, warmupMinutes: 3, rampKWPerMinute: 6, approvalLife: 10 });
export const LOADS = Object.freeze([
  Object.freeze({ id: 'comms', name: 'Communications', kw: 2, essential: true }),
  Object.freeze({ id: 'heat', name: 'Shelter heat', kw: 4, essential: true }),
  Object.freeze({ id: 'water', name: 'Water pump', kw: 3, essential: false }),
  Object.freeze({ id: 'workshop', name: 'Workshop', kw: 5, essential: false }),
]);
export const DEFAULTS = Object.freeze({ capacity: 40, temperature: -5 });
export function parameters(input = {}) {
  const p = { ...DEFAULTS, ...input };
  if (![20, 40, 80].includes(p.capacity) || ![-20, -5, 20].includes(p.temperature)) throw Error('Unsupported scenario parameters');
  // An illustrative fixed capacity allowance, not a chemistry/temperature model.
  const capacityFactor = clamp(1 - .006 * (20 - p.temperature), .65, 1);
  return { ...p, capacityFactor, usableCapacity: p.capacity * capacityFactor };
}
export const linkAvailable = t => t < POLICY.linkDown || t >= POLICY.linkUp;

function flow(energy, capacity, generator, enabled) {
  const demand = LOADS.reduce((sum, l) => sum + (enabled[l.id] ? l.kw : 0), 0);
  const discharge = Math.min(Math.max(0, demand - generator), POLICY.dischargeLimit,
    Math.max(0, energy - capacity * POLICY.reserve) * POLICY.dischargeEfficiency * 60);
  const charge = Math.min(Math.max(0, generator - demand), POLICY.chargeLimit,
    Math.max(0, capacity - energy) / POLICY.chargeEfficiency * 60);
  const generated = Math.min(generator, demand + charge);
  let available = generated + discharge - charge;
  const loads = LOADS.map(l => {
    const requested = enabled[l.id] ? l.kw : 0;
    const served = Math.min(requested, Math.max(0, available));
    available -= served;
    return { ...l, enabled: enabled[l.id], requested, served, unmet: requested - served };
  });
  return { demand, discharge, charge, generated, curtailed: generator - generated,
    served: loads.reduce((s, l) => s + l.served, 0), loads,
    unmet: loads.reduce((s, l) => s + l.unmet, 0) };
}

/** Rebuild every state from explicit minute-stamped actions. No ambient time or randomness. */
export function simulate(options = {}, actions = [], until = POLICY.minutes) {
  const p = parameters(options);
  if (!Number.isInteger(until) || until < 0 || until > POLICY.minutes) throw Error('Invalid replay cutoff');
  let previousAt = -1;
  const ids = new Set();
  for (const a of actions) {
    if (!Number.isInteger(a.at) || a.at < previousAt || a.at < 0 || a.at > POLICY.minutes || typeof a.id !== 'string' || !a.id || ids.has(a.id)) throw Error('Invalid action order or identity');
    if (!['load', 'inspect', 'request', 'approve'].includes(a.kind)) throw Error('Unknown action');
    if (a.kind === 'load' && (!LOADS.some(l => l.id === a.load && !l.essential) || typeof a.enabled !== 'boolean')) throw Error('Invalid load choice');
    previousAt = a.at; ids.add(a.id);
  }
  const enabled = Object.fromEntries(LOADS.map(l => [l.id, true]));
  let energy = p.usableCapacity * POLICY.initialSoC, generator = 18, restartAt = null, inspected = false, revision = 0;
  let heldSoC = 62, unmetEnergy = 0, servedEnergy = 0, generatedEnergy = 0, losses = 0, interval = null;
  const proposals = [], receipts = [], events = [], states = [];
  const receipt = (proposal, time) => {
    let outcome = 'applied';
    if (time > proposal.expiresAt) outcome = 'expired';
    else if (proposal.revision !== revision) outcome = 'configuration-changed';
    else if (!inspected) outcome = 'inspection-missing';
    else if (restartAt !== null || time < POLICY.tripAt) outcome = 'already-running';
    proposal.outcome = outcome;
    receipts.push({ proposal: proposal.id, requestedAt: proposal.at, approvedAt: proposal.approvedAt, receivedAt: time,
      expiresAt: proposal.expiresAt, expectedRevision: proposal.revision, actualRevision: revision, inspected,
      outcome, signed: false, transport: 'simulated' });
    events.push({ at: time, text: outcome === 'applied' ? 'Restart accepted. Three-minute warm-up begins.' : `Restart not applied: ${outcome.replaceAll('-', ' ')}.` });
    if (outcome === 'applied') { restartAt = time; revision++; }
  };
  for (let t = 0; t <= until; t++) {
    if (t > 0) {
      const next = restartAt !== null && t > restartAt + POLICY.warmupMinutes
        ? rateLimit(generator, 18, POLICY.rampKWPerMinute / 60, 60000) : generator;
      const f = flow(energy, p.usableCapacity, (generator + next) / 2, enabled);
      const before = energy;
      energy += (f.charge * POLICY.chargeEfficiency - f.discharge / POLICY.dischargeEfficiency) / 60;
      const loss = (f.discharge / POLICY.dischargeEfficiency - f.discharge + f.charge * (1 - POLICY.chargeEfficiency)) / 60;
      unmetEnergy += f.unmet / 60; servedEnergy += f.served / 60; generatedEnergy += f.generated / 60; losses += loss;
      interval = { from: t - 1, to: t, ...f, before, after: energy, loss,
        residual: f.generated / 60 + before - energy - f.served / 60 - loss };
      generator = next;
      if (restartAt !== null && t === restartAt + POLICY.warmupMinutes + 1) events.push({ at: t, text: 'First generator output. The ramp is still in progress.' });
      if (restartAt !== null && t === restartAt + POLICY.warmupMinutes + 3) events.push({ at: t, text: 'Generator reaches 18 kW capability. Supply and charging follow demand.' });
    }
    if (t === POLICY.tripAt) {
      generator = 0; revision++;
      heldSoC = energy / p.usableCapacity * 100;
      events.push({ at: t, text: 'Generator trips. The battery percentage stops updating.' });
    }
    if (t === POLICY.linkDown) events.push({ at: t, text: 'Approval link interrupted. Local load controls remain available.' });
    if (t === POLICY.linkUp) events.push({ at: t, text: 'Approval link returns. Held approvals reach their checks.' });
    // Previously transmitted approvals arrive before this minute's new local actions.
    for (const proposal of proposals) if (proposal.arrival === t && !proposal.outcome) receipt(proposal, t);
    for (const a of actions.filter(a => a.at === t)) {
      if (a.kind === 'load' && enabled[a.load] !== a.enabled) {
        enabled[a.load] = a.enabled; revision++;
        events.push({ at: t, text: `${LOADS.find(l => l.id === a.load).name} ${a.enabled ? 'restored' : 'shed'} locally.` });
      } else if (a.kind === 'inspect' && t >= POLICY.inspectionAt && !inspected) {
        inspected = true; revision++; events.push({ at: t, text: 'Local inspection recorded. Restart is available for a separate decision.' });
      } else if (a.kind === 'request' && t >= POLICY.tripAt && restartAt === null) {
        proposals.push({ id: a.id, at: t, expiresAt: t + POLICY.approvalLife, revision, approvedAt: null, arrival: null, outcome: null });
        events.push({ at: t, text: 'Restart proposed. No command has been sent.' });
      } else if (a.kind === 'approve') {
        const proposal = proposals.find(x => x.id === a.proposal);
        if (proposal && proposal.approvedAt === null) {
          proposal.approvedAt = t; proposal.arrival = linkAvailable(t) ? t : POLICY.linkUp;
          events.push({ at: t, text: linkAvailable(t) ? 'Approval sent to the simulated receiver.' : 'Approval held by the interrupted link.' });
          if (proposal.arrival === t) receipt(proposal, t);
        }
      }
    }
    const f = flow(energy, p.usableCapacity, generator, enabled);
    const observedAt = Math.min(t, POLICY.tripAt);
    const soc = t < POLICY.tripAt ? energy / p.usableCapacity * 100 : heldSoC;
    const state = { t, energy, generator, inspected, revision, restartAt, ...f, interval,
      status: t < POLICY.tripAt ? 'online' : restartAt === null ? 'tripped' : t < restartAt + POLICY.warmupMinutes ? 'warming' : generator < 18 ? 'ramping' : 'online',
      sensor: { soc, observedAt, deliveredAt: t, age: t - observedAt, held: t >= POLICY.tripAt },
      reserve: p.usableCapacity * POLICY.reserve, usableCapacity: p.usableCapacity,
      remainingMinutesAtDemand: f.demand ? Math.max(0, energy - p.usableCapacity * POLICY.reserve) * POLICY.dischargeEfficiency / f.demand * 60 : null,
      unmetEnergy, servedEnergy, generatedEnergy, losses,
      proposals: structuredClone(proposals), receipts: structuredClone(receipts), events: structuredClone(events),
      registers: [
        { address: BESS_REGISTERS.SOC, name: 'BESS.SOC', raw: encodeValue(soc, SCALE.TENTHS), scale: .1, unit: '%', observedAt, held: t >= POLICY.tripAt },
        { address: BESS_REGISTERS.POWER, name: 'BESS.POWER', raw: Math.round(f.discharge - f.charge), scale: 1, unit: 'kW', observedAt: t, held: false },
        { address: GENSET_REGISTERS.STATUS, name: 'GENSET.STATUS', raw: t < POLICY.tripAt || generator === 18 ? 3 : restartAt === null ? 5 : 2, scale: 1, unit: 'enum', observedAt: t, held: false },
        { address: GENSET_REGISTERS.GEN_POWER, name: 'GENSET.GEN_POWER', raw: Math.round(f.generated), scale: 1, unit: 'kW', observedAt: t, held: false },
      ] };
    states.push(state);
  }
  return { parameters: p, policy: POLICY, actions: structuredClone(actions.filter(a => a.at <= until)), states, current: states.at(-1) };
}

export function exampleActions() {
  return [
    { id: 'e1', at: 5, kind: 'load', load: 'workshop', enabled: false },
    { id: 'e2', at: 6, kind: 'load', load: 'water', enabled: false },
    { id: 'e3', at: 10, kind: 'inspect' },
    { id: 'e4', at: 12, kind: 'request' },
    { id: 'e5', at: 13, kind: 'approve', proposal: 'e4' },
    { id: 'e6', at: 35, kind: 'request' },
    { id: 'e7', at: 36, kind: 'approve', proposal: 'e6' },
    { id: 'e8', at: 44, kind: 'load', load: 'water', enabled: true },
  ];
}
export function exportAccount(options, actions, cursor) {
  const run = simulate(options, actions, cursor);
  return { specimen: 'What stays on', version: 1, evidence: 'Synthetic land-site rehearsal', signed: false,
    sourceManifest: 'https://mothandgravel.com/design/field-power-core.json', cursor, ...run,
    futureActionsExcluded: actions.filter(a => a.at > cursor).length,
    limits: 'Energy arithmetic only. No load flow, thermal safety, fuel depletion, actual Modbus connection or Raivari queue receipts. Approval is simulated and does not operate equipment.' };
}
