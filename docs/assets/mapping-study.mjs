// Inspect crops of the original capture, without changing its plotted pixels.
for (const panel of document.querySelectorAll('[data-mapping-capture]')) {
  const viewport = panel.querySelector('svg');
  const clip = panel.querySelector('[data-crop]');
  const controls = panel.querySelector('fieldset');
  const readout = panel.querySelector('[data-view-caption]');
  const title = panel.querySelector('svg title');
  const width = Number(panel.dataset.width), height = Number(panel.dataset.height);
  const views = JSON.parse(panel.dataset.views);
  const valid = Object.values(views).every(({box}) => box.length === 4 &&
    box.every(Number.isInteger) && box[0] >= 0 && box[1] >= 0 && box[2] > 0 && box[3] > 0 &&
    box[0] + box[2] <= width && box[1] + box[3] <= height);
  if (!valid) continue;
  const render = key => {
    const view = views[key];
    if (!view) return;
    viewport.setAttribute('viewBox', view.box.join(' '));
    ['x', 'y', 'width', 'height'].forEach((name, index) => clip.setAttribute(name, view.box[index]));
    title.textContent = `${panel.dataset.captureName}: ${view.label}`;
    readout.textContent = view.caption;
  };
  controls.addEventListener('input', event => render(event.target.value));
  const restoreView = () => {
    if (!viewport.hasAttribute('hidden')) render(controls.querySelector('input:checked').value);
  };
  // History restores native form state after the module's initial render.
  window.addEventListener('pageshow', restoreView);
  restoreView();
  // A decoded image is required before inspection controls become usable.
  const source = new Image();
  source.src = panel.querySelector('image').href.baseVal;
  source.decode().then(() => {
    restoreView();
    controls.hidden = false;
  }).catch(() => {
    viewport.setAttribute('hidden', '');
    controls.hidden = true;
    readout.textContent = 'This capture could not load. Open the full-resolution capture to retry.';
  });
}
