const finite = n => typeof n === 'number' && Number.isFinite(n);
const start = Date.parse('2026-11-10T22:00:00Z'), end = start + 86400000;
const stamp = t => typeof t === 'string' && Number.isFinite(Date.parse(t));
const fileName = s => typeof s === 'string' && /^[a-zA-Z0-9.-]+$/.test(s);
const bbox = b => JSON.stringify(b) === '[23,59,28.5,61]';

export function readArchives(data) {
  if (data?.schema !== 'mg.coastal-archives.v1' || data.dateLocal !== '2026-11-11' || data.timezone !== 'Europe/Helsinki' || Date.parse(data.windowStartUtc) !== start || Date.parse(data.windowEndUtcExclusive) !== end) throw Error('Invalid archive day');
  if (!Array.isArray(data.gauges) || data.gauges.length !== 6 || !Array.isArray(data.reports) || data.reports.length !== 96 || !Array.isArray(data.frames) || data.frames.length !== 4 || !Array.isArray(data.images) || data.images.length !== 2) throw Error('Invalid archive collection');
  const receipt = name => {
    const r = data.receipts?.[name];
    if (!fileName(name) || !r || r.status !== 200 || r.error || !/^[a-f0-9]{64}$/.test(r.sha256) || !stamp(r.requestedAt) || !stamp(r.completedAt) || Date.parse(r.requestedAt) > Date.parse(r.completedAt)) throw Error('Invalid source receipt');
  };
  const ids = new Set();
  for (const s of data.gauges) {
    if (ids.has(s.id) || !['26045', '41801', '86094'].includes(s.stationCode) || !['WL avg', 'WT avg'].includes(s.parameter) || s.id !== `${s.stationCode}:${s.parameter}` || s.statistic !== 'hourly mean' || s.intervalEdge !== null || !finite(s.latitude) || !finite(s.longitude) || s.points?.length !== 24) throw Error('Invalid gauge series');
    if (s.parameter === 'WL avg' ? s.unit !== 'cm' || s.gaugeZeroMetresEH2000 !== -5 : s.unit !== '°C' || s.gaugeZeroMetresEH2000 !== null) throw Error('Invalid gauge datum');
    ids.add(s.id); receipt(s.sourceFile);
    for (const [i, p] of s.points.entries()) {
      if (Date.parse(p.labelledAt) !== start + i * 3600000 || Date.parse(p.localLabel) !== Date.parse(p.labelledAt) || (p.value === null ? p.rawValue !== null : !finite(p.value) || typeof p.rawValue !== 'string' || !p.rawValue.trim() || Number(p.rawValue) !== p.value)) throw Error('Gauge value differs from source');
    }
  }
  const reportIds = new Set();
  for (const r of data.reports) {
    receipt(r.sourceFile);
    const match = typeof r.raw === 'string' && r.raw.match(/\b(\d{2})(\d{2})(\d{2})Z\b/), t = new Date(r.observedAt);
    if (!['EFHK', 'EETN'].includes(r.station) || reportIds.has(r.id) || !stamp(r.observedAt) || t.getTime() < start || t.getTime() >= end || r.archiveValidAt !== r.observedAt || r.raw.split(' ')[0] !== r.station || !match || Number(match[1]) !== t.getUTCDate() || Number(match[2]) !== t.getUTCHours() || Number(match[3]) !== t.getUTCMinutes()) throw Error('Report clock differs from source');
    reportIds.add(r.id);
  }
  for (const [i, r] of data.frames.entries()) {
    receipt(r.sourceFile); receipt(r.metadataFile);
    if (Date.parse(r.observedAt) !== Date.parse('2026-11-11T10:00:00Z') + i * 300000 || r.noDataCode !== 0 || r.gain !== .5 || r.offset !== -32 || !bbox(r.bbox) || r.crs !== 'EPSG:4326' || r.pixelSizeDegrees !== .005 || r.width !== 1100 || r.height !== 400 || !fileName(r.image) || !fileName(r.pixels)) throw Error('Invalid radar frame');
  }
  for (const [i, r] of data.images.entries()) {
    receipt(r.sourceFile); receipt(r.domainFile);
    if (r.id !== ['terra', 'aqua'][i] || r.productDateUtc !== '2026-11-11' || r.acquiredAt !== null || r.publishedAt !== null || !bbox(r.bbox) || r.width !== 1100 || r.height !== 400 || r.crs !== 'EPSG:4326') throw Error('Invalid daily image clock');
  }
  return data;
}

export const utcAtMinute = minute => {
  if (!Number.isInteger(minute) || minute < 0 || minute > 1439) throw Error('Invalid minute');
  return new Date(start + minute * 60000).toISOString().replace('.000Z', 'Z');
};
export const minuteAtUtc = utc => Math.floor((Date.parse(utc) - start) / 60000);
export const clock = (utc, zone = 'UTC') => new Intl.DateTimeFormat('en-GB', {timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).format(new Date(utc));
export const gaugeAt = (series, utc) => series.points.find(p => Date.parse(p.labelledAt) === start + Math.floor((Date.parse(utc) - start) / 3600000) * 3600000) ?? null;
export function reportAt(reports, station, utc) {
  return reports.filter(r => r.station === station && Date.parse(r.observedAt) <= Date.parse(utc)).sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt)).at(-1) ?? null;
}
export function resolveReport(reports, station, utc, selectedId = null) {
  return reports.find(r => r.id === selectedId && r.station === station && Date.parse(r.observedAt) <= Date.parse(utc)) ?? reportAt(reports, station, utc);
}
export function frameAt(frames, utc) {
  const t = Date.parse(utc);
  if (t < Date.parse(frames[0].observedAt) || t > Date.parse(frames.at(-1).observedAt)) return null;
  return frames.filter(f => Date.parse(f.observedAt) <= t).at(-1) ?? null;
}
export const levelEH2000 = value => value === null ? null : Math.round((value / 100 - 5) * 1000000) / 1000000;
export function radarValue(code) {
  if (!Number.isInteger(code) || code < 0 || code >= 255) throw Error('Unrecognised radar code');
  return code === 0 ? null : .5 * code - 32;
}
export function reportFields(raw) {
  const wind = raw.match(/\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(KT|MPS)\b/);
  const temperature = raw.match(/\b(M?\d{2})\/(M?\d{2})\b/);
  const pressure = raw.match(/\bQ(\d{4})\b/), visibility = raw.match(/(?:^|\s)(\d{4})(?=\s|$)/);
  const signed = token => Number(token.replace('M', '-'));
  return {
    wind: wind ? `${wind[1] === 'VRB' ? 'Variable' : wind[1] + '°'} / ${Number(wind[2])} ${wind[4] === 'KT' ? 'kt' : 'm/s'}${wind[3] ? ' · gust ' + Number(wind[3]) : ''}` : 'Not decoded',
    temperature: temperature ? `${signed(temperature[1])} °C` : 'Not decoded',
    pressure: pressure ? `${Number(pressure[1])} hPa` : 'Not decoded',
    visibility: /\bCAVOK\b/.test(raw) ? 'CAVOK · ≥10 km' : visibility ? visibility[1] === '9999' ? '≥10 km' : `${Number(visibility[1])} m` : 'Not decoded',
    clouds: raw.match(/\b(?:FEW|SCT|BKN|OVC|VV)(?:\d{3}|\/\/\/)(?:CB|TCU)?\b/g)?.join(' · ') ?? (/\bCAVOK\b/.test(raw) ? 'CAVOK criteria; not zero cloud' : 'Read original report'),
  };
}
