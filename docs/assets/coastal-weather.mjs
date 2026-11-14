import {readWeather,utcAtSecond,secondAtUtc,cloudAt,radarAt,buoyAt,radarCell,waveDirectionFrom,inspectWeather} from './coastal-weather-model.mjs';

const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
const root = new URL('../data/coastal-weather/2026-11-11/',import.meta.url);
const buoyRoot = new URL('../data/coastal-sources/2026-11-11/raw/',import.meta.url);
const state = {second:43206,station:'134221',source:'clouds',playing:false};
const text = (id,value) => { $(id).textContent = value; };
const el = (tag,value) => { const n = document.createElement(tag); if (value !== undefined) n.textContent = value; return n; };
const svg = (tag,attrs={},value) => {
  const n = document.createElementNS(NS,tag); for (const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);
  if (value !== undefined) n.textContent = value; return n;
};
const clock = (time,zone='UTC',seconds=true) => new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',...(seconds?{second:'2-digit'}:{}),hourCycle:'h23'}).format(new Date(time));
const number = value => value === null ? 'Missing' : new Intl.NumberFormat('en-GB',{maximumFractionDigits:4}).format(value);
const age = seconds => seconds < 60 ? `${seconds} s` : `${Math.floor(seconds/60)} min ${seconds%60} s`;
let data,cloudImage,cloudVersion=0,radarVersion=0,pixelVersion=0,playVersion=0,timer,inspection,selectedCell=null,broadcasting=false,resizeFrame,pendingExternalSecond=null;
const images = new Map(), cells = new Map();
async function json(url) { const r = await fetch(url); if (!r.ok) throw Error(`Saved data HTTP ${r.status}`); return r.json(); }
function loadImage(url) {
  const key = String(url); if (images.has(key)) return images.get(key);
  const p = new Promise((resolve,reject) => { const img = new Image(); img.onload = () => img.decode().then(() => resolve(img),reject); img.onerror = () => reject(Error('Saved image could not be opened')); img.src = url; });
  images.set(key,p); p.catch(() => images.delete(key)); if (images.size > 8) images.delete(images.keys().next().value); return p;
}
function buildMap(land) {
  const target = $('cw-cloud-map'),x = lon => (lon-23)/5.5*1100,y = lat => (61-lat)/2*400;
  target.replaceChildren(svg('title',{id:'cw-map-title'},'Saved clouds above the Gulf of Finland'),svg('desc',{id:'cw-map-desc'},'EUMETSAT product imagery. Context coastline and actual FMI buoy positions; mobile layout crops the image. Not a navigation chart.'));
  target.setAttribute('preserveAspectRatio','xMidYMid slice');
  cloudImage = svg('image',{width:1100,height:400,x:0,y:0,visibility:'hidden',preserveAspectRatio:'none'}); target.append(cloudImage);
  if (land) for (const polygon of land.polygons) {
    const d = polygon.map(ring => ring.map(([lon,lat],i) => `${i?'L':'M'}${x(lon).toFixed(2)} ${y(lat).toFixed(2)}`).join(' ')+'Z').join(' ');
    target.append(svg('path',{d,class:'cw-map-land'}),svg('path',{d,class:'cw-map-coast'}));
  }
  for (const lon of [24,25,26,27,28]) target.append(svg('line',{x1:x(lon),x2:x(lon),y1:0,y2:400,class:'cw-map-grid'}));
  for (const lat of [59.5,60,60.5]) target.append(svg('line',{x1:0,x2:1100,y1:y(lat),y2:y(lat),class:'cw-map-grid'}));
  for (const [label,lon,lat] of [['HELSINKI',24.94,60.17],['TALLINN',24.75,59.44]]) target.append(svg('text',{x:x(lon)-18,y:y(lat)-13,class:'cw-map-label'},label));
  for (const b of data.buoys) target.append(svg('circle',{cx:x(b.longitude),cy:y(b.latitude),r:5,class:'cw-map-buoy'}),svg('circle',{cx:x(b.longitude),cy:y(b.latitude),r:11,class:'cw-map-buoy-ring','data-cw-buoy-ring':b.id}));
  target.append(svg('text',{x:650,y:225,class:'cw-map-label cw-map-label-small','text-anchor':'middle'},'GULF OF FINLAND'));
  if (!land) text('cw-map-desc','EUMETSAT cloud context. Context coastline unavailable; buoy coordinates still come from FMI.');
  resizeMap();
}
function resizeMap() { $('cw-cloud-map').setAttribute('viewBox',innerWidth <= 760 ? '230 0 550 400' : '0 0 1100 400'); }

