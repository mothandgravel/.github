/** Maritime study specimen and Field Note 014: boundaries, films, both appearances, narrow layouts and no-script access. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, writeFile } from 'node:fs/promises';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
await mkdir(output, { recursive: true });
const options = process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {};
const browser = await launchAuditBrowser(options);
const pages = [
  { name: 'maritime-study', path: '/specimens/maritime-study/' },
  { name: 'maritime-note', path: '/notes/014-enough-light-to-read-by.html' },
];
const results = [];
let filmCheck = 'not run';
const fail = (label, detail) => { throw Error(label + ': ' + JSON.stringify(detail)); };
try {
  for (const target of pages) for (const width of [320, 390, 1440]) for (const theme of ['night', 'afterlight']) {
    const label = `${target.name}-${width}-${theme}`;
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if (response.status() >= 400 && response.url().startsWith(origin)) errors.push(`HTTP ${response.status()} ${response.url()}`); });
    await page.addInitScript(value => localStorage.setItem('moth-and-gravel-theme', value), theme);
    await page.goto(origin + target.path, { waitUntil: 'networkidle' });
    if (await page.locator('html').getAttribute('data-theme') !== theme) fail(label, 'theme not applied');
    for (const image of await page.locator('main img').all()) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(image => image.decode());
    }
    const check = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
      headings: document.querySelectorAll('h1').length,
      images: [...document.querySelectorAll('main img')].every(image => image.naturalWidth > 0 && image.alt.trim()),
      videos: [...document.querySelectorAll('main video')].map(video => ({
        autoplay: video.autoplay, muted: video.muted, preload: video.preload, controls: video.controls,
        poster: !!video.dataset.poster, described: (video.getAttribute('aria-describedby') || '').split(' ').every(id => document.getElementById(id)),
        idle: video.networkState !== HTMLMediaElement.NETWORK_LOADING || video.readyState === 0,
      })),
      boundaries: /not navigation/i.test(document.body.innerText),
      leaks: /github\.com\/navivra|compliance verified|SOLAS|ISPS/.test(document.documentElement.outerHTML),
    }));
    if (check.overflow || check.headings !== 1 || !check.images || !check.boundaries || check.leaks || errors.length) fail(label, { check, errors });
    if (target.name === 'maritime-study') {
      if (check.videos.length !== 3 || check.videos.some(v => v.autoplay || !v.muted || v.preload !== 'none' || !v.controls || !v.poster || !v.described)) fail(label, check.videos);
      if (await page.locator('#boundaries li').count() !== 6) fail(label, 'boundaries list incomplete');
    }
    if (width === 390 || width === 1440) {
      await page.addScriptTag({ content: axe.source });
      const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } }))
        .violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) })));
      if (violations.length) fail(label + ' axe', violations);
      await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
      await page.screenshot({ path: `${output}/${label}-opening.png` });
      await page.screenshot({ path: `${output}/${label}.png`, fullPage: true });
    }
    results.push({ label, ...check, videos: check.videos.length });
    await page.close();
  }
  // A film plays only on request, and leaves the screen paused.
  const film = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await film.goto(origin + '/specimens/maritime-study/', { waitUntil: 'networkidle' });
  const video = film.locator('#motion video');
  await video.scrollIntoViewIfNeeded();
  if (!(await video.evaluate(v => v.paused))) fail('film', 'played before request');
  await film.waitForFunction(() => document.querySelector('#motion video').getAttribute('poster'), null, { timeout: 5000 });
  // Open-source Chromium builds may lack H.264; then playback cannot start and the pause check is recorded as skipped.
  await video.evaluate(v => { v.play().catch(() => {}); });
  const playback = await film.waitForFunction(() => { const v = document.querySelector('#motion video'); return v.error ? 'unsupported' : (!v.paused && v.readyState >= 2 ? 'playing' : false); }, null, { timeout: 15000 }).then(h => h.jsonValue(), () => 'unsupported');
  if (playback === 'playing') {
    await film.locator('#boundaries').scrollIntoViewIfNeeded();
    await film.waitForFunction(() => document.querySelector('#motion video').paused, null, { timeout: 5000 });
  }
  filmCheck = playback === 'playing' ? 'pauses off-screen' : 'H.264 unavailable in this browser; pause check skipped';
  await film.close();
  const noScript = await browser.newPage({ viewport: { width: 390, height: 844 }, javaScriptEnabled: false });
  for (const target of pages) {
    await noScript.goto(origin + target.path, { waitUntil: 'networkidle' });
    if (await noScript.locator('h1').count() !== 1 || await noScript.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) fail(target.name, 'unreadable without JavaScript');
  }
  await noScript.goto(origin + '/', { waitUntil: 'load' });
  if (await noScript.locator('#specimen-maritime-study a[href="./specimens/maritime-study/"]').count() !== 1) fail('home', 'maritime study not on the bench');
  await noScript.close();
  await writeFile(`${output}/maritime-review.json`, JSON.stringify({ results, film: filmCheck, noScript: true }, null, 2));
  console.log(`PASS: maritime study and Field Note 014 at ${results.length} page/viewport/theme combinations, films on request (${filmCheck}), no-script access`);
} finally { await browser.close(); }
