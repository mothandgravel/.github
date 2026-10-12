import test from 'node:test';
import assert from 'node:assert/strict';
import { queryNotes } from '../docs/assets/notes-model.mjs';

const notes = Array.from({ length: 500 }, (_, i) => ({
  id: String(i + 1).padStart(3, '0'), title: `Note ${i + 1}`, summary: i % 2 ? 'bone and brass' : 'making',
  type: 'Study', project: 'Docket', date: '2026-10-13', topics: [i % 2 ? 'Interface' : 'Identity'],
}));
test('archive finds words across metadata and intersects topic selection', () => {
  assert.equal(queryNotes(notes, { q: 'docket BRASS', topic: 'Interface' }).total, 250);
  assert.equal(queryNotes(notes, { q: 'bone', topic: 'Identity' }).total, 0);
});
test('all entries remain reachable with stable date and numeric-id ordering', () => {
  const ids = [];
  for (let page = 1; page <= 25; page++) ids.push(...queryNotes(notes, { page }).entries.map(n => n.id));
  assert.equal(new Set(ids).size, 500);
  assert.equal(ids[0], '500'); assert.equal(ids.at(-1), '001');
  assert.equal(queryNotes(notes, { sort: 'oldest' }).entries[0].id, '001');
});
test('untrusted URL pagination clamps to reachable results', () => {
  assert.equal(queryNotes(notes, { page: 'NaN' }).page, 1);
  assert.equal(queryNotes(notes, { page: -2 }).page, 1);
  assert.equal(queryNotes(notes, { page: 10000 }).page, 25);
  assert.equal(queryNotes(notes, { page: 0.5 }).page, 1);
  assert.equal(queryNotes(notes, { q: 'unknown', page: 4 }).entries.length, 0);
});
