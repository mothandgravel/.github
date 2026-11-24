import { briefLimit, briefText, draftKey, fields, labels, normalizeDraft, roomKey } from './loose-end-model-v2.mjs?v=mending';
import { briefSections, emailHref, formatBrief, updateBrief } from './brief-builder-model.mjs';

const intake = document.getElementById('loose-end');
const preview = document.getElementById('brief-text');
const send = document.getElementById('send-brief');
const limit = document.getElementById('send-limit');
const status = document.getElementById('draft-status');
const panels = [...intake.querySelectorAll('[data-step]')];
const steps = [...intake.querySelectorAll('[data-brief-step]')];
const back = document.getElementById('question-back');
const next = document.getElementById('question-next');
const clearArtifact = document.getElementById('clear-artifact');
const groups = ['domain', 'friction', 'artifact', 'ground'];
const textInputs = ['making', 'difficulty', 'constraints'];
const restoredText = new Map();

function storage() {
  try { return sessionStorage; } catch { return null; }
}

function readSaved() {
  try {
    const draft = JSON.parse(storage()?.getItem(draftKey));
    return draft?.version === 1 ? draft : null;
  } catch {
    return null;
  }
}

function values() {
  return Object.fromEntries([
    ...groups.map(name => [name, [...intake.querySelectorAll('input[name="' + name + '"]:checked')].map(input => input.value)]),
    ...textInputs.map(id => {
      const value = document.getElementById(id).value;
      const original = restoredText.get(id);
      return [id, original?.replace(/\n/g, ' ') === value ? original : value];
    }),
  ]);
}

function restore(saved) {
  const answers = saved?.builder || saved?.answers;
  if (!answers) return;
  for (const id of textInputs) {
    if (typeof answers[id] !== 'string') continue;
    const input = document.getElementById(id);
    const value = answers[id].slice(0, 1800).replace(/\r\n?/g, '\n');
    input.value = input.type === 'text' ? value.replace(/\n/g, ' ') : value;
    // The older form allowed paragraphs in fields that are now single-line.
    if (input.value !== value) restoredText.set(id, value);
  }
  for (const group of groups) {
    const choices = answers[group];
    if (!Array.isArray(choices)) continue;
    for (const input of intake.querySelectorAll('input[name="' + group + '"]')) {
      input.checked = choices.includes(input.value);
    }
  }
}

function updateActions() {
  send.href = emailHref(preview.value);
  limit.hidden = send.href.length <= 1800;
  clearArtifact.hidden = !intake.querySelector('input[name="artifact"]:checked');
}

function initialBrief(saved, sections) {
  const edited = typeof saved?.brief === 'string' ? saved.brief.slice(0, briefLimit) : null;
  if (!saved || saved.builder) return edited ?? formatBrief(sections);
  if (edited !== null && edited !== briefText(saved.answers)) return edited;
  // Migrate generated legacy drafts while keeping answers that have no new control.
  const answers = normalizeDraft(saved.answers);
  const context = fields.flatMap((key, index) => {
    if (textInputs.includes(key) || !saved.answers?.[key] || !answers[key]) return [];
    return ['## ' + labels[index] + '\n' + answers[key]];
  });
  return formatBrief([...sections, ...context]);
}

let saved = readSaved();
restore(saved);
let sections = briefSections(values());
preview.value = initialBrief(saved, sections);

window.addEventListener('pageshow', () => {
  // History traversal can restore form values after the module and pageshow run.
  setTimeout(() => {
    sections = briefSections(values());
    updateActions();
  }, 0);
});

let copyRequest = 0;
function refresh() {
  copyRequest++;
  const updated = briefSections(values());
  const scroll = preview.scrollTop;
  preview.value = updateBrief(preview.value, sections, updated);
  preview.scrollTop = scroll;
  sections = updated;
  status.textContent = '';
  updateActions();
}

intake.querySelector('.brief-controls').addEventListener('input', event => {
  restoredText.delete(event.target.id);
  refresh();
});
preview.addEventListener('input', () => {
  copyRequest++;
  status.textContent = '';
  updateActions();
});
clearArtifact.addEventListener('click', () => {
  const selected = intake.querySelector('input[name="artifact"]:checked');
  if (selected) {
    selected.checked = false;
    selected.focus();
  }
  refresh();
});

let current = 0;
function showStep(index, focus = false) {
  current = index;
  panels.forEach((panel, i) => { panel.hidden = i !== index; });
  steps.forEach((button, i) => {
    if (i === index) button.setAttribute('aria-current', 'step');
    else button.removeAttribute('aria-current');
  });
  back.hidden = index === 0;
  next.textContent = index === panels.length - 1 ? 'Go to the brief' : 'Next step';
  if (focus) panels[index].querySelector('legend').focus();
}

