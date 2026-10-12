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
        workHeadingFits: document.querySelector("#work-title").scrollWidth <=
          document.querySelector("#work-title").clientWidth + 2,
        workColumns: getComputedStyle(document.querySelector(".work-grid")).gridTemplateColumns.split(/\s+/).length,
        workCards: Array.from(document.querySelectorAll(".work-card")).map(card => {
          const rect = card.getBoundingClientRect();
          return { left: Math.round(rect.left), top: Math.round(rect.top),
            bottom: Math.round(rect.bottom), width: Math.round(rect.width) };
        }),
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
    assert(await page.locator(".work-card-link").count() === 4, viewport.name + ": expected 4 working Workbench destinations");
    assert(await page.locator('.work-card .work-card-link[href="./notes/002-afterlight-nightfall.html"]').count() === 1,
      viewport.name + ": Field Note 002 is not a peer card");
    assert(await page.locator('.bench-ledger a[href="./notes/"]').count() === 1,
      viewport.name + ": studio status should link to the Field Notes collection");
    assert(await page.locator(".bench-ledger").count() === 1, viewport.name + ": studio status is not visible");
    assert(report.bandContentFits, `${viewport.name}: slogan is clipped inside its banner`);
    assert(report.heroHeadingFits, `${viewport.name}: hero headline overflows its container`);
    assert(report.workHeadingFits, `${viewport.name}: Workbench headline overflows its container`);
    assert(report.heroHeadingLines === 3,
      `${viewport.name}: headline wraps across ${report.heroHeadingLines} lines; target is 3`);
    const expectedColumns = viewport.width <= 660 ? 1 : 2;
    assert(report.workColumns === expectedColumns,
      `${viewport.name}: expected ${expectedColumns} work-card columns, found ${report.workColumns}`);
    assert(report.workCards.length === 4, `${viewport.name}: expected four equal Workbench cards`);
    if (report.workCards.length === 4) {
      const [first, second, third, fourth] = report.workCards;
      if (expectedColumns === 2) {
        assert(Math.abs(first.top - second.top) <= 2 && Math.abs(third.top - fourth.top) <= 2 &&
          third.top >= first.bottom - 1 && second.left > first.left,
          `${viewport.name}: four cards should form a balanced two-by-two grid`);
        assert(Math.abs(first.width - fourth.width) <= 2,
          `${viewport.name}: card columns should have equal widths`);
      } else {
        assert(second.top >= first.bottom - 1 && third.top >= second.bottom - 1 &&
          fourth.top >= third.bottom - 1,
          `${viewport.name}: four cards should stack without overlaps`);
      }
    }
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


  // The Field Note is a real second page, not a dead home-page card.
  for (const viewport of [
    { name: "note-wide-desktop", width: 1440, height: 900 },
    { name: "note-phone", width: 390, height: 844 },
    { name: "note-small-phone", width: 320, height: 740 },
  ]) {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1, reducedMotion: "reduce" });
    const noteUrl = origin + "/notes/001-curiosity-with-calluses.html";
    const response = await page.goto(noteUrl, { waitUntil: "networkidle", timeout: 30000 });
    assert(response?.status() === 200, viewport.name + ": note did not return HTTP 200");
    const heading = page.locator(".note-heading h1");
    assert(await heading.count() === 1, viewport.name + ": Field Note heading missing");
    const layout = await page.evaluate(() => ({
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
      articleVisible: Boolean(document.querySelector(".note-prose")),
      hasWorkbenchReturn: Boolean(document.querySelector('a[href="../#work"]')),
      headingFits: (() => {
        const el = document.querySelector(".note-heading h1");
        return el.scrollWidth <= el.clientWidth + 2;
      })(),
      theme: document.documentElement.dataset.theme,
      ogImage: document.querySelector('meta[property="og:image"]')?.content,
    }));
    assert(layout.documentWidth <= viewport.width + 2,
      viewport.name + ": horizontal overflow (" + layout.documentWidth + "px > " + viewport.width + "px)");
    assert(layout.headingFits, viewport.name + ": Field Note heading is clipped");
    assert(layout.articleVisible && layout.hasWorkbenchReturn,
      viewport.name + ": note article or route back missing");
    assert(layout.theme === "night", viewport.name + ": note starts in wrong default theme");
    assert(layout.ogImage === "https://mothandgravel.com/assets/social-cover.png",
      viewport.name + ": note Open Graph preview mismatch");

    if (viewport.name === "note-wide-desktop" || viewport.name === "note-phone") {
      await page.addScriptTag({ content: axe.source });
      await accessibilityAudit(page, viewport.name + " night");
    }
    await snap(page, viewport.name + "-night");
    const themeButton = page.locator("#light-switch");
    await themeButton.click();
    await page.reload({ waitUntil: "networkidle" });
    assert(await page.locator("html").getAttribute("data-theme") === "afterlight",
      viewport.name + ": Field Note did not preserve Afterlight preference");
    if (viewport.name === "note-wide-desktop" || viewport.name === "note-phone") {
      await page.addScriptTag({ content: axe.source });
      await accessibilityAudit(page, viewport.name + " afterlight");
    }
    await snap(page, viewport.name + "-afterlight");
    results.push({ name: viewport.name, ...layout, noteUrl });
    await page.close();
  }

  // Sprint 03: Field Notes must function as real, readable destinations,
  // not only as static assets with valid HTML links.
  for (const editorial of [
    { name: "notes-index", path: "/notes/", heading: ".notes-index-hero h1" },
    { name: "note-theme", path: "/notes/002-afterlight-nightfall.html", heading: ".study-heading h1" },
  ]) {
    for (const viewport of widths) {
      const page = await browser.newPage({ viewport, deviceScaleFactor: 1, reducedMotion: "reduce" });
      const browserErrors = [];
      page.on("pageerror", error => browserErrors.push(error.message));
      page.on("response", response => {
        if (response.status() >= 400 && response.url().startsWith(origin)) {
          browserErrors.push(`HTTP ${response.status()} ${response.url()}`);
        }
      });

      const label = `${editorial.name}-${viewport.name}`;
      const response = await page.goto(origin + editorial.path, { waitUntil: "networkidle", timeout: 30000 });
      assert(response?.status() === 200, label + ": request failed");
      const layout = await page.evaluate(selector => {
        const heading = document.querySelector(selector);
        const visibleTextFits = element => !element || element.scrollWidth <= element.clientWidth + 2;
        const tracked = [
          heading,
          ...document.querySelectorAll(".notes-index-entry h2, .sample-body h3, .study-sample, .study-metric"),
        ];
        return {
          width: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          headingPresent: Boolean(heading),
          headingFits: visibleTextFits(heading),
          clippedElements: tracked.filter(element => !visibleTextFits(element))
            .map(element => element.className || element.tagName),
          imagesLoaded: Array.from(document.images).every(img => img.complete && img.naturalWidth > 0),
          notes: document.querySelectorAll(".notes-index-entry").length,
          specimens: document.querySelectorAll(".study-sample").length,
          metrics: document.querySelectorAll(".study-metric").length,
          hasIndexRoute: Boolean(document.querySelector('a[href="./"]')),
          ogImage: document.querySelector('meta[property="og:image"]')?.content,
        };
      }, editorial.heading);
      assert(layout.documentWidth <= viewport.width + 2,
        label + ": document overflow " + layout.documentWidth + " > " + viewport.width);
      assert(layout.headingPresent && layout.headingFits, label + ": heading clipped or missing");
      assert(layout.clippedElements.length === 0, label + ": clipped editorial elements: " + layout.clippedElements.join(", "));
      assert(layout.imagesLoaded, label + ": local brand image failed to load");
      assert(browserErrors.length === 0, label + ": browser errors: " + browserErrors.join("; "));
      if (editorial.name === "notes-index") {
        assert(layout.notes === 2, label + ": index must list exactly two real Field Notes");
      } else {
        assert(layout.specimens === 2 && layout.metrics === 6,
          label + ": missing paired specimens or numeric samples");
        assert(layout.hasIndexRoute, label + ": missing back route to Field Notes");
      }
      assert(layout.ogImage === "https://mothandgravel.com/assets/social-cover.png",
        label + ": social preview URL is missing");
      const capture = viewport.width === 1440 || viewport.width === 390 || viewport.width === 320;
      const audit = viewport.width === 1440 || viewport.width === 390;
      if (audit) {
        await page.addScriptTag({ content: axe.source });
        layout.axeNight = await accessibilityAudit(page, label + " night");
      }
      if (capture) await snap(page, label + "-night");
      if (capture) {
        const toggle = page.locator("#light-switch");
        await toggle.click();
        await page.reload({ waitUntil: "networkidle", timeout: 30000 });
        assert(await page.locator("html").getAttribute("data-theme") === "afterlight",
          label + ": saved Afterlight preference was not restored");
        if (audit) {
          await page.addScriptTag({ content: axe.source });
          layout.axeAfterlight = await accessibilityAudit(page, label + " afterlight");
        }
        await snap(page, label + "-afterlight");
      }
      results.push({ name: label, ...layout, browserErrors });
      await page.close();
    }
  }

  // Ensure this is a real raster asset, not an SVG-only sharing fallback.
  const coverResponse = await browser.newPage();
  try {
    const resource = await coverResponse.request.get(origin + "/assets/social-cover.png");
    assert(resource.status() === 200, "Social image did not return HTTP 200");
    assert((resource.headers()["content-type"] || "").includes("image/png"),
      "Social preview is not served as image/png");
    const buffer = await resource.body();
    assert(buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])),
      "Social asset is not a real PNG");
    assert(buffer.length >= 24 && buffer.readUInt32BE(16) === 1200 && buffer.readUInt32BE(20) === 630,
      "Social preview must be 1200 by 630 pixels");
  } finally {
    await coverResponse.close();
  }


  // Exercise the full visitor journey rather than only testing both routes separately.
  const visitor = await browser.newPage({
    viewport: { width: 390, height: 844 }, reducedMotion: "reduce",
  });
  try {
    await visitor.goto(origin, { waitUntil: "networkidle" });
    await visitor.locator('.work-card-link[href="./notes/001-curiosity-with-calluses.html"]').click();
    await visitor.locator(".note-prose").waitFor();
    assert(visitor.url().includes("/notes/001-curiosity-with-calluses.html"),
      "Workbench Field Note link does not navigate to the published note");
    await visitor.locator('.note-end a[href="../#work"]').click();
    await visitor.locator("#work-title").waitFor();
    assert(!visitor.url().includes("/notes/") && visitor.url().endsWith("#work"),
      "Field Note return link does not navigate to Workbench");
    await visitor.locator('.work-card-link[href="./notes/002-afterlight-nightfall.html"]').click();
    await visitor.locator(".study-heading h1").waitFor();
    assert(visitor.url().endsWith("/notes/002-afterlight-nightfall.html"),
      "Workbench Field Note 002 card must navigate to the complete study");
    await visitor.locator('.note-end a[href="./"]').click();
    assert(visitor.url().endsWith("/notes/"),
      "Theme-study back link must navigate to Field Notes index");
  } finally {
    await visitor.close();
  }

  // Follow the new public navigation path using the actual mobile menu:
  // Home -> Field Notes -> Study 002 -> Field Notes, with no dead ends.
  const editorialVisitor = await browser.newPage({
    viewport: { width: 390, height: 844 }, reducedMotion: "reduce",
  });
  try {
    await editorialVisitor.goto(origin, { waitUntil: "networkidle" });
    await editorialVisitor.locator("#menu-toggle").click();
    await editorialVisitor.locator('#primary-nav a[href="./notes/"]').click();
    assert(editorialVisitor.url().endsWith("/notes/"),
      "The mobile Field Notes navigation did not open the index");
    assert(await editorialVisitor.locator(".notes-index-entry").count() === 2,
      "Field Notes index lost one of the published notes");
    await editorialVisitor.locator('.notes-index-entry a[href="./002-afterlight-nightfall.html"]').first().click();
    assert(editorialVisitor.url().endsWith("/notes/002-afterlight-nightfall.html"),
      "The Field Note 002 index link is broken");
    await editorialVisitor.locator('.note-end a[href="./"]').click();
    assert(editorialVisitor.url().endsWith("/notes/"),
      "The theme study return link did not restore the notes index");
  } finally {
    await editorialVisitor.close();
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
