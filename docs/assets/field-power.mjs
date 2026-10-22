import { DEFAULTS, POLICY, LOADS, simulate, exampleActions, exportAccount, linkAvailable } from './field-power-model.mjs';
import { sceneMarkup, updateScene } from './field-power-scene.mjs';

const $ = id => document.getElementById(id);
const number = (n, digits = 2) => n.toFixed(digits);
const time = n => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
const accounts = [{ name: '01 / Your watch', options: { ...DEFAULTS }, actions: [], cursor: 0 }];
let active = 0, selected = 'battery', timer = null, serial = 0;
const account = () => accounts[active];
const editable = () => account().cursor >= (account().actions.at(-1)?.at ?? 0);
const announce = text => { $('fp-announcement').textContent = text; };
const put = (id, text) => { $(id).textContent = text; };
$('fp-scene').innerHTML = sceneMarkup();
$('fp-loads').innerHTML = LOADS.map(l => `<article class="fp-load" id="fp-load-${l.id}"><p class="fp-label">${l.essential ? 'ESSENTIAL / RETAINED' : 'DEFERRABLE / LOCAL SWITCH'}</p><h3>${l.name}</h3><p class="fp-load-power">${l.kw.toFixed(1)} <small>kW demand</small></p><div class="fp-load-meter"><span></span></div><p class="fp-small" id="fp-load-state-${l.id}"></p>${l.essential ? '<p class="fp-small">Kept in the allocation.</p>' : `<button type="button" data-load="${l.id}">Shed ${l.name.toLowerCase()}</button>`}</article>`).join('');

