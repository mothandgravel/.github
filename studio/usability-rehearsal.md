# First real preparation attempt: observations and fixes

Specimen: **The work outlives the window**, identified as Note 013 in this run.
Baseline: PR #39 at `8258354` after the #33 squash.

This is an operator-observation record, not proof of a successful episode release.
The operator reported narration starting, then **prepare / failed / failed**. A
subsequent offline inspection reported **one of three narration cache records
complete, with chunk 2 uncertain**. The posted inspection did not establish the
original provider or transport error, whether the request was processed remotely,
or whether it was billed. Do not diagnose it as a timeout from the fixture below.

| Observation | Product change | Acceptance check |
| --- | --- | --- |
| Searching EPISODES / Field Note did not find the new written note. | Label the shelf **Prepared recordings**, explain its scope, and offer **Find / prepare a written note…** beside the search. Carry the query into written-note discovery. | The new, unrecorded fixture note is reachable directly from an empty recording search. |
| A valid setup existed in another checkout, but the error prescribed setup again. A recursive shell search ran too long and buffered its output. | Show the expected checkout-local path and offer **Import existing setup…**, with file selection, validated preview and explicit confirmation. No recursive search or automatic Cloud setup. | Cancel is inert; confirmed import copies only allowed settings, strips unrelated keys, rejects changed/unsafe sources and never overwrites the destination. |
| The preparation table showed only a few rows and was easy to confuse with the main shelf. | Add title/number search; show newest written notes first. Keep the selected-note route from job recovery. | Search, refresh, disappearing selection and compact controls are checked with real Tk. |
| The queue reduced the failure to failed / failed; the useful stage was lost. | Journal each narration chunk; retain the last stage on failure/interruption and show the error alongside its next action. | The three-chunk fixture fails at **narration-2-of-3** and exposes its safe diagnostic without opening History. |
| An uncertain request blocked preparation, with no usable recovery action. | **Inspect recovery** opens the correct note. A separate consent accepts possible duplicate charges for the exact uncertain receipt(s). Ordinary retry never supplies that consent. | A simulated failure on chunk 2 preserves chunk 1. Recovery requests only chunks 2 and 3. Changed/deleted receipts, changed sources and a second uncertain attempt require new inspection/consent. |
| It was unclear when to return to the episode shelf or whether to queue again. | **Show job**, **Ready for production**, **Open in production** and **Produce episode** provide explicit routes. Caption waiting still uses the same-operation **Resume**. | Opening a prepared recording clears an obstructing filter but does not queue production, approve media or publish. |

## Recovery semantics

A recovery authorization contains the exact hashes of the uncertain chunk receipts
and the existing captured source/Cloud plan. The worker checks those receipts
under the recording lock before sending. The original diagnostic is archived.
Each new attempt gets a fresh identity, so a repeated identical error cannot reuse
an old authorization. Verified complete audio is reused. A new uncertainty stops
the run again; it is not an automatic retry loop.

When narration reaches caption waiting, its consumed recovery authorizations are
journaled and removed from the caption-resume request. Resume remains bound to the
saved caption operation and audio, not permission to resynthesize narration.

The project, caption/narration regions and private bucket remain visible while
consent is offered. Recovery requires both general preparation authorization and
the separate possible-duplicate-charge confirmation. Neither is restored after
navigation, refresh, another inspection, closure or a queued submission.

## Evidence boundaries

The timeout in the regression fixture is simulated. Tests use mock Cloud calls,
synthetic WAVs, real local FFmpeg and the real receipt/adoption/queue code. The
fixture establishes recovery behavior, not the cause of the operator's failure,
Cloud availability, voice quality or successful publication. Source scripts,
provider timeouts, request chunking and model choices are not changed by this pass.

Remaining human acceptance: inspect the original diagnostic; deliberately decide
whether to resend; finish narration/captions; produce and review actual media;
export and complete the explicit publisher handoff. No successful live retry,
listening approval or publication is inferred from implementation tests.
