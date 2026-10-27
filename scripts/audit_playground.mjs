/** Standing investigations, the three question pages and the playground: both appearances, narrow layouts,
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
  { name: 'how-old', path: '/investigations/how-old/', toys: ['week'], projects: ['raivari', 'liveconnect', 'decision-docket', 'mapping-buggy', 'vahti'] },
  { name: 'take-it-back', path: '/investigations/take-it-back/', toys: ['stamp'], projects: ['ajo', 'skystack-builder', 'decision-docket', 'raivari-rpc', 'paja', 'luotsi', 'verstas'] },
  { name: 'green-light', path: '/investigations/green-light/', toys: ['grid'], projects: ['geaidnu', 'flutter-test-rs', 'decision-docket', 'cyber-grid'] },
  { name: 'playground', path: '/workbench/playground/', toys: ['grid', 'stamp', 'week'] },
];
const results = [];
try {
  for (const target of pages) for (const width of (target.name === 'investigations' || target.projects ? [320, 390, 430, 768, 1024, 1440] : [320, 390, 1440])) for (const theme of ['night', 'afterlight']) {
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
      if (made.items !== 16 || made.height > made.reserve + 0.5) fail(label + ' made here', made);
    } else if (target.name === 'playground' && width === 1440 && toyRequests.some(url => /playground\/(stamp|week)\.mjs/.test(url)))
      fail(label, { eagerToys: toyRequests });
    if (target.name === 'investigations') {
      const index = await page.evaluate(() => {
        const rows = [...document.querySelectorAll('.question-index>li')];
        const labels = [...document.querySelectorAll('.question-made>li')];
        const contains = (outer, inner) => {
          const a = outer.getBoundingClientRect(), b = inner.getBoundingClientRect();
          return b.left >= a.left - 1 && b.right <= a.right + 1 && b.top >= a.top - 1 && b.bottom <= a.bottom + 1;
        };
        return {
          rows: rows.length,
          projects: rows.map(row => row.querySelectorAll('.question-made>li').length),
          // A nested project label used to inherit the outer question's three-column grid.
          // Check actual text fit, rather than merely asserting the replacement CSS selector.
          stretchedLabels: labels.filter(item => {
            const text = document.createRange(); text.selectNodeContents(item);
            const style = getComputedStyle(item);
            const inset = ['paddingLeft', 'paddingRight', 'borderLeftWidth', 'borderRightWidth']
              .reduce((sum, key) => sum + parseFloat(style[key]), 0);
            return item.getBoundingClientRect().width > text.getBoundingClientRect().width + inset + 1
              || text.getClientRects().length !== 1 || item.scrollWidth > item.clientWidth;
          }).map(item => item.textContent),
          escapedContent: rows.flatMap(row => [...row.querySelectorAll('h2,.question-detail,.question-made>li')]
            .filter(item => !contains(row, item)).map(item => item.textContent)),
          register: document.querySelectorAll('#made-here li').length,
          clippedRegister: [...document.querySelectorAll('#made-here li')].filter(item =>
            [...item.children].some(child => !contains(item, child) || child.scrollWidth > child.clientWidth)
          ).map(item => item.textContent),
          exits: [...document.querySelectorAll('.investigation-exits a')].map(a => new URL(a.href).pathname),
        };
      });
      if (index.rows !== 3 || JSON.stringify(index.projects) !== '[5,7,4]' || index.register !== 16
        || index.stretchedLabels.length || index.escapedContent.length || index.clippedRegister.length
        || JSON.stringify(index.exits) !== '["/notes/","/specimens/","/questions/"]') fail(label + ' index integrity', index);
    }
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
    if (target.projects) {
      const chapter = await page.evaluate(() => {
        const inside = (a, b) => { const x = a.getBoundingClientRect(), y = b.getBoundingClientRect();
          return y.left >= x.left - 1 && y.right <= x.right + 1 && y.top >= x.top - 1 && y.bottom <= x.bottom + 1; };
        return {
          projects: [...document.querySelectorAll('.made-stop')].map(el => el.id),
          paths: [...document.querySelectorAll('.question-paths a')].map(a => a.getAttribute('href')),
          clipped: [...document.querySelectorAll('.question-kicker,.thread-heading h1,.thread-margin>p,.thread-margin .status,.question-bridge a,.question-peers a')]
            .filter(el => el.scrollWidth > el.clientWidth + 1 || !inside(el.parentElement, el)).map(el => el.textContent),
          // A document can hide horizontal overflow while its narrow project folios still overlap.
          crossedFolios: [...document.querySelectorAll('.thread-margin')].filter(el => {
            const [a,b] = [...el.children].map(child => child.getBoundingClientRect());
            return a.right > b.left + 1 && b.right > a.left + 1 && a.bottom > b.top + 1 && b.bottom > a.top + 1;
          }).map(el => el.textContent),
          featured: [...document.querySelectorAll('.question-feature>a')].map(a => new URL(a.href).pathname + new URL(a.href).hash),
          // A saved Ajo trace must not borrow SkyStack's footprint preview.
          mismatchedPreview: [...document.querySelectorAll('.question-feature>a')].some(a =>
            new URL(a.href).hash === '#specimen-ajo' && (!a.querySelector('.question-trace') || a.querySelector('img'))),
          peers: [...document.querySelectorAll('.question-peers>a')].map(a => new URL(a.href).pathname),
          lists: [...document.querySelectorAll('.room-tabs,.question-shelf ul')].every(el => el.getAttribute('role') === 'list'),
        };
      });
      const peers = pages.filter(p => p.projects && p.name !== target.name).map(p => p.path);
      if (JSON.stringify(chapter.projects) !== JSON.stringify(target.projects)
        || JSON.stringify(chapter.paths) !== JSON.stringify([`#${target.toys[0]}`, '#shelf-notes', '#shelf-specimens'])
        || chapter.clipped.length || chapter.crossedFolios.length || !chapter.lists || chapter.featured.length !== 2
        || chapter.mismatchedPreview
        || JSON.stringify(chapter.peers) !== JSON.stringify(peers)) fail(label + ' chapter integrity', chapter);
      if (width === 390 && theme === 'night') {
        const destinations = await page.locator('.question-bridge a,.question-shelf a').evaluateAll(links =>
          [...new Set(links.map(a => { const url = new URL(a.href); return url.origin + url.pathname; }))]);
        for (const url of destinations) {
          if (new URL(url).origin !== new URL(origin).origin) fail(label + ' unexpected external connection', url);
          const response = await page.request.head(url);
          if (response.status() !== 200) fail(label + ' connection response', { url, status: response.status() });
        }
        for (const id of ['shelf-notes', 'shelf-specimens']) {
          await page.locator(`.question-paths a[href="#${id}"]`).focus(); await page.keyboard.press('Enter');
          await page.waitForFunction(id => {
            const target = document.getElementById(id), box = target.getBoundingClientRect();
            return document.activeElement === target && box.top >= document.querySelector('.site-header').getBoundingClientRect().bottom - 1 && box.top < innerHeight - 24;
          }, id);
          const link = page.locator(`[aria-labelledby="${id}"] .question-feature>a`);
          const destination = await link.getAttribute('href');
          const expected = new URL(destination, page.url());
          await link.focus(); await page.keyboard.press('Enter');
          await page.waitForURL(expected.href);
          await page.waitForLoadState('domcontentloaded');
          if (expected.hash) await page.locator(expected.hash).waitFor({ state: 'visible' });
          else if (await page.locator('h1').count() !== 1) fail(label + ' connection destination', expected.href);
          await page.goBack();
          await page.locator('.question-paths').waitFor({ state: 'visible' });
          if (new URL(page.url()).pathname !== target.path) fail(label + ' connection return', page.url());
        }
        for (const toy of target.toys) {
          await page.locator(`#toy-${toy}`).scrollIntoViewIfNeeded();
          await page.locator(`#toy-${toy}[data-loaded="ready"]`).waitFor({ timeout: 5000 });
        }
      }
    }
    const check = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
      headings: document.querySelectorAll('h1').length,
      // Reduced motion shortens every transition to a hundredth of a millisecond (site.css); only real motion counts.
      animating: document.getAnimations().filter(a => a.playState === 'running' && (a.effect?.getComputedTiming().duration ?? 0) > 50).length,
      leaks: /navivra|kistradegoods|digablesolutions|vesuno|run\.app/i.test(document.documentElement.outerHTML),
    }));
    if (check.overflow || check.headings !== 1 || check.animating || check.leaks || errors.length) fail(label, { check, errors });
    if (width !== 320 || target.name === 'investigations' || target.projects) {
      // Axe runs on the page at rest at its top: anything scrolled under the sticky header would
      // otherwise read as an obscured target.
      await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
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

  // The question pages open with their toy, and it plays from the keyboard there too.
  const question = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await question.goto(origin + '/investigations/how-old/', { waitUntil: 'networkidle' });
  await question.locator('#toy-week').scrollIntoViewIfNeeded(); await question.locator('#toy-week[data-loaded="ready"]').waitFor();
  await question.locator('#toy-week input[value="ring"]').focus(); await question.keyboard.press('Space');
  await question.locator('#toy-week .week-item').nth(1).focus(); await question.keyboard.press('Enter');
  if ((await question.locator('#toy-week .week-detail h3').textContent()) !== 'A choice now has a name.') fail('how-old keyboard', 'week item not chosen');
  await question.goto(origin + '/investigations/take-it-back/', { waitUntil: 'networkidle' });
  await question.locator('#toy-stamp').scrollIntoViewIfNeeded(); await question.locator('#toy-stamp[data-loaded="ready"]').waitFor();
  await question.locator('#toy-stamp .stamp-cell[tabindex="0"]').focus();
  await question.keyboard.press('Enter'); await question.waitForTimeout(80);
  if (!/^Placed\./.test(await question.locator('#toy-stamp [data-status]').textContent())) fail('take-it-back keyboard', 'stamp not placed');
  await question.locator('#toy-stamp [data-undo]').focus(); await question.keyboard.press('Enter'); await question.waitForTimeout(80);
  if (!/^Undone\./.test(await question.locator('#toy-stamp [data-status]').textContent())) fail('take-it-back keyboard', 'undo did not take the stamp back');
  await question.close();

  // Without JavaScript, every bench still says what its toy shows.
  const quiet = await browser.newContext({ javaScriptEnabled: false });
  const still = await quiet.newPage();
  await still.goto(origin + '/workbench/playground/');
  if (await still.locator('.toy-mount p').count() !== 3) fail('no-script', 'bench fallbacks missing');
  await still.goto(origin + '/');
  if (!(await still.locator('#made-here a[href="./investigations/#made-here"]').isVisible())) fail('no-script', 'Made here link missing on home');
  await still.goto(origin + '/investigations/');
  if (await still.locator('#made-here li').count() !== 16) fail('no-script', 'Made here list missing on the index');
  for (const path of ['/notes/', '/specimens/', '/questions/']) {
    const response = await still.request.head(origin + path);
    if (response.status() !== 200) fail('index exit destination', { path, status: response.status() });
  }
  for (const slug of ['how-old', 'take-it-back', 'green-light']) {
    const link = still.locator(`.question-title a[href="./${slug}/"]`);
    await link.focus(); await still.keyboard.press('Enter');
    await still.waitForURL(origin + `/investigations/${slug}/`);
    if (await still.locator('h1').count() !== 1) fail('no-script index journey', slug);
    await still.goBack();
  }
  await still.locator('#made-here a[href="../sohva/"]').focus(); await still.keyboard.press('Enter');
  await still.waitForURL(origin + '/sohva/');
  if (await still.locator('h1').count() !== 1) fail('no-script register journey', 'Sohva Remote did not open');
  await quiet.close();
  await writeFile(`${output}/playground-audit.json`, JSON.stringify({ results, verdicts }, null, 2));
  console.log(`Playground: ${results.length} page/width/theme checks, zero axe violations, no toys on home, Made here in its reserved box, lazy toys, keyboard play, reduced motion and no-script fallbacks pass.`);
} finally { await browser.close(); }
