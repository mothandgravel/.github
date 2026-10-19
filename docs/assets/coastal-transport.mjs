import {transportPicture,shortObservation,transportClock as clock} from './coastal-transport-model.mjs';

const $=id=>document.getElementById(id);

const add=(tag,text,parent)=>{const el=document.createElement(tag);el.textContent=text;parent.append(el);return el;};

const svg=(tag,attrs,parent)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))el.setAttribute(k,v);parent.append(el);return el;};

const point=(lon,lat)=>[(lon-24.55)*857.143,(60.19-lat)*1714.286];

let state=null,selected=null,station='north',live=false,connected=false,busy=false,timer=null,requestVersion=0;

const announce=text=>{$('ct-status').textContent=text;};

function schedule(){clearTimeout(timer);if(live&&connected&&!document.hidden)timer=setTimeout(()=>refresh(),1500);}

function availability(){for(const el of document.querySelectorAll('#ct-controls input,#ct-controls select,#ct-controls button'))el.disabled=!connected||busy||Boolean(state?.busy);$('ct-export').disabled=!state;}

function select(id,s){selected=id;station=s;$('ct-station').value=s;render();$('ct-selection-status').textContent=`${shortObservation(state.observations.find(o=>o.id===id))} selected. Its record is open below the plots.`;}

