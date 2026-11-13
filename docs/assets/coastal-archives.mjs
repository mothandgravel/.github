import {readArchives, utcAtMinute, minuteAtUtc, clock, gaugeAt, resolveReport, frameAt, levelEH2000, radarValue, reportFields} from './coastal-archives-model.mjs';

const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
const root = new URL('../data/coastal-archives/2026-11-11/', import.meta.url);
const state = {view: 'radar', minute: 720, station: '86094', parameter: 'WL avg', airport: 'EFHK', reportId: null, image: 'terra'};
const pretty = value => value === null ? 'Missing' : new Intl.NumberFormat('en-GB', {maximumFractionDigits: 4}).format(value);
const text = (id, value) => { $(id).textContent = value; };
const svg = (tag, attrs = {}, value) => {
  const node = document.createElementNS(NS, tag);
  for (const [key, val] of Object.entries(attrs)) node.setAttribute(key, val);
  if (value !== undefined) node.textContent = value;
  return node;
};
const element = (tag, className, value) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
};
async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw Error(`Archive HTTP ${r.status}`);
  return r.json();
}
let data, mapImage, inspection, timer = null, pixelRequest = 0, imageRequest = 0, resizeRequest, lastPixelKey = null;
const pixelCache = new Map(), imageCache = new Map(), cards = new Map();
const currentUtc = () => utcAtMinute(state.minute);
const currentGauge = () => data.gauges.find(s => s.stationCode === state.station && s.parameter === state.parameter);
const currentImage = () => data.images.find(s => s.id === state.image);
const currentReport = () => resolveReport(data.reports, state.airport, currentUtc(), state.reportId);
const levelText = value => value === null ? 'Missing' : levelEH2000(value).toFixed(5);
const setDisabled = (id, value) => { $(id).setAttribute('aria-disabled', String(value)); };

function drawRibbons() {
  const x = minute => minute / 1440 * 720;
  for (const kind of ['gauge', 'report', 'radar']) {
    const target = $(`ca-${kind}-ribbon`); target.setAttribute('preserveAspectRatio', 'none'); target.replaceChildren();
    target.append(svg('line', {x1: 0, x2: 720, y1: 14, y2: 14, class: 'ca-ribbon-baseline'}));
    const times = kind === 'gauge' ? currentGauge().points.map(p => p.labelledAt) : kind === 'report' ? data.reports.filter(r => r.station === state.airport).map(r => r.observedAt) : data.frames.map(f => f.observedAt);
    if (kind === 'radar') target.append(svg('rect', {x: x(720), y: 2, width: x(15), height: 24, class: 'ca-ribbon-window'}));
    for (const time of times) target.append(svg('line', {x1: x(minuteAtUtc(time)), x2: x(minuteAtUtc(time)), y1: kind === 'gauge' ? 9 : 5, y2: kind === 'gauge' ? 19 : 23, class: 'ca-ribbon-mark'}));
    const selected = kind === 'gauge' ? gaugeAt(currentGauge(), currentUtc())?.labelledAt : kind === 'report' ? currentReport()?.observedAt : frameAt(data.frames, currentUtc())?.observedAt;
    if (selected) target.append(svg('line', {x1: x(minuteAtUtc(selected)), x2: x(minuteAtUtc(selected)), y1: 1, y2: 27, class: 'ca-ribbon-selected'}));
    target.append(svg('line', {x1: x(state.minute), x2: x(state.minute), y1: -1, y2: 29, class: 'ca-ribbon-cursor'}));
  }
  text('ca-gauge-resolution', `${clock(gaugeAt(currentGauge(), currentUtc()).labelledAt)} UTC label · mean interval edge unknown`);
  const report = currentReport();
  text('ca-report-resolution', report ? `${state.airport} ${clock(report.observedAt)} UTC · ${state.minute - minuteAtUtc(report.observedAt)} min before cursor` : `${state.airport} · no earlier report saved`);
  const frame = frameAt(data.frames, currentUtc());
  text('ca-radar-resolution', frame ? `${clock(frame.observedAt)} UTC scan · ${state.minute - minuteAtUtc(frame.observedAt)} min before cursor` : 'No radar frame in this saved strip at browse time');
}

