const ms = stamp => Date.parse(stamp);
const finite = n => typeof n === 'number' && Number.isFinite(n);
export function readDay(data) {
  if (data?.schema !== 'mg.coastal-day.v1' || data.dateLocal !== '2026-11-21' || data.timezone !== 'Europe/Helsinki' || data.startUtc !== '2026-11-20T22:00:00Z' || data.queryEndUtcInclusive !== '2026-11-21T17:00:00Z' || data.endUtcExclusive !== '2026-11-21T22:00:00Z') throw Error('Unrecognised dated notebook');
  if (!Array.isArray(data.series) || data.series.length !== 17) throw Error('Incomplete source channels');
  const ids = new Set();
  for (const s of data.series) {
    if (ids.has(s.id) || ![10, 30].includes(s.intervalMinutes) || !s.station || !s.unit || !finite(s.latitude) || !finite(s.longitude) || !Array.isArray(s.points) || s.points.length !== 1140 / s.intervalMinutes + 1) throw Error('Invalid source series');
    ids.add(s.id);
    s.points.forEach((p, i) => {
      if (ms(p.time) !== ms(data.startUtc) + i * s.intervalMinutes * 60000 || typeof p.raw !== 'string' || !p.raw.trim() || (p.raw === 'NaN' ? p.value !== null : !finite(p.value) || Number(p.raw) !== p.value)) throw Error('Altered or unordered observation');
    });
  }
  for (const id of ['101039:ws_10min', '101039:wg_10min', '108495:WaveHs', '134221:WaveHs', '134254:WLEVN2K_PT1S_INSTANT']) if (!ids.has(id)) throw Error('Missing display channel');
  const fix = data.ais?.response?.features;
  if (fix?.length !== 1 || fix[0].mmsi !== 273394890 || data.ais.metadata.imo !== 9160994 || ms(data.ais.sourceTimeUtc) !== fix[0].properties.timestampExternal || !fix[0].geometry.coordinates.every(finite)) throw Error('Invalid AIS source');
  if (!Array.isArray(data.reports) || data.reports.some(r => !['EFHK', 'EETN'].includes(r.station) || !r.metar || ms(r.time) < ms(data.startUtc) || ms(r.time) > ms(data.queryEndUtcInclusive))) throw Error('Invalid METAR window');
  return data;
}
export function at(data, series, second) {
  const time = ms(data.startUtc) + second * 1000;
  if (!finite(second) || second < 0 || time > ms(data.queryEndUtcInclusive)) return {kind: 'uncollected', point: null};
  const point = series.points[Math.floor(second / (series.intervalMinutes * 60))];
  if (!point) return {kind: 'uncollected', point: null};
  return {kind: point.value === null ? 'missing' : 'reading', point, ageSeconds: (time - ms(point.time)) / 1000};
}
export function aisAt(data, second) {
  const time = ms(data.startUtc) + second * 1000, source = ms(data.ais.sourceTimeUtc);
  if (!finite(second) || second < 0 || time > ms(data.queryEndUtcInclusive)) return {kind: 'uncollected'};
  if (time < source) return {kind: 'before'};
  return {kind: 'saved', ageSeconds: (time - source) / 1000, fix: data.ais.response.features[0]};
}
export function metarAt(data, station, second) {
  const time = ms(data.startUtc) + second * 1000;
  if (!finite(second) || second < 0 || time > ms(data.queryEndUtcInclusive)) return null;
  return data.reports.filter(r => r.station === station && ms(r.time) <= time).sort((a,b) => ms(b.time) - ms(a.time))[0] ?? null;
}
export const clock = (stamp, seconds = false) => new Intl.DateTimeFormat('en-GB', {timeZone: 'Europe/Helsinki', hour: '2-digit', minute: '2-digit', ...(seconds ? {second: '2-digit'} : {}), hourCycle: 'h23'}).format(new Date(typeof stamp==='string'?stamp.replace(/(\.\d{3})\d+(?=Z|[+-]\d{2}:\d{2}$)/,'$1'):stamp));
export const exact = n => n === null ? 'Missing' : new Intl.NumberFormat('en-GB', {maximumFractionDigits: 6}).format(n);
export function elapsed(seconds) {
  if (seconds < 60) return `${Math.floor(seconds)} s`;
  const mins = Math.floor(seconds / 60);
  return mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)} h ${mins % 60} min`;
}
