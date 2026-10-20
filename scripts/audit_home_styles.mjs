import { launchAuditBrowser } from "./audit_browser.mjs";
import assert from "node:assert/strict";

const origin = process.env.SITE_URL || "http://127.0.0.1:8793";
const browser = await launchAuditBrowser();
try {
  for (const width of [390, 1440]) {
    for (const theme of ["night", "afterlight"]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      await page.addInitScript(
        (t) => localStorage.setItem("moth-and-gravel-theme", t),
        theme,
      );
      let release;
      const gate = new Promise((resolve) => {
        release = resolve;
      });
      await page.route("**/assets/home-full.css?*", async (route) => {
        await gate;
        await route.continue();
      });
      await page.goto(origin, { waitUntil: "commit" });
      await page.locator(".hero h1").waitFor({ state: "visible" });
      const opening = () =>
        page.evaluate(() =>
          [".site-header", ".hero", ".hero h1", ".hero-visual"].map(
            (selector) => {
              const el = document.querySelector(selector);
              const { x, y, width, height } = el.getBoundingClientRect();
              const css = getComputedStyle(el);
              return {
                selector,
                x,
                y,
                width,
                height,
                font: css.font,
                color: css.color,
                background: css.backgroundColor,
              };
            },
          ),
        );
      const before = await opening();
      assert.equal(
        await page.locator('link[rel="preload"][as="style"]').count(),
        1,
        "opening must be readable before the full stylesheet is released",
      );
      release();
      await page.waitForFunction(
        () =>
          document.querySelector('link[href*="home-full.css"]').rel ===
          "stylesheet",
      );
      await page.waitForLoadState("load");
      assert.deepEqual(
        await opening(),
        before,
        `full cascade must not move or restyle the opening: ${width}/${theme}`,
      );
      assert.equal(
        await page
          .locator("#services .services-grid")
          .evaluate((el) => getComputedStyle(el).display),
        "grid",
      );
      await page.close();
    }
    const page = await browser.newPage({
      viewport: { width, height: 1000 },
      javaScriptEnabled: false,
    });
    await page.goto(origin);
    assert.equal(
      await page
        .locator("#services .services-grid")
        .evaluate((el) => getComputedStyle(el).display),
      "grid",
      "no-JavaScript visitors receive the full stylesheet",
    );
    assert.equal(
      await page
        .locator(".contact-band-inner")
        .evaluate((el) => getComputedStyle(el).display),
      "grid",
    );
    await page.close();
  }
  console.log(
    "Opening paints with delayed full CSS, preserves geometry and theme, and retains full no-JavaScript styling.",
  );
} finally {
  await browser.close();
}