function buildMap(land) {
  const target = $('ca-weather-map'), x = lon => (lon - 23) / 5.5 * 1100, y = lat => (61 - lat) / 2 * 400;
  target.replaceChildren(svg('title', {id: 'ca-weather-title'}, 'Saved Gulf of Finland weather-radar frame'), svg('desc', {id: 'ca-weather-desc'}, 'A geographic crop of weather reflectivity. Masked cells are not evidence of dry weather.'));
  const defs = svg('defs'), pattern = svg('pattern', {id: 'ca-mask', width: 9, height: 9, patternUnits: 'userSpaceOnUse'});
  pattern.append(svg('path', {d: 'M-1 1L1 -1M0 9L9 0M8 10L10 8', stroke: 'currentColor', 'stroke-width': .6, opacity: .12}));
  defs.append(pattern); target.append(defs, svg('rect', {width: 1100, height: 400, fill: 'var(--cs-water)'}));
  const paths = land?.polygons.map(poly => poly.map(ring => ring.map(([lon, lat], i) => `${i ? 'L' : 'M'}${x(lon).toFixed(2)} ${y(lat).toFixed(2)}`).join(' ') + 'Z').join(' ')) ?? [];
  for (const d of paths) target.append(svg('path', {d, class: 'ca-map-land'}));
  target.append(svg('rect', {width: 1100, height: 400, fill: 'url(#ca-mask)'}));
  mapImage = svg('image', {x: 0, y: 0, width: 1100, height: 400, preserveAspectRatio: 'none'}); target.append(mapImage);
  for (const d of paths) target.append(svg('path', {d, class: 'ca-map-coast'}));
  for (const lon of [24, 25, 26, 27, 28]) target.append(svg('line', {x1: x(lon), x2: x(lon), y1: 0, y2: 400, class: 'ca-map-grid'}), svg('text', {x: x(lon) + 5, y: 390, class: 'ca-map-note'}, lon + '°E'));
  for (const lat of [59.5, 60, 60.5]) target.append(svg('line', {x1: 0, x2: 1100, y1: y(lat), y2: y(lat), class: 'ca-map-grid'}));
  for (const [name, lon, lat] of [['HELSINKI', 24.94, 60.17], ['TALLINN', 24.75, 59.44]]) target.append(svg('circle', {cx: x(lon), cy: y(lat), r: 4, class: 'ca-map-spot'}), svg('text', {x: x(lon) + 12, y: y(lat) - 10, class: 'ca-map-label'}, name));
  target.append(svg('text', {x: 650, y: 235, class: 'ca-map-label', 'text-anchor': 'middle'}, 'GULF OF FINLAND'), svg('text', {x: 18, y: 23, class: 'ca-map-note ca-map-context'}, land ? 'EPSG:4326 / CONTEXT COASTLINE · NATURAL EARTH' : 'EPSG:4326 / COASTLINE UNAVAILABLE'));
  if (!land) text('ca-weather-desc', 'Saved weather-radar crop. The contextual coastline could not be loaded. Coordinates remain EPSG:4326.');
}

function buildFrames() {
  for (const [i, f] of data.frames.entries()) {
    const b = element('button', 'ca-scan'); b.type = 'button'; b.dataset.frame = f.id;
    const img = element('img'); img.src = new URL(f.image, root); img.width = 1100; img.height = 400; img.alt = '';
    img.addEventListener('error', () => { img.alt = 'Scan preview unavailable'; b.dataset.previewError = 'true'; });
    img.addEventListener('load', () => { delete b.dataset.previewError; img.alt = ''; });
    const caption = element('span', '', `${i + 1} / 4 · ${clock(f.observedAt, 'Europe/Helsinki')} EET`);
    caption.append(element('strong', '', clock(f.observedAt) + ' UTC'));
    b.append(img, caption); b.addEventListener('click', () => setMinute(minuteAtUtc(f.observedAt), true)); $('ca-frames').append(b);
  }
}

function stopReplay(message) {
  if (timer !== null) clearInterval(timer);
  timer = null; text('ca-play', 'Step through 4 scans'); $('ca-play').setAttribute('aria-pressed', 'false');
  if (message) text('ca-replay-status', message);
}

