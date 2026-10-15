/** Repeatable cold-load lab comparison. No telemetry runs on the public site. */
import lighthouse from 'lighthouse';
import desktopConfig from 'lighthouse/core/config/desktop-config.js';
import * as chromeLauncher from 'chrome-launcher';
import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const output = process.env.PERFORMANCE_OUTPUT || 'artifacts/performance';
const candidate = process.env.SITE_URL || 'http://127.0.0.1:8793/';
const baseline = process.env.BASELINE_URL || 'http://127.0.0.1:8794/';
await mkdir(output, { recursive: true });
const runs = [], failures = [];
const chrome = await chromeLauncher.launch({ chromePath: chromium.executablePath(),
  chromeFlags: ['--headless', '--no-sandbox', '--disable-dev-shm-usage'] });
try {
  for (const profile of ['mobile', 'desktop']) {
    for (const [name, url, repetitions] of [
      ['baseline', baseline, 3], ['candidate', candidate, 3],
      ['mapping-study', new URL('/specimens/whose-map/', candidate).href, 3],
      ['editorial-thread', new URL('/threads/something-happened/', candidate).href, 3],
      ['workbench-first', new URL('/workbench/', candidate).href, 3],
      ['workbench-return', new URL('/workbench/return/', candidate).href, 3],
      ['question-sheet', new URL('/questions/', candidate).href, 3],
      ['notes-archive', new URL('/notes/', candidate).href, 3],
      ['notes-reading', new URL('/notes/013-work-outlives-the-window.html', candidate).href, 3],
      ...(process.env.LIVE_URL ? [['live-before', process.env.LIVE_URL, 3]] : []),
    ]) {
      for (let i = 0; i < repetitions; i++) {
        const options = { port: chrome.port, logLevel: 'error', output: ['json', 'html'],
          onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'] };
        const result = await lighthouse(url, options, profile === 'desktop' ? desktopConfig : undefined);
        if (!result || result.lhr.runtimeError) throw new Error(JSON.stringify(result?.lhr.runtimeError));
        const { lhr } = result;
        if (lhr.configSettings.formFactor !== profile) throw new Error('Lighthouse profile mismatch');
        const record = { name, profile, iteration: i + 1, url: lhr.finalDisplayedUrl,
          lighthouseVersion: lhr.lighthouseVersion, fetchTime: lhr.fetchTime,
          settings: lhr.configSettings,
          scores: Object.fromEntries(Object.entries(lhr.categories).map(([k, v]) => [k, v.score])),
          fcp: lhr.audits['first-contentful-paint'].numericValue,
          lcp: lhr.audits['largest-contentful-paint'].numericValue,
          tbt: lhr.audits['total-blocking-time'].numericValue,
          cls: lhr.audits['cumulative-layout-shift'].numericValue,
          bytes: lhr.audits['total-byte-weight'].numericValue,
          diagnostics: Object.values(lhr.audits).filter(a => a.score !== null && a.score < 1)
            .map(a => ({ id: a.id, title: a.title, displayValue: a.displayValue, score: a.score })),
        };
        runs.push(record);
        const prefix = `${name}-${profile}-${i + 1}`;
        await writeFile(join(output, prefix + '.json'), result.report[0]);
        await writeFile(join(output, prefix + '.html'), result.report[1]);
        console.log(JSON.stringify({ ...record, settings: undefined, diagnostics: undefined }));
      }
    }
  }
} finally { await chrome.kill(); }
const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const summaries = [];
for (const profile of ['mobile', 'desktop']) for (const name of [...new Set(runs.map(r => r.name))]) {
  const group = runs.filter(r => r.name === name && r.profile === profile);
  if (!group.length) continue;
  const summary = { name, profile, repeats: group.length,
    ...Object.fromEntries(['fcp', 'lcp', 'tbt', 'cls', 'bytes'].map(k => [k, median(group.map(r => r[k]))])),
    scores: Object.fromEntries(Object.keys(group[0].scores).map(k => [k, median(group.map(r => r.scores[k]))])),
    rangeFcp: [Math.min(...group.map(r => r.fcp)), Math.max(...group.map(r => r.fcp))] };
  summaries.push(summary);
  if (['candidate','mapping-study','editorial-thread','workbench-first','workbench-return','notes-archive','notes-reading','question-sheet'].includes(name)) {
    const fcpBudget = name === 'candidate' ? 1000 : 1800;
    for (const [key, maximum] of [['fcp', fcpBudget], ['lcp', 2500], ['tbt', 200], ['cls', 0.1]])
      if (summary[key] > maximum) failures.push(`${name}/${profile}: ${key} ${summary[key]} exceeds ${maximum}`);
    if (summary.scores.performance < 0.9) failures.push(`${name}/${profile}: performance below 90`);
    if (!name.startsWith('workbench-') && summary.scores.seo < 0.95) failures.push(`${name}/${profile}: technical SEO below 95`);
  }
}
await writeFile(join(output, 'summary.json'), JSON.stringify({
  methodology: 'Median of three independent cold Lighthouse navigations per URL/profile; Lighthouse defaults simulate mobile slow 4G/CPU and desktop. Baseline and candidate homepages are served on the same CI host without compression. The new mapping study is measured independently without a nonexistent base-page comparison; its FCP budget is 1800 ms, with the same 2500 ms LCP, 200 ms TBT and 0.1 CLS limits. The editorial thread is also measured independently with an 1800 ms FCP budget and the same LCP, TBT and CLS limits. Both noindex workbench previews are measured against the same 1800 ms FCP, 2500 ms LCP, 200 ms TBT and 0.1 CLS budgets; their intentional noindex directive is exempt from the SEO score requirement. The Field Notes archive and the Studio article are measured independently with the same 1800 ms FCP, 2500 ms LCP, 200 ms TBT and 0.1 CLS budgets, plus technical SEO of at least 95. The question sheet is measured independently against those same reading-page budgets and technical SEO requirement. The homepage retains its 1000 ms FCP budget. Live-before is a separate deployed-host measurement, not an after result or user field data. FCP is first visible content, LCP is main visible content; neither means every image is loaded. Scores do not establish indexing, AI recommendations or enquiries.',
  summaries, failures, runs,
}, null, 2));
console.log(JSON.stringify({ summaries, failures }, null, 2));
if (failures.length) process.exitCode = 1;
