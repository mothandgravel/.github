import assert from 'node:assert/strict';
import test from 'node:test';
import {activeCaption, clock, videoDuration} from '../src/timeline.mjs';

test('caption boundaries include starts and exclude ends, including silent gaps', () => {
  const pages = [{start: 4, end: 6, text: 'First'}, {start: 8, end: 10, text: 'Second'}];
  assert.equal(activeCaption(pages, 3.99), '');
  assert.equal(activeCaption(pages, 4), 'First');
  assert.equal(activeCaption(pages, 6), '');
  assert.equal(activeCaption(pages, 8), 'Second');
  assert.equal(activeCaption(pages, 10), '');
});

test('preview is bounded by the actual recording and rounds up to a full frame', () => {
  assert.equal(videoDuration(10.01, null, 24), 241);
  assert.equal(videoDuration(10.01, 30, 24), 241);
  assert.equal(videoDuration(300, 12, 24), 288);
  assert.equal(clock(65.9), '1:05');
});
