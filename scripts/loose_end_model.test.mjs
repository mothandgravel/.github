import { test } from 'node:test';
import assert from 'node:assert/strict';
import { briefSections, emailHref, formatBrief, updateBrief } from '../docs/assets/brief-builder-model.mjs';
import { fields, followups, briefLimit, normalizeDraft, briefText, readDraft } from '../docs/assets/loose-end-model-v2.mjs';

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

const builderAnswers = (answers = {}) => ({
  domain: [], making: '', friction: [], difficulty: '', artifact: [], ground: [], constraints: '', ...answers,
});

test('four builder sections are optional and keep supplied choices in order', () => {
  assert.equal(formatBrief(briefSections(builderAnswers())), '');
  const text = formatBrief(briefSections(builderAnswers({
    domain: ['Connected device / telemetry', 'Cloud or mobile software'],
    making: 'A field terminal', artifact: ['Working prototype'],
  })));
  assert.equal(text, '# A brief for Moth & Gravel\n\n## System\n- Connected device / telemetry\n- Cloud or mobile software\nA field terminal\n\n## First artifact\n- Working prototype');
});

test('changing one step updates the generated section and retains hand edits', () => {
  const before = briefSections(builderAnswers({making:'Console', difficulty:'Old automated text.'}));
  const after = briefSections(builderAnswers({making:'New console', difficulty:'Old automated text.'}));
  const edited = formatBrief(before).replace('Old automated text.', 'Keep my exact rewrite.');
  const updated = updateBrief(edited, before, after);
  assert.match(updated, /New console/);
  assert.match(updated, /Keep my exact rewrite\./);
  assert.doesNotMatch(updated, /Old automated text/);
});

test('updates to a hand-edited section apply beneath it without accumulating intermediate keystrokes', () => {
  const original = briefSections(builderAnswers({making:'Console', difficulty:'Old'}));
  const intermediate = briefSections(builderAnswers({making:'Console', difficulty:'N'}));
  const final = briefSections(builderAnswers({making:'Console', difficulty:'New friction'}));
  const edited = formatBrief(original).replace('## Friction\nOld', '## My observation\nKeep these manual words.');
  assert.equal(updateBrief(updateBrief(edited, original, intermediate), intermediate, final),
    edited + '\n\n## Friction\nNew friction');
});

test('mail carries the exact current text and encodes Unicode and mail delimiters', () => {
  const input = 'Topic A + B & C 🌒\nSubject-like data?bcc=someone@example.test\n' + 'Ä&+'.repeat(1800);
  const mail = new URL(emailHref(input));
  assert.equal(mail.pathname, 'hello@mothandgravel.com');
  assert.match(mail.searchParams.get('subject'), /Topic A \+ B & C 🌒/);
  assert.equal(mail.searchParams.get('body').replace(/\r\n/g, '\n'), input);
  assert.equal(mail.searchParams.has('bcc'), false);
  assert.equal(new URL(emailHref('')).searchParams.get('body'), '');
  assert.equal(new URL(emailHref(String.fromCharCode(0xd800))).searchParams.get('body'), '\ufffd');
});
