import { returnKey, revisions, directions, empty, restore, append } from './specimen-model.mjs?v=mending';
import { readDraft, draftKey, roomKey, briefText } from './loose-end-model-v2.mjs?v=mending';

const el = id => document.getElementById(id);
const status = el('return-status');
let storage;
try { storage = sessionStorage; } catch {}
let raw;
try { raw = storage?.getItem(returnKey); } catch {}
let state = restore(raw);
let revision = 'damage-2';
let anchor = revision;
function announce(message) {
  status.textContent = message;
  const feedback = document.activeElement?.closest('[data-feedback-scope]')?.querySelector('[data-room-feedback]');
  if (feedback) feedback.textContent = message;
}
function persist() {
  try {
    if (!storage) throw Error('Storage unavailable');
    storage.setItem(returnKey, JSON.stringify(state));
    return true;
  } catch { return false; }
}
function record(kind, value) {
  try {
    state = append(state, kind, value);
    const kept = persist();
    paint();
    announce(kept ? 'Kept in this tab. Nothing was sent.' : 'Kept for this visit only. Storage is unavailable; download a copy before leaving.');
    return true;
  } catch (error) { announce(error.message); return false; }
}

const draft = readDraft(storage);
if (draft) {
  el('return-brief').hidden = false;
  let brief;
  try { brief = JSON.parse(storage.getItem(draftKey)).brief; } catch {}
  el('return-brief-text').textContent = typeof brief === 'string' ? brief.slice(0, 24000) : briefText(draft);
}
let earlier;
try { earlier = JSON.parse(storage?.getItem(roomKey)); } catch {}
if (earlier?.version === 1 && (earlier.note || earlier.choice)) {
  el('earlier-local').hidden = false;
  el('earlier-local-note').textContent = typeof earlier.note === 'string' ? earlier.note.slice(0, 1800) : 'No first-visit observation.';
  const old = earlier.noteSurface === 'damage' ? 'damage-1' : 'item-1';
  el('earlier-local-note').prepend(revisions[old].label + ': ');
  el('earlier-local-choice').textContent = 'Earlier local choice: ' + ({ item:'Object first', damage:'Damage first', open:'Keep open' }[earlier.choice] || 'Not recorded') + '.';
}

function directionScope() {
  const latest = revision === 'damage-2';
  const scope = el('direction-scope');
  if (scope) scope.textContent = latest ? 'This direction concerns damage-first revision 2.' :
    'You are inspecting ' + revisions[revision].label + '. The direction below concerns revision 2. Return to it before choosing; your draft answers will stay in place.';
  if (el('inspect-latest')) el('inspect-latest').hidden = latest;
  el('return-choice-form').querySelector('fieldset').disabled = !latest;
  el('choice-reason').disabled = !latest;
  el('return-choice-form').querySelector('button[type="submit"]').disabled = !latest;
}
function drawing() {
  const current = revisions[revision];
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 420 390');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', current.label + '. ' + current.heading + ' Choices: ' + current.options.join(', ') + '. Illustrative controls only.');
  function text(value, x, y, size = 16) {
    const node = document.createElementNS(ns, 'text');
    node.setAttribute('x', x); node.setAttribute('y', y); node.setAttribute('font-size', size);
    node.textContent = value; svg.append(node); return node;
  }
  text('FICTIONAL SPECIMEN / ' + revision.toUpperCase(), 24, 32, 11).classList.add('sample-accent');
  text(current.heading, 24, 82, 24);
  current.options.forEach((value, i) => {
    const box = document.createElementNS(ns, 'rect');
    const added = revision === 'damage-2' && i === 2;
    for (const [key, value] of Object.entries({ x:24, y:106+i*66, width:372, height:52, class:added ? 'sample-line added-option' : 'sample-line' })) box.setAttribute(key, value);
    svg.append(box); text(value, 38, 138+i*66);
  });
  const button = document.createElementNS(ns, 'rect');
  for (const [key, value] of Object.entries({ x:24, y:326, width:372, height:42, class:'sample-accent' })) button.setAttribute(key, value);
  svg.append(button);
  text('Continue →', 38, 353).classList.add('sample-ink');
  el('revision-drawing').replaceChildren(svg);
  el('revision-caption').textContent = current.label + ' / illustrative sketch. Controls are drawn, not interactive.';
  directionScope();
}
function node(tag, text) {
  const result = document.createElement(tag); result.textContent = text; return result;
}
function inspect(value) {
  revision = value;
  document.querySelector(`input[name="revision"][value="${revision}"]`).checked = true;
  drawing();
  el('specimen').scrollIntoView();
  document.querySelector('input[name="revision"]:checked').focus({ preventScroll:true });
}
function paint() {
  drawing();
  const notes = el('return-note-records');
  notes.replaceChildren();
  if (!state.notes.length) notes.append(node('p', 'No return-visit notes yet.'));
  for (const note of state.notes) {
    const card = node('div', ''); card.className = 'return-record';
    card.append(node('p', 'Your local note / ' + revisions[note.revision].label), node('blockquote', note.text));
    const button = node('button', 'Inspect the revision this note belongs to');
    button.className = 'quiet-button'; button.type = 'button';
    button.addEventListener('click', () => {
      inspect(note.revision);
      announce('Inspecting ' + revisions[revision].label + '. The note has not moved.');
    });
    card.append(button); notes.append(card);
  }
  const corrections = el('interpretation-records');
  corrections.replaceChildren();
  for (const correction of state.corrections) {
    const card = node('div', ''); card.className = 'return-record';
    card.append(node('p', 'Your local correction / the fictional reading of revision 1'), node('blockquote', correction));
    corrections.append(card);
  }
  const latest = state.choices.at(-1);
  el('return-choice-record').textContent = latest ? 'Your local direction / revision 2: ' + directions[latest.direction] +
    (latest.reason ? ' — ' + latest.reason : '') : 'No direction recorded during this return visit.';
  el('return-choice-history').replaceChildren(...state.choices.slice(0, -1).map(choice => node('li', directions[choice.direction] + (choice.reason ? ' — ' + choice.reason : ''))));
  el('return-next').textContent = latest?.direction === 'reopen' ?
    'Next proposed conversation: return to what the first screen should ask. Keep both earlier approaches beside the new doubt.' : latest?.direction === 'continue' ?
      'Next proposed test: watch someone record a worn jacket and a fraying bag using the revised sketch. No test is booked or result established.' :
      'Still to examine: does “Show the worn part” help someone begin, or leave them with another difficult choice?';
}

