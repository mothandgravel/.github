import {readFile, writeFile, rm} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const [propsPath, publicDir, destination, browserExecutable] = process.argv.slice(2);
if (!propsPath || !publicDir || !destination) throw new Error('Usage: render.mjs props.json public-directory output-directory [browser-executable]');
const root = dirname(fileURLToPath(import.meta.url));
const props = JSON.parse(await readFile(propsPath, 'utf8'));
const serveUrl = await bundle({entryPoint: join(root, 'src/index.jsx'), publicDir, rootDir: root, outDir: join(destination, 'bundle')});
const browser = await openBrowser('chrome', {browserExecutable: browserExecutable ?? null, chromeMode: 'headless-shell'});
const started = performance.now();
try {
  const composition = await selectComposition({serveUrl, id: 'FieldNote', inputProps: props, puppeteerInstance: browser});
  let last = -1;
  await renderMedia({
    serveUrl, composition, inputProps: props, outputLocation: join(destination, 'episode.mp4'),
    puppeteerInstance: browser, codec: 'h264', audioCodec: 'aac', audioBitrate: '192k',
    crf: 20, x264Preset: 'fast', pixelFormat: 'yuv420p',
    concurrency: props.video.concurrency,
    onProgress: ({progress}) => {
      const bucket = Math.floor(progress * 10);
      if (bucket !== last) { last = bucket; console.log(`Video: ${Math.round(progress * 100)}%`); }
    },
  });
  const thumbnailProps = {...props, thumbnail: true, previewSeconds: null};
  const thumbnailComposition = await selectComposition({serveUrl, id: 'FieldNote', inputProps: thumbnailProps, puppeteerInstance: browser});
  await renderStill({
    serveUrl, composition: thumbnailComposition, inputProps: thumbnailProps, puppeteerInstance: browser,
    output: join(destination, 'thumbnail.png'), imageFormat: 'png',
    frame: Math.min(thumbnailComposition.durationInFrames - 1, props.video.fps * 2),
  });
  await writeFile(join(destination, 'render.json'), JSON.stringify({
    frames: composition.durationInFrames, fps: composition.fps,
    width: composition.width, height: composition.height,
    previewSeconds: props.previewSeconds, processingSeconds: (performance.now() - started) / 1000,
  }, null, 2) + '\n');
} finally {
  await browser.close({silent: true});
  await rm(join(destination, 'bundle'), {recursive: true, force: true});
}