function renderRadar() {
  const frame = frameAt(data.frames, currentUtc());
  $('ca-radar-empty').hidden = !!frame;
  mapImage.setAttribute('visibility', 'hidden'); $('ca-radar-error').hidden = true;
  if (frame) {
    text('ca-weather-title', `Weather-radar reflectivity / ${frame.observedAt}`);
    showRadarImage(frame);
  } else text('ca-weather-title', 'No preserved weather-radar frame at browse time');
  if (!frame) { ++imageRequest; $('ca-weather-map').setAttribute('aria-busy', 'false'); text('ca-radar-image-status', 'No selected scan image.'); }
  text('ca-radar-clock', frame ? `SCAN ${clock(frame.observedAt)} UTC / ${clock(frame.observedAt, 'Europe/Helsinki')} EET\n${state.minute - minuteAtUtc(frame.observedAt)} min before browse time · station receipt unknown` : 'NO FRAME SELECTED / OUTSIDE THE CAPTURE');
  const index = data.frames.indexOf(frame);
  setDisabled('ca-step-back', index <= 0); setDisabled('ca-step-next', index < 0 || index === data.frames.length - 1);
  for (const b of $('ca-frames').children) b.setAttribute('aria-pressed', String(b.dataset.frame === frame?.id));
  if (document.querySelector('.ca-pixel-details').open) inspectPixel(false);
  mapTypography();
}

function mapTypography() {
  const width = $('ca-weather-map').getBoundingClientRect().width;
  if (!width) return;
  for (const node of $('ca-weather-map').querySelectorAll('text')) node.style.fontSize = `${11 * 1100 / width}px`;
}

async function showRadarImage(frame) {
  const serial = ++imageRequest;
  $('ca-weather-map').setAttribute('aria-busy', 'true'); text('ca-radar-image-status', 'Opening the preserved scan image…');
  try {
    if (!imageCache.has(frame.id)) imageCache.set(frame.id, (async () => {
      const response = await fetch(new URL(frame.image, root), {cache: 'reload'});
      if (!response.ok) throw Error('Scan image download failed');
      const url = URL.createObjectURL(await response.blob()), image = new Image(); image.src = url;
      try { await image.decode(); if (image.naturalWidth !== frame.width || image.naturalHeight !== frame.height) throw Error('Scan image dimensions differ'); }
      catch (error) { URL.revokeObjectURL(url); throw error; }
      return url;
    })().catch(error => { imageCache.delete(frame.id); throw error; }));
    const url = await imageCache.get(frame.id);
    if (serial !== imageRequest || state.view !== 'radar') return;
    mapImage.setAttribute('href', url); mapImage.setAttribute('visibility', 'visible');
    const preview = [...$('ca-frames').children].find(b => b.dataset.frame === frame.id);
    if (preview?.dataset.previewError) preview.querySelector('img').src = url;
    text('ca-radar-image-status', 'Saved image opened. Transparent cells retain the file’s declared no-data code.');
  } catch {
    if (serial !== imageRequest || state.view !== 'radar') return;
    $('ca-radar-error').hidden = false; text('ca-weather-title', 'Selected radar image unavailable; this is not an empty data mask');
    text('ca-radar-image-status', 'Image could not be opened. The source record and original GeoTIFF remain available.');
  } finally { if (serial === imageRequest) $('ca-weather-map').setAttribute('aria-busy', 'false'); }
}

