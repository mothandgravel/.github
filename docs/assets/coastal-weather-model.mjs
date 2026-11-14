const START = Date.parse('2026-11-10T22:00:00Z'), END = START + 86400000;
const finite = n => typeof n === 'number' && Number.isFinite(n);
const stamp = s => typeof s === 'string' && Number.isFinite(Date.parse(s));
const name = s => typeof s === 'string' && /^[a-zA-Z0-9.-]+$/.test(s);
const hash = s => typeof s === 'string' && /^[a-f0-9]{64}$/.test(s);

export function readWeather(data) {
  if (data?.schema !== 'mg.coastal-weather.v1' || data.timezone !== 'Europe/Helsinki' || data.dateLocal !== '2026-11-11' || Date.parse(data.windowStartUtc) !== START || Date.parse(data.windowEndUtcExclusive) !== END) throw Error('Invalid weather day');
  if (data.clouds?.length !== 144 || data.radar?.length !== 12 || data.buoys?.length !== 3 || JSON.stringify(data.bbox) !== '[23,59,28.5,61]') throw Error('Invalid weather collection');
  const receipt = file => {
    const r = data.receipts?.[file];
    if (!name(file) || !r || r.status !== 200 || r.error || !hash(r.sha256) || !stamp(r.requestedAt) || !stamp(r.completedAt) || Date.parse(r.completedAt) < Date.parse(r.requestedAt)) throw Error('Invalid weather receipt');
  };
  for (const [i, f] of data.clouds.entries()) {
    if (Date.parse(f.productTimeUtc) !== START + i * 600000 || f.id !== f.productTimeUtc || !name(f.sourceFile) || f.perPixelAcquisitionUtc !== null || f.firstPublicationUtc !== null || typeof f.available !== 'boolean') throw Error('Invalid cloud clock');
    if (f.available) receipt(f.sourceFile);
  }
  const ids = new Set();
  for (const f of data.radar) {
    receipt(f.sourceFile);
    if (ids.has(f.id) || f.id !== f.sourceFile || !stamp(f.scanStartUtc) || !stamp(f.scanEndUtc) || Date.parse(f.scanStartUtc) > Date.parse(f.scanEndUtc) || !name(f.image) || !name(f.pixels) || !hash(f.pixelsUncompressedSha256) || f.width !== 720 || f.height !== 720 || f.pixelsUncompressedBytes !== 720 * 720 * 4 || f.quantity !== 'RATE' || f.unit !== 'mm/h' || f.noDataCode !== 65535 || f.undetectCode !== 0 || f.gain !== 1 || f.offset !== 0 || f.georeferencing?.presentation !== 'native grid only') throw Error('Invalid native radar');
    if (Object.values(f.cellCounts).reduce((sum,n) => sum + n,0) !== 720 * 720 || f.sourceNodes.join(',') !== 'eesyr,eehar') throw Error('Invalid radar lineage');
    ids.add(f.id);
  }
  if (!data.radar.every((f,i,a) => i === 0 || Date.parse(f.scanEndUtc) > Date.parse(a[i-1].scanEndUtc))) throw Error('Radar not ordered');
  if (data.policies?.cloudMaxAgeSecondsExclusive !== 600 || data.policies.radarMaxAgeSecondsExclusive !== 300 || data.policies.buoyMaxAgeSecondsExclusive !== 3600 || data.policies.interpolation !== false || data.policies.noFutureSelection !== true) throw Error('Invalid clock policy');
  const stations = new Set();
  for (const b of data.buoys) {
    if (!['134221','103976','108495'].includes(b.id) || stations.has(b.id) || !finite(b.latitude) || !finite(b.longitude) || b.series?.length !== 5) throw Error('Invalid buoy');
    stations.add(b.id); const params = new Set();
    for (const s of b.series) {
      if (s.stationId !== b.id || params.has(s.parameter) || !['WaveHs','ModalWDi','WTP','WHDD','TWATER'].includes(s.parameter) || s.points?.length !== 24) throw Error('Invalid buoy parameter');
      params.add(s.parameter);
      for (const [i,p] of s.points.entries()) if (Date.parse(p.observedAt) !== START + i * 3600000 || (p.value === null ? p.rawValue !== 'NaN' : !finite(p.value) || Number(p.rawValue) !== p.value)) throw Error('Buoy value differs from source');
    }
  }
  return data;
}

