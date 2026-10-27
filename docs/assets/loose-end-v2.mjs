import { fields, followups, briefLimit, intents, labels, draftKey, roomKey, normalizeDraft, readDraft, briefText } from './loose-end-model-v2.mjs?v=mending';

const intake = document.getElementById('loose-end');
const status = document.getElementById('draft-status');
function announce(message, source = document.activeElement) {
  status.textContent = message;
  const scope = source?.closest('[data-feedback-scope]');
  const feedback = (scope && [...scope.querySelectorAll('[data-room-feedback]')].find(el=>el.closest('[data-feedback-scope]')===scope)) || intake?.querySelector('#question-guidance');
  if (feedback) {
    feedback.textContent = message;
    if (intake && source?.tagName === 'BUTTON') feedback.scrollIntoView({ block: 'nearest', behavior: 'instant' });
  }
}
function storage() { try { return sessionStorage; } catch { return null; } }
function clearSaved() { const saved = storage(); try { saved?.removeItem(draftKey); saved?.removeItem(roomKey); } catch {} }
// An email link carries a bounded brief; the page keeps the full text for Copy and Download.
const mailAddress = 'hello@mothandgravel.com';
const mailBodyLimit = 1800;
export function briefMail(text, making) {
  const excerpt = (making || '').replace(/\s+/g, ' ').trim();
  const subject = 'A brief for Moth & Gravel' + (excerpt ? ': ' + (excerpt.length > 60 ? excerpt.slice(0, 59).trimEnd() + '…' : excerpt) : '');
  const shortened = text.length > mailBodyLimit;
  const body = shortened ? text.slice(0, mailBodyLimit).trimEnd() + '\n\n[Shortened for email at 1,800 characters. The full brief is still on the question sheet; copy and paste the rest here.]\n' : text;
  const encode = value => encodeURIComponent(value.replace(/\r?\n/g, '\r\n'));
  return { href: 'mailto:' + mailAddress + '?subject=' + encode(subject) + '&body=' + encode(body), shortened };
}
// Private sending is optional. Its config, module and Turnstile load only once the visitor reaches
// the brief, and only when enabled, so the cold load of this page never pays for them.
let enquiry = null;
function loadEnquiry() {
  enquiry ??= fetch(new URL('./enquiry-config.json', import.meta.url), { cache: 'no-cache' })
    .then(response => response.ok ? response.json() : null)
    .then(config => config?.enabled === true ? import('./enquiry.mjs?v=3').then(module => module.start(config)) : null)
    .catch(() => null);
}
function download(text, name) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

