import {prepareFinnishAccount,householdAccount,gridAccount,heatAccount,finnishInspection} from './datacenter-finland-model.mjs';
import {createHouseholdComparison} from './datacenter-households.mjs';
const $=id=>document.getElementById(id),put=(id,t)=>{$(id).textContent=t;},num=(v,d=1)=>Number.isFinite(v)?(Math.abs(v)<.5*10**-d?0:v).toLocaleString('en-GB',{minimumFractionDigits:d,maximumFractionDigits:d}):'Not reported';
const monthName=m=>new Date(`${m.replace('M','-')}-01T12:00:00Z`).toLocaleDateString('en-GB',{month:'long',year:'numeric',timeZone:'UTC'});
const SVG='http://www.w3.org/2000/svg';let data=null,sha='',provenance=null,panel='homes',playing=null;
const state={month:'2026M06',annualKWh:20000,windowId:'winter',index:112,additionalMW:0,heatYear:2024};
function node(tag,attrs={},text){const el=document.createElementNS(SVG,tag);for(const[k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el;}
function chartFrame(svg,height,label){const w=Math.max(240,Math.round(svg.getBoundingClientRect().width));svg.setAttribute('viewBox',`0 0 ${w} ${height}`);svg.replaceChildren(node('title',{},label));return w;}
function showReceipt(value){$('fi-receipt').textContent=JSON.stringify(value,null,2);}
function renderBill(){
 const account=householdAccount(data,state.month,state.annualKWh),r=account.source;
 put('fi-month-value',monthName(state.month));put('fi-household-value',`${num(state.annualKWh,0)} kWh/year`);put('fi-band',`Consumer band ${account.band} / ${({A:'under 1,000 kWh',B:'1,000–2,499 kWh',C:'2,500–4,999 kWh',D:'5,000–15,000 kWh',E:'over 15,000 kWh'})[account.band]}`);
 put('fi-bill-total',`€${num(account.annualEUR.total,0)}`);put('fi-unit-price',`${num(r.total,3)} c/kWh / published total`);put('fi-bill-period',`If ${monthName(state.month)}’s rate held for one year.`);
 const pieces=[['energy','Energy / before tax'],['network','Network / before tax'],['tax','Electricity tax & VAT']];
 $('fi-bill-parts').replaceChildren(...pieces.map(([key,label])=>{const el=document.createElement('div');el.className=`fi-bill-part fi-${key}`;const p=document.createElement('span');p.textContent=label;const strong=document.createElement('strong');strong.textContent=`€${num(account.annualEUR[key],0)}`;const small=document.createElement('small');small.textContent=`${num(r[key],3)} c/kWh`;el.append(p,strong,small);return el;}));
 const svg=$('fi-bill-chart'),w=chartFrame(svg,210,`Monthly Finnish household electricity prices, band ${account.band}, January 2024 to June 2026. Select a month below to inspect.`),pad=30,rows=data.prices.months.map(m=>data.prices.rows.find(x=>x.month===m&&x.band===account.band)),max=Math.max(...rows.map(x=>x.total))*1.12,step=(w-pad*2)/rows.length;
 svg.append(node('text',{x:pad,y:17},'c/kWh / published components'));
 for(let i=0;i<rows.length;i++){const r=rows[i],x=pad+i*step;let y=179;for(const [key]of pieces){const h=r[key]/max*142;svg.append(node('rect',{x:x+step*.1,y:y-h,width:step*.8,height:h,class:`fi-mark-${key}`,opacity:r.month===state.month?1:.5}));y-=h;}if(r.month===state.month)svg.append(node('path',{d:`M${x+step*.1},187h${step*.8}`,class:'fi-selected-mark'}));}
 for(const [i,label]of [[0,'Jan 2024'],[12,'Jan 2025'],[29,'Jun 2026']])svg.append(node('text',{x:pad+i*step,y:205,'text-anchor':i===29?'end':'start'},label));
 put('fi-bill-formula',`${num(state.annualKWh,0)} kWh × ${num(r.total,3)} c/kWh ÷ 100 = €${num(account.annualEUR.total,2)} / year at this month’s rate. Component rounding residual: €${num(account.roundingEUR,3)}.`);
 if(panel==='bill')showReceipt({source:'Statistics Finland / 13rb',updated:data.prices.updated,query:data.prices.query,record:r,calculation:account});
}
function renderGrid(){
 const a=gridAccount(data,state.windowId,state.index,state.additionalMW),r=a.source,rows=data.grid.windows.find(w=>w.id===state.windowId).rows;
 const end=Number(r.sourceHour),label=`${r.sourceDay} / ${String(end-1).padStart(2,'0')}:00–${String(end).padStart(2,'0')}:00 EET`;
 put('fi-grid-clock',label);put('fi-grid-observed',`${num(r.consumption/1000,3)} GW`);put('fi-grid-production',`${num(r.production/1000,3)} GW`);put('fi-grid-import',`${num(a.netImportMW/1000,3)} GW`);put('fi-grid-wind',`${num(r.wind/1000,3)} GW`);
 put('fi-extra-value',`${num(state.additionalMW,0)} MW`);put('fi-grid-branch',state.additionalMW?`+${num(state.additionalMW,0)} MW to supply / ${num(a.branch.totalDemandMW/1000,3)} GW total demand in this arithmetic branch.`:'The historical account is unchanged. Add a load to inspect a separate requirement.');
 put('fi-grid-formula',`${num(r.production,3)} + ${num(r.import,3)} + (${num(r.exportSigned,3)}) − ${num(r.consumption,3)} = ${num(a.residualMW,6)} MW / balance residual. Week: ${num(a.consumptionMWh/1000,3)} GWh over 168 one-hour intervals.`);
 const svg=$('fi-grid-chart'),w=chartFrame(svg,260,'Recorded national consumption, production and wind power in the selected Finnish week, with a separate authored additional demand line.'),left=45,right=15,top=33,bottom=220,max=Math.max(...rows.map(r=>r.consumption+state.additionalMW),...rows.map(r=>r.production))*1.08;
 const x=i=>left+i/(rows.length-1)*(w-left-right),y=v=>bottom-v/max*(bottom-top);
 for(const gw of [0,5,10,15,20])if(gw*1000<max){svg.append(node('path',{d:`M${left},${y(gw*1000)}H${w-right}`,class:'fi-grid-line'}));svg.append(node('text',{x:left-8,y:y(gw*1000)+4,'text-anchor':'end'},`${gw}`));}svg.append(node('text',{x:left,y:16},'GW / national hourly mean'));
 for(const [key,cls]of [['wind','wind'],['production','production'],['consumption','consumption']])svg.append(node('path',{d:rows.map((r,i)=>`${i?'L':'M'}${x(i)},${y(r[key])}`).join(' '),class:`fi-plot fi-plot-${cls}`}));
 if(state.additionalMW)svg.append(node('path',{d:rows.map((r,i)=>`${i?'L':'M'}${x(i)},${y(r.consumption+state.additionalMW)}`).join(' '),class:'fi-plot fi-plot-branch'}));
 svg.append(node('path',{d:`M${x(state.index)},${top}V${bottom}`,class:'fi-cursor'}));svg.append(node('circle',{cx:x(state.index),cy:y(r.consumption),r:4,class:'fi-point'}));
 svg.append(node('text',{x:left,y:249},rows[0].sourceDay));svg.append(node('text',{x:w-right,y:249,'text-anchor':'end'},rows.at(-1).sourceDay));
 if(panel==='grid')showReceipt({source:data.grid.source,sheet:data.grid.sheet,sourceRow:r.row,columns:data.grid.sourceColumns,record:r,calculation:a,timeConvention:data.methods.grid});
}
function heatCell(id){return data.heat.cells.find(c=>c.id===id);}
function renderHeat(){
 const a=heatAccount(data,state.heatYear);put('fi-heat-sales',`${num(a.customerUseGWh,1)} GWh`);put('fi-heat-homes',a.complete?`${num(a.residentialUseGWh,1)} GWh`:'Not reported');put('fi-heat-year',String(a.year));
 put('fi-heat-boundary',a.complete?'2024 / Nivos company and municipal row 114 / several networks':'2025 / annual report sales; separate central-network origin disclosure');
 put('fi-heat-caption',a.complete?'16.0 GWh is reported for residential buildings. It is not an attribution of server heat to those buildings.':'43.1 GWh is reported for all customers. The 41% recovered-heat origin share concerns central Mäntsälä only. These figures cannot be multiplied.');
 const flow=$('fi-heat-flow');flow.replaceChildren();
 const v=a.values;
 const groups=a.complete?[
  ['INTO THE NETWORK',[['fuelHeat','Other net heat production',v.fuelHeat],['recoveryAndHeatPump','Recovery / heat-pump output',v.recoveryAndHeatPump]]],
  ['ACCOUNTED AT THE NETWORK',[['supply','Total supplied heat',v.supply],['lossAndMeterDifference','Losses & meter differences',v.lossAndMeterDifference]]],
  ['TO CUSTOMERS',[['residentialUse','Residential buildings',v.residentialUse],['industrialUse','Industry',v.industrialUse],['otherUse','Other customers',v.otherUse]]]
 ]:[['ALL COMPANY CUSTOMERS',[['sales2025','Reported heat sales',a.customerUseGWh]]],['RESIDENTIAL BUILDINGS',[['unknown','Breakdown unavailable',null]]],['CENTRAL MÄNTSÄLÄ ONLY',[['origin2025','Recovered-heat origin',a.centralNetworkRecoveryPercent,'percent']]]];
 for(const [heading,items]of groups){const col=document.createElement('div');const title=document.createElement('p');title.className='fi-label';title.textContent=heading;col.append(title);for(const [id,label,value,unit]of items){const b=document.createElement('button');b.type='button';b.className='fi-flow-item';b.dataset.heat=id;const span=document.createElement('span');span.textContent=label;const strong=document.createElement('strong');strong.textContent=value===null?'—':`${num(value,1)} ${unit==='percent'?'%':'GWh'}`;const bar=document.createElement('i');bar.style.setProperty('--fi-share',`${value===null?0:Math.min(100,value/(a.complete?v.supply:a.customerUseGWh)*100)}%`);if(value===null)bar.className='fi-missing';if(unit==='percent')bar.hidden=true;b.append(span,strong,bar);b.addEventListener('click',()=>{flow.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));showReceipt(a.complete?{source:data.heat.source,year:2024,scope:a.scope,selectedCell:heatCell(id),allBalanceCells:data.heat.cells}:a);put('fi-heat-selection',`${label}. ${a.complete?`Source ${heatCell(id).sheet}!${heatCell(id).cell}.`:'The 2025 scopes remain separate.'}`);});b.setAttribute('aria-pressed','false');col.append(b);}flow.append(col);}
 put('fi-heat-formula',a.complete?`${num(v.fuelHeat)} + ${num(v.recoveryAndHeatPump)} = ${num(v.supply)} GWh supplied. ${num(v.residentialUse)} + ${num(v.industrialUse)} + ${num(v.otherUse)} = ${num(v.customerUse)} GWh customer use. ${num(v.customerUse)} + ${num(v.lossAndMeterDifference)} = ${num(v.supply)} GWh. Heat-production electricity is “..” / not reported.`:'No 2025 residential allocation or heat balance is inferred. Missing values remain unavailable. The 2024 balance stays available in the year selector.');
 put('fi-heat-selection','Choose a heat entry to inspect its source.');if(panel==='heat')showReceipt(a);
}
function render(){if(!data)return;renderBill();renderGrid();renderHeat();comparison.render();}
function pause(){if(playing)clearInterval(playing);playing=null;put('fi-play','Play the week');$('fi-play').setAttribute('aria-pressed','false');}
function selectPanel(key){panel=key;for(const b of document.querySelectorAll('[data-fi-panel]'))b.setAttribute('aria-pressed',String(b.dataset.fiPanel===key));for(const el of document.querySelectorAll('[data-fi-content]'))el.hidden=el.dataset.fiContent!==key;pause();render();}
async function open(){
 $('fi-open').disabled=true;put('fi-status','Opening the Finnish records and checking their source fingerprint…');
 try{const [r,m]=await Promise.all([fetch(new URL('./data-center/finland.json',import.meta.url)),fetch(new URL('../design/finland-provenance.json',import.meta.url))]);if(!r.ok||!m.ok)throw Error('Source unavailable');const text=await r.text(),manifest=await m.json();sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text.replaceAll('\r\n','\n'))))].map(b=>b.toString(16).padStart(2,'0')).join('');if(sha!==manifest.sha256)throw Error('Extract fingerprint differs');data=prepareFinnishAccount(JSON.parse(text));provenance=manifest;$('fi-month').replaceChildren(...data.prices.months.map(x=>new Option(monthName(x),x)));$('fi-month').value=state.month;$('fi-workspace').hidden=false;$('fi-open-intro').hidden=true;render();put('fi-status',`Verified Finnish extract / 150 price records · 336 grid hours · reported local heat. Retrieved ${data.retrieved}. Recorded, not live.`);$('fi-export').disabled=false;
 }catch(e){data=null;put('fi-status',`The Finnish account could not open: ${e.message}. Retry below.`);$('fi-open').disabled=false;}
}
$('fi-open').addEventListener('click',open);
for(const b of document.querySelectorAll('[data-fi-panel]'))b.addEventListener('click',()=>selectPanel(b.dataset.fiPanel));
$('fi-month').addEventListener('change',e=>{state.month=e.target.value;renderBill();comparison.render();});
$('fi-household').addEventListener('change',e=>{state.annualKWh=Number(e.target.value);renderBill();});
$('fi-week').addEventListener('change',e=>{pause();state.windowId=e.target.value;state.index=0;$('fi-hour').value=0;renderGrid();});
$('fi-hour').addEventListener('input',e=>{pause();state.index=Number(e.target.value);renderGrid();});
$('fi-extra').addEventListener('input',e=>{state.additionalMW=Number(e.target.value);renderGrid();});
$('fi-play').addEventListener('click',()=>{if(playing){pause();return;}put('fi-play','Pause the week');$('fi-play').setAttribute('aria-pressed','true');playing=setInterval(()=>{state.index=(state.index+1)%168;$('fi-hour').value=state.index;renderGrid();if(state.index===167)pause();},450);});
$('fi-heat-period').addEventListener('change',e=>{state.heatYear=Number(e.target.value);renderHeat();});
const comparison=createHouseholdComparison({getData:()=>data,getMonth:()=>state.month,onMonth:m=>{state.month=m;$('fi-month').value=m;render();},onReceipt:r=>{if(panel==='homes')showReceipt(r);},onInspect:r=>{showReceipt(r);document.querySelector('.fi-receipts').open=true;$('fi-receipt').scrollIntoView({block:'center'});$('fi-receipt').focus({preventScroll:true});},onValidity:valid=>{$('fi-export').disabled=!data||!valid;put('fi-export',data&&!valid?'Complete the two-home inputs to export':'Export Finnish inspection ↓');}});
$('fi-export').addEventListener('click',()=>{if(!data||!comparison.valid)return;const blob=new Blob([JSON.stringify(finnishInspection(data,{...state,comparison:comparison.settings},sha,provenance),null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='moth-gravel-finnish-account.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
new ResizeObserver(()=>{if(data){if(panel==='bill')renderBill();if(panel==='grid')renderGrid();}}).observe($('fi-workspace'));
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
