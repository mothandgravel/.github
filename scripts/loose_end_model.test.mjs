import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fields, followups, briefLimit, normalizeDraft, briefText, readDraft } from '../docs/assets/loose-end-model.mjs';

test('a short question does not acquire unanswered commercial follow-ups', () => {
  const brief = briefText({making:'An idea worth testing.'});
  assert.ok(brief.includes('An idea worth testing.'));
  for (const heading of ['Timing\n','Working budget\n','Existing material\n']) assert.ok(!brief.includes(heading));
});
test('old carried questions remain readable without the new optional answers', () => {
  const draft=readDraft({getItem:()=>JSON.stringify({version:1,answers:{making:'Existing question.',constraints:'Keep the old system.'}})});
  assert.equal(draft.making,'Existing question.');
  assert.equal(draft.constraints,'Keep the old system.');
  for (const key of followups) assert.equal(draft[key],'');
});
test('maximum answers fit in the carried brief without losing the final material', () => {
  const input=Object.fromEntries(fields.map(key=>[key,'x'.repeat(1800)]));
  input.materials='x'.repeat(1780)+'END-OF-MATERIAL';
  const brief=briefText(input);
  assert.ok(brief.length<=briefLimit);
  assert.ok(brief.includes('END-OF-MATERIAL'));
});
test('uncertainty, currency and material links remain the visitor’s literal words', () => {
  const draft=normalizeDraft({making:'Question.',timing:'Not sure yet',budget:'USD 2,000–4,000',materials:'javascript:alert(1) <script>example</script>'});
  const brief=briefText(draft);
  for (const key of followups) assert.ok(brief.includes(draft[key]));
  assert.equal(normalizeDraft({budget:{amount:2000}}).budget,'');
});
