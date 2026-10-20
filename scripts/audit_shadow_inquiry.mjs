import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import axe from "axe-core";
import { launchAuditBrowser } from "./audit_browser.mjs";
const origin = process.env.SITE_URL ?? "http://127.0.0.1:8793";
const output = "artifacts/design-review";
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser();
try {
  for (const [width, theme] of [
    [1440, "night"],
    [390, "afterlight"],
  ]) {
    const page = await browser.newPage({
      viewport: { width, height: 1000 },
      reducedMotion: "reduce",
    });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(
      (t) => localStorage.setItem("moth-and-gravel-theme", t),
      theme,
    );
    await page.goto(`${origin}/specimens/coastal-watch/shadow-inquiry/`);
    await page.locator("#si-desk").waitFor();
    assert.equal(await page.locator("#si-records tr").count(), 2);
    assert.equal(await page.locator("#si-offset").isDisabled(), true);
    await page.locator("#si-next").click();
    assert.equal(await page.locator("#si-deliveries").textContent(), "03");
    assert.equal(await page.locator("#si-originals").textContent(), "02");
    assert.equal(await page.locator("#si-families").textContent(), "01");
    await page.getByRole("button", { name: "A-01-relay", exact: true }).click();
    assert.match(
      await page.locator("#si-lineage").innerText(),
      /No additional witness/,
    );
    await page.locator("#si-next").click();
    assert.match(await page.locator("#si-result").innerText(), /Separated/);
    assert.equal(await page.locator("#si-records tr").count(), 4);
    await page.locator("#si-offset").focus();
    await page.keyboard.press("ArrowLeft");
    assert.equal(await page.locator("#si-offset-value").textContent(), "-1 s");
    await page.locator("#si-reset").click();
    assert.equal(await page.locator("#si-offset-value").textContent(), "0 s");
    await page.locator("#si-next").click();
    assert.match(await page.locator("#si-result").innerText(), /overlap/);
    await page.getByRole("button", { name: "R-17", exact: true }).click();
    assert.match(
      await page.locator("#si-lineage").innerText(),
      /unverified hypothesis/,
    );
    const download = page.waitForEvent("download");
    await page.locator("#si-export").click();
    const file = await download;
    const exported = JSON.parse(await readFile(await file.path(), "utf8"));
    assert.equal(exported.comparison.overlap, true);
    assert.equal(exported.classification, "not assessed");
    assert.equal(exported.fullFixtureIncludesFuture, true);
    await page.locator('[data-si-step="0"]').click();
    assert.equal(await page.locator("#si-records tr").count(), 2);
    assert(
      !(await page.getByRole("button", { name: "R-17", exact: true }).count()),
    );
    await page.locator('[data-si-step="2"]').click();
    await page.addScriptTag({ content: axe.source });
    assert.deepEqual(
      await page.evaluate(async () =>
        (await axe.run()).violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
      ),
      [],
    );
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    );
    assert.deepEqual(errors, []);
    await page.screenshot({
      path: `${output}/shadow-inquiry-${width}-${theme}-full.png`,
      fullPage: true,
    });
    await page.locator(".si-chapters").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: `${output}/shadow-inquiry-${width}-${theme}.png`,
    });
    await page.close();
  }
  console.log(
    "Shadow inquiry: causal chapters, lineage, uncertainty, raw inspection, rewind, export, keyboard, accessibility and responsive checks passed.",
  );
} finally {
  await browser.close();
}
