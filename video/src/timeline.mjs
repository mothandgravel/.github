export const activeCaption = (pages, time) => {
  let low = 0;
  let high = pages.length;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (pages[mid].start <= time) low = mid + 1;
    else high = mid;
  }
  const page = pages[low - 1];
  return page && time < page.end ? page.text : '';
};

export const videoDuration = (duration, preview, fps) =>
  Math.ceil(Math.min(duration, preview ?? duration) * fps);

export const clock = (seconds) => {
  const time = Math.max(0, Math.floor(seconds));
  return `${Math.floor(time / 60)}:${String(time % 60).padStart(2, '0')}`;
};
