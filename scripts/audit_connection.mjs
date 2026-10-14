/** Interaction and reading checks for the source-based connection specimen. */
import { chromium } from 'playwright';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
const route = '/specimens/connected-to-what/';
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const failures = [], results = [];
let checks = 0;
const assert = (value, label) => { checks++; if (!value) failures.push(label); };
const audit = async (page, label) => {
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async () => (await axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
  })).violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.html) })));
  assert(!violations.length, label + ': accessibility ' + JSON.stringify(violations));
};
try {
  for (const width of [320, 390, 768, 1440]) for (const theme of ['night', 'afterlight']) {
    const label = `connection-${width}-${theme}`;
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'reduce', hasTouch: width <= 390 });
    const errors = [], requests = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', req => requests.push({ method: req.method(), url: req.url() }));
    await page.addInitScript(t => localStorage.setItem('moth-and-gravel-theme', t), theme);
    await page.goto(origin + route, { waitUntil: 'networkidle' });
    const controls = page.locator('#inspection-controls'), age = page.locator('#inspection-age');
    await controls.waitFor({ state: 'visible' });
    assert(await page.locator('[data-connection-study]').getAttribute('data-measurement') === 'current', label + ': initial state');
    await age.focus();
    const titleBefore = await page.locator('#inspection-title').boundingBox();
    const controlsBefore = await controls.boundingBox();
    await age.press('Home');
    for (let seconds = 0; seconds <= 30; seconds++) {
      if (seconds) await age.press('ArrowRight');
      assert(await age.inputValue() === String(seconds), label + ': native keyboard age ' + seconds);
      assert(await page.locator('[data-connection-study]').getAttribute('data-measurement') === (seconds <= 15 ? 'current' : 'stale'), label + ': freshness ' + seconds);
      assert(await page.locator('#split-number').textContent() === '24', label + ': aged value changed ' + seconds);
      assert(await page.locator('#sample-age').textContent() === `Sampled ${seconds} seconds ago`, label + ': missing age ' + seconds);
    }
    const titleAfter = await page.locator('#inspection-title').boundingBox();
    const controlsAfter = await controls.boundingBox();
    assert(['x', 'y', 'width', 'height'].every(k => Math.abs(titleBefore[k] - titleAfter[k]) < .02), label + ': question moves during inspection');
    assert(['x', 'y', 'width', 'height'].every(k => Math.abs(controlsBefore[k] - controlsAfter[k]) < .02), label + ': controls move during inspection');
    assert(await age.evaluate(el => document.activeElement === el), label + ': keyboard focus lost');
    await age.fill('18');
    if ([390, 1440].includes(width)) await page.locator('#inspection').screenshot({ path: join(output, label + '-stale.png'), style: '.site-header{visibility:hidden!important}' });
    await page.getByLabel('No measurement', { exact: true }).check();
    assert(await age.isDisabled(), label + ': clock remains active without sample');
    assert(await page.locator('#split-number').textContent() === '—', label + ': missing becomes zero');
    assert(await page.locator('#sketch-number').textContent() === '—', label + ': missing number in collapsed sketch');
    assert(await page.locator('#sample-age').textContent() === 'Nothing measured', label + ': missing retains age');
    assert(await page.locator('[data-connection-study]').getAttribute('data-measurement') === 'unavailable', label + ': missing state');
    assert(!(await page.locator('#clock-hand').isVisible()), label + ': missing sample clock still drawn');
    await audit(page, label + ' unavailable');
    await page.getByLabel('A measured sample', { exact: true }).check();
    assert(await age.inputValue() === '18', label + ': fixture choice loses inspection age');
    assert(await page.locator('[data-connection-study]').getAttribute('data-measurement') === 'stale', label + ': return refreshes old sample');
    await page.locator('.connection-record summary').click();
    assert(await page.locator('.connection-record tbody tr').count() === 3, label + ': fixed record missing');
    await audit(page, label + ' stale record');
    assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)), label + ': horizontal overflow');
    assert(await page.locator('[data-connection-study]').evaluate(el => el.getAnimations({ subtree: true }).length === 0), label + ': inspection animates');
    await page.getByRole('link', { name: 'Inspect Ajo’s saved recovery trace' }).click();
    assert(new URL(page.url()).hash === '#specimen-ajo', label + ': next question route');
    assert(await page.locator('#specimen-ajo').isVisible(), label + ': next specimen not reached');
    assert(!requests.some(r => r.method !== 'GET' || !r.url.startsWith(origin)), label + ': specimen makes external/effect requests');
    assert(!errors.length, label + ': browser errors ' + errors.join('; '));
    results.push({ label }); await page.close();
  }
  for (const mode of ['no-js', 'failed-study', 'failed-helper']) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, javaScriptEnabled: mode !== 'no-js' });
    if (mode === 'failed-study') await page.route('**/assets/connection-study.mjs', r => r.abort());
    if (mode === 'failed-helper') await page.route('**/assets/specimens/measurement-status.mjs', r => r.abort());
    await page.goto(origin + route, { waitUntil: 'networkidle' });
    assert(!(await page.locator('#inspection-controls').isVisible()), mode + ': dead controls exposed');
    await page.locator('.connection-record summary').click();
    assert(await page.locator('.connection-record tbody tr').count() === 3, mode + ': static readings absent');
    assert(await page.locator('#next-title').isVisible(), mode + ': next question absent');
    assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)), mode + ': overflow');
    await page.close();
  }
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.goto(origin, { waitUntil: 'networkidle' });
  await page.locator('#specimen-liveconnect').scrollIntoViewIfNeeded();
  await page.getByRole('link', { name: 'Inspect the decision', exact: true }).click();
  assert(new URL(page.url()).pathname === route, 'homepage discovery route');
  await page.locator('#inspection-controls').waitFor({ state: 'visible' });
  await page.goBack();
  assert(new URL(page.url()).pathname === '/', 'Back returns to studio');
  await page.close();
} finally {
  await browser.close();
  await writeFile(join(output, 'connection-summary.json'), JSON.stringify({ checks, failures, results }, null, 2));
}
console.log(JSON.stringify({ checks, failures, results }, null, 2));
if (failures.length) process.exitCode = 1;