async function inspectPixel(announce = true) {
  const restoreFocus = document.activeElement === $('ca-retry-pixel');
  const serial = ++pixelRequest, frame = frameAt(data.frames, currentUtc());
  $('ca-pixel-value').setAttribute('aria-live', announce === false ? 'off' : 'polite');
  $('ca-retry-pixel').hidden = true;
  if (!frame) { lastPixelKey = null; text('ca-pixel-value', 'No selected frame. No cell value inferred.'); return; }
  const x = $('ca-pixel-x').valueAsNumber, y = $('ca-pixel-y').valueAsNumber;
  if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || x > 1099 || y < 0 || y > 399) { lastPixelKey = null; text('ca-pixel-value', 'Choose a whole column 0–1099 and row 0–399.'); return; }
  const key = `${frame.id}:${x}:${y}`;
  if (announce === false && key === lastPixelKey) return;
  lastPixelKey = null;
  text('ca-pixel-value', 'Opening the preserved pixel codes…');
  try {
    if (!pixelCache.has(frame.id)) pixelCache.set(frame.id, fetch(new URL(frame.pixels, root)).then(async r => { if (!r.ok) throw Error('Pixel download failed'); const bytes = new Uint8Array(await r.arrayBuffer()); if (bytes.length !== 440000) throw Error('Pixel length differs'); return bytes; }).catch(error => { pixelCache.delete(frame.id); throw error; }));
    const pixels = await pixelCache.get(frame.id);
    if (serial !== pixelRequest || state.view !== 'radar') return;
    const code = pixels[y * 1100 + x], value = radarValue(code), lon = 23 + (x + .5) * .005, lat = 61 - (y + .5) * .005;
    text('ca-pixel-value', `${clock(frame.observedAt)} UTC · cell centre ${lon.toFixed(4)}° E, ${lat.toFixed(4)}° N\n${value === null ? 'Code 0 / provider no-data. Physical value unknown.' : `Code ${code} × 0.5 − 32 = ${value} dBZ`}`);
    lastPixelKey = key;
    if (restoreFocus) $('ca-pixel-x').focus({preventScroll: true});
  } catch { if (serial === pixelRequest) { text('ca-pixel-value', 'Pixel codes could not be opened. No cell value inferred. Keep the original GeoTIFF below.'); $('ca-retry-pixel').hidden = false; if (restoreFocus) $('ca-retry-pixel').focus(); } }
}

function buildGauges() {
  for (const s of data.gauges.filter(s => s.parameter === 'WL avg')) {
    const b = element('button', 'ca-gauge-card'); b.type = 'button'; b.dataset.gauge = s.stationCode;
    const name = element('span', 'ca-station-name', s.station), value = element('span', 'ca-gauge-value');
    const range = element('span', 'ca-gauge-range'), plot = svg('svg', {viewBox: '0 0 240 115', 'aria-hidden': 'true'}), scale = element('span', 'ca-gauge-scale');
    scale.append(element('span', '', '00 EET'), element('span', '', '23 EET'));
    b.append(name, value, range, plot, scale); cards.set(s.stationCode, {button: b, value, range, plot});
    b.addEventListener('click', () => { state.station = s.stationCode; render(true); }); $('ca-gauge-cards').append(b);
  }
}

