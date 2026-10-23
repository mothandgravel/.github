import {COMPONENTS,METHODS,clockUs,sourceClock,prepareDataset,hourAccount,comparison,precedingWeather,capacityRehearsal,exportInspection} from './datacenter-model.mjs';
const $=id=>document.getElementById(id),put=(id,t)=>{$(id).textContent=t;},fmt=(n,d=3)=>Number.isFinite(n)?n.toLocaleString('en-GB',{minimumFractionDigits:d,maximumFractionDigits:d}):'Unavailable';
let data=null,index=0,selected='it_power_kw',room=null,roomPromise=null,loadPromise=null,playing=null,hours=[],a='2025-07-14T23',b='2025-07-18T09',rehearsal=null,extractSHA='';
const descriptions={it_power_kw:'Power used by computing equipment on the data-centre floor. This facility-level channel does not identify individual racks, GPUs, jobs or useful work.',cooling_kw:'Fans and pipe trace heaters associated with outdoor heat-rejection equipment. The publisher includes an attributed constant tower-filter pump load here. It is not added again by this study.',pump_kw:'Pumps circulating the energy-recovery and tower-water loops, including boost pumps through the fan walls. The dedicated filter-pump allowance belongs to the cooling channel.',hvac_kw:'Fan walls, electrical-room fan coils and the make-up air unit. These are the published building-service boundaries, not a computed cooling penalty applied to IT power.',plug_and_light_kw:'Dedicated lights and utility plugs, including an attributed share of the emergency generator crank-case heater. The scene’s lighting is authored and is not reconstructed from this channel.'};
const announce=t=>put('dc-announcement',t);
function pause(){if(playing)clearInterval(playing);playing=null;put('dc-play','Play records');$('dc-play').setAttribute('aria-pressed','false');}
function hoursList(){const out=[];for(let us=data.start;us<data.end;us+=3600e6)out.push(sourceClock(us).slice(0,13).replace(' ','T'));return out;}
async function openRoom(){
  if(room)return room;if(roomPromise)return roomPromise;
  $('dc-start-room').disabled=true;put('dc-start-room','Building room…');
  roomPromise=(async()=>{
    try{const {createRoom}=await import('./datacenter-room.mjs');room=await createRoom($('dc-room'),{onSelect:select,onStatus:t=>{put('dc-load-status',t);if(room){const info=room.getInfo();$('dc-refine').disabled=info.softwareRenderer||info.refining;put('dc-refine',info.refining?'Refining light…':'Refine light ↗');}}});
      $('dc-poster').hidden=true;$('dc-room-standby').hidden=true;document.querySelectorAll('[data-camera]').forEach(x=>x.disabled=false);$('dc-approach').disabled=false;$('dc-refine').disabled=room.getInfo().softwareRenderer;put('dc-start-room','3D room open');room.setSelection(selected);return room;
    }catch(e){put('dc-load-status','The 3D renderer is unavailable here. The recorded account, calculations, comparison and export are ready to inspect.');put('dc-start-room','Retry 3D room');$('dc-start-room').disabled=false;roomPromise=null;return null;}
  })();return roomPromise;
}
async function load(withRoom){
  if(data){if(withRoom)await openRoom();return;}
  if(loadPromise){await loadPromise;if(withRoom)await openRoom();return;}
  $('dc-load-room').disabled=$('dc-load-data').disabled=true;put('dc-load-status','Opening the pinned extract. Checking its hash and source-clock order…');
  loadPromise=(async()=>{
    try{
      const [response,manifestResponse]=await Promise.all([fetch(new URL('./data-center/esif-week.json',import.meta.url)),fetch(new URL('../design/datacenter-provenance.json',import.meta.url))]);
      if(!response.ok||!manifestResponse.ok)throw Error('Source record unavailable');
      const text=await response.text(),manifest=await manifestResponse.json();
      extractSHA=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text.replaceAll('\r\n','\n'))))].map(b=>b.toString(16).padStart(2,'0')).join('');
      if(extractSHA!==manifest.sha256)throw Error('Extract hash differs from its source record');
      data=prepareDataset(JSON.parse(text));
      const labels=hoursList();hours=labels.map(hour=>hourAccount(data,hour));
      for(const id of ['dc-hour-a','dc-hour-b'])$(id).replaceChildren(...labels.map(h=>new Option(h.replace('T',' ')+':00',h)));
      $('dc-hour-a').value=a;$('dc-hour-b').value=b;$('dc-scrub').max=data.window.length-1;
      $('dc-meters').innerHTML=COMPONENTS.map(c=>`<button type="button" data-meter="${c.id}" style="--meter-color:${c.color}" aria-pressed="${c.id===selected}">${c.short}<strong id="dc-meter-${c.id}">—</strong><small>kW / facility channel</small></button>`).join('');
      $('dc-meters').querySelectorAll('button').forEach(x=>x.addEventListener('click',()=>select(x.dataset.meter)));
      for(const id of ['dc-hour-a','dc-hour-b','dc-swap','dc-example','dc-export','dc-run-rehearsal','dc-start-room'])$(id).disabled=false;
      $('dc-open').hidden=true;$('dc-workspace').hidden=false;
      renderComparison();renderHistory();renderQuality();moveToHour(a);put('dc-load-status',`Verified extract / ${data.window.length.toLocaleString('en-GB')} window observations · source clock · geometry authored.`);
      announce('The recorded week is open. Select a power category, compare the two hours, or open the method.');
    }catch(e){data=null;loadPromise=null;$('dc-load-room').disabled=$('dc-load-data').disabled=false;put('dc-load-status',`The measured account could not open: ${e.message}. Retry from the buttons above.`);}
  })();await loadPromise;if(data&&withRoom)await openRoom();
}
function select(id){if(!data||!COMPONENTS.some(c=>c.id===id))return;selected=id;renderRecord();room?.setSelection(id);announce(`${COMPONENTS.find(c=>c.id===id).name}. ${descriptions[id]}`);}
function move(i,speak=false){if(!data)return;index=Math.max(0,Math.min(data.window.length-1,i));$('dc-scrub').value=index;renderRecord();if(speak)announce(`Observation ${sourceClock(data.window[index].us,true)}, source clock. Facility component sum ${fmt(data.window[index].totalKW/1000)} MW.`);}
function moveToHour(hour){const start=clockUs(`${hour}:00:00`),i=data.window.findIndex(r=>r.us>=start);move(i<0?data.window.length-1:i);}
function renderRecord(){
  const r=data.window[index],weather=precedingWeather(data,r.us),component=COMPONENTS.find(c=>c.id===selected);
  put('dc-total',fmt(r.validPower?r.totalKW/1000:null));put('dc-pue',fmt(r.pue));put('dc-observed',sourceClock(r.us,true));put('dc-clock',r.sourceClock.replace('T',' '));put('dc-room-clock',sourceClock(r.us,true)+' / SOURCE CLOCK');put('dc-source-row',String(r.sourceRow)+' / zero-based');
  put('dc-weather',weather?`${fmt(weather.tempC,1)}°C · ${fmt(weather.humidity,0)}% RH`:'No eligible earlier reading');put('dc-weather-age',weather?`${fmt(weather.ageSeconds,3)} s / alignment unverified`:'Unavailable');
  $('dc-prev').disabled=index===0;$('dc-next').disabled=index===data.window.length-1;
  for(const c of COMPONENTS){put(`dc-meter-${c.id}`,fmt(r[c.id],2));$('dc-meters').querySelector(`[data-meter="${c.id}"]`).setAttribute('aria-pressed',String(c.id===selected));}
  put('dc-meter-title',component.name);put('dc-meter-copy',descriptions[selected]);put('dc-meter-value',`${fmt(r[selected],6)} kW · ${fmt(r[selected]/r.totalKW*100,3)}% of the component sum. The geometry is an illustrative location for this whole-facility category.`);
  $('dc-record-summary').innerHTML=[['Source clock',r.sourceClock],['Source row / zero-based',r.sourceRow],['Component sum',fmt(r.totalKW,6)+' kW'],['Published sample PUE',fmt(r.pue,9)],['Power status',r.validPower?'Five nonnegative finite channels':'Requires source review'],['Timezone','Not supplied'],['Earlier weather / source clock',weather?.sourceClock??'Unavailable'],['Raw weather / publisher units',weather?`${fmt(weather.tempF,6)} °F · ${fmt(weather.humidity,6)}% RH`:'Unavailable']].map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join('');
  $('dc-raw-components').innerHTML=COMPONENTS.map(c=>`<tr><td>${c.short}<br><small>${c.id}</small></td><td>${fmt(r[c.id],6)}</td><td>${fmt(r[c.id]/r.totalKW*100,2)}%</td></tr>`).join('');
  put('dc-closure',`Sample check: PUE × IT − five-component sum = ${r.closureKW?.toExponential(3)??'unavailable'} kW. A numerical consistency check; no independent calibration is implied.`);
  const raw=Object.fromEntries(data.payload.columns.map(key=>[key,r[key]]));put('dc-raw',JSON.stringify(raw,null,2));
  const hour=sourceClock(r.us).slice(0,13).replace(' ','T');$('dc-hours').querySelectorAll('button').forEach(btn=>{const on=btn.dataset.hour===hour;btn.setAttribute('aria-pressed',String(on));btn.tabIndex=on?0:-1;});
}
function accountMarkup(label,acc){
  return `<article class="dc-account"><p class="dc-label">ACCOUNT ${label} / SAME METER BOUNDARY</p><h3>${acc.hour.replace('T',' ')}:00–${String((Number(acc.hour.slice(-2))+1)%24).padStart(2,'0')}:00</h3><div class="dc-account-values"><div><span>PERIOD PUE / ENERGY RATIO</span><strong>${fmt(acc.PUE)}</strong><small>facility kWh ÷ IT kWh</small></div><div><span>ESTIMATED MEAN POWER</span><strong>${fmt(acc.meanKW/1000)}</strong><small>MW / covered time</small></div></div><dl><dt>Facility energy estimate</dt><dd>${fmt(acc.totalKWh,3)} kWh</dd><dt>IT energy estimate</dt><dd>${fmt(acc.ITKWh,3)} kWh</dd><dt>Covered time</dt><dd>${fmt(acc.coveredSeconds,6)} s</dd><dt>Uncovered time</dt><dd>${fmt(acc.uncoveredSeconds,6)} s</dd><dt>Samples within the hour</dt><dd>${acc.samples}</dd></dl><details><summary>Open the component energies</summary><ul>${COMPONENTS.map(c=>`<li><span>${c.short}</span><span>${fmt(acc.energy[c.id],6)} kWh</span></li>`).join('')}</ul><p class="dc-small">Sample PUE arithmetic mean: ${fmt(acc.samplePUEArithmeticMean,9)}. This is a different calculation from the period energy ratio above.</p><p class="dc-small">Largest sample closure residual: ${acc.maxClosureKW.toExponential(3)} kW.</p></details></article>`;
}
function renderComparison(){
  const c=comparison(data,a,b);$('dc-accounts').innerHTML=accountMarkup('A',c.left)+accountMarkup('B',c.right);
  const sign=c.powerChangePercent>=0?'higher':'lower',direction=c.pueChange<0?'falls':c.pueChange>0?'rises':'stays level';
  put('dc-contrast',`From A to B: mean facility power is ${fmt(Math.abs(c.powerChangePercent),2)}% ${sign}. Period PUE ${direction}${c.pueChange?` by ${fmt(Math.abs(c.pueChange),6)}`:''}. These are two observations of the facility, not a controlled intervention.`);
  rehearsal=null;put('dc-rehearsal-result','Account B changed. Calculate a separate capacity branch with the assumptions above.');
}
function chooseHour(hour){pause();b=hour;$('dc-hour-b').value=b;renderComparison();moveToHour(hour);}
function renderHistory(){
  const x=i=>55+i/167*1010,y=kw=>210-kw/3500*185;
  const path=(key,ratio=false)=>{let drawing=false;return hours.map((h,i)=>{const value=ratio?h.PUE:key==='IT'?h.ITKWh/(h.coveredSeconds/3600):h.meanKW;if(h.coverage<1-1e-12||!Number.isFinite(value)){drawing=false;return '';}const yy=ratio?115-(value-1.04)/.05*90:y(value);const command=drawing?'L':'M';drawing=true;return `${command}${x(i).toFixed(2)},${yy.toFixed(2)}`;}).join(' ');};
  const axis=[0,1,2,3,3.5].map(v=>`<path d="M55 ${y(v*1000)}H1065" stroke="var(--line-soft)"/><text x="43" y="${y(v*1000)+4}" text-anchor="end">${v}</text>`).join('')+[0,24,48,72,96,120,144].map(i=>`<text x="${x(i)}" y="237" text-anchor="middle">${14+i/24} Jul</text>`).join('');
  $('dc-power-content').innerHTML=axis+`<path d="${path('total')}" fill="none" stroke="var(--gold-bright)" stroke-width="2.2"/><path d="${path('IT')}" fill="none" stroke="var(--dc-blue)" stroke-width="1.8"/>`;
  $('dc-ratio-content').innerHTML=[1.04,1.06,1.08].map(v=>{const yy=115-(v-1.04)/.05*90;return `<path d="M55 ${yy}H1065" stroke="var(--line-soft)"/><text x="43" y="${yy+4}" text-anchor="end">${v.toFixed(2)}</text>`;}).join('')+`<path d="${path('',true)}" fill="none" stroke="var(--gold-bright)" stroke-width="2"/><text x="1065" y="138" text-anchor="end">PUE axis 1.04–1.09 / no calibration uncertainty supplied</text>`;
  put('dc-power-desc',`Hourly numerical estimates from ${sourceClock(data.start)} to ${sourceClock(data.end)}. Facility means range ${fmt(Math.min(...hours.map(h=>h.meanKW))/1000)} to ${fmt(Math.max(...hours.map(h=>h.meanKW))/1000)} MW. Power axis begins at zero.`);
  $('dc-hours').innerHTML=hours.map((h,i)=>`<button type="button" data-hour="${h.hour}" data-day-start="${i%24===0}" tabindex="-1" aria-pressed="false" aria-label="Inspect ${h.hour.replace('T',' ')}:00, ${fmt(h.meanKW/1000)} MW, PUE ${fmt(h.PUE)}">${i%24===0?`${14+Math.floor(i/24)} / `:''}${String(i%24).padStart(2,'0')}</button>`).join('');
  $('dc-hours').querySelectorAll('button').forEach((btn,i)=>{btn.addEventListener('click',()=>{pause();chooseHour(btn.dataset.hour);announce(`Account B opened at ${btn.dataset.hour.replace('T',' ')}:00, source clock.`);});btn.addEventListener('keydown',e=>{const offset={ArrowLeft:-1,ArrowRight:1,ArrowUp:-24,ArrowDown:24}[e.key];if(offset){e.preventDefault();const j=Math.max(0,Math.min(167,i+offset));chooseHour(hours[j].hour);$('dc-hours').children[j].focus();}});});
  for(const id of ['dc-power-chart','dc-ratio-chart'])$(id).addEventListener('click',e=>{const rect=e.currentTarget.getBoundingClientRect(),px=(e.clientX-rect.left)/rect.width*1100;chooseHour(hours[Math.max(0,Math.min(167,Math.round((px-55)/1010*167)))].hour);pause();});
}
function renderQuality(){
  const audit=data.payload.archiveAudit,p=audit['power.parquet'],w=audit['weather.parquet'];
  $('dc-quality').innerHTML=`<div class="dc-quality-grid"><article><h3>A long archive.</h3><p>${p.rows.toLocaleString('en-GB')} power records. ${w.rows.toLocaleString('en-GB')} weather records. Typical power interval: ${p.interval_seconds_quantiles[2]} seconds. The fixed replay window contains ${data.window.length.toLocaleString('en-GB')} observations.</p></article><article><h3>Channels can be absent.</h3><p>${p.fields.it_power_kw.nulls.toLocaleString('en-GB')} IT readings and ${p.fields.pue.nulls.toLocaleString('en-GB')} PUE values are null in the full archive. Zero and missing remain different states.</p></article><article><h3>Keep the awkward values.</h3><p>Recorded PUE ranges from ${fmt(p.fields.pue.range.min,3)} to ${fmt(p.fields.pue.range.max,3)} in the full archive. The weather record begins at ${w.timestamp_range.min}. These need source review; they are not silently repaired.</p></article></div>`;
}
$('dc-load-room').addEventListener('click',()=>load(true));$('dc-load-data').addEventListener('click',()=>load(false));$('dc-start-room').addEventListener('click',openRoom);
$('dc-prev').addEventListener('click',()=>{pause();move(index-1,true);});$('dc-next').addEventListener('click',()=>{pause();move(index+1,true);});
$('dc-scrub').addEventListener('input',e=>{pause();move(Number(e.target.value));});$('dc-scrub').addEventListener('change',()=>move(index,true));
$('dc-play').addEventListener('click',()=>{if(playing)return pause();if(index===data.window.length-1)move(0);put('dc-play','Pause records');$('dc-play').setAttribute('aria-pressed','true');playing=setInterval(()=>{move(index+Number($('dc-stride').value));if(index===data.window.length-1)pause();},600);});
$('dc-hour-a').addEventListener('change',e=>{pause();a=e.target.value;renderComparison();});$('dc-hour-b').addEventListener('change',e=>{pause();chooseHour(e.target.value);});
$('dc-swap').addEventListener('click',()=>{pause();[a,b]=[b,a];$('dc-hour-a').value=a;$('dc-hour-b').value=b;renderComparison();moveToHour(b);});
$('dc-example').addEventListener('click',()=>{pause();a='2025-07-14T23';b='2025-07-18T09';$('dc-hour-a').value=a;$('dc-hour-b').value=b;renderComparison();moveToHour(b);announce('Two recorded hours are open: period PUE is lower in B while absolute facility demand is higher.');});
document.querySelectorAll('[data-camera]').forEach(btn=>btn.addEventListener('click',()=>room?.focus(btn.dataset.camera)));
$('dc-refine').addEventListener('click',async()=>{if(!room)return;try{$('dc-refine').disabled=true;await room.refine();}catch(e){put('dc-load-status',e.message);}finally{const info=room.getInfo();$('dc-refine').disabled=info.softwareRenderer||info.refining;put('dc-refine',info.refining?'Refining light…':'Refine light ↗');}});
$('dc-approach').addEventListener('click',()=>{room?.focus(selected);announce(`Approaching the authored representation of ${COMPONENTS.find(c=>c.id===selected).name.toLowerCase()}. The meter remains a whole-facility reading.`);});
$('dc-rehearsal-form').addEventListener('submit',e=>{e.preventDefault();pause();const acc=hourAccount(data,b);rehearsal=capacityRehearsal(data.records,acc.start,acc.end,{gridKW:Number($('dc-grid-cap').value),batteryKWh:Number($('dc-battery').value)});
  const r=rehearsal;$('dc-rehearsal-result').innerHTML=`<p class="dc-label">COUNTERFACTUAL / ${b.replace('T',' ')}:00 / ONE HOUR</p><div class="dc-rehearsal-values">${[['Grid energy',r.gridKWh],['Battery to loads',r.deliveredKWh],['Unmet energy',r.unmetKWh],['Stored at end',r.storedKWh]].map(([k,v])=>`<div><span>${k.toUpperCase()}</span><strong>${fmt(v,2)} <small>kWh</small></strong></div>`).join('')}</div><p>Battery conversion loss ${fmt(r.lossKWh,4)} kWh. Reserve floor ${fmt(r.reserveKWh,2)} kWh. Power-derived energy coverage ${fmt(r.baseline.coverage*100,6)}%. This branch is a numerical supply scenario.</p>`;announce(`Capacity branch calculated. ${fmt(r.unmetKWh,2)} kWh unmet in this authored scenario.`);
});
for(const id of ['dc-grid-cap','dc-battery'])$(id).addEventListener('change',()=>{rehearsal=null;put('dc-rehearsal-result','Assumptions changed. Calculate a new branch before reading its result.');});
$('dc-export').addEventListener('click',()=>{pause();const out={...exportInspection(data,index,a,b,rehearsal),extractSHA256:extractSHA};const url=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)+'\n'],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`where-the-power-goes-row-${data.window[index].sourceRow}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);announce('Inspection exported with raw fields, method, source hashes, publisher notice and any calculated branch.');});
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});window.addEventListener('pagehide',()=>{pause();room?.dispose();});
