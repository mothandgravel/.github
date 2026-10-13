import { fields, followups, briefLimit, intents, labels, draftKey, roomKey, normalizeDraft, readDraft, briefText } from './loose-end-model-v2.mjs';

const intake = document.getElementById('loose-end');
const status = document.getElementById('draft-status');
function announce(message) { status.textContent = message; }
function storage() { try { return sessionStorage; } catch { return null; } }
function clearSaved() { const saved = storage(); try { saved?.removeItem(draftKey); saved?.removeItem(roomKey); } catch {} }
function download(text, name) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

if (intake) {
  const panels = [...intake.querySelectorAll('[data-step]')];
  const controls = document.getElementById('journey-controls');
  const back = document.getElementById('question-back');
  const next = document.getElementById('question-next');
  const progress = document.getElementById('question-progress');
  const brief = document.getElementById('brief-text');
  let step = 0;
  let generatedBrief = '';
  let guidedHistory = true;
  try { history.replaceState({ mgLooseEnd: true, step: 0 }, ''); } catch { guidedHistory = false; }
  const answers = () => normalizeDraft(Object.fromEntries(fields.map(key => [key, key === 'intent' ?
    intake.querySelector('input[name="intent"]:checked')?.value : document.getElementById(key).value])));
  const saved = readDraft(storage());
  if (saved) {
    for (const key of fields) {
      if (key === 'intent') intake.querySelectorAll('input[name="intent"]').forEach(el => { el.checked = el.value === saved[key]; });
      else document.getElementById(key).value = saved[key];
    }
    generatedBrief = briefText(saved);
    try {
      const edited = JSON.parse(storage().getItem(draftKey)).brief;
      brief.value = typeof edited === 'string' ? edited.slice(0, briefLimit) : generatedBrief;
    } catch { brief.value = generatedBrief; }
  }
  for (const key of followups) if (document.getElementById(key).value) document.getElementById(key).closest('details').open = true;
  const guides = [
    ['Describe the possibility you want to explore. You do not need a finished specification.', 'What might stop this being useful? A worry or unanswered question is enough.', 'What would let you decide whether the idea is worth taking further?'],
    ['Tell us what should happen and what happens instead.', 'Describe the moment where it breaks down, and what someone tries next.', 'What could someone do reliably if this difficulty were resolved?'],
    ['Tell us what you are weighing up, or what you would like another pair of eyes on.', 'What would you like us to challenge or inspect?', 'What would help: clearer trade-offs, a testable next step, or a second opinion?'],
    ['A rough description will do. Tell us what caught your attention.', 'An awkward moment is often more useful than a list of features.', 'Tell us what someone could do, understand or stop worrying about.'],
  ];
  function updateGuides() {
    const guide = guides[intents.indexOf(answers().intent)];
    ['making-help', 'difficulty-help', 'outcome-help'].forEach((id, i) => { document.getElementById(id).textContent = guide[i]; });
  }
  function validate() {
    const making = document.getElementById('making');
    if (making.value.trim()) { making.removeAttribute('aria-invalid'); document.getElementById('making-error').hidden = true; return true; }
    making.setAttribute('aria-invalid', 'true'); document.getElementById('making-error').hidden = false; making.focus(); return false;
  }
  function show(value, focus = true, record = true) {
    step = value;
    updateGuides();
    if (record && guidedHistory) {
      try { history.pushState({ mgLooseEnd: true, step }, ''); } catch { guidedHistory = false; }
    }
    panels.forEach((panel, i) => { panel.hidden = i !== step; });
    progress.textContent = `${step + 1} / ${panels.length} — ${panels[step].dataset.title}`;
    back.hidden = step === 0;
    next.hidden = step === panels.length - 1;
    next.textContent = step === panels.length - 2 ? 'Gather the brief →' : step === 0 ? 'Start with what you have →' : 'Continue →';
    if (step === panels.length - 1) {
      const generated = briefText(answers());
      if (!generatedBrief || brief.value === generatedBrief) brief.value = generated;
      else if (generated !== generatedBrief) announce('Your brief has edits. They were kept. Use Rebuild from answers if you want to replace them with your updated answers.');
      generatedBrief = generated;
    }
    if (focus) panels[step].querySelector('legend, h2').focus();
  }
  window.addEventListener('popstate', event => {
    const value = event.state;
    if (value?.mgLooseEnd === true && Number.isInteger(value.step) && value.step >= 0 && value.step < panels.length) {
      // Old browser entries must not bypass the required question after Clear.
      const destination = value.step > 1 && !document.getElementById('making').value.trim() ? 1 : value.step;
      show(destination, true, false);
      if (destination !== value.step) {
        try { history.replaceState({ mgLooseEnd: true, step: destination }, ''); } catch {}
        announce('The draft is empty. Add a few words to give it a starting point.');
      }
    }
  });
  back.addEventListener('click', () => { if (guidedHistory) history.back(); else show(step - 1); });
  next.addEventListener('click', () => { if (step === 1 && !validate()) return; show(step + 1); });
  document.getElementById('edit-answers').addEventListener('click', () => { if (guidedHistory) history.go(1 - step); else show(1); });
  document.getElementById('rebuild-brief').addEventListener('click', () => {
    generatedBrief = briefText(answers()); brief.value = generatedBrief;
    announce('Brief rebuilt from your answers, replacing the edits in the brief.');
  });
  document.getElementById('download-brief').addEventListener('click', () => { download(brief.value, 'moth-and-gravel-loose-end.txt'); announce('Your edited brief was prepared for download. Downloading does not submit an enquiry.'); });
  document.getElementById('copy-brief').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(brief.value); announce('Brief copied. Copying does not submit an enquiry.'); }
    catch { brief.focus(); brief.select(); announce('Select and copy the brief here, or use Download.'); }
  });
  document.getElementById('carry-question').addEventListener('click', () => {
    try {
      const saved = storage(); if (!saved) throw new Error('Storage unavailable');
      saved.setItem(draftKey, JSON.stringify({ version: 1, answers: answers(), brief: brief.value.slice(0, briefLimit) }));
      // New handoff replaces the room's previous experimental annotations.
      saved.removeItem(roomKey);
      location.assign('../workbench/');
    } catch { announce('This browser cannot carry a draft between pages. Download your brief, or open the example workbench below.'); }
  });
  document.getElementById('clear-draft').addEventListener('click', () => {
    clearSaved();
    for (const key of fields) if (key !== 'intent') document.getElementById(key).value = '';
    intake.querySelectorAll('[data-followup]').forEach(el => { el.open = false; });
    intake.querySelectorAll('input[name="intent"]').forEach(el => { el.checked = el.value === intents[3]; });
    document.getElementById('making').removeAttribute('aria-invalid'); document.getElementById('making-error').hidden = true;
    brief.value = ''; generatedBrief = ''; show(0); announce('Your answers and workbench draft were cleared from this tab. Downloaded copies remain yours.');
  });
  controls.hidden = false;
  document.querySelectorAll('[data-enhance]').forEach(el => { el.hidden = false; });
  show(0, false, false);
}