function renderGauges() {
  const selected = currentGauge(), current = gaugeAt(selected, currentUtc()), isLevel = selected.parameter === 'WL avg';
  const transform = value => isLevel ? levelEH2000(value) : value;
  const allValues = data.gauges.filter(s => s.parameter === state.parameter).flatMap(s => s.points).filter(p => p.value !== null).map(p => transform(p.value));
  let min = allValues.length ? Math.min(...allValues) : 0, max = allValues.length ? Math.max(...allValues) : 1; if (min === max) { min -= .5; max += .5; }
  for (const s of data.gauges.filter(s => s.parameter === state.parameter)) {
    const {button, value, range, plot} = cards.get(s.stationCode), p = gaugeAt(s, currentUtc());
    button.setAttribute('aria-pressed', String(s.id === selected.id));
    value.replaceChildren(document.createTextNode(isLevel ? levelText(p.value) : pretty(p.value)), element('small', '', isLevel ? 'm EH2000' : '°C'));
    range.textContent = `${pretty(min)}–${pretty(max)} ${isLevel ? 'm EH2000' : '°C'} / shared scale`;
    const width = Math.max(80, plot.getBoundingClientRect().width), height = Math.max(60, plot.getBoundingClientRect().height);
    plot.setAttribute('viewBox', `0 0 ${width} ${height}`); plot.replaceChildren();
    for (const [i, point] of s.points.entries()) if (point.value !== null) plot.append(svg('circle', {cx: 5 + i / 23 * (width - 10), cy: height - 12 - (transform(point.value) - min) / (max - min) * (height - 27), r: point === p ? 5 : 2.6, class: point === p ? 'ca-gauge-selected' : 'ca-gauge-mark'}));
  }
  text('ca-gauge-station', `${selected.station.toUpperCase()} / ${selected.stationCode}${isLevel ? ' · ORIGINAL CM → METRES EH2000' : ''}`);
  const arithmetic = $('ca-gauge-arithmetic'); arithmetic.replaceChildren();
  if (current.value === null) arithmetic.append(document.createTextNode('Missing / no value inferred'));
  else if (isLevel) arithmetic.append(document.createTextNode(`${current.rawValue} ÷ 100 − 5 = `), element('strong', '', `${levelText(current.value)} m`));
  else arithmetic.append(element('strong', '', `${current.rawValue} °C`), document.createTextNode(' / hourly mean'));
  text('ca-gauge-clock', `LABEL ${clock(current.labelledAt)} UTC / ${clock(current.labelledAt, 'Europe/Helsinki')} EET\nAveraging interval edge / Unknown`);
  text('ca-gauge-limit', isLevel ? 'The station gauge zero is −5 m EH2000. The arithmetic changes the reference, not the source. No conversion to Finland’s N2000 datum has been applied. Reported precision does not establish sensor accuracy.' : 'These are operational hourly mean water temperatures, subject to later quality control. They do not establish conditions throughout the Gulf.');
  text('ca-gauge-caption', `${selected.station} / ${selected.parameter} / original hourly means`);
  const body = $('ca-gauge-rows'); body.replaceChildren();
  for (const p of selected.points) {
    const tr = element('tr'); if (p === current) tr.setAttribute('aria-current', 'true');
    for (const v of [clock(p.labelledAt, 'Europe/Helsinki'), p.labelledAt, p.rawValue === null ? 'Missing' : `${p.rawValue} ${selected.unit}`, `${isLevel ? levelText(p.value) : pretty(p.value)}${p.value === null ? '' : isLevel ? ' m EH2000' : ' °C'}`]) tr.append(element('td', '', v));
    body.append(tr);
  }
}

function reportOptions() {
  const select = $('ca-report-select'); select.replaceChildren();
  const none = element('option', '', 'No earlier report in the saved day'); none.value = ''; none.disabled = true; select.append(none);
  for (const r of data.reports.filter(r => r.station === state.airport)) { const o = element('option', '', `${clock(r.observedAt)} UTC / ${clock(r.observedAt, 'Europe/Helsinki')} EET`); o.value = r.id; select.append(o); }
}

function renderReports() {
  const r = currentReport(), list = data.reports.filter(r => r.station === state.airport), i = list.indexOf(r);
  text('ca-report-station', `${state.airport} / ${state.airport === 'EFHK' ? 'HELSINKI-VANTAA' : 'TALLINN'} · ${list.length} SAVED REPORTS`);
  $('ca-report-select').value = r?.id ?? ''; setDisabled('ca-report-prev', i <= 0); setDisabled('ca-report-next', i === list.length - 1);
  const raw = $('ca-report-raw'), fields = $('ca-report-fields'); raw.replaceChildren(); fields.replaceChildren();
  if (!r) {
    raw.textContent = 'No earlier report saved.';
    text('ca-report-clock', `FIRST SAVED OBSERVATION / ${clock(list[0].observedAt, 'Europe/Helsinki')} EET`); text('ca-clouds', 'The next message is not an observation from browse time. Move to it explicitly.'); return;
  }
  for (const [i, token] of r.raw.split(' ').entries()) { if (i) raw.append(document.createTextNode(' ')); raw.append(element('span', i < 2 ? 'ca-report-token' : '', token)); }
  text('ca-report-clock', `${r.observedAt}\n${state.minute - minuteAtUtc(r.observedAt)} min before cursor · receipt time unknown`);
  const decoded = reportFields(r.raw);
  for (const [label, value] of [['WIND / AS REPORTED', decoded.wind], ['AIR TEMPERATURE', decoded.temperature], ['VISIBILITY / CODE', decoded.visibility], ['PRESSURE / QNH', decoded.pressure]]) {
    const p = element('p'); p.append(element('span', '', label), element('strong', '', value)); fields.append(p);
  }
  text('ca-clouds', `Cloud codes / ${decoded.clouds}`);
}

