import { mkdir, writeFile } from "node:fs/promises";
import { launchAuditBrowser } from "./audit_browser.mjs";
const output = "artifacts/design-review/coastal-haxr-motion-film";
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser();
const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, recordVideo: { dir: output, size: { width: 1440, height: 1080 } } });
try {
  const page = await context.newPage();
  await page.goto(`${process.env.SITE_URL ?? "http://127.0.0.1:8794"}/specimens/coastal-watch/radar-replay/`);
  await page.locator("#hx-load").click(); await page.locator("#hx-workspace").waitFor({ state: "visible" });
  await page.getByRole("button", { name: "Follow this return over time" }).first().click();
  const position = async selector => {
    await page.locator(selector).evaluate(e => scrollTo({ top: e.getBoundingClientRect().top + scrollY - 100, behavior: "smooth" }));
    await page.waitForTimeout(700);
  };
  await position("#hx-motion"); await page.waitForTimeout(1500);
  await position(".hx-motion-grid"); await page.waitForTimeout(2000);
  await page.screenshot({ path: `${output}/seed.png` });
  await page.locator("#hx-motion-frame-4").click(); await position(".hx-motion-grid"); await page.waitForTimeout(2000);
  await page.screenshot({ path: `${output}/ais-gap.png` });
  await page.locator("#hx-motion-frame-10").click(); await position(".hx-motion-grid"); await page.waitForTimeout(2500);
  await page.screenshot({ path: `${output}/stationary-texture.png` });
  await page.locator("#hx-motion-frame-0").click();
  await page.locator("#hx-cell-station").selectOption("reiherstieg");
  await page.locator("#hx-col").fill("46"); await page.locator("#hx-row").fill("40"); await page.locator("#hx-inspect").click();
  await page.locator("#hx-motion-seed-bin").click();
  await page.locator("#hx-motion-frame-1").click(); await position(".hx-motion-grid"); await page.waitForTimeout(3000);
  await page.screenshot({ path: `${output}/competing-patches.png` });
  await page.locator("#hx-motion-frame-2").click(); await position("#hx-motion-reading"); await page.waitForTimeout(2500);
  const video = page.video(); await page.close(); await context.close(); await video.saveAs(`${output}/radar-motion.webm`);
  await writeFile(`${output}/capture.json`, JSON.stringify({ evidence: "Recorded HAXR; experimental fixed-template radar follow, no vessel or shore classification", station: "reiherstieg", uid: "1b1e4", seeds: [{ frame: 0, col: 62, row: 77 }, { frame: 0, col: 46, row: 40 }], sourceFamilies: 1 }, null, 2));
} finally { await browser.close(); }
