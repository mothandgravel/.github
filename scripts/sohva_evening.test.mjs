import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newBreak, breakAction, runPlan, sleepFrame } from '../docs/assets/sohva-evening-model.mjs';

test('a break returns sound it muted, without toggling or repeating its action', () => {
  const start = breakAction(newBreak(), 'start');
  assert.equal(start.muted, true);
  assert.equal(start.ownsMute, true);
  assert.deepEqual(breakAction(start, 'start'), start);
  const end = breakAction(start, 'end');
  assert.equal(end.muted, false);
  assert.equal(end.ownsMute, false);
  assert.deepEqual(breakAction(end, 'end'), end);
});

test('an existing personal mute survives the whole break', () => {
  const end = breakAction(breakAction(newBreak(true), 'start'), 'end');
  assert.equal(end.muted, true);
});

test('manual unmute gives up break ownership; a later personal mute is preserved', () => {
  const manual = breakAction(breakAction(newBreak(), 'start'), 'unmute');
  assert.equal(manual.ownsMute, false);
  assert.equal(breakAction(manual, 'end').muted, false);
  assert.equal(breakAction({ ...manual, muted: true }, 'end').muted, true);
});

test('scheduled scenes skip standby and an explicit wake-up can start the TV', () => {
  assert.deepEqual(runPlan({ on: false, plan: 'scene' }), { on: false, applied: false, channel: null, volume: null });
  for (const [on, plan] of [[true, 'scene'], [false, 'wake'], [true, 'wake']]) {
    assert.deepEqual(runPlan({ on, plan }), { on: true, applied: true, channel: 'Channel 1', volume: 18 });
  }
});

test('the fixture uses six integer steps to one third, then standby, retaining the original level', () => {
  assert.deepEqual([0,10,20,30,40,50,60].map(t => sleepFrame(t).volume), [30,27,24,20,17,14,10]);
  assert.equal(sleepFrame(59).on, true);
  assert.equal(sleepFrame(60).on, false);
  assert.equal(sleepFrame(60).restore, 30);
});

test('a fade never raises a low level and remains bounded at every valid starting level', () => {
  for (let initial = 0; initial <= 100; initial++) {
    const frames = [0,10,20,30,40,50,60].map(t => sleepFrame(t, initial));
    assert.equal(frames[0].volume, initial);
    for (let i = 1; i < frames.length; i++) assert.ok(frames[i].volume <= frames[i-1].volume);
    assert.equal(frames[6].volume, initial <= 4 ? initial : Math.max(4, Math.floor(initial / 3)));
  }
  assert.equal(sleepFrame(-1).seconds, 0);
  assert.equal(sleepFrame(100).seconds, 60);
  assert.throws(() => sleepFrame(NaN), RangeError);
});
