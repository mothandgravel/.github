/** A bounded, synthetic two-station experiment. No sensor or military service is connected. */
export const VERSION = 'coastal-two-stations-v1';
export const END = 720;
export const DEFAULTS = Object.freeze({ interrupted: true, delay: 280, freshness: 120 });
export const STATIONS = Object.freeze({ north: 'North station', south: 'South station' });
export function settings(input = {}) {
  const interrupted = input.interrupted ?? true;
  const delay = Number(input.delay ?? 280), freshness = Number(input.freshness ?? 120);
  if (typeof interrupted !== 'boolean' || !Number.isInteger(delay) || delay < 220 || delay > 340 || !Number.isInteger(freshness) || freshness < 30 || freshness > 180) throw Error('Settings are outside this experiment.');
  return Object.freeze({ interrupted, delay, freshness });
}
export function scenario(input = DEFAULTS) {
  const config = settings(input);
  const observations = [], receipts = [];
  for (let t = 0; t <= 700; t += 100) {
    for (const origin of ['north', 'south']) {
      const id = `${origin === 'north' ? 'N' : 'S'}-${String(t).padStart(3, '0')}`;
      // Authored positions: one fictional contact, identity assigned by this fixture.
      const lon = 24.76 + t * 0.0002;
      const lat = 60.04 + Math.sin(t / 180) * 0.004 + (origin === 'north' ? 0.001 : 0);
      observations.push(Object.freeze({ id, origin, source: origin === 'north' ? 'SIM-RADAR-01' : 'SIM-AIS-01', observedAt: t, lon, lat, contact: 'Fixture vessel 01', evidence: 'synthetic' }));
      receipts.push(Object.freeze({ observationId: id, station: origin, receivedAt: t + 2, via: 'local', duplicate: false }));
      let arrival = t + 8;
      if (origin === 'south' && config.interrupted && t >= 200 && t < 500) arrival = t === 300 ? 300 + config.delay : 500 + (t === 400 ? 5 : 0);
      const station = origin === 'north' ? 'south' : 'north';
      receipts.push(Object.freeze({ observationId: id, station, receivedAt: arrival, via: 'relay', duplicate: false }));
      if (id === 'S-300') receipts.push(Object.freeze({ observationId: id, station, receivedAt: arrival + 4, via: 'retry', duplicate: true }));
    }
  }
  return Object.freeze({ version: VERSION, config, observations: Object.freeze(observations), receipts: Object.freeze(receipts.sort((a, b) => a.receivedAt - b.receivedAt || a.observationId.localeCompare(b.observationId))) });
}
export function picture(data, station, cursor, view = 'then') {
  if (!Object.hasOwn(STATIONS, station) || !Number.isFinite(cursor) || cursor < 0 || cursor > END || !['then', 'later'].includes(view)) throw Error('Invalid picture selection.');
  const horizon = view === 'then' ? cursor : END;
  const seen = new Map();
  const deliveries = data.receipts.filter(r => r.station === station && r.receivedAt <= horizon && data.observations.find(o => o.id === r.observationId).observedAt <= cursor);
  for (const receipt of deliveries) {
    if (seen.has(receipt.observationId)) continue;
    const observation = data.observations.find(o => o.id === receipt.observationId);
    seen.set(observation.id, { ...observation, receipt, age: cursor - observation.observedAt, fresh: cursor - observation.observedAt <= data.config.freshness, hindsight: receipt.receivedAt > cursor });
  }
  const records = [...seen.values()].sort((a, b) => a.observedAt - b.observedAt || a.id.localeCompare(b.id));
  const latest = ['north', 'south'].map(origin => records.filter(o => o.origin === origin).at(-1)).filter(Boolean);
  return { station, cursor, view, records, latest, deliveries, duplicates: deliveries.length - records.length, historicalAdditions: records.filter(r => r.hindsight).length };
}
export function clock(seconds) {
  return `12:${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}
export function evidence(data, cursor, view, station, selected) {
  return { format: VERSION, scope: 'Full authored scenario, including future events; station snapshots are filtered separately.', synthetic: true, signed: false, clock: 'Relative seconds from a fictional 12:00:00 UTC; no real observation date', scenario: data, selection: { cursor, view, station, observationId: selected }, snapshots: ['north', 'south'].map(s => picture(data, s, cursor, view)), limits: ['No sensor feed, fusion, prediction, identity inference or threat assessment.', 'Relayed/retried reports retain the original source and observation ID.', 'Freshness threshold is an experimental reading rule, not operational acceptance.', 'Hindsight is bounded to receipts by scenario end and never changes an earlier then-view.', 'A hash identifies exported bytes; it does not authenticate observations.'] };
}
