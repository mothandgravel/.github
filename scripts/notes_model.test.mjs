import test from 'node:test';
import assert from 'node:assert/strict';
import { queryNotes, specimenFor } from '../docs/assets/notes-model.mjs';
import { readFile } from 'node:fs/promises';

const notes = Array.from({ length: 500 }, (_, i) => ({
  id: String(i + 1).padStart(3, '0'), title: `Note ${i + 1}`, summary: i % 2 ? 'bone and brass' : 'making',
  type: 'Study', project: 'Docket', date: i % 2 ? '2026-10-12' : '2026-10-13', topics: [i % 2 ? 'Interface' : 'Identity'],
}));
test('archive finds words across metadata and intersects topic selection', () => {
  assert.equal(queryNotes(notes, { q: 'docket BRASS', topic: 'Interface' }).total, 250);
  assert.equal(queryNotes(notes, { q: 'bone', topic: 'Identity' }).total, 0);
});
test('all entries remain reachable with stable numeric-id ordering across publication dates', () => {
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

test('a note without optional topic/project metadata remains searchable', () => {
  const minimal = { id: '501', title: 'An observation', summary: 'Making', date: '2026-10-13', type: 'Note' };
  assert.equal(queryNotes([minimal], { q: 'observation' }).total, 1);
  assert.equal(queryNotes([minimal], { topic: 'Interface' }).total, 0);
});

test('specimen routes retain the actual destination and do not relabel investigations', async () => {
  const catalog = JSON.parse(await readFile(new URL('../docs/assets/notes.json', import.meta.url), 'utf8'));
  const specimens = JSON.parse(await readFile(new URL('../docs/assets/specimens.json', import.meta.url), 'utf8'));
  const resolved = id => specimenFor(catalog.find(n => n.id === id), specimens)?.id;
  assert.equal(resolved('017'), '008');
  assert.equal(resolved('014'), '006');
  assert.equal(resolved('012'), '005');
  assert.equal(resolved('006'), '003');
  assert.equal(resolved('008'), '002');
  assert.equal(resolved('015'), undefined);
  assert.equal(specimenFor({specimen:{href:'https://elsewhere.example/specimens/coastal-watch/'}}, specimens), null);
  assert.equal(specimenFor({specimen:{href:'../specimens/coastal-watch-alike/'}}, specimens), null);
  assert.equal(specimenFor({specimen:{href:'../#contact'}}, specimens), null);
  assert.equal(specimenFor({}, specimens), null);
});
