import {householdComparison} from './datacenter-finland-model.mjs';
const $=id=>document.getElementById(id),money=v=>v.toLocaleString('en-GB',{minimumFractionDigits:2,maximumFractionDigits:2}),number=v=>v.toLocaleString('en-GB',{maximumFractionDigits:3});
const signed=v=>`${v>0?'+':v<0?'−':''}€${money(Math.abs(v))}`;
const put=(id,t)=>{$(id).textContent=t;},SVG='http://www.w3.org/2000/svg';
function svgNode(tag,attrs){const e=document.createElementNS(SVG,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;}
function readNumber(id){const el=$(id);if(!el.validity.valid||!Number.isFinite(el.valueAsNumber))throw Error(`Complete “${el.labels[0].textContent.trim()}” within its stated range.`);return el.valueAsNumber;}
export function createHouseholdComparison({getData,getMonth,onMonth,onReceipt,onInspect,onValidity}){
 let valid=false,latest=null;
 function settings(){const active=$('fi-heat-assumption').value==='assumed';return{changeCentsIncludingVAT:readNumber('fi-price-change'),apartment:{annualKWh:readNumber('fi-apartment-use'),exposedPercent:readNumber('fi-apartment-exposure')},electricHome:{annualKWh:readNumber('fi-electric-use'),exposedPercent:readNumber('fi-electric-exposure')},heat:{connection:$('fi-home-connection').value,tariff:$('fi-heat-assumption').value,allocatedHeatMWh:active?readNumber('fi-allocated-heat'):null,reductionEURPerMWh:active?readNumber('fi-heat-reduction'):null,passedThroughPercent:active?readNumber('fi-heat-passthrough'):null}};}
 function drawBar(id,a,max){
  const svg=$(id);svg.replaceChildren();svg.setAttribute('viewBox','0 0 480 76');
  svg.setAttribute('aria-label',`Electricity before €${money(a.baseline.annualEUR.total)}, after €${money(a.afterEUR.total)}. Both homes use the same scale, €0 to €${money(max)}.`);
  for(const [y,values]of [[6,a.baseline.annualEUR],[44,a.afterEUR]]){let x=0;for(const key of ['energy','network','tax']){const width=values[key]/max*470;svg.append(svgNode('rect',{x,y,width,height:20,class:`fi-mark-${key}`}));x+=width;}}
  const before=a.baseline.annualEUR.total/max*470,after=a.afterEUR.total/max*470;
  svg.append(svgNode('path',{d:`M${before},29L${after},39`,class:'fi-home-connector'}));
 }
 function home(prefix,account,max){
  const e=account.electricity,b=e.baseline;
  put(`fi-${prefix}-change`,signed(e.deltaEUR.total));
  put(`fi-${prefix}-basis`,`${number(b.annualKWh)} kWh / band ${b.band} · ${number(b.source.total)} c/kWh recorded total`);
  put(`fi-${prefix}-exposure-value`,`${number(e.exposedPercent)}% / ${number(e.exposedKWh)} kWh`);
  put(`fi-${prefix}-formula`,`${number(e.exposedKWh)} kWh × ${number(e.changeCentsIncludingVAT)} c/kWh ÷ 100 = ${signed(e.deltaEUR.total)}. Net energy ${signed(e.deltaEUR.energy)}; VAT ${signed(e.deltaEUR.tax)}. Network and excise unchanged. Published component rounding is retained; the total uses the source total.`);
  for(const [key,label]of [['energy','Energy / before tax'],['network','Network / before tax'],['tax','Excise & VAT'],['total','Electricity total']]){
   const row=$(`fi-${prefix}-${key}`);row.replaceChildren();const heading=document.createElement('th');heading.scope='row';heading.textContent=label;row.append(heading);
   for(const v of [b.annualEUR[key],e.afterEUR[key]]){const td=document.createElement('td');td.textContent=`€${money(v)}`;row.append(td);}
  }
  drawBar(`fi-${prefix}-bars`,e,max);
  const heat=account.heat;
  put(`fi-${prefix}-heat-value`,heat.householdReductionEUR===null?'Not quantified':`€${money(heat.householdReductionEUR)}`);
  put(`fi-${prefix}-combined`,account.combinedChangeEUR===null?'Heat change remains open':signed(account.combinedChangeEUR));
  $(`fi-${prefix}-combined`).classList.toggle('fi-unquantified',account.combinedChangeEUR===null);
 }
 function render(){
  const data=getData();if(!data)return;
  const month=getMonth();if($('fi-compare-month').options.length!==data.prices.months.length)$('fi-compare-month').replaceChildren(...data.prices.months.map(m=>new Option(new Date(`${m.replace('M','-')}-01T12:00:00Z`).toLocaleDateString('en-GB',{month:'long',year:'numeric',timeZone:'UTC'}),m)));
  $('fi-compare-month').value=month;
  $('fi-heat-assumed-inputs').hidden=$('fi-heat-assumption').value!=='assumed';
  try{
   latest=householdComparison(data,month,settings());valid=true;$('fi-homes-error').hidden=true;
   document.querySelectorAll('.fi-home-calculation,.fi-home-benefits').forEach(e=>e.hidden=false);
   const max=Math.max(1,...[latest.apartment,latest.electricHome].flatMap(a=>[a.electricity.baseline.annualEUR.total,a.electricity.afterEUR.total]));
   home('apartment',latest.apartment,max);home('electric',latest.electricHome,max);
   const shift=latest.assumptions.changeCentsIncludingVAT;put('fi-price-change-value',`${shift>0?'+':''}${number(shift)} c/kWh / VAT included`);
   put('fi-home-scale',`Both homes / same €0–€${money(max)} scale. Upper bar: recorded-rate baseline. Lower bar: chosen price branch.`);
   const h=latest.apartment.heat;
   const statements={
    'tariff-unreported':'A pipe gives this apartment a route to district heat. A household saving is still unreported. Supply mix alone cannot price the benefit.',
    'connection-unknown':'The apartment’s connection is unverified. No direct household heat benefit is quantified, even if a lower tariff is assumed.',
    'no-direct-route':'The apartment is outside the selected district-heat network in this scenario. Its direct benefit from that network is €0. Indirect market effects are unmodelled.',
    'assumed-no-change':'The apartment is connected, but you have assumed no change to its heating charge. The model gives it no tariff reduction.',
    'assumed-reduction':h.status==='assumed-reduction'?`${number(h.allocatedHeatMWh)} thermal MWh × €${money(h.reductionEURPerMWh)}/MWh = €${money(h.allocatedEnergyChargeReductionEUR)} allocated energy-charge reduction. At ${number(h.passedThroughPercent)}% pass-through: €${money(h.householdReductionEUR)} reaches this household. All three quantities are chosen.`:''
   };
   put('fi-home-heat-explanation',statements[h.status]);
   put('fi-home-heat-route',h.connection==='connected'?'Connected building / tariff consequence to inspect':h.connection==='unknown'?'Connection unverified / route unresolved':'No connection / no direct route');
   $('fi-home-heat-diagram').dataset.connection=h.connection;
   put('fi-home-heat-record',`${number(latest.recordedHeatContext.residentialUseGWh)} GWh / residential-building use, Nivos 2024. Taul5!R138. No server-to-home attribution is published.`);
   put('fi-home-vat',`The ${month.replace('M',' / ')} source-month VAT convention is ${number(latest.apartment.electricity.vatRate*100)}%. The change already includes VAT; it is split into net energy and VAT, never taxed a second time.`);
   onReceipt(latest);
  }catch(e){valid=false;latest=null;put('fi-homes-error',e.message);$('fi-homes-error').hidden=false;document.querySelectorAll('.fi-home-calculation,.fi-home-benefits').forEach(e=>e.hidden=true);onReceipt({kind:'incomplete household assumptions',message:e.message,calculation:null});}
  onValidity(valid);
 }
 for(const input of document.querySelectorAll('[data-fi-home-input]'))input.addEventListener(input.tagName==='SELECT'?'change':'input',render);
 $('fi-compare-month').addEventListener('change',e=>onMonth(e.target.value));
 for(const key of ['apartment','electric'])$(`fi-${key}-inspect`).addEventListener('click',()=>{if(valid)onInspect({home:key==='apartment'?latest.apartment:latest.electricHome,recordedHeatContext:latest.recordedHeatContext,scope:latest.scope});});
 $('fi-homes-reset').addEventListener('click',()=>{
  for(const [id,value]of Object.entries({'fi-price-change':1,'fi-apartment-use':3000,'fi-electric-use':20000,'fi-apartment-exposure':100,'fi-electric-exposure':100,'fi-home-connection':'connected','fi-heat-assumption':'unreported','fi-allocated-heat':7.5,'fi-heat-reduction':10,'fi-heat-passthrough':100}))$(id).value=value;
  render();
 });
 return{render,get valid(){return valid;},get settings(){return settings();}};
}
