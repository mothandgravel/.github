/** Project actual queue/receiver evidence. Source evidence remains attached to each observation. */
export function transportPicture(state, station) {
  if (!['north','south'].includes(station)) throw Error('Unknown station');
  const records = state.observations.flatMap(o => {
    const remote = state.accepted.find(r => r.station === station && r.observation_id === o.id);
    const availableAt = o.origin === station ? o.queuedAt : remote?.first_received_at;
    if (availableAt === undefined || availableAt > state.serverTime || o.observedAt > state.serverTime) return [];
    return [{...o,availableAt,age:(state.serverTime-o.observedAt)/1000,local:o.origin===station}];
  }).sort((a,b)=>a.observedAt-b.observedAt || a.id.localeCompare(b.id));
  const latest = [...new Map(records.map(r=>[`${r.origin}:${r.evidence==='public-ais'?'ais-'+r.source.mmsi:'synthetic'}`,r])).values()];
  return {records,latest};
}
export const shortObservation = o => `${o.evidence==='public-ais'?'AIS '+o.source.mmsi+' / ':''}${o.origin==='north'?'N':'S'}-${o.id.slice(0,8)}`;
export const transportClock = time => time == null ? '—' : new Date(time).toISOString().slice(11,23);