if (intake) {
  // Reading context belongs to this page visit, never to the visitor's draft.
  // Keep it available while writing after an explicit thread entrance.
  const threadContext = document.getElementById('signals-context');
  const retainThreadContext = () => {
    if (threadContext && location.hash === '#signals-context') threadContext.dataset.threadEntry = 'true';
  };
  retainThreadContext();
  window.addEventListener('hashchange', retainThreadContext);
  const panels = [...intake.querySelectorAll('[data-step]')];
  const controls = document.getElementById('journey-controls');
  const back = document.getElementById('question-back');
  const next = document.getElementById('question-next');
  const progress = document.getElementById('question-progress');
  const brief = document.getElementById('brief-text');
  let step = 0;
  let generatedBrief = '';
  let copyGeneration = 0;
  const send = document.getElementById('send-brief');
  const sendLimit = document.getElementById('send-limit');
  function updateSend() {
    const mail = briefMail(brief.value, document.getElementById('making').value);
    send.href = mail.href;
    sendLimit.hidden = !mail.shortened;
  }
  brief.addEventListener('input', () => { copyGeneration++; updateSend(); });
  send.addEventListener('click', () => {
    updateSend();
    announce(sendLimit.hidden ? 'Your mail app should open with the brief written in. Send it from there when it reads right.'
      : 'Your mail app should open with the first part of the brief. Copy the brief to paste the rest.', send);
  });
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
    copyGeneration++;
    step = value;
    updateGuides();
    if (record && guidedHistory) {
      try { history.pushState({ mgLooseEnd: true, step }, ''); } catch { guidedHistory = false; }
    }
    panels.forEach((panel, i) => { panel.hidden = i !== step; });
    progress.textContent = `${step + 1} / ${panels.length} — ${panels[step].dataset.title}`;
    const folio = intake.querySelector('[data-question-number]');
    if (folio) folio.textContent = String(step + 1).padStart(2, '0');
    const meter = document.getElementById('question-meter');
    if (meter) { meter.max = panels.length; meter.value = step + 1; }
    intake.querySelectorAll('[data-room-feedback]').forEach(el => { el.textContent = ''; });
    status.textContent = '';
    back.hidden = step === 0;
    next.hidden = step === panels.length - 1;
    next.textContent = step === panels.length - 2 ? 'Gather the brief →' : step === 0 ? 'Start with what you have →' : 'Continue →';
    if (step === panels.length - 1) {
      const generated = briefText(answers());
      if (!generatedBrief || brief.value === generatedBrief) brief.value = generated;
      else if (generated !== generatedBrief) announce('Your brief has edits. They were kept. Use Rebuild from answers if you want to replace them with your updated answers.', brief);
      generatedBrief = generated;
      updateSend();
      loadEnquiry();
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
  document.getElementById('rebuild-brief').addEventListener('click', event => {
    copyGeneration++;
    generatedBrief = briefText(answers()); brief.value = generatedBrief; updateSend();
    announce('Brief rebuilt from your answers, replacing the edits in the brief.', event.currentTarget);
  });
  document.getElementById('download-brief').addEventListener('click', event => { copyGeneration++; download(brief.value, 'moth-and-gravel-loose-end.txt'); announce('Your edited brief was prepared for download. Nothing was sent to the studio.', event.currentTarget); });
  document.getElementById('copy-brief').addEventListener('click', async event => {
    const source = event.currentTarget;
    const text = brief.value;
    const focus = document.activeElement;
    const generation = ++copyGeneration;
    const isCurrent = () => generation === copyGeneration && step === panels.length - 1 && brief.value === text && document.activeElement === focus;
    try {
      await navigator.clipboard.writeText(text);
      if (isCurrent()) announce('Brief copied. Nothing was sent to the studio.', source);
    } catch {
      if (!isCurrent()) return;
      brief.focus({ preventScroll: true }); brief.select();
      announce('Select and copy the brief here, or use Download.', brief);
      // Keep the selected words and their recovery instruction together, even
      // when a long brief puts the delivery controls below another viewport.
      const recovery = brief.closest('.brief-document')?.querySelector('[data-room-feedback]');
      (recovery || brief).scrollIntoView({ block: 'end', behavior: 'instant' });
    }
  });
  document.getElementById('carry-question').addEventListener('click', event => {
    copyGeneration++;
    try {
      const saved = storage(); if (!saved) throw new Error('Storage unavailable');
      saved.setItem(draftKey, JSON.stringify({ version: 1, answers: answers(), brief: brief.value.slice(0, briefLimit) }));
      // New handoff replaces the room's previous experimental annotations.
      saved.removeItem(roomKey);
      location.assign('../workbench/#your-question');
    } catch { announce('This browser cannot carry a draft between pages. Download your brief, or open the example workbench below.', event.currentTarget); }
  });
  document.getElementById('clear-draft').addEventListener('click', event => {
    clearSaved();
    for (const key of fields) if (key !== 'intent') document.getElementById(key).value = '';
    intake.querySelectorAll('[data-followup]').forEach(el => { el.open = false; });
    intake.querySelectorAll('input[name="intent"]').forEach(el => { el.checked = el.value === intents[3]; });
    document.getElementById('making').removeAttribute('aria-invalid'); document.getElementById('making-error').hidden = true;
    brief.value = ''; generatedBrief = ''; show(0, false);
    event.currentTarget.focus({ preventScroll: true });
    announce('Your answers and workbench draft were cleared from this tab. Downloaded copies remain yours.', event.currentTarget);
  });
  controls.hidden = false;
  document.querySelectorAll('[data-enhance]').forEach(el => { el.hidden = false; });
  const previewFallback = intake.querySelector('.question-preview-fallback');
  if (previewFallback) previewFallback.hidden = true;
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
  let state = { surface: 'item', note: '', noteSurface: 'item', choice: '' };
  try {
    const value = JSON.parse(saved?.getItem(roomKey));
    if (value?.version === 1) state = { surface: value.surface === 'damage' ? 'damage' : 'item',
      note: typeof value.note === 'string' ? value.note.slice(0, 1800) : '',
      noteSurface: value.noteSurface === 'damage' ? 'damage' : 'item',
      choice: ['item', 'damage', 'open'].includes(value.choice) ? value.choice : '' };
  } catch {}
  function persist() {
    try { if (!saved) throw new Error('Unavailable'); saved.setItem(roomKey, JSON.stringify({ version: 1, ...state })); return true; }
    catch { return false; }
  }
  const surfaces = { item: 'Start with the object', damage: 'Start with the damage', open: 'Keep the question open' };
  function paint(updateChoice = false) {
    room.querySelectorAll('input[name="surface"]').forEach(el => { el.checked = el.value === state.surface; });
    room.querySelectorAll('[data-surface]').forEach(el => { el.hidden = el.dataset.surface !== state.surface; });
    document.getElementById('artifact-caption').textContent = 'Illustrative sketch · ' + surfaces[state.surface] + '. The drawn controls are not interactive.';
    if (updateChoice) room.querySelectorAll('input[name="choice"]').forEach(el => { el.checked = el.value === state.choice; });
    document.getElementById('recorded-choice').textContent = state.choice ? 'Your draft choice: ' + surfaces[state.choice] + '. The studio has not received this.' : 'No draft choice recorded.';
    document.getElementById('annotation-record').textContent = state.note ? surfaces[state.noteSurface] + ': ' + state.note : 'No observation pinned yet.';
    const noteLink = document.getElementById('inspect-note-surface');
    if (noteLink) noteLink.hidden = !state.note;
    const noteMark = document.getElementById('inspection-note-mark');
    if (noteMark) {
      const matches = Boolean(state.note) && state.noteSurface === state.surface;
      noteMark.dataset.visible = String(matches);
      noteMark.setAttribute('aria-hidden', String(!matches));
    }
  }
  document.getElementById('inspect-note-surface')?.addEventListener('click', () => {
    state.surface = state.noteSurface;
    paint();
    const target = room.querySelector(`input[name="surface"][value="${state.surface}"]`);
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: 'center', behavior: 'instant' });
  });
  room.querySelectorAll('input[name="surface"]').forEach(el => el.addEventListener('change', () => { state.surface = el.value; paint(); }));
  let annotationSurface = state.surface;
  document.getElementById('mark-wrong').addEventListener('click', () => {
    const panel = document.getElementById('annotation-panel'); panel.hidden = false;
    annotationSurface = state.surface;
    document.getElementById('annotation').value = state.note;
    document.getElementById('annotation-context').textContent = 'Attached to: ' + surfaces[annotationSurface] + '. Changing the inspected sketch will not move this note.';
    document.getElementById('mark-wrong').hidden = true;
    document.getElementById('annotation').focus();
  });
  document.getElementById('pin-observation').addEventListener('click', () => {
    const text = document.getElementById('annotation').value.trim();
    if (!text) { announce('Write what caught your attention, even if you cannot explain it yet.'); document.getElementById('annotation').focus(); return; }
    state.note = text; state.noteSurface = annotationSurface;
    const kept = persist(); paint();
    document.getElementById('annotation-panel').hidden = true;
    document.getElementById('mark-wrong').hidden = false;
    document.getElementById('mark-wrong').focus();
    announce(kept ? 'Observation pinned in this tab. Nothing was sent.' : 'Observation pinned for this visit only. Storage is unavailable; download it to keep it.');
  });
  document.getElementById('cancel-observation').addEventListener('click', () => { document.getElementById('annotation-panel').hidden = true; document.getElementById('mark-wrong').hidden = false; document.getElementById('mark-wrong').focus(); });
  document.getElementById('record-choice').addEventListener('click', () => {
    const choice = room.querySelector('input[name="choice"]:checked');
    if (!choice) { announce('Choose an approach, or keep the question open.'); room.querySelector('input[name="choice"]').focus(); return; }
    state.choice = choice.value; const kept = persist(); paint(true);
    announce(kept ? 'Draft choice recorded in this tab. Nothing was sent.' : 'Draft choice recorded for this visit only. Download it to keep it.');
  });
  document.getElementById('download-room').addEventListener('click', () => {
    download((draft ? 'YOUR CARRIED BRIEF — SEPARATE FROM THE FICTIONAL STUDY\n\n' + document.getElementById('carried-brief').textContent + '\n\n' : '') +
      'WORKBENCH EXAMPLE — LOCAL DRAFT\n\nExample question: How do you begin a repair note?\nObservation: ' +
      (state.note ? surfaces[state.noteSurface] + ': ' + state.note : 'Still open.') + '\nDraft choice: ' + (surfaces[state.choice] || 'Still open.') + '\n\nNothing has been sent to the studio.\n', 'moth-and-gravel-workbench-draft.txt');
    announce('Workbench draft prepared for download. Nothing was sent.');
  });
  document.getElementById('clear-room').addEventListener('click', () => {
    clearSaved(); state = { surface: 'item', note: '', noteSurface: 'item', choice: '' }; paint(true);
    document.getElementById('your-question').hidden = true; document.getElementById('your-question').querySelector('dl').replaceChildren();
    document.getElementById('carried-brief').textContent = ''; document.getElementById('original-question').textContent = ''; document.getElementById('annotation-panel').hidden = true;
    document.getElementById('annotation').value = ''; document.getElementById('mark-wrong').hidden = false;
    announce('Your question, observation and draft choice were cleared from this tab.');
  });
  document.querySelectorAll('[data-enhance]').forEach(el => { el.hidden = false; });
  paint(true);
}