function render(){

  if(!state)return;const focused=document.activeElement?.dataset?.transportFocus;

  const expanded=new Set([...document.querySelectorAll('#ct-attempts details[open]')].map(el=>el.dataset.attempt));

  const capture=state.aisCapture;

  $('ct-ais-status').textContent=!capture?'No public AIS captured yet.':capture.status==='complete'?`Captured ${new Date(capture.fetchedAt).toISOString()}: ${capture.added} queued, ${capture.duplicates} already known, ${capture.excluded} outside the extent, older than 10 minutes, future-dated or invalid, ${capture.limited} beyond this capture’s limit.`:capture.status==='failed'?`AIS capture failed: ${capture.error}. Existing records remain; no synthetic replacement was added.`:'Fetching public AIS…';

  $('ct-run').textContent=`Run ${state.runId} · snapshot ${new Date(state.serverTime).toISOString()}`;

  $('ct-paused').checked=state.controls.paused;$('ct-reject').checked=state.controls.reject;$('ct-response').checked=state.controls.failResponseOnce;

  $('ct-summary').textContent=`${state.observations.length} original observations · ${state.receipts.length} HTTP receipts · ${state.attempts.length} POST attempts · ${state.accepted.length} accepted station records`;

  $('ct-journal-warning').textContent=state.journalError||'';

  for(const s of ['north','south']){

    const p=transportPicture(state,s),layer=$(`ct-${s}-marks`);layer.replaceChildren();

    for(const o of p.records){

      const [x,y]=point(o.lon,o.lat),g=svg('g',{role:'button',tabindex:'0','aria-label':`Inspect ${shortObservation(o)} at ${s} station`},layer);

      g.dataset.transportFocus=`${s}-${o.id}`;svg('circle',{cx:x,cy:y,r:16,class:'hit'},g);

      const classes=`mark ${o.origin} ${o.age>120?'old':''} ${selected===o.id&&station===s?'selected':''}`;

      if(o.origin==='north')svg('path',{d:`M${x} ${y-6} l6 6 -6 6 -6 -6Z`,class:classes},g);else svg('circle',{cx:x,cy:y,r:p.latest.some(l=>l.id===o.id)?7:4,class:classes},g);

      g.addEventListener('click',()=>select(o.id,s));g.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select(o.id,s);}});

    }

    const summary=$(`ct-${s}-summary`);summary.replaceChildren();

    const ais=p.latest.filter(o=>o.evidence==='public-ais'); add('p',`${ais.length} available AIS contact records · latest by source time, per MMSI and originating station`,summary); for(const last of p.latest.filter(o=>o.evidence!=='public-ais'))add('p',`Synthetic ${last.origin} · ${shortObservation(last)} · ${Math.floor(last.age)}s old`,summary);

    add('p',`${p.records.length} known observations · ${state.queues[s].pending} outbound pending`,summary);

  }

  const picker=$('ct-observation');picker.replaceChildren();add('option','Choose a record',picker).value='';

  for(const entry of [...state.observations].reverse()){const option=add('option',`${shortObservation(entry)} · ${clock(entry.observedAt)}`,picker);option.value=entry.id;}picker.value=selected??'';

  const record=$('ct-record');record.replaceChildren();

  const o=state.observations.find(o=>o.id===selected);

  if(o){

    add('h3',shortObservation(o),record);const available=transportPicture(state,station).records.find(r=>r.id===selected);

    add('p',available?`${available.local?'Local queue entry':'Received over HTTP'} · available ${clock(available.availableAt)} UTC`:`Not received by ${station} station in this snapshot.`,record);

    const dl=add('dl','',record);

    for(const[k,v]of [['Observation ID',o.id],['Queue message ID',o.messageId],['Origin',o.origin],[o.evidence==='public-ais'?'Source timestampExternal / UTC':'Observed / UTC',new Date(o.observedAt).toISOString()],['Queued / UTC',clock(o.queuedAt)],['Priority',o.priority],['Sender ACK',o.acked?'Acknowledged':'Pending'],['Failed batches',String(o.failedBatches)]]){add('dt',k,dl);add('dd',v,dl);}

    if(o.evidence==='public-ais'){

      for(const[k,v]of [['Evidence','Public AIS / Fintraffic Digitraffic'],['MMSI',String(o.source.mmsi)],['Fetched / UTC',new Date(o.source.fetchedAt).toISOString()],['Source time meaning',o.source.timestampMeaning],['Position',`${o.lat.toFixed(6)}, ${o.lon.toFixed(6)}`],['Speed / course / heading',`${o.source.sog?.toFixed(1)??'unknown'} kn / ${o.source.cog?.toFixed(1)??'unknown'}° / ${o.source.heading??'unknown'}°`]]){add('dt',k,dl);add('dd',v,dl);}

    }else add('p','Synthetic position. No sensor measured this sample.',record);

    add('p','Observation and queue IDs remain unchanged across delivery attempts. A sender ACK is separate from receiver acceptance.',record);

  }else add('p','Capture public AIS or queue a synthetic sample to begin. Nothing is generated or sent automatically.',record);

  const receipts=$('ct-receipts');receipts.replaceChildren();

  for(const r of [...state.receipts].reverse()){

    const tr=add('tr','',receipts),o=state.observations.find(o=>o.id===r.observation_id);

    add('td',`#${r.id} / ${r.station}`,tr);const td=add('td','',tr),button=add('button',o?shortObservation(o):r.observation_id,td);button.type='button';button.dataset.transportFocus=`receipt-${r.id}`;button.addEventListener('click',()=>select(r.observation_id,r.station));

    add('td',clock(r.received_at),tr);add('td',`${r.status} · ${r.outcome}`,tr);

  }

  if(!state.receipts.length){const td=add('td','No HTTP receipts yet.',add('tr','',receipts));td.colSpan=4;}

  const attempts=$('ct-attempts');attempts.replaceChildren();

  for(const a of [...state.attempts].reverse()){

    const tr=add('tr','',attempts);add('td',`Burst ${a.cycle_id} / ${a.origin} / POST ${a.attempt}`,tr);add('td',clock(a.started_at),tr);add('td',clock(a.finished_at),tr);add('td',a.finished_at===null?'Unfinished / outcome unknown':a.error?`${a.status??'Network error'} · ${a.error}`:`${a.status} · acknowledged`,tr);

    const detail=add('td','',tr),expander=add('details','',detail);expander.dataset.attempt=a.id;expander.open=expanded.has(a.id);add('summary','IDs',expander);add('p',`Attempt: ${a.id}`,expander);add('p',`Queue: ${a.message_id}`,expander);

  }

  if(!state.attempts.length){const td=add('td','No POST attempts. An interrupted connection can leave a queue pending without a POST.',add('tr','',attempts));td.colSpan=5;}

  const cycles=$('ct-cycles');cycles.replaceChildren();

  for(const c of [...state.cycles].reverse().slice(0,8))add('p',c.result?`Burst ${c.id} · North: ${c.result.north.messagesSent} sent, ${c.result.north.error??'complete'} · South: ${c.result.south.messagesSent} sent, ${c.result.south.error??'complete'}`:`Burst ${c.id} · unfinished / outcome unknown`,cycles);

  availability();if(focused)document.querySelector(`[data-transport-focus="${focused}"]`)?.focus({preventScroll:true});

}

async function refresh(){

  const version=++requestVersion;

  try{

    const response=await fetch('/api/coastal/state',{cache:'no-store',signal:AbortSignal.timeout(5000)});

    if(!response.ok)throw Error('Local transport endpoint unavailable');

    const next=await response.json();if(next.format!=='raivari.coastal-transport.v1')throw Error('Unexpected transport service');

    if(version!==requestVersion)return;

    state=next;connected=true;$('ct-workbench').hidden=false;render();announce('Connected to the local Raivari transport. Actual receipts; each position retains its source label.');

  }catch{if(version!==requestVersion)return;connected=false;availability();announce(state?'Disconnected. Showing the last received snapshot; controls are disabled. Reconnect to refresh.':'Start Raivari’s local transport server with this site’s docs directory, then open its specimen URL. This static server has no queue or receiver.');}

  schedule();

}

