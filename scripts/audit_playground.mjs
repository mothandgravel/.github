/** Standing investigations, the green-light question and the playground: both appearances, narrow layouts,
 * zero axe violations with every toy mounted and exercised, keyboard play, reduced motion, lazy loading and
 * a homepage that never fetches a toy. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
await mkdir(output, { recursive: true });
const options = process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {};
const browser = await launchAuditBrowser(options);
const fail = (label, detail) => { throw Error(label + ': ' + JSON.stringify(detail)); };
const axeRun = async (page) => {
  await page.addScriptTag({ content: axe.source });
  return page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } }))
    .violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) })));
};
const pages = [
  { name: 'home-questions', path: '/', toys: [] },
  { name: 'investigations', path: '/investigations/', toys: [] },
  { name: 'green-light', path: '/investigations/green-light/', toys: ['grid'] },
  { name: 'playground', path: '/workbench/playground/', toys: ['grid', 'stamp', 'week'] },
];
const results = [];
try {
  for (const target of pages) for (const width of [320, 390, 1440]) for (const theme of ['night', 'afterlight']) {
    const label = `${target.name}-${width}-${theme}`;
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    const errors = [], toyRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('request', request => { if (/assets\/playground/.test(request.url())) toyRequests.push(request.url()); });
    page.on('response', response => { if (response.status() >= 400 && response.url().startsWith(origin)) errors.push(`HTTP ${response.status()} ${response.url()}`); });
    await page.addInitScript(value => localStorage.setItem('moth-and-gravel-theme', value), theme);
    await page.goto(origin + target.path, { waitUntil: 'networkidle' });
    if (await page.locator('html').getAttribute('data-theme') !== theme) fail(label, 'theme not applied');
    if (target.name === 'home-questions') {
      if (toyRequests.length) fail(label, { toysOnHome: toyRequests });
      await page.locator('#questions').scrollIntoViewIfNeeded();
      await page.waitForTimeout(200);
      if (toyRequests.length) fail(label, { toysOnHomeAfterScroll: toyRequests });
      // Made here arrives after load into a box that already has its height.
      await page.locator('#made-here').scrollIntoViewIfNeeded();
      await page.locator('#made-here ul').waitFor({ timeout: 5000 });
      const made = await page.evaluate(() => { const box = document.querySelector('#made-here');
        return { items: box.querySelectorAll('li').length, height: box.getBoundingClientRect().height, reserve: parseFloat(getComputedStyle(box).minHeight) }; });
      if (made.items !== 12 || made.height > made.reserve + 0.5) fail(label + ' made here', made);
    } else if (target.toys.length && width === 1440 && toyRequests.some(url => /playground\/(stamp|week)\.mjs/.test(url)))
      fail(label, { eagerToys: toyRequests });
    for (const toy of target.toys) {
      await page.locator(`#toy-${toy}`).scrollIntoViewIfNeeded();
      await page.locator(`#toy-${toy}[data-loaded="ready"]`).waitFor({ timeout: 5000 });
    }
    // Each bench reserved its toy's height before loading, so mounting moved nothing below it.
    const grown = await page.evaluate(() => [...document.querySelectorAll('[data-toy]')]
      .filter(el => el.getBoundingClientRect().height > parseFloat(getComputedStyle(el).minHeight) + 0.5)
      .map(el => `${el.dataset.toy} ${Math.round(el.getBoundingClientRect().height)} > ${getComputedStyle(el).minHeight}`));
    if (grown.length) fail(label + ' reserved height', grown);
    if (target.toys.includes('grid')) await page.locator('#toy-grid [data-ask]').click();
    if (target.toys.includes('stamp')) await page.locator('#toy-stamp .stamp-cell').nth(26).click();
    if (target.toys.includes('week')) await page.locator('#toy-week input[value="ring"]').check();
    const check = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
      headings: document.querySelectorAll('h1').length,
      // Reduced motion shortens every transition to a hundredth of a millisecond (site.css); only real motion counts.
      animating: document.getAnimations().filter(a => a.playState === 'running' && (a.effect?.getComputedTiming().duration ?? 0) > 50).length,
      leaks: /navivra|kistradegoods|digablesolutions|vesuno|run\.app/i.test(document.documentElement.outerHTML),
    }));
    if (check.overflow || check.headings !== 1 || check.animating || check.leaks || errors.length) fail(label, { check, errors });
    if (width !== 320) {
      const violations = await axeRun(page);
      if (violations.length) fail(label + ' axe', violations);
      await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
      await page.screenshot({ path: `${output}/${label}.png`, fullPage: true });
    }
    results.push({ label, ...check });
    await page.close();
  }

  // Keyboard: every toy is played without a pointer.
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(origin + '/workbench/playground/', { waitUntil: 'networkidle' });
  for (const toy of ['grid', 'stamp', 'week']) {
    await page.locator(`#toy-${toy}`).scrollIntoViewIfNeeded();
    await page.locator(`#toy-${toy}[data-loaded="ready"]`).waitFor();
  }
  await page.locator('#toy-stamp .stamp-cell[tabindex="0"]').focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(80);
  if (!/^Placed\./.test(await page.locator('#toy-stamp [data-status]').textContent())) fail('stamp keyboard', 'not placed');
  await page.locator('#toy-stamp [data-wind]').focus(); await page.keyboard.press('Enter');
  await page.locator('#toy-stamp [data-undo]').focus(); await page.keyboard.press('Enter');
  await page.waitForTimeout(80);
  if (!/^Undo failed\..*history entry stays/.test(await page.locator('#toy-stamp [data-status]').textContent())) fail('stamp undo', 'undo did not refuse after the wind');
  const verdicts = {};
  for (const [preset, budget, expected] of [['open', '25000', 'A ROUTE EXISTS'], ['none', '25000', 'NO ROUTE'], ['corner', '25000', 'RULED OUT BEFORE SEARCHING'], ['three', '40', 'NO ANSWER YET']]) {
    await page.selectOption('#toy-grid [data-preset]', preset);
    await page.selectOption('#toy-grid [data-budget]', budget);
    await page.locator('#toy-grid [data-ask]').focus(); await page.keyboard.press('Enter');
    verdicts[preset + '/' + budget] = await page.locator('#toy-grid [data-verdict-kind]').textContent();
    if (verdicts[preset + '/' + budget] !== expected) fail('grid verdict', verdicts);
  }
  await page.selectOption('#toy-grid [data-preset]', 'open');
  await page.locator('#toy-grid input[value="play"]').check();
  await page.locator('#toy-grid .grid-cell').nth(0).focus(); await page.keyboard.press('Enter');
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight'); await page.keyboard.press('Enter');
  await page.waitForTimeout(80);
  if (!/Jumped to D1/.test(await page.locator('#toy-grid [data-status]').textContent())) fail('grid keyboard play', 'jump not taken');
  await page.locator('#toy-grid [data-clear]').focus(); await page.keyboard.press('Enter');
  if (await page.locator('#toy-grid .grid-cell.is-visited').count() !== 0) fail('grid clear', 'route not cleared');
  // Browser shortcuts stay the browser's: Ctrl/Cmd/Alt+R must not turn the stamp.
  const hijacked = await page.evaluate(() => ['ctrlKey', 'metaKey', 'altKey'].some(mod => {
    const event = new KeyboardEvent('keydown', { key: 'r', [mod]: true, bubbles: true, cancelable: true });
    document.querySelector('#toy-stamp .stamp-cell').dispatchEvent(event);
    return event.defaultPrevented;
  }));
  if (hijacked) fail('stamp shortcuts', 'a modified R was intercepted');
  await page.locator('#toy-week .week-item').nth(5).focus(); await page.keyboard.press('Enter');
  if ((await page.locator('#toy-week .week-detail h3').textContent()) !== 'One conversation still needs you.') fail('week keyboard', 'item not chosen');
  // Normal motion: the river flows. Reduced motion (above) was checked to have no running animation.
  if (!(await page.evaluate(() => document.getAnimations().some(a => a.animationName === 'river-flow' && a.playState === 'running')))) fail('river flow', 'no flow with normal motion');
  await page.close();

  // Without JavaScript, every bench still says what its toy shows.
  const quiet = await browser.newContext({ javaScriptEnabled: false });
  const still = await quiet.newPage();
  await still.goto(origin + '/workbench/playground/');
  if (await still.locator('.toy-mount p').count() !== 3) fail('no-script', 'bench fallbacks missing');
  await still.goto(origin + '/');
  if (!(await still.locator('#made-here a[href="./investigations/#made-here"]').isVisible())) fail('no-script', 'Made here link missing on home');
  await still.goto(origin + '/investigations/');
  if (await still.locator('#made-here li').count() !== 12) fail('no-script', 'Made here list missing on the index');
  await quiet.close();
  await writeFile(`${output}/playground-audit.json`, JSON.stringify({ results, verdicts }, null, 2));
  console.log(`Playground: ${results.length} page/width/theme checks, zero axe violations, no toys on home, Made here in its reserved box, lazy toys, keyboard play, reduced motion and no-script fallbacks pass.`);
} finally { await browser.close(); }
