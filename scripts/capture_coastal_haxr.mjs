// Capture the actual recorded-data desk; no synthetic overlays or simulated returns.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { launchAuditBrowser } from "./audit_browser.mjs";
const output = "artifacts/design-review/coastal-haxr-film";
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1,
  recordVideo: { dir: output, size: { width: 1440, height: 1000 } },
});
try {
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem("moth-and-gravel-theme", "night"));
  await page.goto(`${process.env.SITE_URL ?? "http://127.0.0.1:8794"}/specimens/coastal-watch/radar-replay/`);
  await page.locator("#hx-load").click();
  await page.locator("#hx-workspace").waitFor({ state: "visible" });
  const start = Date.now();
  const position = async selector => {
    await page.locator(selector).evaluate(e => scrollTo({ top: e.getBoundingClientRect().top + scrollY - 95, behavior: "smooth" }));
    await page.waitForTimeout(1000);
  };
  await position(".hx-controls");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${output}/two-recorded-stations.png` });
  await page.locator("#hx-play").click();
  await page.waitForTimeout(5000);
  await page.locator("#hx-play").click();
  await page.locator("#hx-frame").fill("0");
  await page.locator("#hx-frame").dispatchEvent("input");
  await position(".hx-clock");
  await page.locator("#hx-tolerance").focus();
  await page.keyboard.press("Home");
  await page.waitForTimeout(2000);
  await page.keyboard.press("End");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${output}/timing-bound.png` });
  await position(".hx-lineage");
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${output}/shared-ais-source.png` });
  await position(".hx-inspection");
  const recording = JSON.parse(await readFile("docs/data/haxr/hohe-schaar.json", "utf8"));
  const pixels = recording.frames[0].pixels;
  const strongest = pixels.reduce((best, value, i) => (value ?? 0) > (pixels[best] ?? 0) ? i : best, 0);
  await page.locator("#hx-cell-station").selectOption("hohe_schaar");
  await page.locator("#hx-col").fill(String(strongest % 128)); await page.locator("#hx-row").fill(String(Math.floor(strongest / 128)));
  await page.locator("#hx-inspect").click();
  await page.waitForTimeout(3500);
  const video = page.video();
  await page.close();
  await context.close();
  await video.saveAs(`${output}/recorded-radar-desk.webm`);
  await writeFile(`${output}/capture.json`, JSON.stringify({
    source: "Local browser capture of the implemented HAXR desk",
    durationMs: Date.now() - start, evidence: "Recorded HAXR extracts; playback at reading speed; no live vessel feed",
    viewport: "1440 x 1000", interaction: ["Two stations", "Frame playback", "Endpoint tolerance", "Shared AIS", "Raw bin inspection"],
  }, null, 2));
} finally { await browser.close(); }
