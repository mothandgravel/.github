import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { simulate, parameters, exampleActions, exportAccount, POLICY } from '../docs/assets/field-power-model.mjs';
const approx = (a,b,tolerance=1e-9) => assert.ok(Math.abs(a-b)<tolerance, `${a} != ${b}`);
const action = (id,at,kind,fields={})=>({id,at,kind,...fields});
test('bundle matches the pinned Raivari source manifest', async()=>{
  const m=JSON.parse(await readFile('docs/design/field-power-core.json','utf8'));
  const body=(await readFile('docs/assets/field-power-core.mjs','utf8')).replaceAll('\r\n','\n');
  assert.equal(createHash('sha256').update(body).digest('hex'),m.bundleSha256);
  assert.equal(m.revision,'b8ac188973ecccc2ce7068d8dfaa4125e002231b');
});
test('capacity allowance is explicit and bounded, invalid parameters rejected',()=>{
  approx(parameters().usableCapacity,34); approx(parameters({temperature:20}).usableCapacity,40);
  approx(parameters({temperature:-20}).usableCapacity,30.4);
  assert.throws(()=>parameters({capacity:NaN})); assert.throws(()=>parameters({temperature:-100}));
});
test('all supported conditions conserve energy over every minute, saturate without crossing reserve',()=>{
  for(const capacity of [20,40,80]) for(const temperature of [-20,-5,20]) for(const actions of [[],exampleActions()]) {
    const run=simulate({capacity,temperature},actions);
    for(const s of run.states) {
      assert.ok(s.energy>=s.reserve-1e-9 && s.energy<=s.usableCapacity+1e-9);
      approx(s.generated+s.discharge,s.served+s.charge); approx(s.demand,s.served+s.unmet);
      if(s.interval) approx(s.interval.residual,0);
    }
    const end=run.current;
    approx(end.generatedEnergy+run.states[0].energy,end.energy+end.servedEnergy+end.losses);
  }
});
test('trip is instantaneous after four supplied intervals; battery output limit leaves workshop partly unmet',()=>{
  const s=simulate({},[],4).current;
  approx(s.interval.generated,18); approx(s.generator,0); approx(s.discharge,12); approx(s.unmet,2);
  assert.equal(s.loads.find(l=>l.id==='workshop').served,3);
  assert.equal(s.loads.find(l=>l.id==='heat').unmet,0);
});
test('no-action watch reaches reserve and records all subsequent unmet energy',()=>{
  const run=simulate(); const last=run.current;
  approx(last.energy,last.reserve); approx(last.served,0); approx(last.unmet,14);
  assert.ok(last.unmetEnergy>20); assert.ok(run.states.some(s=>s.interval?.discharge>0&&s.interval.discharge<12));
});
test('shedding preserves energy and config revision while essential loads cannot be switched',()=>{
  const a=[action('a',5,'load',{load:'workshop',enabled:false})];
  assert.ok(simulate({},a,50).current.energy>simulate({},[],50).current.energy);
  assert.equal(simulate({},a,5).current.revision,2);
  assert.throws(()=>simulate({},[action('b',5,'load',{load:'heat',enabled:false})]));
});
test('held SOC retains observation time while delivery and actual energy advance',()=>{
  const run=simulate({},[],40), held=run.states[4].sensor;
  approx(run.current.sensor.soc,held.soc); assert.equal(run.current.sensor.observedAt,4);
  assert.equal(run.current.sensor.deliveredAt,40); assert.equal(run.current.sensor.age,36);
  assert.ok(run.current.energy<run.states[4].energy);
  assert.equal(run.current.registers[0].address,30001); assert.equal(run.current.registers[0].raw,627);
  assert.equal(run.current.registers[3].address,43001);
});
test('proposal alone and unapproved expiry never start equipment',()=>{
  const a=[action('a',10,'inspect'),action('b',12,'request')];
  const s=simulate({},a,50).current;
  assert.equal(s.restartAt,null); assert.equal(s.receipts.length,0); assert.equal(s.proposals[0].approvedAt,null);
});
test('delayed approval is held, then rejected as expired without applying restart',()=>{
  const a=exampleActions().slice(0,5);
  assert.equal(simulate({},a,33).current.receipts.length,0);
  const s=simulate({},a,34).current, r=s.receipts[0];
  assert.equal(r.outcome,'expired'); assert.equal(r.approvedAt,13); assert.equal(r.receivedAt,34);
  assert.equal(r.expiresAt,22); assert.equal(s.restartAt,null);
});
test('valid delivery at expiry boundary is accepted, afterwards is expired',()=>{
  for(const [requestedAt,outcome] of [[24,'applied'],[23,'expired']]) {
    const a=[action('a',10,'inspect'),action('b',requestedAt,'request'),action('c',25,'approve',{proposal:'b'})];
    assert.equal(simulate({},a,34).current.receipts[0].outcome,outcome);
  }
});
test('a load change invalidates a still-timely proposal',()=>{
  const a=[action('a',10,'inspect'),action('b',30,'request'),action('c',31,'load',{load:'water',enabled:false}),action('d',32,'approve',{proposal:'b'})];
  const s=simulate({},a,34).current; assert.equal(s.receipts[0].outcome,'configuration-changed'); assert.equal(s.restartAt,null);
});
test('inspection required even on a fresh link; unavailable inspection is not recorded',()=>{
  const a=[action('a',4,'inspect'),action('b',4,'request'),action('c',5,'approve',{proposal:'b'})];
  const s=simulate({},a,5).current; assert.equal(s.inspected,false); assert.equal(s.receipts[0].outcome,'inspection-missing');
});
test('successful approval starts warmup, then rate-limited generation; duplicate approval is inert',()=>{
  const a=exampleActions().slice(0,7); a.push(action('duplicate',37,'approve',{proposal:'e6'}));
  const run=simulate({},a,42);
  assert.equal(run.states[36].restartAt,36); approx(run.states[39].generator,0);
  approx(run.states[40].generator,6); approx(run.states[40].interval.generated,3);
  approx(run.states[41].generator,12); approx(run.current.generator,18);
  assert.equal(run.current.status,'online'); assert.equal(run.current.receipts.length,2);
});
test('deterministic replay does not mutate inputs or expose future decisions',()=>{
  const a=exampleActions(), original=JSON.stringify(a), p={capacity:40,temperature:-5};
  const early=simulate(p,a,10);
  assert.deepEqual(early,simulate(p,a.filter(a=>a.at<=10),10));
  assert.deepEqual(simulate(p,a),simulate(p,a)); assert.equal(JSON.stringify(a),original);
  const branch=a.filter(a=>a.at<=13); branch.push(action('branch',14,'load',{load:'water',enabled:true}));
  assert.deepEqual(simulate(p,branch,13),simulate(p,a,13));
});
test('export excludes future choices and includes the terms behind its unsigned receipt',()=>{
  const e=exportAccount({},exampleActions(),34);
  assert.equal(e.signed,false); assert.equal(e.futureActionsExcluded,3);
  assert.ok(e.actions.every(a=>a.at<=34)); assert.equal(e.current.receipts[0].transport,'simulated');
  assert.equal(e.states.length,35); assert.equal(e.current.receipts[0].outcome,'expired');
});
test('invalid cutoffs, reversed events, duplicate IDs and invalid load values fail closed',()=>{
  for(const t of [-1,.5,241,NaN]) assert.throws(()=>simulate({},[],t));
  assert.throws(()=>simulate({},[action('a',5,'inspect'),action('b',4,'inspect')]));
  assert.throws(()=>simulate({},[action('a',5,'inspect'),action('a',6,'inspect')]));
  assert.throws(()=>simulate({},[action('a',5,'load',{load:'workshop',enabled:1})]));
  assert.throws(()=>simulate({},[action('a',5,'unknown')]));
});
