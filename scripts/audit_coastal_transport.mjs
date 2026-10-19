import { launchAuditBrowser } from "./audit_browser.mjs";
import axe from "axe-core";
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
const origin = process.env.SITE_URL || "http://127.0.0.1:8793";
const output = process.env.AUDIT_OUTPUT || "artifacts/design-review";
const real = process.env.TRANSPORT_REAL === "1";
const now = 1792428800000;
// Explicit browser fixture. Real queue/HTTP tests live in Raivari; this audit
// tests layout, inspection and export without collecting live AIS in site CI.
const o = {
  id: "11111111-1111-4111-8111-111111111111",
  messageId: "22222222-2222-4222-8222-222222222222",
  origin: "south",
  evidence: "public-ais",
  observedAt: now - 30000,
  queuedAt: now - 10000,
  lon: 24.92,
  lat: 60.09,
  priority: "normal",
  acked: true,
  failedBatches: 0,
  source: {
    provider: "Fintraffic / Digitraffic",
    mmsi: 230123456,
    fetchedAt: now - 10000,
    timestampExternal: now - 30000,
    timestampMeaning:
      "Digitraffic timestampExternal; not a verified vessel clock",
    sog: 12,
    cog: 90,
    heading: 90,
  },
};
const fixture = {
  format: "raivari.coastal-transport.v1",
  runId: "browser-fixture",
  serverTime: now,
  controls: { paused: false, reject: false, failResponseOnce: false },
  busy: false,
  observations: [o],
  queues: { north: { pending: 0 }, south: { pending: 0 } },
  accepted: [
    { station: "north", observation_id: o.id, first_received_at: now - 5000 },
  ],
  receipts: [
    {
      id: 1,
      station: "north",
      observation_id: o.id,
      received_at: now - 5000,
      status: 503,
      outcome: "accepted-response-failed",
    },
    {
      id: 2,
      station: "north",
      observation_id: o.id,
      received_at: now - 4000,
      status: 200,
      outcome: "duplicate",
    },
  ],
  attempts: [
    {
      id: "attempt-fixture",
      message_id: o.messageId,
      origin: "south",
      cycle_id: 1,
      attempt: 2,
      started_at: now - 4100,
      finished_at: now - 3900,
      status: 200,
      error: null,
    },
  ],
  cycles: [],
  aisCapture: {
    status: "complete",
    fetchedAt: now - 10000,
    added: 1,
    duplicates: 0,
    excluded: 0,
    limited: 0,
  },
};
await mkdir(output, { recursive: true });
const browser = await launchAuditBrowser();
const results = [];
try {
  for (const width of [320, 390, 768, 1440])
    for (const theme of ["night", "afterlight"]) {
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
      if (!real)
        await page.route("**/api/coastal/state", (r) =>
          r.fulfill({ json: fixture }),
        );
      await page.goto(
        origin + "/specimens/coastal-watch/two-stations/?transport=live",
      );
      await page.locator("#ct-workbench").waitFor();
      await page.locator("#ct-observation").selectOption({ index: 1 });
      assert.match(await page.locator("#ct-record").innerText(), /Public AIS/);
      assert.doesNotMatch(
        await page.locator("#ct-north-summary").innerText(),
        /Radar sample/,
      );
      const beforeHistory = await page
        .locator('#ct-south-marks [role="button"]')
        .count();
      await page.locator("#ct-history").check();
      assert(
        (await page.locator('#ct-south-marks [role="button"]').count()) >=
          beforeHistory,
      );
      await page.locator("#ct-history").uncheck();
      await page.locator("#ct-filter").check();
      assert(await page.locator("#ct-filter").isChecked());
      await page.locator("#ct-observation").selectOption("");
      assert(!(await page.locator("#ct-filter").isChecked()));
      assert(await page.locator("#ct-filter").isDisabled());
      await page.locator("#ct-observation").selectOption({ index: 1 });
      await page.locator("#ct-record details summary").click();
      await page.evaluate(() => {
        window.coastalRecordNode = document.querySelector("#ct-record h3");
        window.coastalPickerOption = document.querySelector(
          "#ct-observation option:last-child",
        );
      });
      await page.locator("#ct-attempts-tab").click();
      await page
        .locator("#ct-attempts details")
        .first()
        .locator("summary")
        .click();
      await page.locator("#ct-refresh").click();
      await page.waitForFunction(() =>
        document
          .querySelector("#ct-status")
          .textContent.startsWith("Connected"),
      );
      assert(
        (await page
          .locator("#ct-attempts details")
          .first()
          .getAttribute("open")) !== null,
      );
      assert(
        await page.evaluate(
          () =>
            window.coastalRecordNode ===
              document.querySelector("#ct-record h3") &&
            window.coastalPickerOption ===
              document.querySelector("#ct-observation option:last-child"),
        ),
      );
      assert(
        (await page.locator("#ct-record details").getAttribute("open")) !==
          null,
      );
      await page.locator("#ct-receipts-tab").click();
      assert(await page.locator("#ct-receipts-pane").isVisible());
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `overflow ${width}/${theme}`,
      );
      await page.addScriptTag({ content: axe.source });
      const violations = await page.evaluate(async () =>
        (
          await axe.run(document, {
            runOnly: {
              type: "tag",
              values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"],
            },
          })
        ).violations.map((v) => ({
          id: v.id,
          targets: v.nodes.map((n) => n.target),
        })),
      );
      assert.deepEqual(violations, []);
      assert.deepEqual(errors, []);
      if (width === 1440 && theme === "night") {
        const pending = page.waitForEvent("download");
        await page.locator("#ct-export").click();
        const download = await pending;
        const exported = JSON.parse(
          await readFile(await download.path(), "utf8"),
        );
        assert.equal(
          exported.integrity.digest,
          createHash("sha256")
            .update(JSON.stringify(exported.payload))
            .digest("hex"),
        );
        assert(
          exported.payload.observations.some(
            (o) => o.evidence === "public-ais",
          ),
        );
        await page.locator("#ct-panel").screenshot({
          path: `${output}/coastal-transport-${real ? "actual" : "fixture"}-desktop.png`,
          style: ".site-header,.skip-link{visibility:hidden!important}",
        });
      }
      if (width === 390 && theme === "night")
        await page.locator("#ct-panel").screenshot({
          path: `${output}/coastal-transport-${real ? "actual" : "fixture"}-mobile.png`,
          style: ".site-header,.skip-link{visibility:hidden!important}",
        });
      await page.locator("#ct-authored").click();
      assert(await page.locator("#cw-desk").isVisible());
      assert(await page.locator("#ct-panel").isHidden());
      results.push({ width, theme, passed: true });
      await page.close();
    }
  await writeFile(
    `${output}/coastal-transport-${real ? "actual" : "fixture"}-results.json`,
    JSON.stringify(
      {
        mode: real
          ? "actual local backend; previously captured public AIS"
          : "browser fixtures; no live provider",
        results,
      },
      null,
      2,
    ),
  );
  console.log(
    `Coastal transport: eight viewport/theme checks, source inspection, export integrity and accessibility passed (${real ? "actual backend" : "fixtures"}).`,
  );
} finally {
  await browser.close();
}
