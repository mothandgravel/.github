import {readSources,sampleAt,segments,localHour,exact,sampledRange} from './coastal-sources-model.mjs';
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
const root=new URL('../data/coastal-sources/2026-11-11/',import.meta.url);
const svg=(tag,attrs={},text)=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;};
const text=(id,value)=>{$(id).textContent=value;};
const definitions={ws_10min:'Mean wind speed during the preceding 10 minutes. One requested sample per hour.',wg_10min:'Highest 3-second mean wind speed during the preceding 10 minutes. One requested sample per hour.',vis:'Horizontal visibility at the station, in metres. One requested sample per hour.',WaveHs:'Significant wave height at the buoy. This is a statistic, not the height or shape of an individual wave.',WATLEV:'Water level relative to theoretical mean water. Its zero differs from N2000.',WLEVN2K_PT1S_INSTANT:'Water level relative to N2000. This is a reference level, not water depth.'};
const labels=['Harmaja / wind','Harmaja / gust','Harmaja / visibility','Gulf buoy / wave height','Loviisa buoy / wave height','Helsinki / water level · N2000','Helsinki / water level · mean water'];
const stationLabels={'Helsinki Harmaja':'Harmaja / wind & visibility','Suomenlahti aaltopoiju':'Gulf buoy / waves','Loviisa Orrengrund aaltopoiju':'Loviisa buoy / waves','Helsinki Kaivopuisto':'Kaivopuisto / water level'};
async function json(url){const r=await fetch(url);if(!r.ok)throw Error(`Source download returned HTTP ${r.status}`);return r.json();}
let data,manifest,hour=0,channel=0;
function drawTrace(target,s,width,height,full=false){
  const range=sampledRange(s);target.replaceChildren();
  if(full){target.append(svg('title',{id:'cs-plot-title'},s.station+' / '+s.label),svg('desc',{id:'cs-plot-desc'},`${range?.numeric??0} numeric samples, ${range?.missing??24} missing. Exact values and original timestamps are in the sample table.`));}
  if(!range){target.append(svg('text',{x:20,y:40,class:'cs-axis'},'No numeric readings returned'));return;}
  const left=full?52:4,right=full?22:4,top=full?22:5,bottom=full?38:5;
  let min=range.min,max=range.max;if(min===max){min-=.5;max+=.5;}const padding=(max-min)*.12;min-=padding;max+=padding;
  const first=Date.parse(data.windowStartUtc),at=p=>(Date.parse(p.observedAt)-first)/3600000;
  const x=i=>left+i/23*(width-left-right),y=v=>top+(max-v)/(max-min)*(height-top-bottom);
  target.setAttribute('viewBox',`0 0 ${width} ${height}`);
  if(full){
    const defs=svg('defs'),pattern=svg('pattern',{id:'cs-gap-pattern',width:7,height:7,patternUnits:'userSpaceOnUse'});pattern.append(svg('path',{d:'M-1 1L1 -1M0 7L7 0M6 8L8 6',stroke:'currentColor','stroke-width':1}));defs.append(pattern);target.append(defs);
    for(let i=0;i<4;i++){const v=min+(max-min)*i/3,Y=y(v);target.append(svg('line',{x1:left,x2:width-right,y1:Y,y2:Y,class:'cs-grid'}),svg('text',{x:left-9,y:Y+4,'text-anchor':'end',class:'cs-axis'},new Intl.NumberFormat('en-GB',{maximumFractionDigits:s.unit==='mm'?0:2}).format(v)));}
    for(const i of [0,6,12,18,23])target.append(svg('text',{x:x(i),y:height-11,'text-anchor':'middle',class:'cs-axis'},String(i).padStart(2,'0')));
    for(const p of s.points)if(p.value===null){const X=x(at(p)),band=Math.min(14,(width-left-right)/23*.75);target.append(svg('rect',{x:X-band/2,y:top,width:band,height:height-top-bottom,class:'cs-gap'}),svg('path',{d:`M${X-3} ${height-bottom-6}l6 6m-6 0l6 -6`,class:'cs-missing-mark'}));}
  }
  for(const run of segments(s.points))if(run.length>1)target.append(svg('path',{d:run.map((p,i)=>`${i?'L':'M'}${x(at(p))} ${y(p.value)}`).join(' '),class:'cs-trace'}));
  for(const p of s.points)if(p.value!==null)target.append(svg('circle',{cx:x(at(p)),cy:y(p.value),r:full?2.6:1.5,class:'cs-point'}));
  const chosen=sampleAt(s,data.series[0].points[hour].observedAt);
  target.append(svg('line',{x1:x(hour),x2:x(hour),y1:top,y2:height-bottom,class:'cs-cursor'}));
  if(chosen?.value!==null&&chosen)target.append(svg('circle',{cx:x(hour),cy:y(chosen.value),r:full?5:3,class:'cs-current'}));
  if(full&&chosen?.value===null)target.append(svg('text',{x:hour<12?x(hour)+9:x(hour)-9,y:top+13,'text-anchor':hour<12?'start':'end',class:'cs-axis'},'Missing sample'));
}
function drawMap(land){
  const map=$('cs-map'),layer=svg('g'),x=lon=>(lon-23.9)/(26.75-23.9)*620;
  const merc=lat=>Math.log(Math.tan(Math.PI/4+lat*Math.PI/360));
  const y=lat=>(merc(60.5)-merc(lat))/(merc(60.5)-merc(59.65))*360;
  const clip=svg('clipPath',{id:'cs-map-clip'});clip.append(svg('rect',{width:620,height:360}));const defs=svg('defs');defs.append(clip);layer.setAttribute('clip-path','url(#cs-map-clip)');map.append(defs,layer);
  for(const lon of [24,25,26])layer.append(svg('line',{x1:x(lon),x2:x(lon),y1:0,y2:360,class:'cs-map-grid'}));
  for(const lat of [59.75,60,60.25,60.5])layer.append(svg('line',{x1:0,x2:620,y1:y(lat),y2:y(lat),class:'cs-map-grid'}));
  if(land)for(const polygon of land.polygons)layer.append(svg('path',{d:polygon.map(ring=>ring.map(([lon,lat],i)=>`${i?'L':'M'}${x(lon).toFixed(2)} ${y(lat).toFixed(2)}`).join(' ')+'Z').join(' '),class:'cs-map-land'}));
  map.append(svg('text',{x:22,y:338,class:'cs-map-text'},'25° E / WGS84'),svg('text',{x:x(24.94)-8,y:y(60.17)-18,class:'cs-map-text city'},'HELSINKI'),svg('text',{x:x(26.23),y:y(60.4),class:'cs-map-text city'},'LOVIISA'),svg('text',{x:365,y:288,class:'cs-map-text'},'GULF OF FINLAND'));
  const stations=data.series.map((s,index)=>({s,index})).filter(({s,index})=>data.series.findIndex(other=>other.stationId===s.stationId)===index);
  for(const {s,index} of stations){
    const X=x(s.longitude),Y=y(s.latitude);layer.append(svg('circle',{cx:X,cy:Y,r:11,class:'cs-map-ring','data-station':s.stationId}),svg('circle',{cx:X,cy:Y,r:5,class:'cs-map-point','data-station':s.stationId}));
    const b=document.createElement('button');b.type='button';b.textContent=stationLabels[s.station];b.dataset.station=s.stationId;b.addEventListener('click',()=>{channel=index;render(true);});$('cs-stations').append(b);
  }
}
function readings(){
  for(const [index,name]of [[0,'wind'],[3,'wave'],[5,'water']]){
    const s=data.series[index],p=s.points[hour],target=$('cs-'+name);target.replaceChildren(document.createTextNode(exact(p.value)));
    if(p.value!==null){const unit=document.createElement('span');unit.textContent=s.unit;target.append(unit);}
    drawTrace($('cs-'+name+'-trace'),s,240,48);
  }
}
function render(announce=false){
  const s=data.series[channel],utc=data.series[0].points[hour].observedAt,p=sampleAt(s,utc),range=sampledRange(s);
  $('cs-channel').value=s.id;$('cs-hour').value=hour;
  text('cs-count',`${range?.numeric??0}/24`);text('cs-measure-definition',definitions[s.parameter]);
  text('cs-hour-label',localHour(utc)+' EET');$('cs-hour').setAttribute('aria-valuetext',`${localHour(utc)} Helsinki; ${s.station}; ${exact(p.value)} ${p.value===null?'':s.unit}`);
  const plot=$('cs-plot'),width=Math.max(240,Math.round(plot.getBoundingClientRect().width));drawTrace(plot,s,width,width<500?245:280,true);readings();
  text('cs-station-name',s.station);text('cs-value',exact(p.value));text('cs-unit',p.value===null?'No numeric reading':s.unit);text('cs-datum',s.parameter==='WATLEV'?'THEORETICAL MEAN WATER':s.parameter==='WLEVN2K_PT1S_INSTANT'?'N2000 DATUM':s.label);
  text('cs-observed',p.observedAt);text('cs-local',`11 Nov · ${localHour(utc)} +02:00`);text('cs-retrieved',s.retrievedAt);text('cs-raw-value',p.rawValue);
  const receipt=manifest.receipts[s.sourceFile];text('cs-receipt-json',JSON.stringify({station:s.station,parameter:s.parameter,unit:s.unit,observedAt:p.observedAt,originalValue:p.rawValue,originalReceiverTime:null,firstPublication:null,retrievedAt:s.retrievedAt,fmiResultTime:s.resultTime,responseTime:s.responseTime,sourceSha256:s.sourceSha256,requestUrl:receipt.url,httpStatus:receipt.status,serverDate:receipt.serverDate,lastModified:receipt.lastModified},null,2));
  $('cs-raw-link').href=new URL('raw/'+s.sourceFile,root);$('cs-http-link').href=new URL('raw/'+s.sourceFile+'.receipt.json',root);$('cs-parameter-link').href=new URL('raw/parameter-'+s.parameter+'.xml',root);
  $('cs-samples').replaceChildren();for(const point of s.points){const tr=document.createElement('tr');if(point===p)tr.setAttribute('aria-current','true');for(const value of [localHour(point.observedAt),point.observedAt,exact(point.value)+(point.value===null?'':' '+s.unit),point.rawValue]){const td=document.createElement('td');td.textContent=value;tr.append(td);}$('cs-samples').append(tr);}
  text('cs-table-caption',s.station+' / '+s.label+' / '+s.unit);
  for(const b of document.querySelectorAll('[data-hour]'))b.setAttribute('aria-pressed',String(Number(b.dataset.hour)===hour));
  for(const b of document.querySelectorAll('[data-channel]'))b.setAttribute('aria-pressed',String(Number(b.dataset.channel)===channel));
  for(const b of $('cs-stations').children)b.setAttribute('aria-pressed',String(b.dataset.station===s.stationId));
  for(const marker of $('cs-map').querySelectorAll('[data-station]')){marker.dataset.selected=String(marker.dataset.station===s.stationId);if(marker.classList.contains('cs-map-ring'))marker.setAttribute('visibility',marker.dataset.selected==='true'?'visible':'hidden');}
  if(announce)text('cs-announcement',`${s.station}, ${s.label}, ${localHour(utc)} Helsinki. ${exact(p.value)}${p.value===null?'':` ${s.unit}`}.`);
}
function sourceLedger(){
  for(const c of manifest.catalogues){
    const wrap=document.createElement('div');wrap.className='cs-table-wrap';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label',c.file.startsWith('sentinel-1')?'Sentinel-1 catalogue clocks':'Sentinel-2 catalogue clocks');const table=document.createElement('table');table.className='cs-catalogue-table';const cap=document.createElement('caption');cap.textContent=c.file+' / metadata only';table.append(cap);const thead=document.createElement('thead'),head=document.createElement('tr');for(const value of ['Product','Acquired / UTC','Created / UTC','Published / UTC']){const th=document.createElement('th');th.scope='col';th.textContent=value;head.append(th);}thead.append(head);table.append(thead);const body=document.createElement('tbody');
    for(const item of c.productsMetadata){const tr=document.createElement('tr');for(const value of [item.id,item.start_datetime||item.datetime,item.created||'Unknown',item.published||'Unknown']){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);}table.append(body);wrap.append(table);$('cs-catalogues').append(wrap);
  }
  const d=manifest.receipts['danish-november-archive-list.xml'],s=manifest.receipts['seismo-calendar.html'];text('cs-archive-status',JSON.stringify({danishArchive:{latestListedDay:manifest.danishArchive.latestListedDate,studyDateListed:manifest.danishArchive.studyDateListed,retrievedAt:d.retrievedAt,requestUrl:d.url,sourceSha256:d.sha256,interpretation:manifest.danishArchive.queryMeaning},seismicCalendar:{latestLinkedDay:manifest.seismology.latestLinkedDate,studyDateLinked:false,retrievedAt:s.retrievedAt,lastModified:s.lastModified,requestUrl:s.url,sourceSha256:s.sha256},publicationSchedule:'No guaranteed release time established. These are saved availability checks, not continuous monitoring.'},null,2));
}
async function start(){
  try{
    const values=await Promise.all([json(new URL('selected.json',root)),json(new URL('manifest.json',root))]);data=readSources(values[0]);manifest=values[1];
    for(const [i,s]of data.series.entries()){const o=document.createElement('option');o.value=s.id;o.textContent=labels[i]+' ['+s.unit+']';$('cs-channel').append(o);}
    const land=await json(new URL('./coastal-replay-land.json',import.meta.url)).catch(()=>null);drawMap(land);sourceLedger();
    $('cs-workbench').hidden=false;$('cs-loading').hidden=true;
    $('cs-channel').addEventListener('change',()=>{channel=data.series.findIndex(s=>s.id===$('cs-channel').value);render(true);});
    $('cs-hour').addEventListener('input',()=>{hour=Number($('cs-hour').value);render(true);});
    for(const b of document.querySelectorAll('[data-hour]'))b.addEventListener('click',()=>{hour=Number(b.dataset.hour);render(true);});
    for(const b of document.querySelectorAll('[data-channel]'))b.addEventListener('click',()=>{channel=Number(b.dataset.channel);render(true);});
    $('cs-try-gap').addEventListener('click',()=>{channel=4;hour=data.series[4].points.findIndex(p=>p.value===null);render(true);});
    $('cs-try-datum').addEventListener('click',()=>{channel=channel===6?5:6;render(true);});
    window.addEventListener('resize',()=>render());render();
  }catch(error){text('cs-loading','The saved records could not be opened. The source downloads below remain available.');console.error(error);}
}
start();