function buildImages() {
  for (const r of data.images) {
    const plate = element('figure', 'ca-image-plate'), a = element('a'); a.href = new URL('raw/' + r.sourceFile, root); a.target = '_blank'; a.rel = 'noopener';
    a.setAttribute('aria-label', `Open full ${r.platform} MODIS daily image / new tab`);
    const img = element('img'); img.src = a.href; img.width = 1100; img.height = 400; img.loading = 'lazy'; img.alt = `${r.platform} MODIS regional corrected-reflectance cloud imagery for UTC product date 11 November 2026. Exact acquisition times unresolved.`;
    img.addEventListener('error', () => { img.alt = `${r.platform} image could not be opened. The original file link remains available.`; }); a.append(img, element('span', 'ca-image-open', 'Open full downloaded crop ↗'));
    const caption = element('figcaption'), top = element('span'); top.append(element('strong', '', r.platform), element('span', '', 'MODIS / NASA GIBS'));
    caption.append(top, element('p', 'cs-small', '11 NOV 2026 / UTC product date.\nAcquisition hour / Unknown.'));
    const b = element('button'); b.append(element('span', '', `Inspect ${r.platform} receipt`), element('span', '', '↳')); b.lastChild.setAttribute('aria-hidden', 'true'); b.type = 'button'; b.dataset.image = r.id; b.setAttribute('aria-controls', 'ca-receipt-details');
    b.addEventListener('click', () => { state.image = r.id; render(true); $('ca-receipt-details').open = true; const summary = $('ca-receipt-details').querySelector('summary'); summary.focus(); summary.scrollIntoView({block: 'start'}); }); plate.append(a, caption, b); $('ca-image-plates').append(plate);
  }
}

function renderReceipt() {
  let record, sourceClock, precision, support;
  if (state.view === 'gauges') { const s = currentGauge(), p = gaugeAt(s, currentUtc()); record = {...s, points: undefined, sample: p, convertedValue: s.parameter === 'WL avg' ? levelEH2000(p.value) : p.value, conversion: s.parameter === 'WL avg' ? 'raw cm / 100 − 5 = metres EH2000' : 'None'}; sourceClock = p.labelledAt; precision = 'Hourly mean label / interval edge unknown'; }
  if (state.view === 'reports') { record = currentReport(); sourceClock = record?.observedAt; precision = 'Observation time encoded in raw METAR'; }
  if (state.view === 'radar') { record = frameAt(data.frames, currentUtc()); sourceClock = record?.observedAt; precision = 'Saved weather-radar scan'; support = record?.metadataFile; }
  if (state.view === 'imagery') { record = currentImage(); sourceClock = record.productDateUtc; precision = 'UTC product date / acquisition hour unknown'; support = record.domainFile; }
  const source = data.sources[state.view], r = record && data.receipts[record.sourceFile];
  inspection = {schema: 'mg.coastal-archive-inspection.v1', view: state.view, browseTimeUtc: state.view === 'imagery' ? null : currentUtc(), browseTimeApplies: state.view !== 'imagery', interfaceBrowseTimeUtc: currentUtc(), browseTimezone: 'Europe/Helsinki', sourceTime: sourceClock ?? null, timeMeaning: precision, originalReceiverTime: null, firstPublication: null, source, record: record ?? null, httpReceipt: r ?? null};
  text('ca-receipt-source', source.origin.toUpperCase());
  text('ca-receipt-clock', r ? `${sourceClock} · ${state.view === 'imagery' ? 'DAY ONLY' : 'SOURCE CLOCK'} · SHA ${r.sha256.slice(0, 12)}` : 'No record selected at browse time. No receipt inferred.');
  text('ca-lineage', `${source.origin} → ${source.distribution} → this saved archive`);
  const dl = $('ca-receipt-dl'); dl.replaceChildren();
  for (const [label, value] of [['Time meaning', precision], ['Source clock', sourceClock ?? 'No selected record'], ['Browse clock / UTC', state.view === 'imagery' ? 'Does not apply to daily image' : currentUtc()], ['Retrieval request / UTC', r?.requestedAt ?? 'No selected record'], ['Download completed / UTC', r?.completedAt ?? 'No selected record'], ['Original receiver time', 'Unknown'], ['First publication', 'Unknown'], ['Source SHA-256', r?.sha256 ?? 'No selected record'], ['Reuse', source.licence]]) dl.append(element('dt', '', label), element('dd', '', value));
  text('ca-receipt-json', JSON.stringify(inspection, null, 2));
  for (const id of ['ca-original', 'ca-http']) $(id).hidden = !r;
  if (r) { $('ca-original').href = new URL('raw/' + record.sourceFile, root); $('ca-http').href = new URL('raw/' + record.sourceFile + '.receipt.json', root); }
  $('ca-definition').href = source.definitionUrl; $('ca-licence').href = source.licenceUrl;
  $('ca-support').hidden = !support; if (support) $('ca-support').href = new URL('raw/' + support, root);
}

