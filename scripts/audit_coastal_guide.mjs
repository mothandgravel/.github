import assert from "node:assert/strict";
import axe from "axe-core";

// Controlled browser fixture, never presented as a live-provider receipt.
export async function auditGuidedRun(
  browser,
  origin,
  fixture,
  observation,
  output,
) {
  for (const [width, theme] of [
    [1440, "night"],
    [390, "afterlight"],
  ]) {
    const page = await browser.newPage({
      viewport: { width, height: 1000 },
      reducedMotion: "reduce",
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(
      (t) => localStorage.setItem("moth-and-gravel-theme", t),
      theme,
    );
    const state = structuredClone(fixture);
    for (const key of [
      "observations",
      "receipts",
      "accepted",
      "attempts",
      "cycles",
    ])
      state[key] = [];
    state.queues = { north: { pending: 0 }, south: { pending: 0 } };
    state.aisCapture = null;
    let captures = 0,
      syncs = 0;
    await page.route("**/api/coastal/state", (route) =>
      route.fulfill({ json: state }),
    );
    await page.route("**/api/coastal/command", async (route) => {
      const body = route.request().postDataJSON();
      state.serverTime += 100;
      if (body.action === "controls") state.controls = body.controls;
      if (body.action === "capture-ais") {
        captures++;
        state.observations.push({
          ...structuredClone(observation),
          id: `guided-${captures}`,
          messageId: `message-${captures}`,
          priority: body.priority,
          observedAt: fixture.serverTime - (captures === 1 ? 30000 : 10000),
          queuedAt: state.serverTime,
          acked: false,
        });
        state.queues.south.pending++;
        state.aisCapture = {
          status: "complete",
          startedAt: state.serverTime,
          fetchedAt: state.serverTime,
          added: 1,
          duplicates: 0,
          excluded: 0,
          limited: 0,
        };
      }
      if (body.action === "sync") {
        syncs++;
        state.cycles.push({
          id: syncs,
          started_at: state.serverTime,
          finished_at: state.serverTime,
          result: {
            north: { success: true, messagesSent: 0 },
            south: {
              success: !state.controls.paused,
              messagesSent: state.controls.paused ? 0 : 2,
              error: state.controls.paused ? "No connection" : undefined,
            },
          },
        });
        if (!state.controls.paused) {
          for (const o of [...state.observations].reverse()) {
            o.acked = true;
            state.accepted.push({
              station: "north",
              observation_id: o.id,
              first_received_at: state.serverTime,
            });
            const attemptId = `guided-attempt-${state.receipts.length + 1}`;
            state.attempts.push({
              id: attemptId,
              cycle_id: syncs,
              message_id: o.messageId,
              origin: "south",
              attempt: 1,
              started_at: state.serverTime,
              finished_at: state.serverTime,
              status: state.controls.failResponseOnce ? 503 : 200,
            });
            state.receipts.push({
              attempt_id: attemptId,
              id: state.receipts.length + 1,
              station: "north",
              observation_id: o.id,
              received_at: state.serverTime,
              status: state.controls.failResponseOnce ? 503 : 200,
              outcome: state.controls.failResponseOnce
                ? "accepted-response-failed"
                : "accepted",
            });
            if (state.controls.failResponseOnce) {
              const retryId = `guided-attempt-${state.receipts.length + 1}`;
              state.attempts.push({
                ...state.attempts.at(-1),
                id: retryId,
                attempt: 2,
                status: 200,
              });
              state.receipts.push({
                ...state.receipts.at(-1),
                attempt_id: retryId,
                id: state.receipts.length + 1,
                status: 200,
                outcome: "duplicate",
              });
              state.controls.failResponseOnce = false;
            }
          }
          state.queues.south.pending = 0;
        }
      }
      await route.fulfill({ json: state });
    });
    await page.goto(
      origin + "/specimens/coastal-watch/two-stations/?transport=live",
    );
    await page.locator("#ct-workbench").waitFor();
    await page.locator("#ct-guide-action").click();
    await page.locator('#ct-guide[data-phase="held"]').waitFor();
    assert(await page.locator("#ct-sync").isDisabled());
    assert.equal(state.receipts.length, 0);
    await page.clock.install();
    await page.locator("#ct-guide-action").click();
    await page.clock.runFor(21000);
    await page.locator('#ct-guide[data-phase="ready"]').waitFor();
    assert.equal(
      state.receipts.length,
      0,
      "ready still waits for the user to release",
    );
    await page.locator("#ct-guide-action").click();
    await page.locator('#ct-guide[data-phase="complete"]').waitFor();
    assert.equal(captures, 2);
    assert.equal(syncs, 2);
    assert.match(
      await page.locator("#ct-guide-note").innerText(),
      /Receipt #3.*Retry receipt #2/,
    );
    await page.locator("#ct-guide-inspect").click();
    assert.equal(await page.locator("#ct-receipts tr").count(), 1);
    assert.match(
      await page.locator("#ct-arrival-heading").innerText(),
      /History grows/,
    );
    await page.locator("#ct-guide-retry").click();
    assert.equal(await page.locator("#ct-receipts tr").count(), 2);
    assert.equal(
      await page.locator("#ct-observation").inputValue(),
      "guided-2",
    );
    assert.equal(await page.locator("#ct-paused").isChecked(), false);
    const sentBeforeReplay = syncs,
      capturesBeforeReplay = captures;
    await page.locator("#ct-guide-replay").click();
    assert.equal(
      await page.locator("#ct-knowledge-position").textContent(),
      "1 / 7",
    );
    assert.equal(
      await page.locator("#ct-north-marks [data-observation]").count(),
      0,
    );
    assert.equal(
      await page.locator("#ct-south-marks [data-observation]").count(),
      1,
    );
    assert(await page.locator("#ct-sync").isDisabled());
    assert(
      await page.locator("#ct-replay-journey").isDisabled(),
      "historical plots do not run a second transport animation",
    );
    for (let i = 0; i < 4; i++)
      await page.locator("#ct-knowledge-next").click();
    assert.match(
      await page.locator("#ct-knowledge-heading").innerText(),
      /newer report arrives/,
    );
    const latest = page.locator('#ct-north-marks [data-latest="true"]');
    assert.equal(await latest.getAttribute("data-observation"), "guided-2");
    const position = await latest.locator("circle.mark").getAttribute("cx");
    const replayClock = await page.locator("#ct-knowledge-clock").textContent();
    state.serverTime += 40000;
    state.busy = true;
    await page.locator("#ct-refresh").click();
    assert.equal(
      await page.locator("#ct-knowledge-clock").textContent(),
      replayClock,
      "live refresh cannot move the replay clock",
    );
    assert.equal(
      await page.locator("#ct-knowledge-controls").isVisible(),
      true,
      "another service operation must not erase the frozen replay",
    );
    state.busy = false;
    await page.locator("#ct-refresh").click();
    await page.locator("#ct-knowledge-next").click();
    assert.equal(
      await page.locator("#ct-north-marks [data-observation]").count(),
      1,
      "duplicate adds no observation",
    );
    await page.locator("#ct-knowledge-next").click();
    assert.equal(
      await page.locator("#ct-north-marks [data-observation]").count(),
      2,
    );
    assert.equal(await latest.getAttribute("data-observation"), "guided-2");
    assert.equal(
      await latest.locator("circle.mark").getAttribute("cx"),
      position,
    );
    assert.match(
      await page.locator("#ct-knowledge-stations").innerText(),
      /north \/ 1 → 2 reports known/i,
    );
    assert.match(
      await page
        .locator('[data-station="north"] .ct-delta-summary')
        .innerText(),
      /position retained.*\+1 to history/,
    );
    assert.equal(
      await page
        .locator(
          '#ct-north-marks [data-change="history"][data-arriving="true"]',
        )
        .count(),
      1,
    );
    assert.equal(
      await page
        .locator('#ct-north-marks [data-change="retained"]')
        .getAttribute("data-observation"),
      "guided-2",
    );
    await page.locator("#ct-knowledge-receipt").click();
    assert.equal(await page.locator("#ct-receipts tr").count(), 1);
    await page.locator("#ct-knowledge").screenshot({
      path: `${output}/coastal-knowledge-${width}-${theme}.png`,
    });
    await page.locator("#ct-knowledge-prev").click();
    assert.equal(
      await page.locator("#ct-north-marks [data-observation]").count(),
      1,
      "rewind removes late history",
    );
    await page.locator("#ct-knowledge-play").click();
    await page.clock.runFor(2500);
    assert.equal(
      await page.locator("#ct-knowledge-position").textContent(),
      "7 / 7",
    );
    assert.equal(
      await page.locator("#ct-knowledge-play").getAttribute("aria-pressed"),
      "false",
      "playback pauses at the final recorded step",
    );
    assert.equal(syncs, sentBeforeReplay);
    assert.equal(captures, capturesBeforeReplay);
    await page.addScriptTag({ content: axe.source });
    const violations = await page.evaluate(async () =>
      (await axe.run(document.querySelector("#ct-panel"))).violations.map(
        (v) => v.id,
      ),
    );
    assert.deepEqual(violations, []);
    assert.deepEqual(errors, []);
    await page.locator("#ct-knowledge-live").click();
    assert(!(await page.locator("#ct-sync").isDisabled()));
    assert.equal(
      await page.locator("#ct-knowledge-controls").isVisible(),
      false,
    );
    await page.reload();
    await page.locator("#ct-workbench").waitFor();
    assert(
      await page.locator("#ct-knowledge-start").isEnabled(),
      "persisted journal reconstructs the replay after reload",
    );
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    );
    await page
      .locator("#ct-guide")
      .screenshot({ path: `${output}/coastal-guide-${width}-${theme}.png` });
    await page.close();
  }
  console.log(
    "Guided AIS run: interruption, bounded source wait, explicit burst release, retained position and both receipt links passed (browser fixtures).",
  );
}
