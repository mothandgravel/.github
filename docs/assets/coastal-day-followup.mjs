const frames = [...document.querySelectorAll('[data-cdf-time]')];
const image = document.getElementById('cdf-cloud-image');
const localTime = document.getElementById('cdf-local');
const utcTime = document.getElementById('cdf-utc');
const status = document.getElementById('cdf-frame-status');
let selection = 0;

for (const frame of frames) {
  frame.addEventListener('click', async event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    event.preventDefault();
    const revision = ++selection;
    const label = frame.textContent.trim();
    status.textContent = `Opening the ${label} frame…`;
    const candidate = new Image();
    candidate.src = frame.href;
    try {
      await candidate.decode();
    } catch {
      if (revision === selection) status.textContent = `The ${label} frame could not open. The last available frame is still shown.`;
      return;
    }
    if (revision !== selection) return;

    const utc = frame.dataset.cdfTime;
    image.src = candidate.src;
    image.alt = `EUMETSAT GeoColour image of cloud cover across the Gulf of Finland at the ${label} product label.`;
    localTime.textContent = label;
    utcTime.textContent = `${utc} UTC`;
    utcTime.dateTime = `2026-11-21T${utc}:00Z`;
    for (const other of frames) other.removeAttribute('aria-current');
    frame.setAttribute('aria-current', 'true');
    status.textContent = `Showing ${label} / ${utc} UTC.`;
  });
}