function render(announce = false) {
  const utc = currentUtc();
  $('ca-minute').value = state.minute; text('ca-local', clock(utc, 'Europe/Helsinki')); text('ca-utc', `${clock(utc)} UTC · ${utc.slice(8, 10)} Nov`);
  $('ca-minute').setAttribute('aria-valuetext', `${clock(utc, 'Europe/Helsinki')} Helsinki, ${utc}. Browse time; source clocks differ.`);
  $('ca-study').dataset.daily = String(state.view === 'imagery');
  for (const b of document.querySelectorAll('[data-view]')) { const active = b.dataset.view === state.view; b.setAttribute('aria-pressed', String(active)); $(`ca-${b.dataset.view}`).hidden = !active; }
  for (const b of document.querySelectorAll('[data-image]')) b.setAttribute('aria-pressed', String(b.dataset.image === state.image));
  drawRibbons();
  if (state.view === 'radar') renderRadar();
  if (state.view === 'gauges') renderGauges();
  if (state.view === 'reports') renderReports();
  renderReceipt();
  if (announce) text('ca-announcement', `${clock(utc, 'Europe/Helsinki')} Helsinki. ${state.view}. ${$('ca-receipt-clock').textContent}`);
}

function setMinute(minute, announce = false, fromPlayback = false) {
  if (!fromPlayback && timer !== null) stopReplay('Stepping paused. Browse time changed.');
  state.minute = minute; state.reportId = null; render(announce);
  document.documentElement.dataset.coastalMinute = String(minute);
  document.dispatchEvent(new CustomEvent('coastal-archive-clock', {detail: {utc: currentUtc()}}));
}
function selectReport(report) {
  setMinute(minuteAtUtc(report.observedAt)); state.reportId = report.id; render(true);
}

