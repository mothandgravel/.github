import { DEFAULT_RATE, playbackRate, stepIndex, cueAt } from './field-listen-model.mjs';

function setupPlayer(root) {
  const audio = root.querySelector('audio');
  const speed = root.querySelector('[data-audio-speed]');
  const status = root.querySelector('[data-audio-status]');
  const applyRate = () => { audio.defaultPlaybackRate = playbackRate(speed.value); audio.playbackRate = playbackRate(speed.value); };
  speed.value = String(DEFAULT_RATE); applyRate();
  speed.closest('label').hidden = false;
  const follow = root.querySelector('[data-audio-follow]');
  if (follow) root.querySelector('[data-audio-follow-control]').hidden = false;
  speed.addEventListener('change', applyRate);
  audio.addEventListener('loadedmetadata', applyRate);
  const play = async () => {
    for (const other of document.querySelectorAll('audio')) if (other !== audio) other.pause();
    try { await audio.play(); status.textContent = ''; }
    catch { status.textContent = 'Ready to listen. Press play on the audio controls.'; }
  };
  audio.addEventListener('play', () => {
    for (const other of document.querySelectorAll('audio')) if (other !== audio) other.pause();
  });
  audio.addEventListener('error', () => { status.textContent = 'Audio could not load. Try again, or download the recording.'; });
  root.addEventListener('click', event => {
    const link = event.target.closest('[data-audio-seek]');
    if (!link || !root.contains(link)) return;
    event.preventDefault(); audio.currentTime = Number(link.dataset.audioSeek); play();
  });
  const paragraphs = [...root.querySelectorAll('[data-cue-start]')];
  const cues = paragraphs.map(p => ({start:Number(p.dataset.cueStart), end:Number(p.dataset.cueEnd)}));
  let active = -1;
  audio.addEventListener('timeupdate', () => {
    const index = cueAt(cues, audio.currentTime);
    if (active === index) return;
    if (active >= 0) paragraphs[active].removeAttribute('aria-current');
    active = index;
    if (index >= 0) {
      const paragraph = paragraphs[index]; paragraph.setAttribute('aria-current', 'true');
      const container = paragraph.closest('.audio-cues');
      if (follow?.checked && container?.clientHeight) {
        const current = paragraph.getBoundingClientRect(), bounds = container.getBoundingClientRect();
        if (current.top < bounds.top) container.scrollTop += current.top - bounds.top;
        else if (current.bottom > bounds.bottom) container.scrollTop += current.bottom - bounds.bottom;
      }
    }
  });
  return { audio, play, status, applyRate };
}

for (const root of document.querySelectorAll('[data-note-player]')) setupPlayer(root);
for (const root of document.querySelectorAll('[data-archive-player]')) {
  try {
    const entries = JSON.parse(root.querySelector('[data-queue-data]').textContent);
    if (!Array.isArray(entries) || !entries.length) continue;
    const { audio, play, status, applyRate } = setupPlayer(root);
    const title = root.querySelector('[data-queue-title]');
    const previous = root.querySelector('[data-queue-previous]');
    const next = root.querySelector('[data-queue-next]');
    const auto = root.querySelector('[data-queue-auto]');
    const transcript = root.querySelector('[data-queue-transcript]');
    const buttons = [...root.querySelectorAll('[data-queue-index]')];
    let index = 0;
    function select(target, start = true) {
      index = target;
      const entry = entries[index];
      title.textContent = entry.title; audio.setAttribute('aria-label', entry.title);
      transcript.href = entry.transcript;
      previous.disabled = index === 0; next.disabled = index === entries.length - 1;
      for (const [position, button] of buttons.entries()) {
        if (position === index) button.setAttribute('aria-current', 'true');
        else button.removeAttribute('aria-current');
      }
      if (audio.getAttribute('src') !== entry.audio) {
        audio.src = entry.audio;
        audio.querySelector('track').src = entry.vtt;
        audio.load(); applyRate();
      }
      if (start) play();
    }
    for (const button of buttons) button.addEventListener('click', () => select(Number(button.dataset.queueIndex)));
    previous.addEventListener('click', () => select(stepIndex(index, -1, entries.length)));
    next.addEventListener('click', () => select(stepIndex(index, 1, entries.length)));
    root.querySelector('[data-queue-start]').addEventListener('click', () => select(index));
    audio.addEventListener('ended', () => {
      if (index === entries.length - 1) status.textContent = 'You have reached the end of the archive.';
      else if (auto.checked) select(index + 1);
      else status.textContent = 'Note finished. Select Next when you are ready.';
    });
    select(0, false);
    for (const control of root.querySelectorAll('[data-queue-index],[data-queue-start],[data-queue-previous],[data-queue-next],[data-queue-auto-label]')) control.hidden = false;
    root.classList.add('has-audio-queue');
  } catch { /* Static audio and article links stay usable when enhancement fails. */ }
}
