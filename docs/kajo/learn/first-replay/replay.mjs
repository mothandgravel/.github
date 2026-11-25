const exercise = document.querySelector('[data-replay]');
const controls = exercise.querySelector('[data-replay-controls]');
const status = exercise.querySelector('[data-replay-status]');
const rows = [...exercise.querySelectorAll('tbody tr')].map((row) => ({
  row,
  observation: row.cells[0].textContent.trim(),
  input: Number(row.cells[1].textContent),
  recorded: row.cells[2].textContent.trim(),
  result: row.querySelector('[data-replay-result]'),
}));

function render() {
  const threshold = Number(controls.querySelector('input:checked').value);
  let command = 'OFF';
  let firstMismatch;
  let firstOn;

  for (const sample of rows) {
    if (sample.input < threshold) command = 'ON';
    else if (sample.input >= 116) command = 'OFF';

    if (command === 'ON') firstOn ??= sample.observation;
    const differs = command !== sample.recorded;
    if (differs) firstMismatch ??= sample.observation;

    sample.row.toggleAttribute('data-difference', differs);
    sample.result.classList.toggle('kajo-on', command === 'ON');
    sample.result.classList.toggle('kajo-off', command === 'OFF');
    sample.result.textContent = differs ? `${command} · differs` : command;
  }

  status.textContent = firstMismatch === undefined
    ? 'Replay matches all ten recorded commands.'
    : `First difference at observation ${firstMismatch}. Replay stays OFF there and turns ON at ${firstOn}.`;
}

render();
for (const sample of rows) sample.result.hidden = false;
exercise.querySelector('[data-replay-column]').hidden = false;
controls.hidden = false;
status.hidden = false;
controls.addEventListener('change', render);
