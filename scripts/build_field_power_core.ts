/** bun scripts/build_field_power_core.ts C:/path/to/raivari */
import { resolve, join, dirname, basename } from "node:path";
import { readFile, writeFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

if (!process.argv[2]) throw Error("Supply the reviewed Raivari checkout");
const source = resolve(process.argv[2]);
const revision = execFileSync("git", ["rev-parse", "HEAD"], { cwd: source, encoding: "utf8" }).trim();
if (revision !== "b8ac188973ecccc2ce7068d8dfaa4125e002231b") throw Error("Unreviewed source revision");
const paths = ["packages/modbus-simulator/src/behaviors/maritime-behaviors.ts", "packages/maritime-types/src/registers.ts"];
if (execFileSync("git", ["status", "--porcelain", "--", ...paths], { cwd: source, encoding: "utf8" }).trim()) throw Error("Modified source inputs");
const hash = (s: string | Buffer) => createHash("sha256").update(s).digest("hex");
const inputs = await Promise.all(paths.map(async path => ({ path, sha256: hash(await readFile(join(source, path))) })));
const scratch = await mkdtemp(join(tmpdir(), "field-power-build-"));
try {
  const entry = join(scratch, "entry.ts");
  const absolute = paths.map(p => JSON.stringify(join(source, p).replaceAll("\\", "/")));
  await writeFile(entry, `export {clamp, rateLimit} from ${absolute[0]};\nexport {BESS_REGISTERS, GENSET_REGISTERS, SCALE, encodeValue} from ${absolute[1]};\n`);
  const build = await Bun.build({ entrypoints: [entry], target: "browser", minify: true,
    external: [], plugins: [{ name: "reviewed-registers", setup(b) {
      b.onResolve({ filter: /^@raivari\/maritime-types$/ }, () => ({ path: join(source, paths[1]) }));
    } }] });
  if (!build.success) throw new AggregateError(build.logs, "Power core build failed");
  const body = `/* Generated from navivra/raivari ${revision}. Unmodified helpers and register definitions. Rebuild: scripts/build_field_power_core.ts. */\n` + await build.outputs[0].text();
  await writeFile("docs/assets/field-power-core.mjs", body);
  await writeFile("docs/design/field-power-core.json", JSON.stringify({ source: "Raivari", revision, inputs, bun: Bun.version, bundleSha256: hash(body),
    exports: ["clamp", "rateLimit", "BESS_REGISTERS", "GENSET_REGISTERS", "SCALE", "encodeValue"],
    scope: "Unmodified numerical helpers and register definitions. The energy accounting, decision receipts and land-site scenario are new specimen code. No actual Modbus connection or offline queue. No calibrated electrical or thermal simulation."
  }, null, 2) + "\n");
  console.log(`Built ${Buffer.byteLength(body)} bytes from ${revision}`);
} finally {
  if (dirname(resolve(scratch)) !== resolve(tmpdir()) || !basename(scratch).startsWith("field-power-build-")) throw Error("Unsafe scratch path");
  await rm(scratch, { recursive: true });
}
