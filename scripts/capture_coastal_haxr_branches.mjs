import { mkdir, writeFile } from "node:fs/promises";
import { launchAuditBrowser } from "./audit_browser.mjs";
const output = "artifacts/design-review/coastal-haxr-branches-film";
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser();
const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, recordVideo: { dir: output, size: { width: 1440, height: 1080 } } });
try {
  const page = await context.newPage();
  await page.goto(`${process.env.SITE_URL ?? "http://127.0.0.1:8794"}/specimens/coastal-watch/radar-replay/`);
  await page.locator("#hx-load").click(); await page.locator("#hx-workspace").waitFor({ state: "visible" });
  const position = async selector => {
    await page.locator(selector).evaluate(e => scrollTo({ top: e.getBoundingClientRect().top + scrollY - 100, behavior: "smooth" }));
    await page.waitForTimeout(800);
  };
  await position(".hx-radars"); await page.waitForTimeout(2000);
  await page.locator("#hx-motion-example").click(); await position("#hx-motion-candidates"); await page.waitForTimeout(2500);
  await page.locator("#hx-motion-candidates").screenshot({ path: `${output}/competing-patches.png`, style: ".site-header,.skip-link{visibility:hidden}" });
  await page.locator(".hx-patch-card").nth(2).locator("summary").click(); await page.waitForTimeout(2000);
  await page.locator('[data-candidate="1"]').click(); await position("#hx-motion-accounts"); await page.waitForTimeout(2500);
  await page.locator("#hx-motion-frame-2").click(); await position("#hx-motion-accounts"); await page.waitForTimeout(2000);
  await page.locator("#hx-motion-account").selectOption("H01"); await position("#hx-motion-candidates"); await page.waitForTimeout(2000);
  await page.locator('[data-candidate="0"]').click();
  await page.locator("#hx-motion-frame-2").click(); await position("#hx-motion-accounts"); await page.waitForTimeout(3000);
  await page.screenshot({ path: `${output}/three-accounts.png` });
  await page.locator("#hx-motion-account").selectOption("H01"); await page.waitForTimeout(2000);
  const video = page.video(); await page.close(); await context.close(); await video.saveAs(`${output}/radar-branches.webm`);
  await writeFile(`${output}/capture.json`, JSON.stringify({ evidence: "Recorded HAXR; manual branches retain an ambiguous parent; no vessel association or shore classification", station: "reiherstieg", uid: "1b1e4", rootSeed: { frame: 0, col: 46, row: 40 }, stopFrame: 1, choiceOrder: [1, 0], sourceFamilies: 1 }, null, 2));
} finally { await browser.close(); }