async function renderCloud() {
  const version = ++cloudVersion,f = cloudAt(data,state.second),expected = data.clouds[Math.floor(state.second/600)];
  cloudImage.setAttribute('visibility','hidden'); $('cw-cloud-map').setAttribute('aria-busy',String(Boolean(f)));
  $('cw-cloud-message').hidden = false; $('cw-cloud-retry').hidden = true;
  text('cw-cloud-stamp',`EUMETSAT / ${f ? clock(f.productTimeUtc)+' UTC PRODUCT' : 'NO ELIGIBLE CLOUD FRAME'}`);
  text('cw-cloud-age',f ? `${age(state.second-secondAtUtc(f.productTimeUtc))} before cursor / saved RGB product` : `Expected ${clock(expected.productTimeUtc)} UTC product / unavailable`);
  text('cw-cloud-message-title',f ? 'Opening this cloud frame…' : 'A frame is missing.');
  text('cw-cloud-message-detail',f ? 'The previous picture is hidden while this file opens.' : 'No earlier image has been stretched across the gap.');
  if (!f) { $('cw-cloud-map').setAttribute('aria-busy','false'); $('cw-sky').dataset.ready='false'; return; }
  try {
    const url = new URL('raw/'+f.sourceFile,root); await loadImage(url);
    if (version !== cloudVersion) return;
    cloudImage.setAttribute('href',url);cloudImage.setAttribute('visibility','visible');$('cw-cloud-message').hidden=true;$('cw-sky').dataset.ready='true';
    const next = data.clouds[data.clouds.indexOf(f)+1]; if (next?.available) loadImage(new URL('raw/'+next.sourceFile,root)).catch(() => {});
  } catch {
    if (version !== cloudVersion) return;
    if(state.playing)stop('Playback paused: a saved cloud frame could not open. Retry or choose another time.');
    text('cw-cloud-message-title','This saved frame could not open.');text('cw-cloud-message-detail','Its source record remains available below.');$('cw-cloud-retry').hidden=false;$('cw-sky').dataset.ready='false';
  } finally { if (version === cloudVersion) $('cw-cloud-map').setAttribute('aria-busy','false'); }
}
async function renderRadar() {
  const version = ++radarVersion,f = radarAt(data,state.second); ++pixelVersion;selectedCell=null;
  $('cw-cell-marker').style.display='none';
  $('cw-radar-image').hidden=true;$('cw-radar-pick').hidden=true;$('cw-radar-empty').hidden=false;$('cw-radar-retry').hidden=true;$('cw-radar-stage').setAttribute('aria-busy',String(Boolean(f)));
  if (!f) {
    text('cw-radar-clock',`Saved ends ${clock(data.radar[0].scanEndUtc)}–${clock(data.radar.at(-1).scanEndUtc)} UTC / browse time outside an eligible scan.`);
    text('cw-radar-image-status','No saved scan at this cursor. This does not mean no rain.');$('cw-radar-stage').setAttribute('aria-busy','false');
    text('cw-cell-value','No eligible saved radar frame. Physical value unknown.');renderReceipt();return;
  }
  text('cw-radar-clock',`${clock(f.scanStartUtc)}–${clock(f.scanEndUtc)} UTC scan / finished ${age(state.second-secondAtUtc(f.scanEndUtc))} before cursor.`);
  text('cw-radar-image-status','Opening the saved native grid…');
  try {
    const url=new URL(f.image,root);await loadImage(url);if(version!==radarVersion)return;
    const img=$('cw-radar-image');img.src=url;img.alt=`Estonian radar-derived rain-rate composite, scan ${f.scanStartUtc} to ${f.scanEndUtc}. Native row/column grid, geographic placement unresolved.`;img.hidden=false;
    $('cw-radar-empty').hidden=true;$('cw-radar-pick').hidden=false;
    text('cw-radar-image-status',`${f.cellCounts.missing.toLocaleString('en-GB')} cells have no data. Below detection is a separate class. Palette capped at 10 mm/h; original floats retained.`);
    if ($('cw-cell-details').open) await inspectCell();
  } catch {
    if(version!==radarVersion)return;if(state.playing)stop('Playback paused: a saved radar image could not open. Retry or choose another time.');text('cw-radar-image-status','The saved radar image could not open. Its original and receipt remain available.');$('cw-radar-retry').hidden=false;
  } finally {if(version===radarVersion)$('cw-radar-stage').setAttribute('aria-busy','false');}
}
function drawRibbons() {
  const x = second => second/86400*1000;
  for (const kind of ['cloud','radar','buoy']) {
    const target=$(`cw-${kind}-ribbon`);target.setAttribute('preserveAspectRatio','none');target.replaceChildren(svg('line',{x1:0,x2:1000,y1:10,y2:10,class:'cw-ribbon-base'}));
    if(kind==='cloud') for(const f of data.clouds) target.append(svg('rect',{x:x(secondAtUtc(f.productTimeUtc)),y:5,width:Math.max(2,x(600)-1),height:10,class:f.available?'cw-ribbon-saved':'cw-ribbon-gap'}));
    if(kind==='radar') for(const f of data.radar) target.append(svg('rect',{x:x(secondAtUtc(f.scanStartUtc)),y:2,width:Math.max(2,x(240)),height:16,class:'cw-ribbon-strip'}));
    if(kind==='buoy') for(const p of data.buoys.find(b=>b.id===state.station).series.find(s=>s.parameter==='WaveHs').points) target.append(svg('rect',{x:x(secondAtUtc(p.observedAt)),y:5,width:x(3600)-2,height:10,class:p.value===null?'cw-ribbon-gap':'cw-ribbon-saved'}));
    target.append(svg('line',{x1:x(state.second),x2:x(state.second),y1:0,y2:20,class:'cw-ribbon-cursor'}));
  }
}
function compass(direction,spread) {
  const target=$('cw-compass'),d=waveDirectionFrom(direction,spread),point=(angle,r)=>[110+Math.sin(angle*Math.PI/180)*r,110-Math.cos(angle*Math.PI/180)*r];
  target.replaceChildren(svg('title',{id:'cw-compass-title'},d?`Waves from ${d.fromDegrees} degrees ${d.cardinal}; reported spread ${spread ?? 'missing'} degrees`:'Wave direction is missing'));
  for(const radius of [40,77])target.append(svg('circle',{cx:110,cy:110,r:radius,class:'cw-compass-circle'}));
  for(const [letter,a] of [['N',0],['E',90],['S',180],['W',270]]) {const [x,y]=point(a,96);target.append(svg('text',{x,y:y+4,class:'cw-compass-note'},letter));}
  if(d){
    if(spread!==null&&spread>0){const a=point(direction-spread,77),b=point(direction+spread,77);target.append(svg('path',{d:`M110 110L${a.join(' ')}A77 77 0 ${spread>90?1:0} 1 ${b.join(' ')}Z`,class:'cw-compass-sector'}));}
    const origin=point(direction,77),end=point(direction,15),left=point(direction+35,27),right=point(direction-35,27);
    target.append(svg('line',{x1:origin[0],y1:origin[1],x2:end[0],y2:end[1],class:'cw-compass-bearing'}),svg('path',{d:`M${left.join(' ')}L${end.join(' ')}L${right.join(' ')}`,fill:'none',class:'cw-compass-bearing'}),svg('circle',{cx:origin[0],cy:origin[1],r:4,class:'cw-compass-bearing'}));
  }else target.append(svg('text',{x:110,y:114,class:'cw-compass-note'},'MISSING'));
  target.append(svg('circle',{cx:110,cy:110,r:3,class:'cw-compass-origin'}));
}
function history(parameter,targetId,max) {
  const target=$(targetId),s=data.buoys.find(b=>b.id===state.station).series.find(s=>s.parameter===parameter),x=i=>8+i/24*584,y=v=>80-v/max*68;
  target.replaceChildren(svg('line',{x1:8,x2:592,y1:80,y2:80,class:'cw-wave-baseline'}));let path='';
  for(const [i,p]of s.points.entries()) {if(p.value===null){if(path)target.append(svg('path',{d:path,class:'cw-history-line'}));path='';continue;}path+=`${path?'L':'M'}${x(i)} ${y(p.value)} `;target.append(svg('circle',{cx:x(i),cy:y(p.value),r:Math.floor(state.second/3600)===i?4:2,class:Math.floor(state.second/3600)===i?'cw-history-selected':'cw-history-dot'}));}
  if(path)target.append(svg('path',{d:path,class:'cw-history-line'}));target.append(svg('line',{x1:x(state.second/3600),x2:x(state.second/3600),y1:5,y2:84,class:'cw-history-cursor'}));
}
function renderBuoy() {
  const {station:b,points:p}=buoyAt(data,state.station,state.second),height=p.WaveHs.value,period=p.WTP.value,d=waveDirectionFrom(p.ModalWDi.value,p.WHDD.value);
  $('cw-buoy').value=state.station;text('cw-buoy-clock',`${b.station} / ${clock(p.WaveHs.observedAt)} UTC sample / ${age(state.second-secondAtUtc(p.WaveHs.observedAt))} before cursor.`);
  text('cw-height',height===null?'Missing':`${number(height)} m`);text('cw-period',period===null?'Missing':`${number(period)} s`);
  text('cw-direction',d?`From ${d.fromDegrees}° / ${d.cardinal}`:'Direction missing');text('cw-spread',p.WHDD.value===null?'Spread missing':`Reported spread / ${number(p.WHDD.value)}°`);
  compass(p.ModalWDi.value,p.WHDD.value);
  const wave=$('cw-wave');wave.replaceChildren(svg('title',{id:'cw-wave-title'},'Schematic, not a recorded waveform'),svg('line',{x1:0,x2:600,y1:70,y2:70,class:'cw-wave-baseline'}));
  if(height!==null&&period!==null&&period>0){let path='';for(let x=0;x<=600;x+=2)path+=`${x?'L':'M'}${x} ${70-Math.sin(x/600*20/period*Math.PI*2)*height/2*48} `;wave.append(svg('path',{d:path,class:'cw-wave-line'}),svg('text',{x:0,y:133,class:'cw-wave-note'},'20 seconds / illustrative shape'));}
  else wave.append(svg('text',{x:10,y:75,class:'cw-wave-note'},'No waveform drawn from a missing sample.'));
  history('WaveHs','cw-height-history',2);history('WTP','cw-period-history',6);
  const numeric=b.series.find(s=>s.parameter==='WaveHs').points.filter(p=>p.value!==null).length;
  text('cw-buoy-gap',`${numeric} of 24 saved height samples are numeric. ${height===null?'This hour is missing; an earlier value has not been carried forward.':'The spaces between hourly samples are not measured wave histories.'}`);
  text('cw-buoy-table-caption',`${b.station} / original values, including missing samples`);
  const body=$('cw-buoy-rows');body.replaceChildren();
  for(let i=0;i<24;i++){const tr=el('tr');if(i===Math.floor(state.second/3600))tr.setAttribute('aria-current','true');tr.append(el('td',b.series[0].points[i].observedAt));for(const parameter of ['WaveHs','ModalWDi','WTP','WHDD','TWATER']){const point=b.series.find(s=>s.parameter===parameter).points[i];tr.append(el('td',point.value===null?'Missing / NaN':point.rawValue));}body.append(tr);}
  for(const ring of document.querySelectorAll('[data-cw-buoy-ring]'))ring.setAttribute('opacity',ring.dataset.cwBuoyRing===state.station?'1':'.2');
}
function renderReceipt() {
  inspection=inspectWeather(data,state.second,state.station);
  if(selectedCell?.frameId===inspection.radar.record?.id)inspection.radar.selectedCell=selectedCell;
  for(const button of document.querySelectorAll('[data-cw-source]'))button.setAttribute('aria-pressed',String(button.dataset.cwSource===state.source));
  const selected=inspection[state.source==='buoys'?'buoy':state.source],source=data.sources[state.source];
  const record=selected.record,receipt=selected.httpReceipt;
  let description,sourceTime;
  if(state.source==='clouds'){sourceTime=record?.productTimeUtc ?? null;description=record?`Cloud product / ${sourceTime} · per-pixel acquisition unknown`:`Cloud product unavailable at this cursor / expected ${selected.expectedProductTimeUtc}`;}
  else if(state.source==='radar'){sourceTime=record?`${record.scanStartUtc} – ${record.scanEndUtc}`:null;description=record?`Radar scan / ${sourceTime} · native grid`:'No eligible radar scan in the saved strip at this cursor.';}
  else{sourceTime=selected.points.WaveHs.observedAt;description=`${selected.station} / ${sourceTime} · hourly requested sample`;}
  text('cw-receipt-clock',description);text('cw-lineage',`${source.origin} → ${source.distribution} → saved original → this inspection`);text('cw-receipt-limit',source.limits);
  const dl=$('cw-clocks');dl.replaceChildren();
  for(const [label,value]of [['Browse UTC',inspection.browseTimeUtc],['Source clock',sourceTime??'No eligible record'],['Requested UTC',receipt?.requestedAt??(state.source==='buoys'?selected.sourceRecords[0].retrievedAt:'No eligible record')],['Downloaded UTC',receipt?.completedAt??'Unknown'],['Pixel acquisition',state.source==='clouds'?'Unknown / not the product clock':'Not assigned'],['Station receipt','Unknown'],['First publication','Unknown']])dl.append(el('dt',label),el('dd',value));
  const file=state.source==='buoys'?data.buoys.find(b=>b.id===state.station).series[0].sourceFile:record?.sourceFile;
  for(const id of ['cw-original','cw-http'])$(id).hidden=!file;
  if(file){const base=state.source==='buoys'?buoyRoot:new URL('raw/',root);$('cw-original').href=new URL(file,base);$('cw-http').href=new URL(file+'.receipt.json',base);}
  $('cw-definition').href=source.definitionUrl;text('cw-json',JSON.stringify({...inspection,selectedSource:state.source},null,2));
}
async function nativeCells(f) {
  if(cells.has(f.id))return cells.get(f.id);
  const pending=(async()=>{
    if(typeof DecompressionStream==='undefined')throw Error('Gzip inspection unavailable in this browser');
    const r=await fetch(new URL(f.pixels,root));if(!r.ok)throw Error('Native cells unavailable');
    const compressed=await r.arrayBuffer();if(compressed.byteLength>2_000_000)throw Error('Unexpected compressed cell size');
    const reader=new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip')).getReader();
    const output=new Uint8Array(f.pixelsUncompressedBytes);let length=0;
    try{while(true){const {done,value}=await reader.read();if(done)break;if(length+value.length>output.length)throw Error('Native cells exceed the expected bound');output.set(value,length);length+=value.length;}}finally{await reader.cancel().catch(()=>{});}
    if(length!==f.pixelsUncompressedBytes)throw Error('Unexpected native cell count');const buffer=output.buffer;
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',buffer))].map(n=>n.toString(16).padStart(2,'0')).join('');
    if(digest!==f.pixelsUncompressedSha256)throw Error('Native cell integrity mismatch');return new DataView(buffer);
  })();cells.set(f.id,pending);pending.catch(()=>cells.delete(f.id));if(cells.size>3)cells.delete(cells.keys().next().value);return pending;
}
async function inspectCell() {
  const version=++pixelVersion,f=radarAt(data,state.second),x=Number($('cw-cell-x').value),y=Number($('cw-cell-y').value);selectedCell=null;$('cw-cell-retry').hidden=true;$('cw-cell-marker').style.display='none';
  if(!Number.isInteger(x)||!Number.isInteger(y)||x<0||y<0||x>719||y>719||!$('cw-cell-x').value||!$('cw-cell-y').value){text('cw-cell-value','Choose an integer row and column from 0 to 719.');renderReceipt();return;}
  if(!f){text('cw-cell-value','No eligible saved radar frame. Physical value unknown.');renderReceipt();return;}
  text('cw-cell-value','Opening the original float32 cells…');
  try{
    const view=await nativeCells(f);if(version!==pixelVersion)return;
    const cell=radarCell(f,view.getFloat32((y*720+x)*4,true));selectedCell={frameId:f.id,x,y,...cell,scanStartUtc:f.scanStartUtc,scanEndUtc:f.scanEndUtc};
    const prefix=`Column ${x}, row ${y} / scan ends ${clock(f.scanEndUtc)} UTC. `;
    text('cw-cell-value',prefix+(cell.kind==='missing'?'Code 65535 / no data. Physical value unknown.':cell.kind==='below detection'?'Code 0 / below detection. No measured zero assigned.':`Stored float ${cell.rawValue} × ${f.gain} + ${f.offset} = ${number(cell.value)} mm/h. Display rounded; full float in export.`));
    $('cw-cell-marker').style.cssText=`display:block;left:${(x+.5)/720*100}%;top:${(y+.5)/720*100}%`;
  }catch{if(version!==pixelVersion)return;text('cw-cell-value','Native cells could not be read or verified. No physical value assigned.');$('cw-cell-retry').hidden=false;}
  renderReceipt();
}
function stop(message='Playback paused.') {
  state.playing=false;++playVersion;clearTimeout(timer);text('cw-play','Play the day ▶');$('cw-play').setAttribute('aria-pressed','false');
  for(const id of ['cw-cell-value','cw-cloud-message','cw-radar-image-status'])$(id).setAttribute('aria-live','polite');if(message)text('cw-play-status',message);
}
async function setSecond(second,{external=false,playing=false}={}) {
  if(!playing&&state.playing)stop();state.second=Math.max(0,Math.min(86399,Math.round(second)));
  const utc=utcAtSecond(state.second);$('cw-second').value=String(state.second);text('cw-local',clock(utc,'Europe/Helsinki',false));text('cw-local-seconds',`:${String(state.second%60).padStart(2,'0')} EET`);text('cw-utc',clock(utc)+' UTC');
  $('cw-second').setAttribute('aria-valuetext',`${clock(utc,'Europe/Helsinki')} Helsinki, ${utc}. Source times differ.`);
  $('cw-back').disabled=state.second===0;$('cw-next').disabled=state.second===86399;
  document.documentElement.dataset.coastalMinute=String(Math.floor(state.second/60));
  drawRibbons();renderBuoy();renderReceipt();
  if(!external){broadcasting=true;try{document.dispatchEvent(new CustomEvent('coastal-fmi-hour',{detail:{utc}}));}finally{broadcasting=false;}}
  await Promise.allSettled([renderCloud(),renderRadar()]);
}
async function play() {
  if(state.playing){stop();return;}if(state.second>=86399)await setSecond(0);
  state.playing=true;const version=++playVersion;text('cw-play','Pause the day Ⅱ');$('cw-play').setAttribute('aria-pressed','true');for(const id of ['cw-cell-value','cw-cloud-message','cw-radar-image-status'])$(id).setAttribute('aria-live','off');text('cw-play-status','Ten minutes per step. Saved frames; no interpolation.');
  const tick=async()=>{
    if(!state.playing||version!==playVersion)return;
    const next=Math.min(86399,state.second+600);await setSecond(next,{playing:true});
    if(!state.playing||version!==playVersion)return;
    if(next===86399){stop('End of the saved day.');return;}timer=setTimeout(tick,900);
  };timer=setTimeout(tick,900);
}
async function start() {
  const restoreFocus = document.activeElement === $('cw-retry');
  $('cw-retry').hidden=true;$('cw-loading').hidden=false;text('cw-loading','Opening the saved weather passage…');
  try{
    data=readWeather(await json(new URL('notebook.json',root)));const land=await json(new URL('./coastal-replay-land.json',import.meta.url)).catch(()=>null);buildMap(land);
    text('cw-availability',`${data.clouds.filter(f=>f.available).length} cloud frames / ${data.radar.length} radar composites / 3 buoys`);
    $('cw-workbench').hidden=false;$('cw-loading').hidden=true;
    $('cw-second').oninput=()=>{setSecond(Number($('cw-second').value));};
    $('cw-play').onclick=play;for(const [id,step]of [['cw-back',-600],['cw-next',600]])$(id).onclick=()=>setSecond(state.second+step);
    $('cw-radar-jump').onclick=()=>setSecond(secondAtUtc(data.radar[2].scanEndUtc)+5);
    $('cw-gap-jump').onclick=()=>{state.station='108495';const series=data.buoys.find(b=>b.id===state.station).series.find(s=>s.parameter==='WaveHs');const p=series.points.find(p=>p.value===null);if(p)setSecond(secondAtUtc(p.observedAt));};
    $('cw-buoy').onchange=()=>{state.station=$('cw-buoy').value;setSecond(state.second);};
    $('cw-cloud-retry').onclick=()=>renderCloud();$('cw-radar-retry').onclick=()=>renderRadar();$('cw-cell-retry').onclick=inspectCell;
    for(const id of ['cw-cell-x','cw-cell-y'])$(id).oninput=inspectCell;
    $('cw-cell-details').ontoggle=()=>{if($('cw-cell-details').open)inspectCell();};
    $('cw-radar-pick').onclick=e=>{const rect=$('cw-radar-pick').getBoundingClientRect();if(e.detail>0){$('cw-cell-x').value=String(Math.min(719,Math.floor((e.clientX-rect.x)/rect.width*720)));$('cw-cell-y').value=String(Math.min(719,Math.floor((e.clientY-rect.y)/rect.height*720)));}$('cw-cell-details').open=true;stop();inspectCell();$('cw-cell-x').focus();};
    for(const b of document.querySelectorAll('[data-cw-source]'))b.onclick=()=>{state.source=b.dataset.cwSource;stop();renderReceipt();};
    $('cw-export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...inspection,selectedSource:state.source},null,2)+'\n'],{type:'application/json'}));const a=el('a');a.href=url;a.download='coastal-watch-weather-2026-11-11.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    await setSecond(pendingExternalSecond ?? state.second);if(restoreFocus)$('cw-second').focus({preventScroll:true});
  }catch(error){$('cw-workbench').hidden=true;text('cw-loading','The weather passage could not open. The saved notebook and original source files remain available below.');$('cw-retry').hidden=false;if(restoreFocus)$('cw-retry').focus({preventScroll:true});console.error(error);}
}
document.addEventListener('coastal-archive-clock',e=>{if(!broadcasting&&!e.detail.initial){const s=secondAtUtc(e.detail.utc);if(Number.isInteger(s)&&s>=0&&s<=86399){pendingExternalSecond=s;if(data)setSecond(s,{external:true});}}});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop('Playback stopped while the page was away.');});
window.addEventListener('pagehide',()=>{if(data)stop();});window.addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(data)resizeMap();});});
$('cw-retry').onclick=start;start();
