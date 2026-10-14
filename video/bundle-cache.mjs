import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {mkdir, mkdtemp, readFile, readdir, rename, rm, symlink, cp, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {bundle} from '@remotion/bundler';

const digest = async (path) => {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest('hex');
};

const files = async (directory, prefix = '') => {
  const found = [];
  for (const entry of await readdir(join(directory, prefix), {withFileTypes: true})) {
    if (!prefix && ['public', 'bundle-cache.json'].includes(entry.name)) continue;
    const path = join(prefix, entry.name);
    if (entry.isDirectory()) found.push(...await files(directory, path));
    else if (entry.isFile()) found.push(path);
  }
  return found.sort();
};

const valid = async (directory) => {
  try {
    const state = JSON.parse(await readFile(join(directory, 'bundle-cache.json'), 'utf8'));
    const actual = await files(directory);
    if (!state['index.html'] || !state['bundle.js'] || actual.join('\n') !== Object.keys(state).sort().join('\n')) return false;
    for (const name of actual) if (await digest(join(directory, name)) !== state[name]) return false;
    return true;
  } catch (error) {
    if (error.code === 'ENOENT' || error instanceof SyntaxError || error instanceof TypeError) return false;
    throw error;
  }
};

// Caller holds the renderer-cache lock throughout rendering. Only public assets
// change between episodes; compiled code is verified and reused across runs.
export const preparedBundle = async (root, publicDir, directory, build = bundle) => {
  if (!await valid(directory)) {
    await mkdir(dirname(directory), {recursive: true});
    const stage = await mkdtemp(join(dirname(directory), '.bundle-'));
    try {
      await build({entryPoint: join(root, 'src/index.jsx'), publicDir, symlinkPublicDir: true, rootDir: root, outDir: stage});
      const state = {};
      for (const name of await files(stage)) state[name] = await digest(join(stage, name));
      await writeFile(join(stage, 'bundle-cache.json'), JSON.stringify(state));
      await rm(directory, {recursive: true, force: true});
      await rename(stage, directory);
    } finally {
      await rm(stage, {recursive: true, force: true});
    }
  }
  await removePublic(directory);
  try {
    await symlink(publicDir, join(directory, 'public'), process.platform === 'win32' ? 'junction' : 'dir');
  } catch (error) {
    if (!['EPERM', 'EACCES', 'ENOTSUP'].includes(error.code)) throw error;
    await cp(publicDir, join(directory, 'public'), {recursive: true});
  }
  return directory;
};

export const removePublic = async (directory) => {
  await rm(join(directory, 'public'), {recursive: true, force: true});
};
