// A browser recording of actual report expiry and recovery in the pinned extracts.
import { mkdir, writeFile } from "node:fs/promises";
import { launchAuditBrowser } from "./audit_browser.mjs";
const output = "artifacts/design-review/coastal-haxr-history-film";
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, recordVideo: { dir: output, size: { width: 1440, height: 1000 } } });
try {
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem("moth-and-gravel-theme", "night"));
  await page.goto(`${process.env.SITE_URL ?? "http://127.0.0.1:8794"}/specimens/coastal-watch/radar-replay/`);
  await page.locator("#hx-load").click();
  await page.locator("#hx-workspace").waitFor({ state: "visible" });
  await page.locator("#hx-follow-id").selectOption("1b1e4");
  const position = async selector => {
    await page.locator(selector).evaluate(e => scrollTo({ top: e.getBoundingClientRect().top + scrollY - 95, behavior: "smooth" }));
    await page.waitForTimeout(800);
  };
  await position(".hx-radars");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${output}/both-recordings.png` });
  await position(".hx-history-tools");
  await page.waitForTimeout(1500);
  await page.locator("#hx-history-next").click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${output}/one-copy-eligible.png` });
  await page.locator("#hx-history-next").click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${output}/both-copies-expired.png` });
  await page.locator("#hx-history-next").click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${output}/later-report.png` });
  await position(".hx-radars");
  await page.waitForTimeout(2500);
  await position(".hx-continuity");
  await page.waitForTimeout(2500);
  await page.locator(".hx-history-records summary").click();
  await page.waitForTimeout(3000);
  const video = page.video(); await page.close(); await context.close();
  await video.saveAs(`${output}/selected-id-history.webm`);
  await writeFile(`${output}/capture.json`, JSON.stringify({
    evidence: "Actual recorded HAXR extracts; pseudonymous ID 1b1e4; no verified radar object track",
    interaction: ["Both recordings", "One copy passes the age limit", "Both copies too old", "Later report eligible", "Shared-stream continuity", "Timestamp account"],
    sourceFamilyCount: 1, viewport: "1440 x 1000",
  }, null, 2));
} finally { await browser.close(); }
