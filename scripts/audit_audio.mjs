// Test real listening controls with synthetic clips. Never calls Google.
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {resolve, extname} from 'node:path';
const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const root = resolve(process.env.AUDIO_AUDIT_ROOT || 'artifacts/audio-site-qa/docs');
const output = resolve(process.env.AUDIO_AUDIT_OUTPUT || 'artifacts/audio-site-qa');
await mkdir(output, {recursive:true});
const syntheticMedia = root !== resolve('docs');
const expectedCount = JSON.parse(await readFile(root + '/assets/audio/episodes.json','utf8')).length;
const types = {'.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.mjs':'text/javascript', '.svg':'image/svg+xml', '.webp':'image/webp', '.png':'image/png', '.jpg':'image/jpeg', '.mp3':'audio/mpeg', '.vtt':'text/vtt', '.json':'application/json', '.xml':'application/xml', '.txt':'text/plain'};
const server = createServer(async (req, res) => {
  try {
    let path = resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
    if (!path.startsWith(root + '/') && path !== root) throw Error('Invalid path');
    if (!extname(path)) path += '/index.html';
    const data = await readFile(path);
    const headers = {'Content-Type':types[extname(path)] || 'application/octet-stream', 'Accept-Ranges':'bytes'};
    const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');
    let body = data;
    if (range) {
      const start = Number(range[1]), end = range[2] ? Math.min(Number(range[2]),data.length - 1) : data.length - 1;
      if (start > end || start >= data.length) { res.writeHead(416, {'Content-Range':`bytes */${data.length}`});res.end();return; }
      body = data.subarray(start,end + 1);headers['Content-Range'] = `bytes ${start}-${end}/${data.length}`;
    }
    headers['Content-Length'] = body.length;
    res.writeHead(range ? 206 : 200,headers);res.end(req.method === 'HEAD' ? undefined : body);
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({headless:true,args:['--no-sandbox']});
const reports = [];
const check = (condition, message) => { if (!condition) throw Error(message); };
try {
  for (const width of [320,390,1440]) for (const theme of ['night','afterlight']) {
    const page = await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'});
    const errors = [], requested = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (request.url().endsWith('.mp3')) requested.push(request.url()); });
    await page.goto(base + '/notes/001-curiosity-with-calluses.html');
    await page.evaluate(theme => document.documentElement.setAttribute('data-theme',theme), theme);
    await page.waitForFunction(() => !document.querySelector('[data-audio-speed]').closest('label').hidden);
    check(requested.length === 0, 'Note fetched audio before a playback action');
    await page.locator('#listen-note>summary').click();
    await page.locator('.audio-transcript>summary').click();
    const cue = page.locator('[data-audio-seek]').nth(1); await cue.focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('audio').currentTime >= 1.1 && !document.querySelector('audio').paused);
    check(await page.locator('audio').evaluate(a => a.playbackRate === 1.15), 'Article default speed is not 1.15');
    await page.waitForFunction(() => document.querySelectorAll('[data-cue-start][aria-current=true]').length === 1);
    await page.locator('audio').evaluate(a => a.pause());
    await page.addScriptTag({path:require.resolve('axe-core/axe.min.js')});
    const violations = await page.evaluate(async () => (await axe.run()).violations.map(v => ({id:v.id,nodes:v.nodes.map(n=>({html:n.html,summary:n.failureSummary}))})));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    check(!overflow && !violations.length && !errors.length, JSON.stringify({width,theme,overflow,violations,errors}));
    await page.screenshot({path:output + `/note-${width}-${theme}.png`,fullPage:true});
    await page.goto(base + '/notes/');
    await page.evaluate(theme => document.documentElement.setAttribute('data-theme',theme), theme);
    await page.waitForSelector('.has-audio-queue');
    check(!(await page.locator('.archive-session').evaluate(d => d.open)), 'Listening takes over the reading archive on arrival');
    await page.locator('.archive-session>summary').click();
    const count = await page.locator('[data-queue-index]').count(); check(count === expectedCount,'Queue lost an episode');
    await page.locator('[data-queue-start]').click();
    await page.waitForFunction(() => !document.querySelector('audio').paused && document.querySelector('audio').readyState >= 2);
    check(await page.locator('audio').evaluate(a => a.playbackRate === 1.15),'Queue default speed is not 1.15');
    await page.waitForFunction(() => document.querySelector('[data-queue-start]').textContent === 'Pause');
    await page.locator('[data-queue-start]').click();
    check(await page.locator('audio').evaluate(a => a.paused),'Pause action does not pause');
    await page.locator('[data-queue-start]').click();
    await page.waitForFunction(() => !document.querySelector('audio').paused && document.querySelector('[data-queue-start]').textContent === 'Pause');
    await page.locator('audio').evaluate(a => {a.currentTime = a.duration - .05;});
    await page.waitForFunction(() => document.querySelector('[data-queue-index="1"]').getAttribute('aria-current') === 'true').catch(async error => {
      console.log(await page.locator('audio').evaluate(a => ({duration:a.duration,currentTime:a.currentTime,paused:a.paused,ended:a.ended,seeking:a.seeking,readyState:a.readyState,mediaError:a.error?.message})));
      throw error;
    });
    await page.waitForFunction(() => !document.querySelector('audio').paused && document.querySelector('audio').readyState >= 2);
    check(await page.locator('audio').evaluate(a => a.playbackRate === 1.15),'Advancing changed playback speed');
    await page.locator('[data-queue-auto]').uncheck();
    await page.locator('[data-queue-transcript-panel]>summary').click();
    await page.waitForSelector('[data-queue-cues] [data-audio-seek]');
    check((await page.locator('[data-queue-entry-link]').getAttribute('href')).includes('002-'),'Selected recording lost its written note');
    const archiveCue = page.locator('[data-queue-cues] [data-audio-seek]').nth(1);
    const seekTime = Number(await archiveCue.getAttribute('data-audio-seek'));
    await archiveCue.focus();await page.keyboard.press('Enter');
    await page.waitForFunction(time => document.querySelector('audio').currentTime >= time && !document.querySelector('audio').paused, seekTime);
    await page.locator('audio').evaluate(a => {a.currentTime = a.duration - .05;});
    await page.waitForFunction(() => document.querySelector('audio').ended);
    check(await page.locator('[data-queue-index="1"]').getAttribute('aria-current') === 'true','Unchecked autoplay advanced the queue');
    await page.locator('.audio-queue-sheet>summary').click();
    if (width === 390 && theme === 'night') {
      const entries = await page.locator('[data-queue-data]').evaluate(node => JSON.parse(node.textContent));
      const unavailable = '**/' + entries[2].cues.split('/').at(-1);
      await page.route(unavailable, route => route.abort());
      await page.locator('[data-queue-index="2"]').click();
      await page.waitForFunction(() => document.querySelector('[data-queue-cues]').textContent.includes('could not load'));
      check((await page.locator('[data-queue-transcript]').getAttribute('href')) === entries[2].transcript,'Failed transcript download belongs to another episode');
      await page.unroute(unavailable);
      await page.locator('[data-queue-index="2"]').click();
      await page.waitForSelector('[data-queue-cues] [data-audio-seek]');
      const delayed = '**/' + entries[3].cues.split('/').at(-1);
      let receiveRequest;
      const intercepted = new Promise(resolve => { receiveRequest = resolve; });
      await page.route(delayed, route => receiveRequest(route));
      await page.locator('[data-queue-index="3"]').click();
      const held = await intercepted;
      await page.locator('[data-queue-index="4"]').click();
      await page.waitForSelector('[data-queue-cues] [data-audio-seek]');
      await held.fulfill({contentType:'application/json',body:JSON.stringify([{start:0,end:1,text:'Stale transcript must not replace the selected episode.'}])});
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      check(!(await page.locator('[data-queue-cues]').textContent()).includes('Stale transcript'),'Late transcript replaced the selected episode');
      check((await page.locator('[data-queue-transcript]').getAttribute('href')) === entries[4].transcript,'Late transcript changed the download link');
      await page.unroute(delayed);
    }
    await page.locator(`[data-queue-index="${expectedCount - 1}"]`).click();
    await page.waitForFunction(() => !document.querySelector('audio').paused && document.querySelector('audio').readyState >= 2);
    await page.locator('audio').evaluate(a => {a.currentTime = a.duration - .05;});
    await page.waitForFunction(() => document.querySelector('[data-audio-status]').textContent.includes('end of the archive'));
    check(await page.locator('[data-queue-next]').isDisabled(),'Queue wraps past its final item');
    check(await page.locator('[data-queue-entry-link]').textContent() === 'Open this episode ↗','Comparison offers a nonexistent written note');
    await page.addScriptTag({path:require.resolve('axe-core/axe.min.js')});
    const archiveViolations = await page.evaluate(async () => (await axe.run()).violations.map(v => ({id:v.id,nodes:v.nodes.map(n=>({html:n.html,summary:n.failureSummary}))})));
    const archiveOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    check(!archiveOverflow && !archiveViolations.length && !errors.length,JSON.stringify({width,theme,archiveOverflow,archiveViolations,errors}));
    await page.locator('#listen-archive').scrollIntoViewIfNeeded();
    await page.screenshot({path:output + `/archive-${width}-${theme}.png`,fullPage:true});
    await page.locator('.archive-session>summary').click();
    await page.waitForFunction(() => document.querySelector('audio').paused);
    reports.push({width,theme,articleDefaultRate:1.15,queueDefaultRate:1.15,actualPlayback:true,keyboardSeek:true,autoAdvance:true,stopAtEnd:true,violations,archiveViolations,overflow,archiveOverflow,errors});
    await page.close();
  }
  const nojs = await browser.newPage({javaScriptEnabled:false,viewport:{width:390,height:900}});
  await nojs.goto(base + '/notes/001-curiosity-with-calluses.html');
  await nojs.locator('#listen-note>summary').click(); await nojs.locator('.audio-transcript>summary').click();
  check(await nojs.locator('.audio-cues').isVisible(),'Transcript needs JavaScript');
  check(await nojs.locator('audio').getAttribute('controls') !== null,'No-JavaScript player missing');
  check(!(await nojs.locator('[data-audio-speed]').isVisible()),'Dead speed control is visible without JavaScript');
  await nojs.goto(base + '/notes/');
  await nojs.locator('.archive-session>summary').click();
  await nojs.locator('.audio-queue-sheet>summary').click();
  check(await nojs.locator('.audio-queue-read').count() === expectedCount,'No-JavaScript archive lost episode links');
  check(await nojs.locator('.audio-queue-read').first().isVisible(),'No-JavaScript episode links are hidden');
  const feed = await (await nojs.request.get(base + '/notes/podcast.xml')).text();
  check((feed.match(/<enclosure /g)||[]).length === expectedCount,'Podcast feed lost completed episodes');
  await writeFile(output + '/browser.json',JSON.stringify({syntheticMedia,reports,noJavaScript:true,podcastEnclosures:expectedCount},null,2)+'\n');
  console.log(`PASS: article players and archive queue, 320/390/1440px, both themes, keyboard, native playback, timed transcripts, 1.15×, no JavaScript and zero axe violations. ${syntheticMedia ? 'Synthetic clips.' : 'Real published recordings.'}`);
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
