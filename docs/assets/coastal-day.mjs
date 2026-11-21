import {readDay, at, aisAt, metarAt, clock, exact, elapsed} from './coastal-day-model.mjs';
const $ = id => document.getElementById(id), base = new URL('../data/coastal-days/2026-11-21/', import.meta.url);
const NS = 'http://www.w3.org/2000/svg';
function svg(tag, attrs, parent, text) {const el = document.createElementNS(NS, tag); for (const [k,v] of Object.entries(attrs)) el.setAttribute(k, v); if(text !== undefined) el.textContent = text; parent.append(el); return el;}
function el(tag, text, parent, cls) {const node = document.createElement(tag); if(text !== undefined) node.textContent = text; if(cls) node.className = cls; parent.append(node); return node;}
function link(parent, text, file) {const a = el('a', text, parent); a.href = new URL('raw/' + file, base).href; return a;}
const definitions = [
  ['101039:ws_10min', 'Wind', 'Loviisa Orrengrund', 'Ten-minute mean, preceding the time label.'],
  ['108495:WaveHs', 'Waves', 'Orrengrund buoy', 'Significant wave height. A period statistic, not the highest wave.'],
  ['134221:WaveHs', 'Waves further west', 'Gulf of Finland buoy', 'A separate station. Not a substitute for an Orrengrund gap.'],
  ['134254:WLEVN2K_PT1S_INSTANT', 'Sea level', 'Hamina Pitäjänsaari', 'Millimetres relative to N2000. Not mean-sea-level anomaly.']
];
const project = ([lon,lat]) => [(lon - 23) / 5.5 * 1100, (60.7 - lat) / 1.3 * 520];
let data, channel = definitions[1][0], second = 32503, station = 'EETN', mapLayers, cards;
function value(id) {return data.series.find(s => s.id === id);}
function stamp() {return new Date(Date.parse(data.startUtc) + second * 1000).toISOString();}
function map(land) {
  const root = $('cd-map');
  root.querySelectorAll(':scope > g, :scope > defs').forEach(node=>node.remove());
  const defs = svg('defs',{},root); const clip = svg('clipPath',{id:'cd-clip'},defs);svg('rect',{width:1100,height:520},clip);
  const group = svg('g',{'clip-path':'url(#cd-clip)'},root);
  for(let lon=23;lon<=28;lon++) svg('line',{x1:project([lon,59])[0],x2:project([lon,59])[0],y1:0,y2:520,class:'cd-grid'},group);
  for(const lat of [59,59.5,60,60.5,61]) svg('line',{x1:0,x2:1100,y1:project([23,lat])[1],y2:project([23,lat])[1],class:'cd-grid'},group);
  for(const polygon of land.polygons) svg('path',{d:polygon.map(r => r.map((p,i) => `${i?'L':'M'}${project(p).map(n=>n.toFixed(2)).join(',')}`).join(' ')+'Z').join(' '),class:'cd-land','fill-rule':'evenodd'},group);
  for(const [name,lon,lat] of [['HELSINKI',24.94,60.17],['TALLINN',24.75,59.44],['LOVIISA',26.23,60.46],['HAMINA',27.18,60.65],['GULF OF FINLAND',25.2,59.72]]) {
    const [x,y] = project([lon,lat]);svg('text',{x,y,class:'cd-place'},group,name);
  }
  for(const id of ['108495:WaveHs','134221:WaveHs','134254:WLEVN2K_PT1S_INSTANT']) {
    const s=value(id), [x,y]=project([s.longitude,s.latitude]);
    svg('circle',{cx:x,cy:y,r:4,class:'cd-station'},group);
    svg('text',{x:x+10,y:y-10,class:'cd-station-label'},group,s.stationId==='108495'?'Orrengrund buoy':s.stationId==='134221'?'Gulf buoy':'Hamina gauge');
  }
  const [wx,wy]=project([value('101039:ws_10min').longitude,value('101039:ws_10min').latitude]);
  svg('rect',{x:wx-3,y:wy-3,width:6,height:6,class:'cd-station'},group);
  svg('path',{d:`M${wx+5},${wy-5}L${wx+40},${wy-35}L${wx+185},${wy-35}`,class:'cd-wind-leader'},group);
  svg('text',{x:wx+45,y:wy-42,class:'cd-station-label'},group,'Orrengrund wind');
  const [x,y]=project(data.ais.response.features[0].geometry.coordinates);
  const ais=svg('g',{id:'cd-ais-mark'},group);
  svg('path',{d:`M${x-26},${y}h10M${x+16},${y}h10M${x},${y-26}v10M${x},${y+16}v10`,class:'cd-fix-leader'},ais);svg('circle',{cx:x,cy:y,r:7,class:'cd-fix'},ais);
  svg('path',{d:`M${x+9},${y+9}L${x+42},${y+39}L${x+220},${y+39}`,class:'cd-fix-leader'},ais);
  svg('text',{x:x+49,y:y+33,class:'cd-fix-label'},ais,'SPARTA II / ONE SAVED POSITION');
  const focus=svg('circle',{r:9,class:'cd-selected-station'},group);
  mapLayers={ais,focus};
  if (matchMedia('(max-width:600px)').matches) requestAnimationFrame(()=>{
    root.parentElement.scrollLeft=Math.max(0,x*root.clientWidth/1100-root.parentElement.clientWidth/2);
  });
}
function prepare() {
  for(const id of ['cd-channels','cd-ledger','cd-catalogues','cd-failures','cd-report-rows','cd-ais-fields'])$(id).replaceChildren();
  $('cd-captured').textContent = `${clock(data.capturedAtUtc, true)} EET / 21 November 2026`;
  $('cd-metars-count').textContent = `${data.reports.length} original messages`;
  cards=definitions.map(([id,label,name,note])=>{
    const button=el('button',undefined,$('cd-channels'),'cd-instrument');button.type='button';button.dataset.channel=id;
    el('span',label,button,'cd-kicker');el('span',name,button,'cd-card-station');
    const number=el('strong','',button,'cd-number'),state=el('span','',button,'cd-card-state');
    el('span',note,button,'cd-card-note');
    button.addEventListener('click',()=>{channel=id;render();});return{id,button,number,state};
  });
  const fields=$('cd-ais-fields'), dl=el('dl',undefined,fields), fix=data.ais.response.features[0], props=fix.properties, metadata=data.ais.metadata;
  for(const [key,raw] of [['Speed over ground',`${props.sog} kn`],['Course over ground',`${props.cog}°`],['Heading',`${props.heading}°`],['Navigational status / raw',String(props.navStat)],['Rate of turn / raw',String(props.rot)],['AIS seconds field / raw',String(props.timestamp)],['Source timestampExternal / UTC',data.ais.sourceTimeUtc],['Response dataUpdatedTime / UTC',data.ais.response.dataUpdatedTime],['Separate metadata clock / UTC',new Date(metadata.timestamp).toISOString()],['Separate metadata clock / EET',clock(metadata.timestamp,true)+' EET'],['Metadata destination / raw',metadata.destination]]) {el('dt',key,dl);el('dd',raw,dl);}
  const raw=el('details',undefined,fields);el('summary','Complete saved position and metadata fields',raw);el('pre',JSON.stringify({position:fix,metadata},null,2),raw);
  for(const [file,label] of [['loviisa-orrengrund-weather.xml','FMI / Orrengrund weather'],['orrengrund-waves.xml','FMI / Orrengrund buoy'],['orrengrund-native.xml','FMI / omitted-timestep control'],['orrengrund-hourly.xml','FMI / hourly control'],['gulf-waves.xml','FMI / Gulf buoy'],['hamina-sea-level.xml','FMI / Hamina gauge'],['sparta-location-gzip.json','Digitraffic / dated AIS query'],['sparta-latest-gzip.json','Digitraffic / latest-response control'],['sparta-vessel.json','Digitraffic / identity metadata'],['sparta-after-0800.json','Digitraffic / after 10:00 EET'],['metar.csv','IEM / airport messages'],['estonian-gauges.json','Estonian Environment Agency / gauges'],['danish-day-list.xml','Danish Maritime Authority / day listing'],...data.catalogues.map((c,i)=>[c.file,`Copernicus / Sentinel-${i+1} catalogue`])]) {
    const r=data.receipts[file], article=el('article',undefined,$('cd-ledger'));
    el('h3',label,article);el('p',`Saved ${clock(r.downloadCompletedAtUtc,true)} EET`,article);
    link(article,'Original response',file);link(article,'Retrieval receipt',file+'.receipt.json');
    const detail=el('details',undefined,article);el('summary','Source URL and SHA-256',detail);el('p',r.url,detail,'cd-source-url');el('code',r.sha256,detail);
  }
  for(const c of data.catalogues) {
    const details=el('details',undefined,$('cd-catalogues'));el('summary',`${c.file.startsWith('sentinel-1')?'Sentinel-1 SAR':'Sentinel-2 optical'} / ${c.count} catalogue records`,details);
    el('p','Footprints intersect the broad Gulf query rectangle. A listing is not a decoded image or a vessel detection. Product time is separate from catalogue publication and our retrieval.',details);
    const list=el('ul',undefined,details);
    for(const e of c.entries) {const li=el('li',undefined,list);el('code',e.id,li);el('p',`${e.time}${typeof e.cloudCoverPercent==='number'?` / whole-tile cloud cover ${exact(e.cloudCoverPercent)}%`:''}`,li);}
  }
  for(const r of data.availability.cloudRequestsFailed) {
    const li=el('li',undefined,$('cd-failures'));el('span',`${new URL(r.url).searchParams.get('time')} / ${r.error}`,li);link(li,'Failed request receipt',r.file+'.receipt.json');
  }
  for(const r of data.reports) {const tr=el('tr',undefined,$('cd-report-rows'));el('td',r.station,tr);el('td',r.time,tr);el('td',r.metar,tr);}
  $('cd-time').oninput=e=>{second=Number(e.target.value);render();};
  $('cd-time').onkeydown=e=>{
    const direction=['ArrowRight','ArrowUp'].includes(e.key)?1:['ArrowLeft','ArrowDown'].includes(e.key)?-1:0;
    if(direction){e.preventDefault();second=Math.max(0,Math.min(86399,second+direction*(e.shiftKey?1:600)));render();}
  };
  document.querySelectorAll('[data-second]').forEach(b=>b.onclick=()=>{second=Number(b.dataset.second);render();announce(`${clock(stamp(),true)} EET. ${$('cd-ais-age').textContent}.`);});
  $('cd-gap').onclick=()=>{channel='108495:WaveHs';second=34200;render();announce('09:30 EET. Orrengrund buoy: source NaN. The other buoy remains a separate station.');};
  $('cd-airport').onchange=e=>{station=e.target.value;render();};
}
function announce(text) {$('cd-announcement').textContent='';requestAnimationFrame(()=>{$('cd-announcement').textContent=text;});}
function plot(s) {
  const root=$('cd-plot');root.replaceChildren();
  svg('title',{},root,`${s.station}: ${s.parameter}, original samples and gaps`);
  const vals=s.points.filter(p=>p.value!==null).map(p=>p.value), min=Math.min(0,...vals),max=Math.max(...vals,1),range=max-min||1;
  const x=t=>50+(Date.parse(t)-Date.parse(data.startUtc))/86400000*1000, y=v=>170-(v-min)/range*130;
  const defs=svg('defs',{},root),pat=svg('pattern',{id:'cd-hatch',width:7,height:7,patternUnits:'userSpaceOnUse'},defs);
  svg('path',{d:'M-1,1L1,-1M0,7L7,0M6,8L8,6',class:'cd-gap-stroke'},pat);
  const cut=50+19/24*1000;
  svg('rect',{x:cut,y:25,width:1050-cut,height:150,class:'cd-uncollected'},root);
  for(const n of [0,.5,1]) {const yy=170-n*130;svg('line',{x1:50,x2:1050,y1:yy,y2:yy,class:'cd-grid'},root);svg('text',{x:40,y:yy+4,'text-anchor':'end',class:'cd-axis'},root,exact(min+n*range));}
  const current=at(data,s,second);
  for(const p of s.points) {
    const xx=x(p.time), active=current.point?.time===p.time;
    const marker=svg('g',{class:Date.parse(p.time)>Date.parse(stamp())?'cd-after-cursor':''},root);
    if(p.value===null) svg('rect',{x:xx-5,y:155,width:10,height:15,fill:'url(#cd-hatch)',class:active?'cd-active-gap':''},marker);
    else {svg('line',{x1:xx,x2:xx,y1:170,y2:y(p.value),class:active?'cd-measure cd-measure-active':'cd-measure'},marker);svg('circle',{cx:xx,cy:y(p.value),r:active?5:2.5,class:active?'cd-dot-active':'cd-dot'},marker);}
  }
  svg('line',{x1:cut,x2:cut,y1:20,y2:180,class:'cd-cutoff'},root);
  for(const hour of [0,6,12,18,24]) svg('text',{x:50+hour/24*1000,y:205,'text-anchor':'middle',class:'cd-axis'},root,`${String(hour).padStart(2,'0')}${hour===24?' EET':''}`);
  const cursor=50+second/86400*1000;svg('line',{x1:cursor,x2:cursor,y1:20,y2:180,class:'cd-cursor'},root);
  const numbers=s.points.filter(p=>p.value!==null).length;
  $('cd-plot-title').textContent=`${definitions.find(d=>d[0]===s.id)[1]} / ${s.station} / ${s.unit}`;
  $('cd-plot-count').textContent=`${numbers} numeric / ${s.points.length-numbers} source NaN / ${s.intervalMinutes}-minute requested labels`;
}
function receipt(s) {
  const state=at(data,s,second), p=state.point, r=data.receipts[s.file], box=$('cd-receipt');box.replaceChildren();
  el('p','THE SELECTED RECORD',box,'cd-kicker');el('h3',s.station,box);
  const dl=el('dl',undefined,box);
  for(const [key,val] of [['Parameter',`${s.parameter} / ${s.unit}`],['Original label / UTC',p?.time??'Outside saved query'],['Original value',p?.raw??'Not requested'],['FMI response timestamp',s.responseTimeUtc],['FMI result-time label',s.resultTimeLabelsUtc.join(', ')||'Not supplied'],['Request sent / UTC',r.requestedAtUtc],['Download completed / UTC',r.downloadCompletedAtUtc],['First publication / original receiver','Unknown']]){el('dt',key,dl);el('dd',val,dl);}
  if(p) {
    const siblings=data.series.filter(other=>other.stationId===s.stationId&&other.id!==s.id);
    for(const other of siblings) {const original=other.points.find(point=>point.time===p.time);el('dt',other.parameter,dl);el('dd',`${original.raw} ${other.unit}`,dl);}
  }
  link(box,'Open the original XML',s.file);link(box,'Inspect the retrieval receipt',s.file+'.receipt.json');
  el('p','The request, response and result-time labels do not establish when the station published this measurement. A raw NaN remains missing; a later numeric sample does not fill it.',box,'cd-fine');
  if(s.parameter==='WaveHs')el('p','Buoy labels mark the start of a 1600- or 1800-second measurement series. ModalWDi is the direction waves come from; WTP is the modal period. WHDD is directional spread, not a confidence interval.',box,'cd-fine');
}
function render() {
  $('cd-time').value=second;$('cd-time-label').textContent=`${clock(stamp(),true)} EET`;$('cd-utc').textContent=stamp();
  $('cd-time').setAttribute('aria-valuetext',`${clock(stamp(),true)} EET on 21 November 2026${second>68400?', outside saved query':''}`);
  for(const card of cards) {
    const s=value(card.id),state=at(data,s,second);card.button.setAttribute('aria-pressed',String(card.id===channel));
    card.number.textContent=state.kind==='reading'?`${state.point.raw} ${s.unit}`:state.kind==='missing'?'Source NaN':'Not collected';
    card.state.textContent=state.point?`${clock(state.point.time)} EET label / ${state.kind==='missing'?'cause or delay unknown':elapsed(state.ageSeconds)+' before browse time'}`:'After 19:00 EET query cutoff';
  }
  const a=aisAt(data,second);mapLayers.ais.setAttribute('visibility',a.kind==='saved'?'visible':'hidden');
  $('cd-ais-age').textContent=a.kind==='saved'?`${elapsed(a.ageSeconds)} after source time`:a.kind==='before'?'Before the saved source time':'Outside the saved query window';
  $('cd-ais-state').textContent=a.kind==='saved'?'One returned position. No later saved fix. The marker stays at its reported coordinates.':a.kind==='before'?'The map has no AIS position at or before this browse time. Saved report details remain available here for inspection.':'No position is projected into the uncollected evening.';
  const s=value(channel),[x,y]=project([s.longitude,s.latitude]);mapLayers.focus.setAttribute('cx',x);mapLayers.focus.setAttribute('cy',y);
  plot(s);receipt(s);
  const report=metarAt(data,station,second);
  $('cd-metar').textContent=report?.metar??'No saved message at or before this browse time.';
  $('cd-metar-time').textContent=report?`${report.time} / ${elapsed((Date.parse(stamp())-Date.parse(report.time))/1000)} before browse time`:'Outside message coverage at this time';
}
async function boot() {
  $('cd-retry').hidden=true;
  let phase='download';
  try {
    const get=async url=>{const response=await fetch(url);if(!response.ok)throw Error('Saved file unavailable');return response.json();};
    const [notebook,land]=await Promise.allSettled([get(new URL('notebook.json',base)),get(new URL('./coastal-replay-land.json',import.meta.url))]);
    if(notebook.status==='rejected')throw notebook.reason;
    phase='validation';data=readDay(notebook.value);
    const coastOk=land.status==='fulfilled'&&Array.isArray(land.value?.polygons);
    phase='view';map(coastOk?land.value:{polygons:[]});prepare();render();
    $('cd-map-warning').hidden=coastOk;$('cd-loading').hidden=true;$('cd-workbench').hidden=false;
  } catch(error) {
    $('cd-loading').textContent=phase==='validation'?'The saved notebook failed record validation. Open the original sources below or try again.':phase==='view'?'The interactive view could not be prepared. Open the original sources below or try again.':'The saved notebook could not be downloaded. Open the original sources below or try again.';
    $('cd-loading').hidden=false;$('cd-workbench').hidden=true;$('cd-fallback').open=true;$('cd-retry').hidden=false;
  }
}
$('cd-retry').addEventListener('click',boot);boot();
