import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_RATE, playbackRate, stepIndex, cueAt} from '../docs/assets/field-listen-model.mjs';

test('default playback is 1.15 and unsupported rates fall back to it', () => {
  assert.equal(DEFAULT_RATE, 1.15);
  assert.equal(playbackRate('1.25'), 1.25);
  for (const value of ['', -1, 100, 'NaN', undefined]) assert.equal(playbackRate(value), 1.15);
});
test('queue stops at both ends and a one-item queue stays on its item', () => {
  assert.equal(stepIndex(0, -1, 9), 0);
  assert.equal(stepIndex(8, 1, 9), 8);
  assert.equal(stepIndex(0, 1, 9), 1);
  assert.equal(stepIndex(0, 1, 1), 0);
});
test('cue highlighting follows actual intervals and clears in a pause', () => {
  const cues = [{start:0,end:1}, {start:1.1,end:2}];
  assert.equal(cueAt(cues, .5), 0);
  assert.equal(cueAt(cues, 1), -1);
  assert.equal(cueAt(cues, 1.1), 1);
  assert.equal(cueAt(cues, 2), -1);
});