async function command(body){

  if(!connected||busy)return;busy=true;availability();clearTimeout(timer);++requestVersion;

  try{

    const response=await fetch('/api/coastal/command',{method:'POST',headers:{'Content-Type':'application/json','X-Coastal-Workbench':'1'},body:JSON.stringify(body),signal:AbortSignal.timeout(120000)});

    if(!response.ok)throw Error(await response.text());const next=await response.json();++requestVersion;state=next;

    if(body.action==='observe'||body.action==='capture-ais')selected=state.observations.filter(o=>o.origin===body.station).at(-1)?.id;

    render();announce(body.action==='sync'?'Burst finished. Inspect the HTTP attempts and receiver receipts below.':'Saved by the local Raivari service.');

  }catch(error){announce(`Request did not complete: ${error.message}. Refresh before retrying; the server may have stored it.`);connected=false;}

  finally{busy=false;availability();schedule();}

}

function mode(value){live=value;$('ct-panel').hidden=!live;$('cw-desk').hidden=live;$('ct-live').setAttribute('aria-pressed',String(live));$('ct-authored').setAttribute('aria-pressed',String(!live));if($('cw-play').getAttribute('aria-pressed')==='true')$('cw-play').click();if(live)void refresh();else clearTimeout(timer);}

for(const s of ['north','south']){

  const original=document.querySelector(`#cw-${s}-marks`).closest('svg'),map=original.cloneNode(true);map.setAttribute('aria-label',`${s} station, actual transport availability of labelled observations`);

  map.querySelectorAll('[id]').forEach(el=>el.id=el.id.replace('cw-','ct-').replace(`${s}-grid`,`ct-${s}-grid`));map.querySelector('rect').setAttribute('fill',`url(#ct-${s}-grid)`);map.querySelector('.cw-land').replaceChildren();map.querySelector(`#ct-${s}-marks`).replaceChildren();$(`ct-${s}-map`).append(map);

}

fetch(new URL('./coastal-replay-land.json',import.meta.url)).then(r=>{if(!r.ok)throw Error();return r.json();}).then(land=>{for(const layer of document.querySelectorAll('#ct-panel .cw-land'))for(const polygon of land.polygons)svg('path',{class:'land',d:polygon.map(ring=>ring.map(([lon,lat],i)=>{const[x,y]=point(lon,lat);return`${i?'L':'M'}${x} ${y}`;}).join(' ')+'Z').join(' ')},layer);}).catch(()=>{$('ct-map-note').textContent='Coastline unavailable. Queue and receipt inspection remains available.';});

$('ct-live').addEventListener('click',()=>mode(true));$('ct-authored').addEventListener('click',()=>mode(false));$('ct-refresh').addEventListener('click',refresh);

$('ct-observe').addEventListener('click',()=>command({action:'observe',station:$('ct-origin').value,priority:$('ct-priority').value}));

$('ct-observation').addEventListener('change',e=>{if(e.target.value)select(e.target.value,station);});

$('ct-ais').addEventListener('click',()=>command({action:'capture-ais',station:$('ct-origin').value,priority:$('ct-priority').value}));

$('ct-sync').addEventListener('click',()=>command({action:'sync'}));

for(const id of ['ct-paused','ct-reject','ct-response'])$(id).addEventListener('change',()=>command({action:'controls',controls:{paused:$('ct-paused').checked,reject:$('ct-reject').checked,failResponseOnce:$('ct-response').checked}}));

$('ct-station').addEventListener('change',e=>{station=e.target.value;render();});

$('ct-export').addEventListener('click',async()=>{if(!state)return;const payload=structuredClone(state),digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(payload)));const blob=new Blob([JSON.stringify({integrity:{algorithm:'SHA-256',encoding:'UTF-8 JSON.stringify(payload)',digest:Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join(''),signed:false},payload},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`coastal-transport-${state.runId}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);announce('Exported the displayed snapshot of actual transport evidence. Unsigned; source provenance included.');});

document.addEventListener('visibilitychange',()=>{clearTimeout(timer);if(!document.hidden&&live&&connected&&!busy)void refresh();});

document.querySelector('.ct-mode').hidden=false;
availability();if(new URL(location.href).searchParams.get('transport')==='live')mode(true);

