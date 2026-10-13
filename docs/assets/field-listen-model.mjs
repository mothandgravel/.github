export const DEFAULT_RATE = 1.15;
export const PLAYBACK_RATES = [1, 1.15, 1.25, 1.5];
export const playbackRate = value => PLAYBACK_RATES.includes(Number(value)) ? Number(value) : DEFAULT_RATE;
export const stepIndex = (index, direction, count) => Math.max(0, Math.min(count - 1, index + direction));
export const cueAt = (cues, time) => cues.findIndex(c => time >= c.start && time < c.end);