function switchStep(index) {
  if (index === current) return;
  try { history.pushState({ mgBriefStep: index }, ''); } catch {}
  showStep(index, true);
}

function restoredStep(state) {
  const index = state?.mgBriefStep;
  return Number.isInteger(index) && index >= 0 && index < panels.length ? index : null;
}

function rememberStep() {
  try { history.replaceState({ ...history.state, mgBriefStep: current }, ''); } catch {}
}

steps.forEach((button, index) => button.addEventListener('click', () => switchStep(index)));
back.addEventListener('click', () => switchStep(current - 1));
next.addEventListener('click', () => {
  if (current === panels.length - 1) preview.focus();
  else switchStep(current + 1);
});
window.addEventListener('popstate', event => {
  const step = restoredStep(event.state);
  if (step !== null) showStep(step);
});

function retainThread() {
  if (location.hash === '#signals-context') {
    document.getElementById('signals-context').dataset.threadEntry = 'true';
  }
}
retainThread();
window.addEventListener('hashchange', () => {
  retainThread();
  if (restoredStep(history.state) === null) rememberStep();
});

document.getElementById('copy-brief').addEventListener('click', async () => {
  const revision = ++copyRequest;
  const focus = document.activeElement;
  const currentCopy = () => copyRequest === revision && document.activeElement === focus;
  try {
    await navigator.clipboard.writeText(preview.value);
    if (currentCopy()) status.textContent = 'Brief copied.';
  } catch {
    if (!currentCopy()) return;
    preview.focus();
    preview.select();
    status.textContent = 'Copying is unavailable here. The full brief is selected for you to copy.';
    status.scrollIntoView({ block: 'nearest' });
  }
});

document.getElementById('download-brief').addEventListener('click', () => {
  copyRequest++;
  const file = URL.createObjectURL(new Blob([preview.value], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = file;
  link.download = 'moth-and-gravel-brief.md';
  link.click();
  setTimeout(() => URL.revokeObjectURL(file), 1000);
  status.textContent = 'Brief prepared for download.';
});

document.getElementById('carry-question').addEventListener('click', () => {
  copyRequest++;
  const builder = values();
  const text = preview.value;
  if (text.length > briefLimit) {
    status.textContent = 'This brief is too long to carry into the example workbench. Copy or download it to keep the full text.';
    return;
  }
  const making = builder.making.trim() || builder.domain.join(', ') || builder.difficulty.trim() ||
    builder.artifact[0] || builder.constraints.trim() || builder.ground.join(', ') ||
    (text.trim() ? 'Editable brief' : '');
  if (!making && !saved) {
    location.assign('../workbench/');
    return;
  }
  const answers = normalizeDraft({
    ...saved?.answers,
    making,
    difficulty: [...builder.friction, builder.difficulty].filter(Boolean).join('\n'),
    constraints: [...builder.ground, builder.constraints].filter(Boolean).join('\n'),
    outcome: builder.artifact[0] || (saved?.builder ? '' : saved?.answers?.outcome),
  });
  try {
    const session = storage();
    if (!session) throw new Error('Storage unavailable');
    session.setItem(draftKey, JSON.stringify({ version: 1, answers, brief: text, builder }));
    session.removeItem(roomKey);
    location.assign('../workbench/#your-question');
  } catch {
    status.textContent = 'This browser cannot carry the draft to another page. Copy or download it here.';
    document.getElementById('workbench-fallback').hidden = false;
  }
});

document.getElementById('clear-draft').addEventListener('click', () => {
  copyRequest++;
  for (const input of intake.querySelectorAll('.brief-controls input, .brief-controls textarea')) {
    if (input.type === 'radio' || input.type === 'checkbox') input.checked = false;
    else input.value = '';
  }
  try {
    const session = storage();
    session?.removeItem(draftKey);
    session?.removeItem(roomKey);
  } catch {}
  saved = null;
  restoredText.clear();
  sections = briefSections(values());
  preview.value = '';
  showStep(0);
  rememberStep();
  updateActions();
  status.textContent = 'This tab’s brief was cleared.';
});

for (const id of ['journey-controls', 'brief-navigation', 'copy-brief', 'download-brief', 'carry-question', 'clear-draft']) {
  document.getElementById(id).hidden = false;
}
document.getElementById('brief-fallback').hidden = true;
document.getElementById('workbench-fallback').hidden = true;
showStep(restoredStep(history.state) ?? 0);
rememberStep();
updateActions();
