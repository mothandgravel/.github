import { scenario, picture, clock, evidence, END, DEFAULTS } from './coastal-replay-model.mjs';
const $ = id => document.getElementById(id);
let config = { ...DEFAULTS }, data = scenario(config), cursor = 420, view = 'then', station = 'north', selected = 'S-300';
let running = false, previous = 0, frame = 0;
const point = (lon, lat) => [(lon - 24.55) * 857.143, (60.19 - lat) * 1714.286];
const safeText = (tag, value, parent) => { const e = document.createElement(tag); e.textContent = value; parent.append(e); return e; };
const svgElement = (tag, attrs, parent) => { const el = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k,v] of Object.entries(attrs)) el.setAttribute(k,v); parent.append(el); return el; };
function stop() { running = false; cancelAnimationFrame(frame); $('cw-play').textContent = 'Play · 20×'; $('cw-play').setAttribute('aria-pressed', 'false'); }
function select(id, origin) { stop(); selected = id; station = origin; $('cw-station').value = station; render(); $('cw-message').textContent = `${id} selected. Its ${station} station record is open below the plots.`; }
function draw(stationName, p) {
  const layer = $(`cw-${stationName}-marks`); layer.replaceChildren();
  for (const origin of ['north', 'south']) {
    const records = p.records.filter(o => o.origin === origin);
    // Separate dots only: connecting absent reports would imply an unobserved route.
    for (const o of records) {
      const [x,y] = point(o.lon, o.lat), latest = p.latest.some(r => r.id === o.id);
      const g = svgElement('g', { role: 'button', tabindex:'0', 'aria-label': `${o.id}, ${origin === 'north' ? 'radar' : 'AIS'}, observed ${clock(o.observedAt)}, ${o.hindsight ? 'received later' : 'received at this station'}` }, layer);
      g.dataset.focusKey = `${stationName}-${o.id}`;
      g.addEventListener('focus', stop);
      svgElement('circle', {cx:x,cy:y,r:16,class:'hit'},g);
      const classes = `mark ${origin} ${!o.fresh ? 'old' : ''} ${o.hindsight ? 'historical' : ''} ${selected === o.id && station === stationName ? 'selected' : ''}`;
      if (origin === 'north') svgElement('path',{d:`M${x} ${y-6} l6 6 -6 6 -6 -6Z`,class:classes,opacity:latest?1:.6},g);
      else svgElement('circle',{cx:x,cy:y,r:latest?7:4,class:classes,opacity:latest?1:.65},g);
      g.addEventListener('click',()=>select(o.id, stationName));
      g.addEventListener('keydown', e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(o.id,stationName);}});
    }
  }
  const summary = $(`cw-${stationName}-summary`); summary.replaceChildren();
  for (const origin of ['north','south']) {
    const last = p.latest.find(o=>o.origin===origin), name = origin==='north'?'Radar':'AIS';
    safeText('p', last ? `${name} · ${last.id} · ${Math.floor(last.age)}s old · ${last.hindsight ? 'arrived later' : last.fresh ? 'within age limit' : 'outside age limit'}` : `${name} · no report received`, summary);
  }
  safeText('p', `${p.records.length} unique observations · ${p.deliveries.length} receipts${p.historicalAdditions ? ` · ${p.historicalAdditions} added by hindsight` : ''}`,summary);
}
function renderRecord(p) {
  const box = $('cw-record'); box.replaceChildren();
  safeText('h3', selected, box);
  const record = p.records.find(o=>o.id===selected);
  if (!record) {
    safeText('p', `Not received in ${station === 'north' ? 'North' : 'South'} station’s picture at ${clock(cursor)} UTC.`,box);
    safeText('p','This report is named by the experiment. Its position and observation time stay out of this station’s record until they become available. Inspect South, advance the clock, or explicitly look back with later receipts.',box);
    return;
  }
  const dl=document.createElement('dl');box.append(dl);
  for (const [key,value] of [ ['Origin',record.source],['Observed',`${clock(record.observedAt)} UTC`],['First received here',`${clock(record.receipt.receivedAt)} UTC`],['Delivery lag',`${record.receipt.receivedAt-record.observedAt}s`],['Observation age',`${Math.floor(record.age)}s`],['Position',`${record.lat.toFixed(4)} N, ${record.lon.toFixed(4)} E`],['Path',record.receipt.via],['Evidence','Synthetic fixture'] ]) { safeText('dt',key,dl);safeText('dd',value,dl); }
  safeText('p',record.hindsight ? 'Hindsight: this observation was not available here at the selected time. It is included only because this view looks through to 12:12:00.' : 'This station had received this report by the selected time.',box);
  const count=p.deliveries.filter(r=>r.observationId===selected).length;
  safeText('p',`${count} receipt${count===1?'':'s'} here; one original observation. A relay or retry adds no independent corroboration.`,box);
  if(record.id==='S-300' && record.receipt.receivedAt>508) safeText('p','Its late arrival fills a historical gap. It does not replace a newer observation as the latest AIS position.',box);
}
function renderLedger(p) {
  const body=$('cw-ledger-body');body.replaceChildren();
  for(const r of [...p.deliveries].reverse()) {
    const o=data.observations.find(o=>o.id===r.observationId), tr=document.createElement('tr');
    tr.dataset.selected=String(selected===o.id);body.append(tr);
    const cell=document.createElement('td');tr.append(cell);
    const button=safeText('button',o.id,cell);button.type='button';button.setAttribute('aria-label',`Inspect ${o.id}${r.duplicate?' retry':''}`);button.addEventListener('click',()=>select(o.id,station));
    button.dataset.focusKey = `receipt-${station}-${o.id}-${r.receivedAt}`;
    button.addEventListener('focus', stop);
    safeText('td',clock(o.observedAt),tr);safeText('td',clock(r.receivedAt),tr);
    safeText('td',r.duplicate?'Retry':r.receivedAt>cursor?'Later':r.via==='local'?'Local':'Relay',tr);
  }
  if(!p.deliveries.length){const tr=document.createElement('tr');body.append(tr);const td=safeText('td','No receipts at this time.',tr);td.colSpan=4;}
  $('cw-ledger-caption').textContent=`${station==='north'?'North':'South'} receipts · ${view==='then'?'available by the cursor':'observations by cursor, receipts through 12:12:00'} · newest receipt first`;
}
function render() {
  const focusKey = document.activeElement?.dataset?.focusKey;
  $('cw-clock').textContent=clock(cursor);$('cw-time').value=String(cursor);$('cw-time').setAttribute('aria-valuetext',`${clock(cursor)} UTC`);
  const interrupted=config.interrupted&&cursor>=200&&cursor<500;
  $('cw-link').textContent=interrupted?'South → North · interrupted':config.interrupted&&cursor>=500?'South → North · restored':'South → North · connected';
  $('cw-status').textContent=interrupted?'North keeps receiving local radar. South keeps observing. Only the South-to-North relay is interrupted.':config.interrupted&&cursor>=500?'The link is back. Historical reports can still be in transit. Connection and completeness are separate.':'Both stations receive locally and exchange reports. Relays retain their original source.';
  $('cw-view-note').textContent=view==='then'?'As known then: each station includes only reports it had received by the cursor. Empty space is missing evidence, not an empty sea.':'Looking back: include observations made by the cursor that arrive by 12:12:00. Dotted marks arrived later. This is hindsight, not what the operator knew.';
  $('cw-view-note').classList.toggle('cw-hindsight',view==='later');
  $('cw-then').setAttribute('aria-pressed',String(view==='then'));$('cw-later').setAttribute('aria-pressed',String(view==='later'));
  for(const s of ['north','south']) draw(s,picture(data,s,cursor,view));
  const p=picture(data,station,cursor,view);renderRecord(p);renderLedger(p);
  $('cw-delay-value').textContent=`${config.delay}s · arrival ${clock(300+config.delay)}`;
  $('cw-freshness-value').textContent=`${config.freshness}s`;
  $('cw-delay').disabled=!config.interrupted;
  $('cw-unique').textContent=`${p.records.length} observations / ${p.deliveries.length} receipts / ${p.duplicates} retries`;
  if (focusKey) document.querySelector(`[data-focus-key="${focusKey}"]`)?.focus({preventScroll:true});
}
function changeTime(t){stop();cursor=Math.max(0,Math.min(END,t));render();}
$('cw-time').addEventListener('input',e=>changeTime(Number(e.target.value)));
document.querySelectorAll('[data-cw-time]').forEach(b=>b.addEventListener('click',()=>changeTime(b.dataset.cwTime==='late'?300+config.delay:Number(b.dataset.cwTime))));
$('cw-play').addEventListener('click',()=>{
  if(running){stop();return;} if(cursor>=END)cursor=0;running=true;previous=performance.now();$('cw-play').textContent='Pause';$('cw-play').setAttribute('aria-pressed','true');
  function tick(now){if(!running)return;cursor=Math.min(END,cursor+(now-previous)/1000*20);previous=now;render();if(cursor>=END)stop();else frame=requestAnimationFrame(tick);}
  frame=requestAnimationFrame(tick);
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
for(const mode of ['then','later']) $(`cw-${mode}`).addEventListener('click',()=>{stop();view=mode;render();});
$('cw-station').addEventListener('change',e=>{stop();station=e.target.value;render();});
$('cw-interrupted').addEventListener('change',e=>{stop();config.interrupted=e.target.checked;data=scenario(config);render();});
for(const key of ['delay','freshness']) $(`cw-${key}`).addEventListener('input',e=>{stop();config[key]=Number(e.target.value);data=scenario(config);render();});
$('cw-reset').addEventListener('click',()=>{stop();config={...DEFAULTS};data=scenario(config);cursor=420;view='then';station='north';selected='S-300';$('cw-interrupted').checked=true;$('cw-delay').value=280;$('cw-freshness').value=120;$('cw-station').value='north';render();$('cw-message').textContent='Original experiment restored.';});
$('cw-export').addEventListener('click',async()=>{
  stop();const payload=evidence(data,Math.floor(cursor),view,station,selected);
  const bytes=new TextEncoder().encode(JSON.stringify(payload));
  const digest=globalThis.crypto?.subtle?Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join(''):null;
  const blob=new Blob([JSON.stringify({integrity:{algorithm:'SHA-256',encoding:'UTF-8 JSON.stringify(payload)',digest,signed:false},payload},null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='coastal-watch-two-stations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('cw-message').textContent='Exported the full synthetic scenario, current selections and filtered station records. The hash is an integrity check, not a signature.';
});
$('cw-desk').hidden=false;$('cw-fallback').hidden=true;render();
try {
  const response=await fetch(new URL('./coastal-replay-land.json',import.meta.url));if(!response.ok)throw Error('map');const land=await response.json();
  for(const svg of document.querySelectorAll('.cw-map')){
    const layer=svg.querySelector('.cw-land');
    for(const polygon of land.polygons){const d=polygon.map(ring=>ring.map(([lon,lat],i)=>{const[x,y]=point(lon,lat);return`${i?'L':'M'}${x.toFixed(2)} ${y.toFixed(2)}`;}).join(' ')+'Z').join(' ');svgElement('path',{d,class:'land'},layer);}
  }
} catch { $('cw-map-note').textContent='Coastline unavailable. Station records and the coordinate plots still work.'; }