function pause() {
  if (timer) clearInterval(timer);
  timer = null;
  $('fp-play').setAttribute('aria-pressed', 'false'); put('fp-play', 'Play time');
}
function move(t, speak = true) {
  account().cursor = Math.max(0, Math.min(POLICY.minutes, t));
  render();
  if (speak) {
    const s = simulate(account().options, account().actions, account().cursor).current;
    announce(`Minute ${s.t}. ${s.events.at(-1)?.text ?? 'All four loads are supplied. The generator charges the battery.'}`);
  }
}
function choose(kind, fields = {}) {
  pause();
  if (!editable()) return announce('This is an earlier reading. Make a new account here to keep the original choices intact.');
  account().actions.push({ id: `choice-${++serial}`, at: account().cursor, kind, ...fields });
  render();
  const s = simulate(account().options, account().actions, account().cursor).current;
  announce(s.events.at(-1)?.text ?? 'The account is unchanged.');
}
function setAccounts() {
  $('fp-account').replaceChildren(...accounts.map((a, i) => new Option(a.name, String(i), false, i === active)));
}
function addAccount(name, options, actions = [], cursor = 0) {
  pause(); accounts.push({ name: `${String(accounts.length + 1).padStart(2, '0')} / ${name}`, options: { ...options }, actions: structuredClone(actions), cursor });
  active = accounts.length - 1; setAccounts(); render();
}
function drawChart(states, baseline, capacity) {
  const x = t => 50 + t / 240 * 920, y = energy => 197 - energy / capacity * 170;
  const path = list => list.map((s, i) => `${i ? 'L' : 'M'}${x(s.t).toFixed(2)},${y(s.energy).toFixed(2)}`).join(' ');
  const last = states.at(-1);
  $('fp-chart-content').innerHTML = [0, .25, .5, .75, 1].map(f => `<path d="M50 ${y(capacity*f)}H970" stroke="var(--line-soft)"/><text x="40" y="${y(capacity*f)+4}" text-anchor="end">${number(capacity*f,1)}</text>`).join('') +
    [0,60,120,180,240].map(t => `<text x="${x(t)}" y="223" text-anchor="middle">${t}m</text>`).join('') +
    `<path d="M50 ${y(capacity*.1)}H970" stroke="var(--gold)" opacity=".5" stroke-dasharray="2 5"/><text x="960" y="${y(capacity*.1)-8}" text-anchor="end">10% reserve</text><path d="${path(baseline)}" fill="none" stroke="var(--muted)" stroke-width="2" stroke-dasharray="5 5"/><path d="${path(states)}" fill="none" stroke="var(--gold-bright)" stroke-width="2.5"/><path d="M${x(last.t)} 20V197" stroke="var(--line)"/><circle cx="${x(last.t)}" cy="${y(last.energy)}" r="4" fill="var(--gold-bright)"/>`;
  put('fp-chart-description', `Through minute ${last.t}: this account holds ${number(last.energy)} kWh, the no-action account ${number(baseline.at(-1).energy)} kWh. Reserve floor ${number(capacity*.1)} kWh. No future values are drawn.`);
}
function inspectEquipment(s) {
  const l = s.loads.find(l => l.id === selected);
  const copy = selected === 'battery' ? ['The battery account.', `${number(s.energy)} kWh stored; ${number(s.reserve)} kWh reserved. ${number(s.discharge,1)} kW out, ${number(s.charge,1)} kW in. The BMS percentage is ${s.sensor.held ? `held at its minute ${s.sensor.observedAt} observation` : 'fresh in the simulation'}. The energy figure is simulator truth, not another sensor.`]
    : selected === 'generator' ? ['Starting is not supplying.', `State: ${s.status}. ${number(s.generator,1)} kW available; ${number(s.generated,1)} kW dispatched. ${number(s.curtailed,1)} kW unused capability. An accepted restart waits three minutes, then ramps by 6 kW per minute. Fuel depletion is outside this study.`]
    : [l.name + '.', `${l.enabled ? `${number(l.served,1)} of ${l.kw.toFixed(1)} kW is being served.` : 'Locally shed. No power requested.'} ${l.essential ? 'An essential load, kept ahead of deferrable loads in this illustrative allocation.' : 'A deferrable load. The local switch changes demand and the configuration revision.'} The model records partial supply as unmet power; it does not simulate a motor or heater at reduced voltage.`];
  put('fp-equipment-title', copy[0]); put('fp-equipment-copy', copy[1]);
  document.querySelectorAll('[data-equipment]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.equipment === selected)));
  updateScene($('fp-scene'), s, selected);
}
function render() {
  const a = account(), run = simulate(a.options, a.actions, a.cursor), s = run.current;
  const baseline = simulate(a.options, [], a.cursor), canEdit = editable();
  put('fp-time', time(s.t)); put('fp-minute', String(s.t)); $('fp-scrub').value = s.t;
  put('fp-now',s.events.length ? `${time(s.events.at(-1).at)} / ${s.events.at(-1).text}` : '00:00 / All four loads are supplied. The generator charges the battery.');
  $('fp-events').innerHTML=s.events.length ? s.events.map(e=>`<li><span>${time(e.at)}</span>${e.text}</li>`).join('') : '<li><span>00:00</span>All four loads are supplied. No choices recorded.</li>';
  $('fp-prev').disabled = s.t === 0; $('fp-next').disabled = s.t === POLICY.minutes;
  put('fp-site-weather', `${run.parameters.temperature}°C / fixed ambient`);
  put('fp-energy', number(s.energy)); $('fp-energy-fill').style.width = `${s.energy/s.usableCapacity*100}%`;
  put('fp-reserve-label', `${number(s.usableCapacity)} kWh adjusted capacity · ${number(s.reserve)} kWh reserved`);
  put('fp-demand', `${number(s.demand,1)} kW`); put('fp-served', `${number(s.served,1)} kW`);
  put('fp-unmet', `${number(s.unmet,1)} kW`); $('fp-unmet').classList.toggle('is-unmet', s.unmet > .01);
  put('fp-generator', s.status); put('fp-bms', `${number(s.sensor.soc,1)}%`);
  put('fp-bms-age', s.sensor.held ? `HELD / ${s.sensor.age}m since observation` : 'FRESH / SIMULATED');
  put('fp-bms-note', `Observed ${time(s.sensor.observedAt)} · delivered ${time(s.sensor.deliveredAt)}. ${s.sensor.held ? 'A new delivery of an old value.' : 'The percentage follows model energy.'}`);
  put('fp-watch-title', s.t < 4 ? 'Before the interruption.' : s.energy <= s.reserve + 1e-8 && s.generator === 0 ? 'The reserve has a boundary.' : s.status === 'online' ? 'Power has returned.' : s.restartAt !== null ? 'Permission is only the start.' : s.unmet > .01 ? 'There is less to go around.' : 'The battery holds the watch.');
  const frontier = a.actions.at(-1)?.at ?? 0;
  put('fp-frontier', canEdit ? 'Choices made here enter this account at the displayed minute.' : `Reading earlier history. This account has choices through minute ${frontier}. Make a new account here to try another decision without rewriting them.`);
  put('fp-account-note', `${a.name}. ${a.actions.length} recorded choices. ${canEdit ? 'Ready for a decision.' : 'Earlier history / read-only.'} Accounts last for this tab only; export to keep one.`);
  for (const l of s.loads) {
    const el = $(`fp-load-${l.id}`); el.classList.toggle('is-off', !l.enabled);
    el.querySelector('.fp-load-meter span').style.width = `${l.served/l.kw*100}%`;
    put(`fp-load-state-${l.id}`, l.enabled ? `${number(l.served,1)} kW served · ${number(l.unmet,1)} kW unmet` : 'Shed locally. Its demand is zero.');
    const b = el.querySelector('button'); if (b) { b.textContent = `${l.enabled ? 'Shed' : 'Restore'} ${l.name.toLowerCase()}`; b.disabled = !canEdit; }
  }
  put('fp-link', linkAvailable(s.t) ? 'AVAILABLE' : `HELD UNTIL ${time(POLICY.linkUp)}`);
  put('fp-inspection-note', s.inspected ? 'Recorded locally. This remains a simulated declaration.' : s.t < 10 ? 'Available from minute 10, after the local check interval.' : 'Record the local check. It grants no automatic restart.');
  $('fp-inspect').disabled = !canEdit || s.t < 10 || s.inspected;
  $('fp-request').disabled = !canEdit || s.t < 4 || s.restartAt !== null;
  const proposal = s.proposals.findLast(p => p.approvedAt === null);
  $('fp-approve').disabled = !canEdit || !proposal;
  put('fp-proposal-note', proposal ? `Proposal ${proposal.id} · revision ${proposal.revision}. Valid through ${time(proposal.expiresAt)}. ${linkAvailable(s.t) ? 'Delivery is immediate in this simulation.' : 'A transmitted approval waits until minute 34.'}` : s.proposals.at(-1)?.outcome ? `Last result: ${s.proposals.at(-1).outcome.replaceAll('-', ' ')}. A fresh proposal is a separate decision.` : s.proposals.length ? 'Approval is held by the link. The generator has not restarted.' : 'No restart proposal yet.');
  put('fp-revision', `REV ${String(s.revision).padStart(2,'0')}`);
  const oldReceiptState = new Map([...$('fp-receipt-list').querySelectorAll('details')].map(el=>[el.dataset.receipt,el.open]));
  $('fp-receipt-list').innerHTML = s.receipts.length ? s.receipts.map(r => `<details class="fp-receipt" data-receipt="${r.proposal}" ${oldReceiptState.get(r.proposal) !== false ? 'open' : ''}><summary>${r.outcome === 'applied' ? '↗' : '−'} ${r.outcome.replaceAll('-', ' ')} / ${time(r.receivedAt)}</summary><dl><dt>Proposed</dt><dd>${time(r.requestedAt)}</dd><dt>Approved</dt><dd>${time(r.approvedAt)}</dd><dt>Valid through</dt><dd>${time(r.expiresAt)}</dd><dt>Received</dt><dd>${time(r.receivedAt)}</dd><dt>Expected / actual rev</dt><dd>${r.expectedRevision} / ${r.actualRevision}</dd><dt>Inspection recorded</dt><dd>${r.inspected ? 'yes' : 'no'}</dd></dl><p>${r.outcome === 'applied' ? 'Warm-up begins. Power must still return through the ramp.' : 'No restart was applied. This receipt remains in the account.'}</p></details>`).join('') : `<div class="fp-empty-receipt"><strong>${s.proposals.some(p=>p.approvedAt!==null) ? 'Still in transit.' : 'No receipt yet.'}</strong><span class="fp-small">${s.proposals.some(p=>p.approvedAt!==null) ? 'The held approval has not reached the receiver.' : 'Propose, then approve. Watch what reaches the receiver.'}</span></div>`;
  drawChart(run.states, baseline.states, s.usableCapacity);
  put('fp-total-served', `${number(s.servedEnergy)} kWh`); put('fp-total-unmet', `${number(s.unmetEnergy)} kWh`); put('fp-losses', `${number(s.losses)} kWh`);
  put('fp-endurance', s.remainingMinutesAtDemand === null ? 'No demand' : `${number(s.remainingMinutesAtDemand,0)} min`);
  const i = s.interval;
  $('fp-arithmetic').innerHTML = i ? `<p class="fp-small">Interval ${time(i.from)}–${time(i.to)}. Actions at ${time(s.t)} affect the next interval.</p><div class="fp-equation">${[
    ['Energy before',`${number(i.before,4)} kWh`],['Charge to battery',`${number(i.charge,3)} kW`],['Battery to loads',`${number(i.discharge,3)} kW`],['Energy after',`${number(i.after,4)} kWh`],['Served this interval',`${number(i.served/60,4)} kWh`],['Loss this interval',`${number(i.loss,5)} kWh`],['Generator dispatched',`${number(i.generated/60,4)} kWh`],['Balance residual',`${i.residual.toExponential(1)} kWh`]
  ].map(([k,v])=>`<div>${k}<strong>${v}</strong></div>`).join('')}</div>` : '<p class="fp-small">No interval has elapsed. Advance one minute to open its energy balance.</p>';
  $('fp-registers').innerHTML = s.registers.map(r=>`<tr><td>${r.name}</td><td>${r.address}</td><td>${r.raw}</td><td>×${r.scale} ${r.unit}</td><td>${time(r.observedAt)}${r.held ? ' / held' : ''}</td></tr>`).join('');
  $('fp-capacity').value = a.options.capacity; $('fp-temperature').value = a.options.temperature;
  document.querySelectorAll('[data-minute]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.minute)===s.t)));
  inspectEquipment(s);
}
$('fp-play').addEventListener('click', () => {
  if (timer) return pause();
  if (account().cursor === POLICY.minutes) move(0);
  $('fp-play').setAttribute('aria-pressed','true'); put('fp-play','Pause time');
  timer = setInterval(() => { move(account().cursor+1,false); if (account().cursor===POLICY.minutes) { pause(); announce('Four-hour rehearsal complete. Export or rewind the account.'); } }, 650);
});
$('fp-prev').addEventListener('click',()=>{pause();move(account().cursor-1);});
$('fp-next').addEventListener('click',()=>{pause();move(account().cursor+1);});
$('fp-trip').addEventListener('click',()=>{pause();move(4);});
$('fp-scrub').addEventListener('input',e=>{pause();move(Number(e.target.value),false);});
$('fp-scrub').addEventListener('change',()=>move(account().cursor));
document.querySelectorAll('[data-minute]').forEach(b=>b.addEventListener('click',()=>{pause();move(Number(b.dataset.minute));}));
document.querySelectorAll('[data-equipment]').forEach(b=>b.addEventListener('click',()=>{selected=b.dataset.equipment;render();announce($('fp-equipment-copy').textContent);}));
document.querySelectorAll('[data-load]').forEach(b=>b.addEventListener('click',()=>{
  const l=simulate(account().options,account().actions,account().cursor).current.loads.find(l=>l.id===b.dataset.load);
  choose('load',{load:l.id,enabled:!l.enabled});
}));
$('fp-inspect').addEventListener('click',()=>choose('inspect'));
$('fp-request').addEventListener('click',()=>choose('request'));
$('fp-approve').addEventListener('click',()=>{
  const p=simulate(account().options,account().actions,account().cursor).current.proposals.findLast(p=>p.approvedAt===null);
  if(p) choose('approve',{proposal:p.id});
});
$('fp-example').addEventListener('click',()=>{
  addAccount('Worked recovery',DEFAULTS,exampleActions());
  announce('Worked recovery loaded. Play or step through: workshop shed at 5, water at 6, inspection at 10, approval held at 13, expired at 34. A fresh approval at 36 restores supply by 42. Make a new account at any minute to try another choice.');
});
$('fp-fork').addEventListener('click',()=>{
  const a=account(); addAccount(`From ${time(a.cursor)}`,a.options,a.actions.filter(e=>e.at<=a.cursor),a.cursor);
  announce('A separate account is ready at this minute. The original remains in the account selector.');
});
$('fp-account').addEventListener('change',e=>{pause();active=Number(e.target.value);render();announce(`Opened ${account().name} at minute ${account().cursor}.`);});
$('fp-settings').addEventListener('submit',e=>{e.preventDefault();
  addAccount('New conditions',{capacity:Number($('fp-capacity').value),temperature:Number($('fp-temperature').value)});
  announce('A separate watch begins with the new capacity and ambient condition. The previous account is retained.');
});
$('fp-settings').addEventListener('focusin',pause);
$('fp-export').addEventListener('click',()=>{
  pause(); const a=account(), data={...exportAccount(a.options,a.actions,a.cursor),name:a.name};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=`what-stays-on-minute-${a.cursor}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  announce(`Exported the account through minute ${a.cursor}. Future choices are excluded; this is an unsigned synthetic record.`);
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
window.addEventListener('pagehide',pause);
setAccounts();render();