export const utcAtSecond = second => {
  if (!Number.isInteger(second) || second < 0 || second > 86399) throw Error('Invalid browse second');
  return new Date(START + second * 1000).toISOString().replace('.000Z','Z');
};
export const secondAtUtc = time => Math.floor((Date.parse(time) - START) / 1000);
export function cloudAt(data, second) {
  const time = Date.parse(utcAtSecond(second));
  const f = data.clouds[Math.floor(second / 600)];
  return f?.available && Date.parse(f.productTimeUtc) <= time && time - Date.parse(f.productTimeUtc) < 600000 ? f : null;
}
export function radarAt(data, second) {
  const time = Date.parse(utcAtSecond(second)), frames = data.radar;
  if (time < Date.parse(frames[0].scanEndUtc) || time > Date.parse(frames.at(-1).scanEndUtc)) return null;
  const f = frames.filter(f => Date.parse(f.scanEndUtc) <= time).at(-1);
  return f && time - Date.parse(f.scanEndUtc) < 300000 ? f : null;
}
export function buoyAt(data, stationId, second) {
  utcAtSecond(second);
  const b = data.buoys.find(b => b.id === stationId);
  if (!b) throw Error('Unknown buoy');
  return {station: b, points: Object.fromEntries(b.series.map(s => [s.parameter, s.points[Math.floor(second / 3600)]]))};
}
export function radarCell(frame, code) {
  if (!finite(code)) throw Error('Invalid native radar code');
  if (code === frame.noDataCode) return {kind:'missing',rawValue:code,value:null,unit:frame.unit};
  if (code === frame.undetectCode) return {kind:'below detection',rawValue:code,value:null,unit:frame.unit};
  return {kind:'quantitative',rawValue:code,value:code * frame.gain + frame.offset,unit:frame.unit};
}
export function waveDirectionFrom(degrees, spread = null) {
  if (!finite(degrees) || degrees < 0 || degrees > 360 || (spread !== null && (!finite(spread) || spread < 0 || spread > 180))) return null;
  const bearing = degrees % 360;
  return {fromDegrees:bearing,travellingTowardsDegrees:(bearing + 180) % 360,spreadDegrees:spread,
    cardinal:['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'][Math.round(bearing/22.5)%16]};
}
export function inspectWeather(data, second, stationId) {
  const utc = utcAtSecond(second), cloud = cloudAt(data,second), radar = radarAt(data,second), buoy = buoyAt(data,stationId,second);
  return {schema:'mg.coastal-weather-inspection.v1',browseTimeUtc:utc,browseTimezone:'Europe/Helsinki',
    interpolation:false,originalReceiverTimeUtc:null,firstPublicationUtc:null,
    clouds:{record:cloud,expectedProductTimeUtc:data.clouds[Math.floor(second/600)].productTimeUtc,
      ageSeconds:cloud ? second-secondAtUtc(cloud.productTimeUtc) : null,
      httpReceipt:cloud ? data.receipts[cloud.sourceFile] : null,source:data.sources.clouds},
    radar:{record:radar,ageSeconds:radar ? second-secondAtUtc(radar.scanEndUtc) : null,
      httpReceipt:radar ? data.receipts[radar.sourceFile] : null,source:data.sources.radar},
    buoy:{stationId,station:buoy.station.station,points:buoy.points,source:data.sources.buoys,
      sourceRecords:buoy.station.series.map(s => ({parameter:s.parameter,sourceFile:s.sourceFile,sourceSha256:s.sourceSha256,retrievedAt:s.retrievedAt,completedAt:null,publicationTime:s.publicationTime ?? null}))}};
}
