/**
 * Rebuild the public replay core from an explicitly supplied Raivari checkout.
 * bun scripts/build_haxr_core.ts C:/path/to/raivari
 * The pinned source revision and original file hashes are recorded with the bundle.
 */
import { resolve, join, dirname, basename } from "node:path";
import { mkdir, readFile, writeFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const source = resolve(process.argv[2] ?? "");
if (!process.argv[2]) throw Error("Supply the Raivari source checkout");
const revision = execFileSync("git", ["rev-parse", "HEAD"], { cwd: source, encoding: "utf8" }).trim();
const expected = "b8ac188973ecccc2ce7068d8dfaa4125e002231b";
if (revision !== expected) throw Error(`Expected reviewed source ${expected}; got ${revision}`);
const paths = ["packages/modbus-simulator/src/replay/haxr.ts", "packages/modbus-simulator/src/replay/radar-pairing.ts"];
const changed = execFileSync("git", ["status", "--porcelain", "--", ...paths], { cwd: source, encoding: "utf8" }).trim();
if (changed) throw Error("Replay source differs from the pinned revision; commit and review it before rebuilding");
const hash = (value: string | Buffer) => createHash("sha256").update(value).digest("hex");
const inputs = await Promise.all(paths.map(async path => ({ path, sha256: hash(await readFile(join(source, path))) })));
const scratch = await mkdtemp(join(tmpdir(), "coastal-haxr-build-"));
try {
  const entry = join(scratch, "entry.ts");
  await writeFile(entry, `export {parseHaxr, selectHaxrAis, haxrPixels, HAXR_AIS_POLICY} from ${JSON.stringify(join(source, paths[0]).replaceAll("\\", "/"))};\nexport {pairRadarFrames} from ${JSON.stringify(join(source, paths[1]).replaceAll("\\", "/"))};\n`);
  const build = await Bun.build({ entrypoints: [entry], target: "browser", minify: true });
  if (!build.success) throw new AggregateError(build.logs, "Replay core build failed");
  const body = `/* Generated from navivra/raivari ${revision}. Rebuild: scripts/build_haxr_core.ts.\nIncludes Zod (MIT); see coastal-haxr-core.LICENSE.txt. */\n` + await build.outputs[0].text();
  const assets = resolve("docs/assets");
  await mkdir(assets, { recursive: true });
  await writeFile(join(assets, "coastal-haxr-core.mjs"), body);
  const zodPackage = JSON.parse(await readFile(join(source, "node_modules/zod/package.json"), "utf8"));
  await writeFile(join(assets, "coastal-haxr-core.LICENSE.txt"), await readFile(join(source, "node_modules/zod/LICENSE")));
  await writeFile("docs/design/coastal-haxr-core.json", JSON.stringify({
    source: "Raivari", revision, inputs, bun: Bun.version,
    zod: zodPackage.version, bundleSha256: hash(body),
    exports: ["parseHaxr", "selectHaxrAis", "haxrPixels", "HAXR_AIS_POLICY", "pairRadarFrames"],
    scope: "Unmodified Raivari replay validation, AIS selection, amplitude mapping and directional timestamp pairing. No server, credentials, transport or RF analyzer included."
  }, null, 2) + "\n");
  console.log(`Built ${Buffer.byteLength(body)} bytes from ${revision}`);
} finally {
  // This is the exact directory returned by mkdtemp, never a source checkout.
  if (dirname(resolve(scratch)) !== resolve(tmpdir()) || !basename(scratch).startsWith("coastal-haxr-build-"))
    throw Error("Refusing cleanup outside the build scratch directory");
  await rm(scratch, { recursive: true });
}
