import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const origin = process.env.SITE_URL ?? 'http://127.0.0.1:8793';
const parent = '/specimens/coastal-watch/source-notebook/21-november/';
const route = parent + 'sparta-ii/';
const out = 'artifacts/design-review/coastal-sparta';
await mkdir(out, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  for (const [name, width, height, colorScheme] of [
    ['desktop-night', 1440, 1050, 'dark'],
    ['mobile-afterlight', 390, 880, 'light'],
    ['narrow-night', 320, 800, 'dark'],
  ]) {
    const context = await browser.newContext({ viewport: { width, height }, colorScheme,
      javaScriptEnabled: name !== 'narrow-night', reducedMotion: 'reduce' });
    const page = await context.newPage();
    const outside = [];
    page.on('request', request => {
      if (new URL(request.url()).origin !== new URL(origin).origin) outside.push(request.url());
    });

    assert.equal((await page.goto(origin + route)).ok(), true);
    assert.match(await page.locator('h1').innerText(), /Sparta II/);
    assert.deepEqual(await page.locator('.sv-clock-mark time').evaluateAll(elements =>
      elements.map(element => element.dateTime)), ['2026-11-21T07:01:42.644Z', '2026-11-21T19:03:09Z']);
    assert.match(await page.locator('.sv-clock-gap strong').innerText(), /12 h 01 min 26\.356 s/);
    assert.equal(await page.locator('video, audio, iframe').count(), 0);
    assert.match(await page.getByRole('link', { name: 'Watch the source clip' }).getAttribute('href'), /2124217067708522514\/video\/1$/);

    await page.locator('img[loading="lazy"]').evaluateAll(images =>
      images.forEach(image => { image.loading = 'eager'; }));
    await page.locator('main img').evaluateAll(images => Promise.all(images.map(image => image.decode())));
    assert.equal(await page.locator('main img').count(), 7);
    assert.deepEqual(outside, []);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);

    await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
    await page.getByText('Inspect the other frames and regional catalogues', { exact: true }).click();
    assert.equal(await page.locator('.sv-frame-table tbody tr').count(), 5);
    const ledgerPath = await page.getByRole('link', { name: 'All catalogue bodies, frame receipts and licences' }).getAttribute('href');
    assert.equal((await page.request.get(new URL(ledgerPath, page.url()).href)).ok(), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
    await context.close();
  }
  const parentPage = await browser.newPage();
  await parentPage.goto(origin + parent);
  assert.equal(await parentPage.getByRole('link', {name: /Sparta II \/ A point and a fire/}).isVisible(), true);
  console.log('Sparta II: desktop, mobile, script-free use, image decoding, evidence clocks and discovery passed.');
} finally {
  await browser.close();
}
