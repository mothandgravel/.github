import {readFile, writeFile, rm} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {preparedBundle, removePublic} from './bundle-cache.mjs';

const [propsPath, publicDir, destination, browserExecutable, sharedBundle] = process.argv.slice(2);
if (!propsPath || !publicDir || !destination) throw new Error('Usage: render.mjs props.json public-directory output-directory [browser-executable]');
const root = dirname(fileURLToPath(import.meta.url));
const props = JSON.parse(await readFile(propsPath, 'utf8'));
// Per-frame budget. A busy desktop can need far longer than Remotion's 30 s default.
const configuredTimeout = process.env.MG_RENDER_FRAME_TIMEOUT_MS;
const FRAME_TIMEOUT_DEFAULT = 120000;
// Remotion refuses under 7000 ms; Node timers overflow past 2^31-1 ms.
const timeoutValid = configuredTimeout !== undefined && /^\d+$/.test(configuredTimeout)
  && Number(configuredTimeout) >= 7000 && Number(configuredTimeout) <= 2147483647;
if (configuredTimeout !== undefined && !timeoutValid) {
  console.warn(`MG_RENDER_FRAME_TIMEOUT_MS must be a whole number from 7000 to 2147483647; using ${FRAME_TIMEOUT_DEFAULT}.`);
}
const timeoutInMilliseconds = timeoutValid ? Number(configuredTimeout) : FRAME_TIMEOUT_DEFAULT;
const started = performance.now();
const serveUrl = await preparedBundle(root, publicDir, sharedBundle || join(destination, 'bundle'));
let browser;
try {
  browser = await openBrowser('chrome', {browserExecutable: browserExecutable || null, chromeMode: 'headless-shell'});
  const composition = await selectComposition({serveUrl, id: 'FieldNote', inputProps: props, puppeteerInstance: browser, timeoutInMilliseconds});
  let last = -1;
  await renderMedia({
    serveUrl, composition, inputProps: props, outputLocation: join(destination, 'episode.mp4'),
    puppeteerInstance: browser, codec: 'h264', audioCodec: 'aac', audioBitrate: '192k',
    crf: 20, x264Preset: 'fast', pixelFormat: 'yuv420p',
    concurrency: props.video.concurrency, timeoutInMilliseconds,
    onProgress: ({progress}) => {
      const bucket = Math.floor(progress * 10);
      if (bucket !== last) { last = bucket; console.log(`Video: ${Math.round(progress * 100)}%`); }
    },
  });
  const thumbnailProps = {...props, thumbnail: true, previewSeconds: null};
  const thumbnailComposition = await selectComposition({serveUrl, id: 'FieldNote', inputProps: thumbnailProps, puppeteerInstance: browser, timeoutInMilliseconds});
  await renderStill({
    serveUrl, composition: thumbnailComposition, inputProps: thumbnailProps, puppeteerInstance: browser, timeoutInMilliseconds,
    output: join(destination, 'thumbnail.png'), imageFormat: 'png',
    frame: Math.min(thumbnailComposition.durationInFrames - 1, props.video.fps * 2),
  });
  await writeFile(join(destination, 'render.json'), JSON.stringify({
    frames: composition.durationInFrames, fps: composition.fps,
    width: composition.width, height: composition.height,
    previewSeconds: props.previewSeconds, processingSeconds: (performance.now() - started) / 1000,
  }, null, 2) + '\n');
} finally {
  if (browser) await browser.close({silent: true});
  await removePublic(serveUrl);
  if (!sharedBundle) await rm(serveUrl, {recursive: true, force: true});
}
