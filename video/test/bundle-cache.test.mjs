import assert from 'node:assert/strict';
import {mkdtemp, mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import test from 'node:test';
import {preparedBundle, removePublic} from '../bundle-cache.mjs';

test('compiled bundle is reused, episode assets switch, and corruption triggers rebuild', async () => {
  const root = await mkdtemp(join(tmpdir(), 'podcast-bundle-'));
  try {
    const cache = join(root, 'cache');
    const publicA = join(root, 'episode-a');
    const publicB = join(root, 'episode-b');
    for (const directory of [publicA, publicB]) await mkdir(directory);
    await writeFile(join(publicA, 'master.wav'), 'first recording');
    await writeFile(join(publicB, 'master.wav'), 'second recording');
    let builds = 0;
    const build = async ({outDir}) => {
      builds++;
      await writeFile(join(outDir, 'index.html'), 'compiled HTML');
      await writeFile(join(outDir, 'bundle.js'), 'compiled composition');
    };
    await preparedBundle(root, publicA, cache, build);
    assert.equal(await readFile(join(cache, 'public/master.wav'), 'utf8'), 'first recording');
    await preparedBundle(root, publicB, cache, build);
    assert.equal(builds, 1);
    assert.equal(await readFile(join(cache, 'public/master.wav'), 'utf8'), 'second recording');
    await writeFile(join(cache, 'bundle.js'), 'corrupt');
    await preparedBundle(root, publicA, cache, build);
    assert.equal(builds, 2);
    await removePublic(cache);
    assert.equal(await readFile(join(publicA, 'master.wav'), 'utf8'), 'first recording');
    assert.equal(await readFile(join(publicB, 'master.wav'), 'utf8'), 'second recording');
  } finally {
    await rm(root, {recursive: true, force: true});
  }
});

test('a failed compilation leaves no completed bundle and the next attempt works', async () => {
  const root = await mkdtemp(join(tmpdir(), 'podcast-bundle-'));
  try {
    const cache = join(root, 'cache');
    const publicDir = join(root, 'public');
    await mkdir(publicDir);
    await assert.rejects(preparedBundle(root, publicDir, cache, async () => {
      throw new Error('Compilation interrupted');
    }), /Compilation interrupted/);
    await preparedBundle(root, publicDir, cache, async ({outDir}) => {
      await writeFile(join(outDir, 'index.html'), 'HTML');
      await writeFile(join(outDir, 'bundle.js'), 'composition');
    });
    assert.equal(await readFile(join(cache, 'bundle.js'), 'utf8'), 'composition');
  } finally {
    await rm(root, {recursive: true, force: true});
  }
});
