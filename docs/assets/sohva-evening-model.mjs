/* Authored reductions of Sohva's mute ownership, scheduled-scene gate and sleep fade.
 * Source revision and limits: /design/sohva-study-provenance.json. No device I/O. */
export function newBreak(alreadyMuted = false) {
  return { muted: alreadyMuted, ownsMute: false, phase: 'ready' };
}

export function breakAction(state, action) {
  if (action === 'start' && state.phase === 'ready') {
    return { muted: true, ownsMute: !state.muted, phase: 'running' };
  }
  if (action === 'unmute' && state.phase === 'running') {
    return { ...state, muted: false, ownsMute: false };
  }
  if (action === 'end' && state.phase === 'running') {
    return { muted: state.ownsMute ? false : state.muted, ownsMute: false, phase: 'ended' };
  }
  return state;
}

export function runPlan({ on, plan }) {
  if (!['scene', 'wake'].includes(plan)) throw new RangeError('Unknown plan');
  const applied = on || plan === 'wake';
  return { on: applied, applied, channel: applied ? 'Channel 1' : null, volume: applied ? 18 : null };
}

export function sleepFrame(elapsed, startingVolume = 30) {
  if (!Number.isFinite(elapsed) || !Number.isInteger(startingVolume) || startingVolume < 0 || startingVolume > 100) {
    throw new RangeError('Invalid sleep fixture');
  }
  const seconds = Math.min(60, Math.max(0, elapsed));
  const step = Math.floor(seconds / 10);
  const floor = Math.max(4, Math.floor(startingVolume / 3));
  const volume = startingVolume <= 4 ? startingVolume : startingVolume - Math.floor((startingVolume - floor) * step / 6);
  return { seconds, step, volume, on: seconds < 60, restore: startingVolume };
}
