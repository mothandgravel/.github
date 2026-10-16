/** A written note must lead somewhere deliberately, with ordinary navigation. */
import { launchAuditBrowser } from './audit_browser.mjs';
import axe from 'axe-core';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { draftKey } from '../docs/assets/loose-end-model-v2.mjs';
import { execFileSync } from 'node:child_process';
const origin = process.env.SITE_URL || 'http://127.0.0.1:8793';
const output = process.env.AUDIT_OUTPUT || 'artifacts/design-review';
const notes = JSON.parse(await readFile('docs/assets/notes.json', 'utf8'));
const browser = await launchAuditBrowser({ headless: true });
const results = [], failures = [];
let assertions = 0;
const assert = (value, label) => { assertions++; if (!value) failures.push(label); };
await mkdir(output, { recursive: true });
async function review(page, label, capture = false) {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), label + ': no horizontal overflow');
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async () => (await axe.run(document)).violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })));
  assert(!violations.length, label + ': ' + JSON.stringify(violations));
  results.push({ label, violations });
  if (capture) await page.screenshot({ path: join(output, label + '.png'), animations: 'disabled' });
}
async function followContinuation(page, note, collection) {
  const exit = page.locator('.reading-exit');
  assert(await exit.count() === 1, note.id + ': one coherent ending');
  const links = await exit.locator('a').evaluateAll(els => els.map(el => el.getAttribute('href')));
  assert(new Set(links).size === links.length, note.id + ': distinct exits without repeated recommendations');
  const nextId = note.nextReading?.id || note.related?.[0];
  const next = collection.find(n => n.id === nextId);
  if (next) {
    const bridge = note.nextReading?.bridge || next.summary;
    assert(!await exit.locator('.reading-next').getAttribute('aria-labelledby') && (await exit.locator('.reading-next').innerText()).includes(bridge), note.id + ': native link name retains its visible connection');
    await exit.locator('.reading-next').focus(); await page.keyboard.press('Enter');
    await page.waitForURL(origin + '/notes/' + next.slug);
    assert(await page.locator('h1').count() === 1 && await page.locator('article.note-prose').first().isVisible(), note.id + ': opens a complete published article');
  } else assert(await exit.locator('.reading-next').count() === 0, note.id + ': independent note has no invented recommendation');
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), note.id + ': article fits viewport');
}
try {
  for (const width of [1440, 1024, 768, 390, 320]) for (const theme of ['night', 'afterlight']) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(theme => localStorage.setItem('moth-and-gravel-theme', theme), theme);
    await page.goto(origin + '/notes/');
    await page.locator('#archive-controls').waitFor({ state: 'visible' });
    await review(page, `reading-entrance-${width}-${theme}`, [1440, 390, 320].includes(width));
    for (const [fragment, focus] of [['reading-selection', true], ['archive-title', true], ['listen-archive', false]]) {
      const link = page.locator(`.notes-wayfinding a[href="#${fragment}"]`);
      await link.focus(); await page.keyboard.press('Enter');
      const target = page.locator('#' + fragment);
      assert(await target.evaluate(el => { const r = el.getBoundingClientRect(); return r.top >= 72 && r.top < innerHeight; }), `${width}/${theme}/${fragment}: landing below header`);
      if (focus) assert(await page.evaluate(id => document.activeElement.id === id, fragment), fragment + ': keyboard focus follows native anchor');
    }
    for (const id of ['003', '013']) {
      const note = notes.find(n => n.id === id);
      await page.goto(origin + '/notes/' + note.slug);
      await page.locator('.reading-exit').scrollIntoViewIfNeeded();
      if (await page.locator('.reading-next').count())
        assert(await page.locator('.reading-next').evaluate(el => getComputedStyle(el).transform === 'none'), 'Reading surface remains still');
      else assert(await page.locator('.reading-alternatives').isVisible(), 'Independent ending keeps its native exits');
      await review(page, `reading-ending-${id}-${width}-${theme}`, [1440, 390, 320].includes(width));
    }
    assert(!errors.length, `${width}/${theme}: no browser errors ${errors}`);
    await page.close();
  }
  // Follow every recommendation, rather than merely comparing generated strings.
  const page = await browser.newPage({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
  const journeyErrors = [];
  page.on('pageerror', error => journeyErrors.push(error.message));
  for (const note of notes) {
    await page.goto(origin + '/notes/' + note.slug);
    await followContinuation(page, note, notes);
  }
  await page.goto(origin + '/notes/?topic=Robotics&sort=oldest#archive');
  await page.locator('#archive-controls').waitFor({ state: 'visible' });
  const before = await page.locator('#archive-results').innerText();
  await page.locator('#archive-results h3 a').first().click();
  await page.goBack();
  await page.locator('#archive-controls').waitFor({ state: 'visible' });
  assert(await page.locator('#archive-results').innerText() === before, 'Browser Back restores the selected archive results');
  assert(await page.locator('#archive-topic').inputValue() === 'Robotics' && await page.locator('#archive-sort').inputValue() === 'oldest', 'Archive controls reflect restored URL');
  await page.goto(origin + '/notes/012-the-picture-stays.html');
  await page.locator('.reading-exit a[href="../specimens/coastal-watch/"]').click();
  assert(new URL(page.url()).pathname === '/specimens/coastal-watch/', 'Source specimen return survives the new ending');
  await page.goto(origin + '/notes/013-work-outlives-the-window.html');
  const saved = JSON.stringify({ version: 1, answers: { making: 'An existing unfinished question', difficulty: 'Keep these exact words.' } });
  await page.evaluate(({ key, saved }) => sessionStorage.setItem(key, saved), { key: draftKey, saved });
  // Exercise an actual deferred enhancement. Visible HTML can arrive before its
  // module restores the draft; the revealed controls mark initialization complete.
  let releaseModule;
  const moduleGate = new Promise(resolve => { releaseModule = resolve; });
  const modulePattern = '**/assets/loose-end-v2.mjs*';
  await page.route(modulePattern, async route => { await moduleGate; await route.continue(); });
  await page.getByRole('link', { name: 'Bring your version' }).click({ noWaitAfter: true });
  await page.waitForURL(origin + '/questions/', { waitUntil: 'commit' });
  await page.locator('#making').waitFor({ state: 'attached' });
  assert(await page.locator('#journey-controls').isHidden(), 'Question sheet remains native while its module is deferred');
  releaseModule();
  await page.locator('#journey-controls').waitFor({ state: 'visible' });
  await page.unroute(modulePattern);
  assert(new URL(page.url()).pathname === '/questions/', 'Invitation opens the actual question sheet');
  assert(await page.locator('#making').inputValue() === 'An existing unfinished question', 'Editorial invitation restores the visitor’s own words');
  assert(await page.evaluate(key => sessionStorage.getItem(key), draftKey) === saved, 'Reading route does not replace stored material');
  await page.evaluate(key => sessionStorage.removeItem(key), draftKey);
  await page.goto(origin + '/notes/013-work-outlives-the-window.html');
  await page.getByRole('link', { name: 'Bring your version' }).click();
  await page.locator('#journey-controls').waitFor({ state: 'visible' });
  assert(await page.locator('#making').inputValue() === '', 'Fresh editorial invitation does not invent a visitor’s question');
  assert(!journeyErrors.length, 'Reading and question journeys have no browser errors: ' + journeyErrors);
  await page.close();
  const fallback = await browser.newPage({ viewport: { width: 320, height: 900 }, javaScriptEnabled: false });
  await fallback.goto(origin + '/notes/');
  assert(await fallback.locator('#archive-fallback article').count() === notes.length, 'No-script archive retains the whole collection');
  await fallback.locator('.notes-wayfinding a[href="#reading-selection"]').click();
  assert(new URL(fallback.url()).hash === '#reading-selection', 'Reading entrance needs no script');
  for (const note of notes) {
    await fallback.goto(origin + '/notes/' + note.slug);
    const hasNext = Boolean(note.nextReading?.id || note.related?.length);
    assert(hasNext ? await fallback.locator('.reading-next').isVisible() : await fallback.locator('.reading-next').count() === 0, note.id + ': no-script continuation reflects available relationships');
    assert(await fallback.locator('.reading-exit a[href="../questions/"]').isVisible(), note.id + ': no-script invitation visible');
  }
  await fallback.close();
  const denied = await browser.newPage({ viewport: { width: 390, height: 900 } });
  await denied.route('**/assets/notes.json', route => route.abort());
  await denied.goto(origin + '/notes/', { waitUntil: 'networkidle' });
  assert(await denied.locator('#archive-fallback article').count() === notes.length && await denied.locator('#archive-controls').isHidden(), 'Failed catalog leaves the complete static reading route');
  await denied.close();
  // Render actual generator output for valid authoring states absent from today's
  // catalog. The fixture-only relationships never enter published pages or audio.
  const fixtures = JSON.parse(execFileSync('python3', ['scripts/reading_output.test.py', '--fixtures'], { encoding: 'utf8' }));
  const template = await readFile('docs/notes/001-curiosity-with-calluses.html', 'utf8');
  for (const fixture of fixtures) for (const width of [320, 1440]) {
    const sample = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
    const html = template.replace(/<!-- related-notes:start -->[\s\S]*?<!-- related-notes:end -->/, () => fixture.html);
    await sample.route('**/notes/001-curiosity-with-calluses.html', route => route.fulfill({ contentType: 'text/html', body: html }));
    await sample.goto(origin + '/notes/001-curiosity-with-calluses.html');
    await sample.locator('.reading-exit').scrollIntoViewIfNeeded();
    await review(sample, `reading-authoring-${fixture.case}-${width}`, true);
    if (!fixture.nextSlug) {
      const grid = sample.locator('.reading-exit-grid');
      assert(await grid.evaluate(el => Math.abs(el.getBoundingClientRect().width - el.firstElementChild.getBoundingClientRect().width) < 1), 'Independent ending uses the available width');
    }
    await followContinuation(sample, fixture.note, fixture.notes);
    await sample.close();
  }
} finally { await browser.close(); }
await writeFile(join(output, 'reading-review.json'), JSON.stringify({ assertions, results, failures }, null, 2));
console.log(JSON.stringify({ assertions, responsiveReviews: results.length, failures }, null, 2));
if (failures.length) process.exitCode = 1;
