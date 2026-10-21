import { mkdir, writeFile } from "node:fs/promises";
import { launchAuditBrowser } from "./audit_browser.mjs";
const output = "artifacts/design-review/coastal-haxr-returns-film";
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
  await position("#hx-returns"); await page.waitForTimeout(2000);
  await page.screenshot({ path: `${output}/inspection-desk.png` });
  await position(".hx-return-panels"); await page.waitForTimeout(2500);
  await page.screenshot({ path: `${output}/two-apertures.png` });
  await page.locator("#hx-returns-radius").selectOption("250");
  await page.locator("#hx-returns-floor").fill("80"); await page.locator("#hx-returns-floor").dispatchEvent("input");
  await position(".hx-return-panels"); await page.waitForTimeout(2000);
  await page.locator("#hx-return-reiherstieg-3").click();
  await position(".hx-return-panels"); await page.waitForTimeout(2000);
  await page.screenshot({ path: `${output}/one-position-expired.png` });
  await page.locator("#hx-return-reiherstieg-4").click();
  await position(".hx-return-panels"); await page.waitForTimeout(2000);
  await page.locator("#hx-return-reiherstieg-10").click();
  await position(".hx-return-panels"); await page.waitForTimeout(2000);
  await page.getByRole("button", { name: "Inspect nearest qualifying bin" }).first().click();
  await page.waitForTimeout(3000);
  const video = page.video(); await page.close(); await context.close();
  await video.saveAs(`${output}/local-returns.webm`);
  await writeFile(`${output}/capture.json`, JSON.stringify({ evidence: "Recorded HAXR; pseudonymous AIS 1b1e4; local proximity inspection, no confirmed radar association", sourceFamilies: 1, frames: [0, 3, 4, 10], viewport: "1440 x 1080" }, null, 2));
} finally { await browser.close(); }