async function start() {
  const restoreFocus = document.activeElement === $('ca-retry');
  $('ca-radar-image-status').setAttribute('aria-live', 'off');
  $('ca-retry').hidden = true; text('ca-loading', 'Opening the preserved archive files…'); $('ca-loading').hidden = false;
  try {
    data = readArchives(await json(new URL('notebook.json', root)));
    const land = await json(new URL('./coastal-replay-land.json', import.meta.url)).catch(() => null);
    for (const id of ['ca-frames', 'ca-gauge-cards', 'ca-image-plates']) $(id).replaceChildren(); cards.clear();
    buildMap(land); buildFrames(); buildGauges(); buildImages(); reportOptions();
    for (const b of document.querySelectorAll('[data-view]')) b.onclick = () => { if (timer !== null) stopReplay('Stepping paused.'); state.view = b.dataset.view; ++pixelRequest; ++imageRequest; $('ca-weather-map').setAttribute('aria-busy', 'false'); if (state.view === 'radar') text('ca-replay-status', `${data.frames.length} saved scans. Choose a frame or step through the strip.`); render(true); };
    $('ca-minute').addEventListener('input', () => setMinute(Number($('ca-minute').value)));
    $('ca-minute').addEventListener('change', () => render(true));
    $('ca-parameter').addEventListener('change', () => { state.parameter = $('ca-parameter').value; render(true); });
    $('ca-airport').addEventListener('change', () => { state.airport = $('ca-airport').value; state.reportId = null; reportOptions(); render(true); });
    $('ca-report-select').addEventListener('change', () => { const r = data.reports.find(r => r.id === $('ca-report-select').value); if (r) selectReport(r); });
    for (const [id, direction] of [['ca-report-prev', -1], ['ca-report-next', 1]]) $(id).addEventListener('click', () => { if ($(id).getAttribute('aria-disabled') === 'true') return; const list = data.reports.filter(r => r.station === state.airport), i = list.indexOf(currentReport()), r = list[i + direction]; if (r) selectReport(r); });
    $('ca-find-radar').addEventListener('click', () => { setMinute(minuteAtUtc(data.frames[0].observedAt), true); $('ca-frames').querySelector('[aria-pressed=true]').focus(); });
    $('ca-retry-image').addEventListener('click', () => { const frame = frameAt(data.frames, currentUtc()); if (frame) { imageCache.delete(frame.id); renderRadar(); $('ca-frames').querySelector('[aria-pressed=true]').focus(); } });
    for (const [id, direction] of [['ca-step-back', -1], ['ca-step-next', 1]]) $(id).addEventListener('click', () => { if ($(id).getAttribute('aria-disabled') === 'true') return; const i = data.frames.indexOf(frameAt(data.frames, currentUtc())), frame = data.frames[i + direction]; if (frame) setMinute(minuteAtUtc(frame.observedAt), true); });
    $('ca-play').addEventListener('click', () => {
      if (timer !== null) { stopReplay('Stepping paused.'); return; }
      setMinute(minuteAtUtc(data.frames[0].observedAt)); let i = 0; text('ca-play', 'Pause stepping'); $('ca-play').setAttribute('aria-pressed', 'true'); text('ca-replay-status', `1 / ${data.frames.length} saved scans · ${clock(currentUtc(), 'Europe/Helsinki')} EET`);
      timer = setInterval(() => { ++i; setMinute(minuteAtUtc(data.frames[i].observedAt), false, true); text('ca-replay-status', `${i + 1} / ${data.frames.length} saved scans · ${clock(currentUtc(), 'Europe/Helsinki')} EET`); if (i === data.frames.length - 1) stopReplay(`${data.frames.length} / ${data.frames.length} saved scans. End of the preserved strip.`); }, 1500);
    });
    document.querySelector('.ca-pixel-details').addEventListener('toggle', () => { if (document.querySelector('.ca-pixel-details').open) inspectPixel(); });
    for (const id of ['ca-pixel-x', 'ca-pixel-y']) $(id).addEventListener('input', inspectPixel);
    $('ca-retry-pixel').addEventListener('click', inspectPixel);
    document.addEventListener('visibilitychange', () => { if (document.hidden) stopReplay('Stepping stopped while the page was away.'); });
    window.addEventListener('pagehide', () => stopReplay());
    window.addEventListener('resize', () => { cancelAnimationFrame(resizeRequest); resizeRequest = requestAnimationFrame(() => { if (state.view === 'gauges') renderGauges(); if (state.view === 'radar') mapTypography(); }); });
    document.addEventListener('coastal-fmi-hour', e => { const minute = minuteAtUtc(e.detail.utc); if (Number.isInteger(minute) && minute >= 0 && minute <= 1439) setMinute(minute); });
    $('ca-export').addEventListener('click', () => { const url = URL.createObjectURL(new Blob([JSON.stringify(inspection, null, 2) + '\n'], {type: 'application/json'})); const a = element('a'); a.href = url; a.download = `coastal-watch-${state.view}-2026-11-11.json`; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
    $('ca-desk').hidden = false; $('ca-loading').hidden = true; setMinute(state.minute);
    if (restoreFocus) $('ca-minute').focus();
  } catch (error) {
    $('ca-desk').hidden = true; $('ca-retry').hidden = false;
    text('ca-loading', 'The day desk could not open. '); const a = element('a', '', 'Read the saved notebook and its source receipts ↗'); a.href = new URL('notebook.json', root); $('ca-loading').append(a); console.error(error);
    if (restoreFocus) $('ca-retry').focus();
  }
}
$('ca-retry').addEventListener('click', start);
start();
