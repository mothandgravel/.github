import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import axe from "axe-core";
import { launchAuditBrowser } from "./audit_browser.mjs";
const origin = process.env.SITE_URL ?? "http://127.0.0.1:8793";
const output = "artifacts/design-review";
await mkdir(output, { recursive: true });
const fixture = {
  runId: "browser-fixture",
  serverTime: 5000,
  observations: [
    {
      id: "old",
      origin: "south",
      evidence: "public-ais",
      observedAt: 1000,
      queuedAt: 1100,
      lat: 60,
      lon: 24,
      source: { mmsi: 990000001, provider: "<img src=x onerror=alert(1)>" },
    },
    {
      id: "new",
      origin: "south",
      evidence: "public-ais",
      observedAt: 2000,
      queuedAt: 2100,
      lat: 61,
      lon: 25,
      source: { mmsi: 990000001, provider: "Fixture" },
    },
  ],
  accepted: [
    { station: "north", observation_id: "new", first_received_at: 3000 },
    { station: "north", observation_id: "old", first_received_at: 4000 },
  ],
  receipts: [
    {
      id: 1,
      station: "north",
      observation_id: "new",
      received_at: 3000,
      outcome: "accepted",
    },
    {
      id: 2,
      station: "north",
      observation_id: "old",
      received_at: 4000,
      outcome: "accepted",
    },
  ],
};
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
    const errors = [],
      writes = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (r) => {
      if (!["GET", "HEAD"].includes(r.method())) writes.push(r.method());
    });
    await page.addInitScript(
      (t) => localStorage.setItem("moth-and-gravel-theme", t),
      theme,
    );
    await page.route("**/api/coastal/state", (route) =>
      route.fulfill({ json: fixture }),
    );
    await page.goto(`${origin}/specimens/coastal-watch/identity-ledger/`);
    await page.locator("#il-desk").waitFor();
    await page.locator(".il-dataset").first().waitFor();
    assert.equal(await page.locator("#il-records tr").count(), 1);
    assert(
      await page
        .getByRole("button", { name: "Link to candidate A", exact: true })
        .isDisabled(),
    );
    await page.screenshot({
      path: `${output}/coastal-identity-${width}-${theme}-opening.png`,
    });
    await page
      .getByRole("button", { name: "Next boundary", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Link to candidate A", exact: true })
      .click();
    assert.match(
      await page.locator("#il-assessment").innerText(),
      /candidate A/,
    );
    await page
      .getByRole("button", { name: "Next boundary", exact: true })
      .click();
    assert.equal(await page.locator("#il-accounts").textContent(), "03");
    assert.equal(await page.locator("#il-roots").textContent(), "01");
    await page.locator('[data-source="gnss"]').click();
    assert.equal(
      await page.locator('#il-records tr[data-linked="true"]').count(),
      3,
    );
    await page
      .getByRole("button", { name: "Next boundary", exact: true })
      .click();
    assert.match(await page.locator("#il-result").textContent(), /Separated/);
    const raw = await page.locator("#il-raw").textContent();
    await page.locator("#il-correction").focus();
    await page.keyboard.press("End");
    for (let i = 0; i < 6; i++) await page.keyboard.press("ArrowLeft");
    assert.equal(await page.locator("#il-correction").inputValue(), "180");
    assert.equal(
      await page.locator('[data-mark="shared"]').getAttribute("data-position"),
      "120",
    );
    assert.match(
      await page.locator("#il-result").textContent(),
      /Identity still open/,
    );
    assert.equal(await page.locator("#il-raw").textContent(), raw);
    await page
      .getByRole("button", { name: "Next boundary", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Link to candidate B", exact: true })
      .click();
    assert.match(await page.locator("#il-assessment").innerText(), /conflict/);
    await page
      .getByRole("button", { name: "Keep unresolved", exact: true })
      .click();
    assert.equal(await page.locator("#il-journal li").count(), 3);
    await page
      .getByRole("button", { name: "Previous boundary", exact: true })
      .click();
    assert.match(
      await page.locator("#il-assessment").innerText(),
      /candidate A/,
    );
    assert(await page.locator("#il-other").isHidden());
    assert.equal(await page.locator("#il-journal li.future").count(), 2);
    await page
      .getByRole("button", { name: "Next boundary", exact: true })
      .click();
    const downloadEvent = page.waitForEvent("download");
    await page.locator("#il-export").click();
    const download = await downloadEvent;
    const exported = JSON.parse(await readFile(await download.path(), "utf8"));
    assert.equal(exported.signed, false);
    assert.equal(exported.assessment, "unresolved");
    assert.equal(exported.sessionRevisions.length, 3);
    await page.locator("#il-load-local").click();
    await page.getByText("Reported MMSI 990000001", { exact: true }).waitFor();
    assert.match(
      await page.locator("#il-imported").innerText(),
      /Retained position: 61.00000, 25.00000/,
    );
    await page
      .getByText("Inspect known reports and receipts", { exact: true })
      .click();
    await page.getByRole("button", { name: /^History ·/ }).click();
    assert.match(await page.locator("#il-import-raw").textContent(), /onerror/);
    assert.equal(await page.locator("#il-import-raw img").count(), 0);
    await page
      .locator("#il-import")
      .setInputFiles({
        name: "bad.json",
        mimeType: "application/json",
        buffer: Buffer.from('{"observations":[]}'),
      });
    await page.getByText(/Could not import:/).waitFor();
    assert.match(
      await page.locator("#il-import-status").innerText(),
      /Could not import/,
    );
    assert.match(await page.locator("#il-imported").innerText(), /61.00000/);
    await page.addScriptTag({ content: axe.source });
    const violations = await page.evaluate(
      async () =>
        (
          await axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
          })
        ).violations,
    );
    assert.deepEqual(
      violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
      [],
    );
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    );
    await page.locator("#il-desk").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: `${output}/coastal-identity-${width}-${theme}.png`,
      fullPage: true,
    });
    if (width === 1440) {
      await page.locator(".il-workspace").scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${output}/coastal-identity-desk.png` });
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    await writeFile(
      `${output}/coastal-identity-${width}.json`,
      JSON.stringify(
        {
          width,
          theme,
          errors,
          writes,
          violations: violations.length,
          retainedPosition: [61, 25],
          revisions: 3,
        },
        null,
        2,
      ),
    );
    await page.close();
  }
} finally {
  await browser.close();
}
console.log(
  "Coastal identity: causal replay, dependency roots, reversible decisions, real projection import, accessibility and responsive checks passed.",
);