for (const id of ['revision-controls','open-return-note','interpretation-form','return-choice-form','return-actions']) el(id).hidden = false;
document.querySelectorAll('input[name="revision"]').forEach(input => input.addEventListener('change', () => { revision = input.value; drawing(); }));
el('inspect-latest')?.addEventListener('click', () => { inspect('damage-2'); announce('Inspecting revision 2. Your unrecorded direction and reason are still in place.'); });
el('open-return-note').addEventListener('click', () => {
  el('open-return-note').hidden = true; anchor = revision;
  el('return-note-anchor').textContent = 'Attached to ' + revisions[anchor].label + '. Switching the inspected sketch will not move this note.';
  el('return-note-editor').hidden = false; el('return-note').value = ''; el('return-note').focus();
});
function closeNote() {
  el('return-note-editor').hidden = true; el('open-return-note').hidden = false; el('open-return-note').focus();
}
el('cancel-return-note').addEventListener('click', () => { closeNote(); announce('Unrecorded note dismissed.'); });
el('return-note-editor').addEventListener('submit', event => {
  event.preventDefault();
  const text = el('return-note').value.trim();
  if (!text) { announce('Add a few words before keeping the note.'); el('return-note').focus(); return; }
  if (record('notes', { revision:anchor, text })) closeNote();
});
el('interpretation-form').addEventListener('submit', event => {
  event.preventDefault();
  const text = el('interpretation').value.trim();
  if (!text) { announce('Write the correction you want to keep.'); el('interpretation').focus(); return; }
  if (record('corrections', text)) el('interpretation').value = '';
});
el('return-choice-form').addEventListener('submit', event => {
  event.preventDefault();
  if (revision !== 'damage-2') { announce('This direction concerns revision 2. Inspect it before keeping a direction.'); (el('inspect-latest') || document.querySelector('input[name="revision"][value="damage-2"]')).focus(); return; }
  const direction = document.querySelector('input[name="return-choice"]:checked')?.value;
  if (!direction) { announce('Choose a direction, or explicitly leave it unresolved.'); document.querySelector('input[name="return-choice"]').focus(); return; }
  if (record('choices', { direction, reason:el('choice-reason').value, revision:'damage-2' })) el('choice-reason').value = '';
});
el('export-return').addEventListener('click', () => {
  const text = 'MOTH & GRAVEL / STAGED RETURN / LOCAL DRAFT\n\n' +
    (el('return-brief-text').textContent ? 'YOUR CARRIED BRIEF (not the fictional specimen)\n' + el('return-brief-text').textContent + '\n\n' : '') +
    'FICTIONAL STUDY: mending notebook. Revision 2 adds a way to show the damage; no usability result.\n\n' +
    (earlier?.version === 1 ? 'FIRST-VISIT LOCAL DRAFT\n' + el('earlier-local-note').textContent + '\n' + el('earlier-local-choice').textContent + '\n\n' : '') +
    'RETURN RECORDS\n' + JSON.stringify(state, null, 2) + '\n\nNEXT PROPOSED STEP\n' + el('return-next').textContent +
    '\n\nNothing sent or agreed. Session-only preview, not a private account.\n';
  const url = URL.createObjectURL(new Blob([text], { type:'text/plain;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = 'moth-and-gravel-return-visit.txt'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000); announce('Return visit prepared for download. Nothing was sent.');
});
el('reset-return').addEventListener('click', () => {
  state = empty(); el('open-return-note').hidden = false;
  try { storage?.removeItem(returnKey); } catch {}
  el('return-note-editor').hidden = true; el('return-note').value = ''; el('interpretation').value = ''; el('choice-reason').value = '';
  document.querySelectorAll('input[name="return-choice"]').forEach(input => { input.checked = false; });
  paint(); announce('Return drafts cleared. Your carried question and first-visit draft remain.');
});
paint();
