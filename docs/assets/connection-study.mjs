import { inspectReading } from './connection-study-model.mjs';

const specimen = document.querySelector('[data-connection-study]');
if (specimen) {
  const controls = specimen.querySelector('#inspection-controls');
  const age = specimen.querySelector('#inspection-age');
  const read = selector => specimen.querySelector(selector);
  const words = {
    current: { title: 'A recent reading.', detail: 'The sample is within the source’s freshness window. It records frames; it does not tell us whether the picture is useful.', label: 'Current measurement' },
    stale: { title: 'The number stayed. The evidence aged.', detail: 'The sample is older than the source’s 15-second window. The connection is still marked connected. We cannot use this old number to describe the picture now.', label: 'Stale measurement' },
    unavailable: { title: 'No reading to lean on.', detail: 'There is no measurement in this fixture. We can name the connection, but the picture’s condition remains unknown. Missing is different from a measured zero.', label: 'Measurement unavailable' },
  };
  let lastMeasurement;
  const render = () => {
    const kind = controls.querySelector('input[name="reading"]:checked').value;
    const state = inspectReading(kind, Number(age.value));
    const copy = words[state.measurement];
    specimen.dataset.measurement = state.measurement;
    age.disabled = state.kind === 'missing';
    age.setAttribute('aria-valuetext', `${age.value} seconds since the sample`);
    read('#age-label').textContent = state.age === null ? 'No sample' : `${state.age} seconds`;
    read('#sketch-number').textContent = state.frameRate === null ? '—' : String(state.frameRate);
    read('#split-number').textContent = state.frameRate === null ? '—' : String(state.frameRate);
    read('#measurement-state').textContent = copy.label;
    read('#sample-age').textContent = state.age === null ? 'Nothing measured' : `Sampled ${state.age} seconds ago`;
    read('#reading-caption').textContent = state.frameRate === null ? 'Frame rate unavailable' : 'Frames / second at sampling';
    read('#clock-hand').style.setProperty('--sample-age', `${Number(age.value) / 30 * 100}%`);
    read('#clock-hand').hidden = state.age === null;
    read('#finding-title').textContent = copy.title;
    read('#finding-detail').textContent = copy.detail;
    read('#source-result').textContent = `Connection fixture: ${state.connection}. Measurement helper: ${state.measurement}.`;
    // The native range announces each age. Announce only a changed classification here.
    if (lastMeasurement && lastMeasurement !== state.measurement) {
      read('#inspection-status').textContent = `${copy.label}. Connection remains connected.`;
    }
    lastMeasurement = state.measurement;
  };
  controls.addEventListener('input', render);
  render();
  controls.hidden = false;
}
