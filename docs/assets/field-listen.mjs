import { DEFAULT_RATE, playbackRate, stepIndex, cueAt } from './field-listen-model.mjs';

function setupPlayer(root) {
  const audio = root.querySelector('audio');
  const speed = root.querySelector('[data-audio-speed]');
  const status = root.querySelector('[data-audio-status]');
  const applyRate = () => {
    const nativeOption = speed.selectedOptions[0]?.hasAttribute('data-native-rate');
    const rate = nativeOption ? Number(speed.value) : playbackRate(speed.value);
    const validRate = Number.isFinite(rate) && rate > 0 && rate <= 16 ? rate : DEFAULT_RATE;
    audio.defaultPlaybackRate = validRate; audio.playbackRate = validRate;
  };
  speed.value = String(DEFAULT_RATE); applyRate();
  audio.addEventListener('ratechange', () => {
    const value = String(audio.playbackRate);
    if (![...speed.options].some(option => option.value === value)) {
      speed.querySelector('[data-native-rate]')?.remove();
      const option = document.createElement('option'); option.value = value;
      option.textContent = value + '×'; option.setAttribute('data-native-rate', ''); speed.append(option);
    }
    speed.value = value;
  });
  speed.closest('label').hidden = false;
  root.querySelector('[data-audio-default-speed]')?.removeAttribute('hidden');
  const follow = root.querySelector('[data-audio-follow]');
  if (follow) root.querySelector('[data-audio-follow-control]').hidden = false;
  speed.addEventListener('change', applyRate);
  audio.addEventListener('loadedmetadata', applyRate);
  const session = root.matches('details') ? root : root.querySelector('[data-audio-session]');
  session?.addEventListener('toggle', () => {
    if (!session.open) { audio.pause(); return; }
    if (audio.preload === 'none' && audio.readyState === 0 && audio.paused) {
      audio.preload = 'metadata'; audio.load();
    }
  });
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
  let paragraphs = [], cues = [], active = -1;
  function refreshTranscript() {
    if (active >= 0) paragraphs[active]?.removeAttribute('aria-current');
    paragraphs = [...root.querySelectorAll('[data-cue-start]')];
    cues = paragraphs.map(p => ({start:Number(p.dataset.cueStart), end:Number(p.dataset.cueEnd)}));
    active = -1;
  }
  refreshTranscript();
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
  return { audio, play, status, applyRate, refreshTranscript };
}

for (const root of document.querySelectorAll('[data-note-player]')) setupPlayer(root);
for (const root of document.querySelectorAll('[data-archive-player]')) {
  try {
    const entries = JSON.parse(root.querySelector('[data-queue-data]').textContent);
    if (!Array.isArray(entries) || !entries.length) continue;
    const { audio, play, status, applyRate, refreshTranscript } = setupPlayer(root);
    const title = root.querySelector('[data-queue-title]');
    const previous = root.querySelector('[data-queue-previous]');
    const next = root.querySelector('[data-queue-next]');
    const auto = root.querySelector('[data-queue-auto]');
    const transcript = root.querySelector('[data-queue-transcript]');
    const context = root.querySelector('[data-queue-context]');
    const entryLink = root.querySelector('[data-queue-entry-link]');
    const startButton = root.querySelector('[data-queue-start]');
    const transcriptPanel = root.querySelector('[data-queue-transcript-panel]');
    const cueContainer = root.querySelector('[data-queue-cues]');
    const transcriptCache = new Map();
    const buttons = [...root.querySelectorAll('[data-queue-index]')];
    let index = 0, transcriptRequest = 0;
    const clock = seconds => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
    function transcriptMessage(text) {
      const paragraph = document.createElement('p'); paragraph.className = 'audio-caption-note';
      paragraph.setAttribute('role', 'status'); cueContainer.setAttribute('aria-busy', 'false');
      paragraph.textContent = text; cueContainer.replaceChildren(paragraph); refreshTranscript();
    }
    async function loadTranscript() {
      const request = ++transcriptRequest, entry = entries[index];
      if (!transcriptPanel.open) return;
      transcriptMessage('Loading the transcript…');
      cueContainer.setAttribute('aria-busy', 'true');
      try {
        let recognized = transcriptCache.get(entry.id);
        if (!recognized) {
          const response = await fetch(entry.cues);
          if (!response.ok) throw Error('Transcript unavailable');
          recognized = await response.json();
          if (!Array.isArray(recognized) || !recognized.length || recognized.length > 5000 ||
            recognized.some((cue, i) => typeof cue.text !== 'string' ||
              !Number.isFinite(cue.start) || !Number.isFinite(cue.end) ||
              cue.start < 0 || cue.end <= cue.start || cue.end > 1200.5 ||
              (i > 0 && cue.start <= recognized[i - 1].start))) throw Error('Invalid transcript');
          transcriptCache.set(entry.id, recognized);
        }
        if (request !== transcriptRequest || entries[index].id !== entry.id || !transcriptPanel.open) return;
        const fragment = document.createDocumentFragment();
        for (const cue of recognized) {
          const paragraph = document.createElement('p');
          paragraph.dataset.cueStart = cue.start; paragraph.dataset.cueEnd = cue.end;
          const link = document.createElement('a'); link.href = '#listen-archive';
          link.dataset.audioSeek = cue.start; link.textContent = clock(cue.start);
          link.setAttribute('aria-label', 'Listen from ' + clock(cue.start));
          const text = document.createElement('span'); text.textContent = cue.text.replace(/\s+/g, ' ').trim();
          paragraph.append(link, text); fragment.append(paragraph);
        }
        cueContainer.replaceChildren(fragment); cueContainer.setAttribute('aria-busy', 'false'); refreshTranscript();
      } catch {
        if (request === transcriptRequest && entries[index].id === entry.id && transcriptPanel.open)
          transcriptMessage('The timed transcript could not load. Download the readable transcript below.');
      }
    }
    transcriptPanel.addEventListener('toggle', loadTranscript);
    function select(target, start = true) {
      index = target;
      const entry = entries[index];
      title.textContent = entry.title; audio.setAttribute('aria-label', entry.title);
      transcript.href = entry.transcript;
      context.textContent = `${entry.label.toUpperCase()} / ${index + 1} OF ${entries.length} · ${entry.duration}`;
      entryLink.href = entry.url;
      entryLink.querySelector('[data-queue-entry-label]').textContent = entry.kind === 'note' ? 'Read this field note' : 'Open this episode';
      transcriptMessage('The readable transcript is available below.');
      loadTranscript();
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
    startButton.addEventListener('click', () => { if (audio.paused) play(); else audio.pause(); });
    const reflectPlayback = () => { startButton.textContent = audio.paused ? 'Play' : 'Pause'; };
    audio.addEventListener('play', reflectPlayback);
    audio.addEventListener('pause', reflectPlayback);
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
