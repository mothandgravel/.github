import { newBreak, breakAction, runPlan, sleepFrame } from './sohva-evening-model.mjs';

const root = document.querySelector('[data-evening]');
if (root) {
  const get = id => root.querySelector(`#${id}`);
  let act = 'break';
  let breakState = newBreak();
  const room = get('evening-room');
  const status = get('evening-status');
  function draw({ on = true, muted = false, volume = 30, clock = '19:12', title = 'Channel 3', detail = 'Sound on' }) {
    room.dataset.power = on ? 'on' : 'off';
    room.dataset.muted = String(muted || !on);
    room.style.setProperty('--sound', on && !muted ? volume / 30 : 0);
    get('room-clock').textContent = clock;
    get('room-programme').textContent = on ? title : 'Standby';
    get('room-sound').textContent = detail;
  }
  function say(title, detail) {
    get('result-title').textContent = title;
    get('result-detail').textContent = detail;
    status.textContent = `${title} ${detail}`;
  }
  function renderBreak(announce = false) {
    const { muted, ownsMute, phase } = breakState;
    draw({ muted, clock: phase === 'ended' ? '19:15' : '19:12', detail: muted ? 'Muted' : 'Sound on · 30' });
    get('break-start').disabled = phase !== 'ready';
    get('break-end').disabled = phase !== 'running';
    get('break-unmute').disabled = phase !== 'running' || !muted;
    get('already-muted').disabled = phase !== 'ready';
    const messages = phase === 'ready'
      ? ['Three minutes of quiet.', 'Start a break, then skip to its end. Try it again with a TV you had already muted.']
      : phase === 'running'
        ? ['The break is holding.', ownsMute ? 'Sohva made this mute. It can give the sound back when the break ends.' : muted ? 'This mute belongs to you. The break has no sound of its own to restore.' : 'You brought the sound back. The break no longer owns the mute.']
        : muted
          ? ['Your quiet stays yours.', 'The TV was already muted. Ending the break leaves it that way.']
          : ['The sound is back.', 'The break has ended. A mute is restored only if the break still owns it.'];
    get('break-owner').textContent = phase === 'ready' ? 'No break running' : ownsMute ? 'Mute held by the break' : muted ? 'Mute held by you' : 'Sound chosen by you';
    if (announce) say(...messages);
    else { get('result-title').textContent = messages[0]; get('result-detail').textContent = messages[1]; }
  }
  function renderPlan(tryIt = false) {
    const on = get('tv-awake').checked;
    const plan = root.querySelector('input[name="evening-plan"]:checked').value;
    const clock = plan === 'scene' ? '20:00' : '06:30';
    if (!tryIt) {
      draw({ on, clock, detail: on ? 'Sound on · 30' : 'The room is quiet' });
      say('A plan is not always permission.', 'Choose whether the TV is on. A scheduled scene and a wake-up have different jobs.');
      return;
    }
    const result = runPlan({ on, plan });
    draw({ on: result.on, volume: result.volume ?? 0, clock, title: 'Channel 1', detail: result.applied ? 'Sound on · 18' : 'Left in standby' });
    say(result.applied ? (plan === 'wake' && !on ? 'A morning, expressly asked for.' : 'The evening carries on.') : 'The television stays off.',
      result.applied ? 'The saved plan selects Channel 1 at volume 18. These are example settings.' : 'A scheduled scene acts only while the TV is on. It does not wake the room to keep an appointment.');
  }
  function renderSleep(announce = true) {
    const frame = sleepFrame(Number(get('sleep-time').value));
    get('sleep-elapsed').textContent = `${frame.seconds} / 60 seconds`;
    draw({ on: frame.on, volume: frame.volume, clock: frame.on ? '22:59' : '23:00', detail: frame.on ? `Sound on · ${frame.volume}` : 'Standby · previous level kept' });
    get('fade-position').style.setProperty('--fade-position', `${frame.seconds / 60 * 100}%`);
    const messages = frame.on
      ? ['An ending in six small steps.', `The example level is ${frame.volume}. Sohva lowers the volume towards a floor, then switches the TV off. Move the clock yourself.`]
      : ['The evening has somewhere to end.', 'The TV is off. Sohva remembers the earlier level, 30, for when it next sees the TV on, provided nobody has chosen another level.'];
    if (announce) say(...messages);
    else { get('result-title').textContent = messages[0]; get('result-detail').textContent = messages[1]; }
  }
  for (const input of root.querySelectorAll('input[name="evening-act"]')) {
    input.addEventListener('change', () => {
      act = input.value;
      for (const panel of root.querySelectorAll('[data-act-panel]')) panel.hidden = panel.dataset.actPanel !== act;
      root.dataset.act = act;
      if (act === 'break') renderBreak(true);
      if (act === 'plan') renderPlan();
      if (act === 'sleep') renderSleep();
    });
  }
  get('already-muted').addEventListener('change', event => { breakState = newBreak(event.target.checked); renderBreak(true); });
  for (const [id, action] of [['break-start', 'start'], ['break-end', 'end'], ['break-unmute', 'unmute']]) {
    get(id).addEventListener('click', () => { breakState = breakAction(breakState, action); renderBreak(true); });
  }
  get('break-reset').addEventListener('click', () => { get('already-muted').checked = false; breakState = newBreak(); renderBreak(true); });
  get('tv-awake').addEventListener('change', () => renderPlan());
  for (const input of root.querySelectorAll('input[name="evening-plan"]')) input.addEventListener('change', () => renderPlan());
  get('plan-run').addEventListener('click', () => renderPlan(true));
  get('sleep-time').addEventListener('input', () => renderSleep());
  root.querySelectorAll('[data-evening-controls]').forEach(element => element.hidden = false);
  renderBreak();
}
