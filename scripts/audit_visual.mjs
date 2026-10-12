/**
 * Browser-level design/interaction audit for the public static landing.
 * Runs only in CI / local development, never in production.
 * Setup: npm install --no-save playwright@1.55.1; npx playwright install chromium
 */
import { chromium } from "playwright";
import axe from "axe-core";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const origin = process.env.SITE_URL || "http://127.0.0.1:8793";
const output = process.env.AUDIT_OUTPUT || "artifacts/design-review";
const widths = [
  { name: "wide-desktop", width: 1440, height: 900 },
  { name: "laptop", width: 1024, height: 768 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "phone", width: 390, height: 844 },
  { name: "small-phone", width: 320, height: 740 },
];
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const failures = [];
const results = [];

function assert(condition, message) {
  if (!condition) failures.push(message);
}
const snap = async (page, name) => {
  await page.screenshot({ path: join(output, `${name}.png`), fullPage: true, animations: "disabled" });
};

try {
  async function accessibilityAudit(page, label) {
    const result = await page.evaluate(async () => {
      const result = await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] }
      });
      return result.violations.map(item => ({
        id: item.id,
        impact: item.impact,
        description: item.help,
        targets: item.nodes.slice(0, 5).map(node => ({
          path: node.target.join(" "),
          failureSummary: node.failureSummary,
          evidence: node.any.map(check => check.data).filter(Boolean)
        }))
      }));
    });
    for (const violation of result) {
      failures.push(`${label}: axe ${violation.id} (${violation.impact}) on ${violation.targets.map(item => item.path).join(", ")}`);
    }
    return result;
  }

  // Contrast is independently measured from *rendered* text and panel colors.
  // This catches actual regressions even when an accessibility engine caches stale styles.
  async function sampleCardContrast(page, label) {
    const measurements = await page.evaluate(() => {
      const panel = document.querySelector(".work-card");
      const background = getComputedStyle(panel).backgroundColor;
      function luminance(color) {
        const channels = color.match(/[0-9.]+/g)?.slice(0, 3).map(Number);
        if (!channels || channels.length !== 3) throw new Error(`Unrecognized color: ${color}`);
        const linear = channels.map(channel => {
          const value = channel / 255;
          return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
        });
        return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
      }
      const backgroundLightness = luminance(background);
      const selectors = [
        ".work-card-top span:first-child",
        ".work-card-top span:last-child",
        ".work-card-content h3",
        ".work-card-content p",
      ];
      return selectors.map(selector => {
        const foreground = getComputedStyle(document.querySelector(selector)).color;
        const foregroundLightness = luminance(foreground);
        const ratio = (Math.max(backgroundLightness, foregroundLightness) + 0.05) /
          (Math.min(backgroundLightness, foregroundLightness) + 0.05);
        return { selector, foreground, background, ratio: Number(ratio.toFixed(2)) };
      });
    });
    for (const measurement of measurements) {
      assert(measurement.ratio >= 4.5,
        `${label}: insufficient *rendered* text contrast ${measurement.ratio}:1 on ${measurement.selector} ` +
        `(${measurement.foreground} vs ${measurement.background})`);
    }
    return measurements;
  }

  for (const viewport of widths) {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1, reducedMotion: "reduce" });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => {
      if (response.status() >= 400 && response.url().startsWith(origin)) {
        errors.push(`HTTP ${response.status()} ${response.url()}`);
      }
    });

    await page.goto(origin, { waitUntil: "networkidle", timeout: 30000 });
    await page.locator("#hero-title").waitFor();
    const report = await page.evaluate(() => {
      const box = selector => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) };
      };
      return {
        viewportWidth: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        heroHeading: box("#hero-title"),
        heroImage: box(".hero-visual"),
        heroAction: box(".button-brass"),
        navVisible: getComputedStyle(document.querySelector("#primary-nav")).display !== "none",
        brandMarkVisible: getComputedStyle(document.querySelector(".brand-stamp")).display !== "none",
        heroHeadingLines: Math.round(document.querySelector("#hero-title").getBoundingClientRect().height /
          parseFloat(getComputedStyle(document.querySelector("#hero-title")).lineHeight)),
        heroHeadingFits: document.querySelector("#hero-title").scrollWidth <=
          document.querySelector("#hero-title").clientWidth + 2,
        workColumns: getComputedStyle(document.querySelector(".work-grid")).gridTemplateColumns.split(/\s+/).length,
        bandContentFits: (() => {
          const band = document.querySelector(".statement-band").getBoundingClientRect();
          const strong = document.querySelector(".band-inner strong");
          return strong.getBoundingClientRect().right <= band.right + 1 &&
            strong.scrollWidth <= strong.clientWidth + 1;
        })(),
        imagesLoaded: Array.from(document.images).every(img => img.complete && img.naturalWidth > 0),
      };
    });

    assert(report.documentWidth <= viewport.width + 2,
      `${viewport.name}: horizontal overflow (${report.documentWidth}px > ${viewport.width}px)`);
    assert(report.imagesLoaded, `${viewport.name}: a brand image did not load`);
    assert(report.bandContentFits, `${viewport.name}: slogan is clipped inside its banner`);
    assert(report.heroHeadingFits, `${viewport.name}: hero headline overflows its container`);
    assert(report.heroHeadingLines === 3,
      `${viewport.name}: headline wraps across ${report.heroHeadingLines} lines; target is 3`);
    const expectedColumns = viewport.width <= 660 ? 1 : viewport.width <= 900 ? 2 : 3;
    assert(report.workColumns === expectedColumns,
      `${viewport.name}: expected ${expectedColumns} work-card columns, found ${report.workColumns}`);
    if (viewport.width <= 390) {
      assert(report.brandMarkVisible, `${viewport.name}: moth symbol missing from mobile masthead`);
    }
    assert(report.heroHeading?.height > 40 && report.heroAction,
      `${viewport.name}: headline or primary CTA is missing`);
    assert(report.heroHeading && report.heroAction && 
      report.heroHeading.y + report.heroHeading.height < report.heroAction.y,
      `${viewport.name}: hero heading overlaps its action`);
    assert(errors.length === 0, `${viewport.name}: browser errors: ${errors.join("; ")}`);

    report.nightCardContrast = await sampleCardContrast(page, `${viewport.name} night`);
    if (viewport.name === "wide-desktop" || viewport.name === "phone") {
      await page.addScriptTag({ content: axe.source });
      report.axeNight = await accessibilityAudit(page, `${viewport.name} night`);
    }
    await snap(page, `${viewport.name}-night`);
    const theme = page.locator("#light-switch");
    assert(await theme.getAttribute("aria-label") === "Afterlight theme", "Theme toggle has an unstable label");
    await theme.click();
    assert(await theme.getAttribute("aria-pressed") === "true", `${viewport.name}: theme not activated`);
    assert(await page.locator("html").getAttribute("data-theme") === "afterlight",
      `${viewport.name}: afterlight data-theme missing`);

    // Axe virtual-node/style caches from the earlier night run may survive a theme
    // mutation. Reload to exercise persisted Afterlight and audit a fresh DOM.
    // This is NOT a skip: the fresh page gets a full axe WCAG sweep, and the
    // rendered text contrast is independently asserted at every viewport.
    await page.reload({ waitUntil: "networkidle", timeout: 30000 });
    assert(await page.locator("html").getAttribute("data-theme") === "afterlight",
      `${viewport.name}: afterlight preference did not persist on reload`);
    assert(await theme.getAttribute("aria-pressed") === "true",
      `${viewport.name}: reloaded theme control is not pressed`);
    report.afterlightCardContrast = await sampleCardContrast(page, `${viewport.name} afterlight`);
    if (viewport.name === "wide-desktop" || viewport.name === "phone") {
      await page.addScriptTag({ content: axe.source });
      report.axeAfterlight = await accessibilityAudit(page, `${viewport.name} afterlight`);
    }
    await snap(page, `${viewport.name}-afterlight`);

    if (viewport.width <= 900) {
      const menu = page.locator("#menu-toggle");
      await menu.click();
      assert(await menu.getAttribute("aria-expanded") === "true", `${viewport.name}: mobile menu failed to open`);
      await snap(page, `${viewport.name}-menu`);
      await page.keyboard.press("Escape");
      assert(await menu.getAttribute("aria-expanded") === "false", `${viewport.name}: Escape failed to close menu`);
      assert(await page.evaluate(() => document.activeElement?.id === "menu-toggle"),
        `${viewport.name}: Escape failed to restore menu focus`);

      // Escape while closed must NOT take focus from unrelated controls.
      await theme.focus();
      await page.keyboard.press("Escape");
      assert(await page.evaluate(() => document.activeElement?.id === "light-switch"),
        `${viewport.name}: closed menu steals keyboard focus`);

      await menu.click();
      await page.locator('#primary-nav a[href="#ethos"]').click();
      assert(await page.evaluate(() => document.activeElement?.id === "ethos"),
        `${viewport.name}: anchor navigation failed to move keyboard focus`);
    } else {
      assert(report.navVisible, `${viewport.name}: desktop navigation hidden`);
    }

    results.push({ name: viewport.name, ...report, errors });
    await page.close();
  }

  // Without JavaScript, mobile navigation must remain usable.
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 }, javaScriptEnabled: false,
    reducedMotion: "reduce", deviceScaleFactor: 1,
  });
  await page.goto(origin, { waitUntil: "load" });
  const noJSNavVisible = await page.locator("#primary-nav").evaluate(
    element => getComputedStyle(element).display !== "none");
  const noJSMenuHidden = await page.locator("#menu-toggle").evaluate(
    element => getComputedStyle(element).display === "none");
  const noJSThemeHidden = await page.locator("#light-switch").evaluate(
    element => getComputedStyle(element).display === "none");
  assert(noJSNavVisible && noJSMenuHidden && noJSThemeHidden,
    "No-JS mobile navigation is inaccessible or a dead theme toggle is visible");
  await snap(page, "phone-no-javascript");
  await page.close();

  await writeFile(join(output, "audit.json"), JSON.stringify({ results, failures }, null, 2));
  console.log(JSON.stringify({ results, failures }, null, 2));
} finally {
  await browser.close();
}
if (failures.length) process.exitCode = 1;
