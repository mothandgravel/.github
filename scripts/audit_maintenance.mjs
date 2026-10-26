/** Static-deployment journeys and the PR #85 layout, focus and evidence regressions. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import axe from 'axe-core';
import { launchAuditBrowser } from './audit_browser.mjs';

const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const out = process.env.AUDIT_OUTPUT || 'artifacts/design-review/maintenance';
await mkdir(out, { recursive: true });
const browser = await launchAuditBrowser();
const results = [];
const ma = '/specimens/maintenance-acceptance/';
const tnt = ma + 'tnt/';

async function within(page, selector, container = 'main') {
  const overflow = await page.locator(selector).evaluateAll((elements, parent) => elements.flatMap((el) => {
    const rect = el.getBoundingClientRect(), bounds = el.closest(parent).getBoundingClientRect();
    return rect.left < Math.max(0, bounds.left) - 1 || rect.right > Math.min(innerWidth, bounds.right) + 1 || el.scrollWidth > el.clientWidth + 1
      ? [{ id: el.id, left: rect.left, right: rect.right, scroll: el.scrollWidth, client: el.clientWidth }] : [];
  }), container);
  assert.deepEqual(overflow, [], selector + ' is clipped');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'Document overflow');
}

async function accessible(page, label) {
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async () => (await axe.run(document.querySelector('main'), {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
  })).violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) })));
  assert.deepEqual(violations, [], label + ' accessibility');
}

try {
  for (const width of [320, 375, 600, 768, 1440]) for (const theme of ['night', 'afterlight']) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
    const errors = [], writes = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url()); });
    await page.addInitScript((value) => localStorage.setItem('moth-and-gravel-theme', value), theme);
    const label = `${width}-${theme}`;
    await page.goto(origin + ma);
    await page.waitForFunction(() => document.querySelector('#ma-steps').children.length >= 6);
    for (const scenario of ['lost-reply', 'acceptance-held']) {
      await page.locator('#ma-scenario').selectOption(scenario);
      for (const point of ['Home', 'End']) {
        await page.locator('#ma-cursor').press(point);
        await within(page, '.ma-change > div, .ma-change strong, #ma-change-note', '.ma-change');
      }
      assert.equal(await page.locator('#ma-http-code').innerText(), scenario === 'lost-reply' ? 'HTTP 200' : 'HTTP 503');
      assert.equal(await page.locator('#ma-starts').innerText(), '1');
      assert.equal(await page.locator('#ma-queries').innerText(), '1');
      assert.equal(await page.locator('#ma-writes').innerText(), '1');
      await page.locator('#ma-steps button').filter({ hasText: 'Dispatch intent saved' }).click();
      assert.equal(await page.locator('#ma-receiver-state').innerText(), 'UNKNOWN');
      assert.equal(await page.locator('#ma-receiver-detail').innerText(), 'outcome unresolved');
      const first = page.locator('#ma-steps button').first();
      await first.focus(); await page.keyboard.press('Enter');
      assert.equal(await first.evaluate((el) => el === document.activeElement), true, 'Step focus lost');
      assert.equal(await first.getAttribute('aria-current'), 'step');
      await page.locator('#ma-cursor').press('End');
      await page.locator('#ma-cursor').press('ArrowLeft');
      await page.locator('#ma-next').focus(); await page.keyboard.press('Enter');
      assert.equal(await page.locator('#ma-next').evaluate((el) => el === document.activeElement), true, 'Last Next focus lost');
      assert.equal(await page.locator('#ma-next').getAttribute('aria-disabled'), 'true');
      const finalLabel = await page.locator('#ma-cursor-label').innerText();
      await page.keyboard.press('Space');
      assert.equal(await page.locator('#ma-cursor-label').innerText(), finalLabel, 'Disabled Next advanced');
    }
    await page.locator('#ma-cursor').press('Home');
    await page.locator('#ma-prev').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('#ma-prev').evaluate((el) => el === document.activeElement), true);
    assert.equal(await page.locator('#ma-prev').getAttribute('aria-disabled'), 'true');
    await page.locator('#ma-steps button').nth(1).focus(); await page.keyboard.press('Space');
    await page.locator('#ma-play').click();
    await page.locator('#ma-steps button').nth(1).focus();
    await page.waitForFunction(() => document.querySelector('#ma-steps button[aria-current=step]') !== document.activeElement);
    assert.equal(await page.locator('#ma-steps button').nth(1).evaluate((el) => el === document.activeElement), true, 'Playback stole focus');
    await page.locator('#ma-play').click();
    await page.locator('#ma-cursor').press('End');
    await page.locator('#ma-evidence-drawer summary').click();
    await page.locator('[data-evidence=verification]').click();
    assert.match(await page.locator('#ma-json').innerText(), /"httpStatus": 503/);
    await accessible(page, label + '-maintenance');
    await page.locator('.ma-change').screenshot({ path: `${out}/${label}-configuration.png` });

    await page.goto(origin + tnt);
    await page.waitForFunction(() => !document.querySelector('#tn-end').disabled);
    await page.locator('#tn-packet').fill('1000'); await page.locator('#tn-packet').press('Enter');
    await page.locator('#tn-cursor').press('End');
    await page.locator('[data-weave-scope=packet]').click();
    assert.equal(await page.locator('#tn-count-sent').innerText(), '1,000');
    assert.equal(await page.locator('#tn-count-received').innerText(), '927');
    assert.match(await page.locator('#tn-weave-carry').innerText(), /73 without receive rows at capture end/);
    await within(page, '#tn-weave-carry, #tn-weave-canvas', '.tn-weave');
    await page.locator('.tn-weave').screenshot({ path: `${out}/${label}-time-weave.png` });
    await page.locator('#tn-cursor').press('ArrowLeft');
    assert.match(await page.locator('#tn-weave-carry').innerText(), /\d+ awaiting a receive observation/);
    await within(page, '#tn-weave-carry', '.tn-weave');
    await page.locator('#tn-to-send').click();
    await page.locator('[data-evidence=receiver]').click();
    assert.equal(await page.locator('#tn-row').innerText(), 'NO ROW AT THIS POINT');
    assert.deepEqual(JSON.parse(await page.locator('#tn-json').innerText()), { state: 'awaiting', evidence: 'No receiver observation is present at this replay point.' });
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#tn-export').click();
    const download = await downloadEvent, exportedPath = `${out}/${label}-prefix.json`;
    await download.saveAs(exportedPath);
    const exported = JSON.parse(await readFile(exportedPath, 'utf8'));
    assert.equal(exported.selected.receiver, null);
    assert.ok(exported.events.every((event) => event.atUs <= exported.cursorUs));
    await page.locator('#tn-open-image').click();
    assert.equal(await page.locator('#tn-close-image').evaluate((el) => el === document.activeElement), true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#tn-image-dialog').evaluate((el) => el.open), false);
    assert.equal(await page.locator('#tn-open-image').evaluate((el) => el === document.activeElement), true);
    await accessible(page, label + '-tnt');
    // Exercise both actual links rather than accepting an href-only assertion.
    for (const selector of ['.tn-boundary a', '.tn-rehearsal-copy a']) {
      if (!page.url().includes('/tnt/')) {
        await page.goto(origin + tnt);
        await page.waitForFunction(() => !document.querySelector('#tn-end').disabled);
      }
      await page.locator(selector).click();
      await page.waitForFunction(() => document.querySelector('#ma-steps')?.children.length >= 6);
      assert.equal(new URL(page.url()).searchParams.has('mode'), false);
      assert.equal(await page.locator('#ma-status').getAttribute('data-error'), 'false');
      assert.match(await page.locator('#ma-status').innerText(), /Captured runtime evidence/);
    }
    if (width === 320 && theme === 'night') {
      await page.goto(origin + ma + '?mode=live#ma-bench');
      await page.waitForFunction(() => document.querySelector('#ma-status').textContent.includes('Showing captured runtime evidence'));
      assert.equal(await page.locator('#ma-status').getAttribute('data-error'), 'false');
      assert.equal(await page.locator('#ma-new').isVisible(), false);
    }
    assert.deepEqual(errors, [], label + ' runtime errors');
    assert.deepEqual(writes, [], label + ' static specimen sent a mutation');
    results.push({ width, theme, scenarios: 2, keyboard: 'steps, boundaries, playback and dialog', navigation: 'both CTAs and optional live fallback', prefixExport: 'verified', overflow: false, axeViolations: 0, errors, writes });
    await page.close();
  }
  await writeFile(`${out}/audit.json`, JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(results, null, 2));
} finally { await browser.close(); }
