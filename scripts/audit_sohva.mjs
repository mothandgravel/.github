/** The Sohva room: selected source rules, keyboard, both appearances and native fallback. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';

const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review/sohva';
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {});
const pages = [['sohva-room','/specimens/sohva/'],['sohva-note','/notes/018-leave-the-evening-alone.html']];
const results = [];
function assert(condition, message) { if (!condition) throw new Error(message); }
try {
  for (const width of [320,390,768,1440]) for (const theme of ['night','afterlight']) {
    for (const [name, path] of pages) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      await page.addInitScript(t => localStorage.setItem('moth-and-gravel-theme', t), theme);
      const response = await page.goto(origin + path, { waitUntil: 'networkidle' });
      assert(response.status() === 200, `${path}: response`);
      assert(await page.locator('h1').count() === 1, `${path}: heading`);
      if (name === 'sohva-room') assert(await page.locator('#break-start').isVisible(), `${path}: interaction module must load`);
      for (const image of await page.locator('img').all()) {
        await image.scrollIntoViewIfNeeded();
        await image.evaluate(element => element.decode());
      }
      await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
      assert(await page.locator('img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0)), `${path}: images`);
      assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `${name}/${width}/${theme}: horizontal overflow`);
      await page.addScriptTag({ content: axe.source });
      const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a','wcag2aa','wcag21aa'] })).violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })));
      assert(violations.length === 0, `${name}/${width}/${theme}: ${JSON.stringify(violations)}`);
      assert(errors.length === 0, `${path}: ${errors.join('; ')}`);
      if (width === 390 || width === 1440) await page.screenshot({ path: `${output}/${name}-${width}-${theme}.png`, fullPage: true });
      if (name === 'sohva-room' && (width === 390 || width === 1440)) {
        await page.locator('#evening').screenshot({ path: `${output}/sohva-controls-${width}-${theme}.png` });
        await page.locator('.evening-phone').screenshot({ path: `${output}/sohva-phone-${width}-${theme}.png` });
      }
      results.push({ name, width, theme, axe: 'pass', overflow: false, errors });
      await page.close();
    }
  }
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  await page.goto(origin + '/specimens/sohva/', { waitUntil: 'networkidle' });
  const muted = async () => page.locator('#evening-room').getAttribute('data-muted');
  await page.locator('#break-start').click();
  assert(await muted() === 'true', 'Break must mute');
  await page.locator('#break-end').click();
  assert(await muted() === 'false', 'Break must restore its mute');
  await page.locator('#break-reset').click();
  await page.locator('#already-muted').check();
  await page.locator('#break-start').click();
  await page.locator('#break-end').click();
  assert(await muted() === 'true', 'Existing personal mute must survive');
  await page.screenshot({ path: `${output}/sohva-personal-mute.png`, fullPage: true });
  await page.locator('#break-reset').click();
  await page.locator('#break-start').click();
  await page.locator('#break-unmute').click();
  await page.locator('#break-end').click();
  assert(await muted() === 'false', 'Manual unmute must not be toggled at the end');

  // Native radio navigation: arrows change the visible act without moving focus into hidden content.
  await page.locator('input[name="evening-act"][value="break"]').focus();
  await page.keyboard.press('ArrowRight');
  assert(await page.locator('[data-act-panel="plan"]').isVisible(), 'Keyboard must reach familiar hour');
  assert(await page.locator('input[name="evening-act"][value="plan"]').evaluate(el => el === document.activeElement), 'Act focus must remain on its radio');
  await page.locator('#plan-run').click();
  assert(await page.locator('#evening-room').getAttribute('data-power') === 'off', 'Scene must leave standby alone');
  await page.screenshot({ path: `${output}/sohva-empty-room.png`, fullPage: true });
  await page.locator('input[name="evening-plan"][value="wake"]').check();
  await page.locator('#plan-run').click();
  assert(await page.locator('#evening-room').getAttribute('data-power') === 'on', 'Wake-up may switch on');
  await page.locator('#tv-awake').check();
  await page.locator('input[name="evening-plan"][value="scene"]').check();
  await page.locator('#plan-run').click();
  assert(await page.locator('#room-programme').textContent() === 'Channel 1', 'Scene must apply while on');

  await page.locator('input[name="evening-act"][value="plan"]').focus();
  await page.keyboard.press('ArrowRight');
  await page.locator('#sleep-time').focus();
  await page.keyboard.press('End');
  assert(await page.locator('#evening-room').getAttribute('data-power') === 'off', 'Final minute must reach standby');
  assert((await page.locator('#result-detail').textContent()).includes('30'), 'Earlier level must be remembered');
  await page.screenshot({ path: `${output}/sohva-last-minute.png`, fullPage: true });
  await page.keyboard.press('Home');
  assert(await page.locator('#evening-room').getAttribute('data-power') === 'on', 'Inspection clock must be reversible');
  assert((await page.locator('#room-sound').textContent()).includes('30'), 'Beginning of last minute');
  // Explicitly load axe for this separately exercised state.
  await page.addScriptTag({ content: axe.source });
  assert((await page.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a','wcag2aa','wcag21aa'] })).violations)).length === 0, 'Last-minute state accessibility');
  await page.close();

  for (const [name,path] of pages) {
    const plain = await browser.newPage({ viewport: { width: 320, height: 900 }, javaScriptEnabled: false });
    await plain.goto(origin + path, { waitUntil: 'networkidle' });
    assert(!(await plain.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `${name}: no-script overflow`);
    assert(await plain.locator('h1').isVisible(), `${name}: no-script title`);
    if (name === 'sohva-room') {
      assert(await plain.locator('.evening-static').isVisible(), 'All three no-script moments must be readable');
      assert(await plain.locator('[data-evening-controls]:visible').count() === 0, 'No dead controls without scripts');
      await plain.locator('#record').evaluate(el => el.open = true);
      assert(await plain.locator('#record a[href*="16e47c3"]').first().isVisible(), 'Source record without scripts');
    }
    await plain.close();
  }
  const routes = await browser.newPage();
  await routes.goto(origin + '/notes/');
  assert(await routes.locator('a[href="./018-leave-the-evening-alone.html"]').count() > 0, 'Note must be discoverable');
  await routes.goto(origin + '/specimens/');
  assert(await routes.locator('#specimen-010 a[href="./sohva/"]').count() > 0, 'Specimen must be discoverable');
  await routes.close();
  await writeFile(`${output}/sohva-review.json`, JSON.stringify({ results, behaviours: ['break-owned mute','personal mute','manual unmute','scene skips standby','wake-up starts TV','scene applies while on','six-step fade','reversible clock','keyboard acts'], noScript: true }, null, 2));
  console.log(`PASS: ${results.length} Sohva layout/appearance combinations, mute ownership, scheduled/wake-up distinction, final minute, keyboard and no-script access.`);
} finally { await browser.close(); }