const room = document.getElementById('workbench-preview');
if (room) {
  const saved = storage();
  const draft = readDraft(saved);
  if (draft) {
    const original = document.getElementById('your-question'); original.hidden = false;
    document.getElementById('original-question').textContent = draft.making;
    const list = original.querySelector('dl');
    fields.forEach((key, i) => {
      if (followups.includes(key) && !draft[key]) return;
      const dt = document.createElement('dt'); dt.textContent = labels[i];
      const dd = document.createElement('dd'); dd.textContent = draft[key] || 'Still open.'; list.append(dt, dd);
    });
    let edited = null; try { edited = JSON.parse(saved.getItem(draftKey)).brief; } catch {}
    document.getElementById('carried-brief').textContent = typeof edited === 'string' ? edited.slice(0, briefLimit) : briefText(draft);
  }
  let state = { surface: 'host', note: '', noteSurface: 'host', choice: '' };
  try {
    const value = JSON.parse(saved?.getItem(roomKey));
    if (value?.version === 1) state = { surface: value.surface === 'reason' ? 'reason' : 'host',
      note: typeof value.note === 'string' ? value.note.slice(0, 1800) : '',
      noteSurface: value.noteSurface === 'reason' ? 'reason' : 'host',
      choice: ['host', 'reason', 'open'].includes(value.choice) ? value.choice : '' };
  } catch {}
  function persist() {
    try { if (!saved) throw new Error('Unavailable'); saved.setItem(roomKey, JSON.stringify({ version: 1, ...state })); return true; }
    catch { return false; }
  }
  const surfaces = { host: 'Ask for the host first', reason: 'Ask for the reason first', open: 'Keep the question open' };
  function paint(updateChoice = false) {
    room.querySelectorAll('input[name="surface"]').forEach(el => { el.checked = el.value === state.surface; });
    room.querySelectorAll('[data-surface]').forEach(el => { el.hidden = el.dataset.surface !== state.surface; });
    document.getElementById('artifact-caption').textContent = 'Example screen · ' + surfaces[state.surface];
    if (updateChoice) room.querySelectorAll('input[name="choice"]').forEach(el => { el.checked = el.value === state.choice; });
    document.getElementById('recorded-choice').textContent = state.choice ? 'Your draft choice: ' + surfaces[state.choice] + '. The studio has not received this.' : 'No draft choice recorded.';
    document.getElementById('annotation-record').textContent = state.note ? surfaces[state.noteSurface] + ': ' + state.note : 'No observation pinned yet.';
  }
  room.querySelectorAll('input[name="surface"]').forEach(el => el.addEventListener('change', () => { state.surface = el.value; paint(); }));
  let annotationSurface = state.surface;
  document.getElementById('mark-wrong').addEventListener('click', () => {
    const panel = document.getElementById('annotation-panel'); panel.hidden = false;
    annotationSurface = state.surface;
    document.getElementById('annotation').value = state.note;
    document.getElementById('annotation-context').textContent = 'Looking at: ' + surfaces[state.surface];
    document.getElementById('annotation').focus();
  });
  document.getElementById('pin-observation').addEventListener('click', () => {
    const text = document.getElementById('annotation').value.trim();
    if (!text) { announce('Write what caught your attention, even if you cannot explain it yet.'); document.getElementById('annotation').focus(); return; }
    state.note = text; state.noteSurface = annotationSurface;
    const kept = persist(); paint();
    document.getElementById('annotation-panel').hidden = true;
    document.getElementById('mark-wrong').focus();
    announce(kept ? 'Observation pinned in this tab. Nothing was sent.' : 'Observation pinned for this visit only. Storage is unavailable; download it to keep it.');
  });
  document.getElementById('cancel-observation').addEventListener('click', () => { document.getElementById('annotation-panel').hidden = true; document.getElementById('mark-wrong').focus(); });
  document.getElementById('record-choice').addEventListener('click', () => {
    const choice = room.querySelector('input[name="choice"]:checked');
    if (!choice) { announce('Choose an approach, or keep the question open.'); room.querySelector('input[name="choice"]').focus(); return; }
    state.choice = choice.value; const kept = persist(); paint(true);
    announce(kept ? 'Draft choice recorded in this tab. Nothing was sent.' : 'Draft choice recorded for this visit only. Download it to keep it.');
  });
  document.getElementById('download-room').addEventListener('click', () => {
    download((draft ? document.getElementById('carried-brief').textContent + '\n\n' : '') +
      'WORKBENCH EXAMPLE — LOCAL DRAFT\n\nExample question: Where should a visitor check-in begin?\nObservation: ' +
      (state.note ? surfaces[state.noteSurface] + ': ' + state.note : 'Still open.') + '\nDraft choice: ' + (surfaces[state.choice] || 'Still open.') + '\n\nNothing has been sent to the studio.\n', 'moth-and-gravel-workbench-draft.txt');
    announce('Workbench draft prepared for download. Nothing was sent.');
  });
  document.getElementById('clear-room').addEventListener('click', () => {
    clearSaved(); state = { surface: 'host', note: '', noteSurface: 'host', choice: '' }; paint(true);
    document.getElementById('your-question').hidden = true; document.getElementById('your-question').querySelector('dl').replaceChildren();
    document.getElementById('carried-brief').textContent = ''; document.getElementById('original-question').textContent = ''; document.getElementById('annotation-panel').hidden = true;
    document.getElementById('annotation').value = '';
    announce('Your question, observation and draft choice were cleared from this tab.');
  });
  document.querySelectorAll('[data-enhance]').forEach(el => { el.hidden = false; });
  paint(true);
}
