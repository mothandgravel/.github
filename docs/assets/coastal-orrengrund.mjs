const view = document.getElementById('orr-view');
const channelLabels = [
  ['WaveHs', 'Significant height', 'm'],
  ['ModalWDi', 'Direction from', '°'],
  ['WTP', 'Modal period', 's'],
  ['WHDD', 'Directional spread', '°'],
  ['TWATER', 'Water temperature', '°C'],
];
const time = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Helsinki', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function timeLabel(record) {
  return time.format(new Date(record.observedAtUtc));
}

function present(raw, unit) {
  return raw === 'NaN' ? 'Missing / NaN' : `${raw} ${unit}`;
}

function instrument(record, source) {
  const reading = element('section', undefined, 'orr-reading');
  const clock = element('time', `${timeLabel(record)} EET`);
  clock.dateTime = record.observedAtUtc;
  const fields = element('dl');
  for (const [key, label, unit] of channelLabels.slice(1)) {
    fields.append(element('dt', label), element('dd', present(record.raw[key], unit)));
  }
  reading.append(element('h3', source), clock,
    element('p', record.observedAtUtc.replace('T', ' ').replace('Z', ' UTC'), 'orr-source-time'),
    element('strong', present(record.raw.WaveHs, 'm'), 'orr-height'), fields);
  return reading;
}

function build(hours) {
  const chart = document.getElementById('orr-chart');
  const table = document.getElementById('orr-rows');
  const range = document.getElementById('orr-hour');
  const readings = document.getElementById('orr-readings');
  const output = document.getElementById('orr-label');
  const announcement = document.getElementById('orr-announcement');
  const records = hours.flatMap(hour => [hour.hourly, hour.halfHour]);
  const maxHeight = Math.max(1, ...records.map(record => Number(record.raw.WaveHs) || 0));
  document.getElementById('orr-scale').textContent = `Significant wave height / 0–${maxHeight} m`;
  const rows = [];
  const columns = hours.map(({hourly, halfHour}) => {
    const column = element('div', undefined, 'orr-pair');
    for (const [index, record] of [hourly, halfHour].entries()) {
      const height = record.raw.WaveHs;
      const kind = height === 'NaN' ? 'orr-missing' : index === 0 ? 'orr-hour' : 'orr-extra';
      const bar = element('i', undefined, kind);
      if (height !== 'NaN') bar.style.setProperty('--wave', `${Number(height) / maxHeight * 100}%`);
      column.append(bar);

      const row = element('tr');
      const label = element('th', `${timeLabel(record)} EET`);
      label.scope = 'row';
      row.append(label, element('td', record.observedAtUtc), element('td', index === 0 ? 'Original hourly' : 'Half-hour follow-up'));
      for (const [key] of channelLabels) row.append(element('td', record.raw[key]));
      if (kind === 'orr-extra') row.dataset.additional = '';
      rows.push(row);
      table.append(row);
    }
    chart.append(column);
    return column;
  });
  const extraHours = hours.flatMap((hour, index) => hour.halfHour.raw.WaveHs === 'NaN' ? [] : [index]);

  function select(index, announce = false) {
    const {hourly, halfHour} = hours[index];
    range.value = String(index);
    const label = `${timeLabel(hourly)} EET`;
    output.textContent = label;
    const description = `${label}. On the hour: ${present(hourly.raw.WaveHs, 'metres')}. At half past: ${present(halfHour.raw.WaveHs, 'metres')}.`;
    range.setAttribute('aria-valuetext', description);
    for (const [position, column] of columns.entries()) column.classList.toggle('orr-current', position === index);
    for (const [position, row] of rows.entries()) row.classList.toggle('orr-row-current', Math.floor(position / 2) === index);
    readings.replaceChildren(instrument(hourly, 'On the hour / 13 November capture'),
      instrument(halfHour, 'At half past / 16 November capture'));
    if (announce) announcement.textContent = description;
  }
  range.addEventListener('input', () => select(Number(range.value)));
  document.getElementById('orr-find').addEventListener('click', () => {
    const next = extraHours.find(hour => hour > Number(range.value)) ?? extraHours[0];
    select(next, true);
  });
  select(extraHours[0]);
  view.hidden = false;
}

const response = await fetch(view.dataset.source).catch(() => null);
try {
  if (!response?.ok) throw new Error('Saved Orrengrund comparison unavailable');
  const data = await response.json();
  if (data.schema !== 'mg.coastal-orrengrund.v1' || data.hours.length !== 24 || !data.counts.WaveHs.additionalAtHalfPast) {
    throw new Error('Unexpected Orrengrund comparison');
  }
  build(data.hours);
} catch {
  document.getElementById('orr-status').hidden = false;
}
