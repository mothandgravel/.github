# Studio design sprint: towards a one-shot episode

Date: 17 October 2026. Base: `main` at `3b771d0`. Subject: the Tk/ttk production studio
(`python3 -m field_notes_studio`) and the engine underneath it (`field_notes_audio`).
This is internal research and may name products. Nothing here goes under `docs/`.

The owner's question was whether pro podcast tools suggest UI/UX flows, or subtle changes,
that would make the studio easier to grasp and close to a "one shot" experience. The
owner also wants production-quality polish.

The sprint builds on the decisions already recorded in `studio/`:
[production flow](../studio/episode-production-flow.md),
[readiness and recipes](../studio/episode-readiness-recipes.md),
[preparation](../studio/preparation.md), [progress research](../studio/progress-ux-research.md),
[publishing UX](../studio/publishing-ux.md), [rehearsal](../studio/usability-rehearsal.md) and
[the 502 incident](../studio/narration-502-incident.md). Those decisions are not
re-litigated here. That includes one full-episode job, one full review, receipt-bound
duplicate-charge consent, no invented progress percentages and no simulated publication.

**Evidence.** The screenshots come from the repo's own UI fixtures (`STUDIO_SCREENSHOT_DIR`),
captured under a local Xvfb. A few extra states were driven through the same harness. Every
job, failure, price and publication state shown is a controlled example. No Cloud API was
called. The prototypes are static Tk windows from [`studio-sprint/mockups.py`](studio-sprint/mockups.py).
They use the real `theme.py` palette and `icons.py` pictograms, and every value in them is
illustrative. All images live on the orphan branch
[`evidence/studio-sprint`](https://github.com/mothandgravel/.github/tree/evidence/studio-sprint).

## 1. Audit

### The real end-to-end path today

This path takes one new written note to a YouTube upload plus the website/RSS edition. It
is counted from the docs and from walking the fixture UI.

| Stage | Steps (actions) | Where | Waits | Decisions |
|---|---|---|---|---|
| Prepare | 1 Prepare new notes… · 2 find note · 3 Inspect script · 4 read plan · 5 tick Authorize · 6 Queue preparation · 7 (Resume if captions wait) | second window | inspection; narration + captions (minutes) | spend; recovery consent if uncertain |
| Produce | 8 back to main window, select job/episode · 9 Produce episode | main | render (minutes) | none; the optional output selector is a trap |
| Review | 10 Review tab · 11 Watch video · 12 Check subtitles · 13–14 two ticks · 15 type name · 16 Record approval | main + external player + subtitle viewer | none | approve |
| Package | 17 Export updated package (or Release → Inspect package → Queue inspected output) · 18 Package files → Check files | main | export | none |
| YouTube | 19 YouTube Studio · 20–22 for video, thumbnail, subtitles: select row, Copy upload path, paste into picker · 23–25 title/description/tags: pick field in a combobox, Copy, paste · 26 publish in browser | browser + file picker | YouTube processing | visibility |
| Record | 27 paste URL · 28 date (Use today) · 29 Save publication record | main | none | which date |
| Website/RSS | 30 `promote` · 31 `publish` · 32 merge PR · 33 `verify-live` | **terminal** + GitHub | Pages deploy | none |

**About 33 steps across 8 surfaces**: the main window, the Prepare window, the player, the
subtitle viewer, the file manager/picker, the browser, the terminal and GitHub. There are
**5 machine waits** and **4–5 real decisions**. Only about five of those steps are
judgement calls. The rest is transport.

### Where a first-time user stalls

1. **Two front doors.** "Prepare new notes…" sits in the header, and the shelf shows only
   *Prepared recordings*. A new note is invisible until the user learns that preparation
   is a separate window. This was already observed in the rehearsal.
2. **Produce shows three action buttons of equal weight.** *Produce episode*, *Inspect
   changes* and *Queue inspected output* sit beside an "Optional output: video" selector.
   The brass primary button is somewhere else, in the readiness card (`produce-inspected-plan`).
3. **After preparation succeeds**, the user has to work out that *Produce episode* lives on
   the queue row or in the main window. The Prepare window's *Open in production* only
   navigates.
4. **Release is a tab inside a tab.** It has four sub-tabs (Upload details, Published
   destination, Package files, Publishing editor) plus three toolbar buttons. Each upload
   field is copied one at a time through a combobox (`release-upload-details`).
5. **The website/RSS edition needs the terminal** (`promote`, `publish`). Studio has no
   step for it, so the release stepper ends before the episode is on the site.

### Jargon

These terms appear in the UI and mean something only to the engine: *edition*, *recipe*,
*preflight*, *inspected output*, *Optional output: video/audio/preview/export*, *worker*,
*prepared recording*, *package*, *captured recipe*, *cache records*, *socket timeout*,
*receipt*, *chunk*. Raw stage ids also leak into the queue (Stage `video`, `queued`). A
proposed glossary is in §4.

### Where state is unclear

- **Raw exception text reaches the user.** `readiness.py` returns `str(exc)`. For a
  `KeyError`, that renders as `'audio_sha256'` in both the readiness card and the Preflight
  line (`readiness-export-fixture`, `progress-failure-fixture`). See `readiness.py:173`,
  `:238`, `:244` and `:287`.
- **The readiness card and the Produce tab can disagree.** The card can say "Package
  needs refreshing" while the subtitle says "No local edition yet…" (`release-*` captures).
- **The failed preparation row repeats a 400-character diagnostic in the main window**
  (`preparation-failed-queue-fixture`).
- **The footer carries 2–3 lines of hints.** These include a static
  "Produce episode → Review once → Export package → Upload manually" that never reflects
  where the episode actually is.
- **"Choose an episode" leaves the recipe controls and *Inspect changes* enabled** when the
  shelf is empty.

### Polish

| Area | Finding |
|---|---|
| Alignment | The selected notebook tab grows about 5 px taller than its siblings, so the label baseline jumps. Readiness's "EPISODE READINESS" heading touches its *Check* button at 1050 px. The shelf truncates mid-word ("Curiosity with call▌Feed"). |
| Hierarchy | Brass marks one primary action in the card, but Produce has three equal white buttons. The serif title, the serif "Production studio" and the uppercase headings compete in the top 150 px. |
| Icons | The pictograms are consistent and labelled. The *Produce* waveform also appears on *Queue inspected output*, *Start / restart worker* and *Queue inspected batch*, so the same glyph means four different things. |
| Controls | The clam theme's checkbuttons render as an ✕ box (recovery) or a blue indeterminate square, which reads as "already ticked". |
| Space | When the queue is visible the shelf list collapses to almost nothing (`progress-*`). Package files shows one row in a scroll area inside another scroll area. |
| Keyboard | Escape clears search, and nothing else exists: no accelerators, no menu bar, no shortcut for the primary action. |
| Dark appearance | None. There is one light palette, while the website ships Night/Afterlight. |
| HiDPI | Fonts are in points and icons scale from `tk scaling` (`icons.py:117`). Not verified at 150 % or 200 % on WSLg. One extra fixture capture showed the Prepare window's "Note" column clipped at a larger text size. The cause is not confirmed, so treat it as unverified. |
| Progress | Milestones are good. There is elapsed time but no local duration history and no notification, so the user has to keep the window open to know when they are needed. |
| Empty/error/recovery | Recovery is correct and very cautious. The copy, however, is engine language, and the next step depends on reading a paragraph. |

Captures: [current/](https://github.com/mothandgravel/.github/tree/evidence/studio-sprint/studio-sprint/current).

### Today's incident: provider failure, uncertain billing and resume

**What happened (reported by the owner, 17 October).** Gemini TTS returned **502**, then
**499**, then **600-second timeouts** across three runs. An **unattended retry loop kept
issuing paid attempts**.

**What the code does.** Neither the Studio worker nor the engine retries on its own
(`preparation.md`, `usability-rehearsal.md`). Every uncertain resend needs fresh,
receipt-bound consent in Studio or `--retry-uncertain` on the CLI. Three gaps remain:

1. **The CLI tells the reader to loop.** `http_guidance()` (`field_notes_audio/audio.py`)
   says, for any 5xx: *"After a short pause, repeat the same generate command with
   --retry-uncertain."* An unattended driver, whether a shell loop, a script or an agent,
   follows that literally. Nothing counts attempts across runs, so nothing stops it.
2. **499 is not classified.** It falls through to generic text. In Google's error model
   it maps to `CANCELLED`, and [AIP-194](https://google.aip.dev/194) says not to
   auto-retry it.
3. **Uncertain spending is invisible in aggregate.** Each receipt records one attempt, but
   no surface sums them as "3 uncertain attempts on part 3, each possibly billed, at most
   about $X".

**Design.** Prototype `b-provider-failure-spend-guard`:

- **Provider-incident state.** After two consecutive service-side failures (5xx, 499 or a
  timeout) on any part, the episode is **Paused: the narration service is failing**. The
  wording is not "Failed". Saved parts are listed as safe. Nothing else in Studio is
  blocked.
- **Attempt ledger.** One table holds every attempt for the part, with time, a plain
  meaning for the status, the wait, and "Billing: unknown; may be billed". It also shows
  an upper-bound estimate from the existing `estimated_output_cost_usd`, plus an *Open
  billing console* link. Studio never claims a charge or a refund.
- **Spend guard in the engine, not the UI.** The guard is a per-part and per-episode
  uncertain-attempt budget. The default is 2 per part per 24 h, chosen at pre-flight. It is
  counted from receipts on disk, so the CLI, Studio and any script hit the same wall.
  Exceeding it needs a deliberate override, such as a typed reason or a new
  pre-flight consent. A loop cannot keep spending.
- **Retry guidance stops telling the reader to retry.** For 5xx/499/timeouts the text
  becomes: wait, check the provider status, then try **once** with consent. The attempt
  count is always shown.
- **Resume stays explicit.** *Try part 3 once more…* reuses the existing duplicate-charge
  consent. *Pause until I come back* keeps the job parked. *Copy diagnostics* produces the
  bounded, redacted text for a bug report.
- **Engine option to investigate.** Google's
  [Long Audio Synthesis](https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-long-audio-synthesis)
  is asynchronous and polls an operation. That would turn "uncertain" into a resumable
  wait, the way captions already work. It is unverified whether it supports the Gemini
  voices in use. This is an owner question.

Cloud budgets [alert but do not cap](https://docs.cloud.google.com/billing/docs/how-to/budgets).
The local guard is the only hard stop.

## 2. What professional tools do

This extends the comparisons in `progress-ux-research.md` and `publishing-ux.md`. Sources
are official help pages unless marked. Lines marked *(unverified)* could not be confirmed
on a fetched official page.

| Job | Documented pattern | What it suggests here |
|---|---|---|
| TTS narration | [ElevenLabs Studio](https://elevenlabs.io/docs/creative-platform/products/studio) labels the button **Regenerate** when free and **Generate** when it costs credits. It shows the credit cost before export and keeps a per-paragraph generation history with *Restore*. | Put the paid/free state on the button. Keep per-part versions, so re-narrating one part never discards the approved take. |
| TTS narration (async) | [Google Long Audio Synthesis](https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-long-audio-synthesis) runs as a long-running operation with `progressPercentage`, written to `gs://`. | Use a pollable operation instead of an uncertain synchronous call (see the incident). |
| Retry policy | [Google retry strategy](https://docs.cloud.google.com/storage/docs/retry-strategy) retries only idempotent or precondition-protected requests, with backoff and jitter. [AIP-194](https://google.aip.dev/194) says not to retry CANCELLED. | Paid synthesis is not idempotent, so a person decides each retry and the budget is enforced. |
| Transcript-first editing | Descript and Premiere text-based editing put transcript edits on the media *(unverified on fetched official pages)*. | For review rather than editing: a timecoded transcript to play from, flag and fix captions (Concept C). |
| Loudness presets | Auphonic defaults to −16 LUFS for podcasts. Apple is about −16 LUFS / −1 dBTP, and Spotify normalises to about −14 *(secondary sources)*. Hindenburg ships export loudness targets *(third-party)*. | Show the measured LUFS/peak as a saved milestone ("−16.1 LUFS · peak −1.2 dBTP"). It is evidence, not approval. |
| Chapters | [YouTube chapters](https://support.google.com/youtube/answer/9884579) need 00:00 first, at least 3 chapters, each at least 10 s. [Podcasting 2.0 chapters](https://podcasting2.org/docs/podcast-namespace/tags/chapters) are JSON, editable after publishing. [Auphonic](https://auphonic.com/blog/2013/07/08/howto-chapter-marks-auphonic/) offsets chapters by the intro automatically. | Later: derive chapters from note headings plus intro offset, write them into the description and a JSON chapters file. Out of scope for the concepts. |
| Review/approval | Frame.io: timecoded comments and an *Approved* status *(third-party)*. | Notes are attached to timecodes. Approval is blocked until notes are resolved or dismissed (Concept C). |
| Publish hand-off | [YouTube upload](https://support.google.com/youtube/answer/57407): Checks continue in the background, SD publishes before HD, and closing early saves as private. The [resumable upload protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol) resumes by byte range. | Keep the manual browser hand-off, but put everything to copy on one page. A future authenticated upload would be resumable, not restarted. |
| Show templates | [Auphonic batch](https://auphonic.com/help/web/batch.html) applies a preset to many inputs, with per-production overrides. | Already built (named recipes). Name the recipe in the episode header, with an override count. |
| Batch queue | Media Encoder watch folders and queue *(unverified)*. A known complaint is that one stalled item blocks the queue. | Group the queue by "needs you / working / ready", not by job row (Concept B home). |
| Progress | [NN/g progress indicators](https://www.nngroup.com/articles/progress-indicators/): show a step count for series jobs and give an estimate for long jobs. | Use step counts ("3 of 3 parts"). Base estimates only on durations measured on this computer. Notify when the user is needed. |

Guidelines applied: [NN/g error messages](https://www.nngroup.com/articles/error-message-guidelines/)
(near the source, plain language, a remedy, input preserved), [confirmation
dialogs](https://www.nngroup.com/articles/confirmation-dialog/) (only for costly actions, with
outcome-labelled buttons), [visibility of system status](https://www.nngroup.com/articles/ten-usability-heuristics/),
[empty states](https://www.nngroup.com/articles/empty-state-interface-design/), and the
ui-patterns.com [Wizard](https://ui-patterns.com/patterns/Wizard) pattern (a summary before
the final step and an expert path). The uxpatterns.dev stepper page could not be fetched.

**What makes these tools feel one-shot and trustworthy:**

1. **One summary, one confirm, then walk away.** The cost and consequences are shown once,
   up front.
2. **The paid/free state is on the button itself.**
3. **Machine stages chain automatically. People are interrupted only for judgement**
   (review, publish).
4. **Every unit keeps its versions**, so redoing one part never destroys the approved
   whole.
5. **Failures are classified.** A transient fault is not a permanent one, and a cancel is
   never auto-retried.
6. **Status is grouped by who acts next**, not by job id.
7. **The hand-off page has everything needed to publish**, with copy buttons, limits and
   files.

## 3. Concepts

### A: Polish in place

**Stance.** Keep today's information architecture (shelf, readiness card, Produce /
Review / Release). Make it read like a finished product: one primary action, a stage
stepper, tools separated from stages, plain words, a Night palette and a one-page Release.

![Review: current vs A](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/compare/1-review-before-after.png)
![Release: current vs A](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/compare/2-release-before-after.png)
![A in Night](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/prototypes/a-review-polished-night.png)

- **Stepper** (Prepare · Produce · Review · Release) under the title, with pictogram, text
  state and time. Colour is never the only signal.
- **Stage tabs** are Produce/Review/Release only. Transcript, Sound, Several episodes and
  Setup check move to a tools row.
- **The readiness card becomes a checklist** with one brass action. It is the only brass
  button on screen apart from the in-panel commit (Approve, Save).
- **Release is one page**: each copy field with *Copy* and a limit counter, the files with
  *Copy path*, *Open YouTube Studio*, a "Website and podcast feed" block (wrapping
  `promote`/`publish`), and the release record.
- The reviewer name is remembered per computer. The consent ticks never are.
- A one-line status bar with a *Jobs (n)* button replaces the always-open queue.
  Attention still opens the queue.

**Flow.** About 33 steps become **about 25**. Combined field copy saves 3 steps, the
remembered name saves 1, export is offered on approval for 1, and the terminal steps
collapse to *Prepare website update…* plus merging the PR, saving 2. Surfaces drop from 8
to 7, because the terminal goes. Waits are unchanged.

**Engine.** No pipeline change. It needs a plain-language error mapper in `readiness.py`,
a local preference for the reviewer name, a Night palette in `theme.py`, and a Studio
action that calls the existing `promote` and then `publish`. `publish` pushes a branch, so
it stays an explicit, labelled action.

**Risk/effort.** Low risk, about 3–5 focused PRs. It does not change the number of
decisions or waits, so it is not "one shot" on its own.

### B: One-shot "Make episode"

**Stance.** One path from a written note to "needs your review". A pre-flight summary
shows what will happen, what is paid and the spend guard. There is **one confirm**. A
progress timeline chains narration → captions → sound → video. The user is interrupted
only for review. The upload package is made automatically after approval. The home
screen becomes a work list grouped by who acts next.

![Pre-flight: current vs B](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/compare/3-preflight-before-after.png)
![Progress: current vs B](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/compare/4-progress-before-after.png)
![Failure: current vs B](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/compare/5-failure-before-after.png)
![Home: current vs B](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/compare/6-home-before-after.png)

**Flow.** *Make episode from a note…* → check the summary → tick *Allow paid narration and
captions* → **Make episode** → (walk away; optional desktop notification) → review (watch,
subtitles, two ticks, Approve) → package made locally → Release page (YouTube files and
copy, website update, record link). That is **about 18–19 steps**. The machine waits the
user sits through drop from 5 to **1** (plus YouTube processing). Surfaces drop to 4:
Studio, the player, the browser and GitHub.

**Engine.**

- A **chained "make" plan.** The existing preparation job, then the full `video` job, are
  queued as one captured plan with one consent covering exactly the displayed paid
  requests. Each job keeps its own captured recipe and identity. A failure stops the chain
  where it is.
- **Spend guard and attempt ledger**, enforced in `field_notes_audio` for the CLI and
  Studio alike (see the incident above).
- **Export on approval.** It is local and free. It could also be a single click, which is
  an owner choice.
- A local **duration history** per stage, for "6–9 min on this computer before". Without
  history there is no estimate.
- An optional **desktop notification** (for example `notify-send`, where available) when
  review is needed or the job pauses.

**Risk/effort.** Medium. The consent model has to stay as strict as today: the one consent
binds the displayed requests and never covers an uncertain resend. Job chaining touches the
worker and repository. Roughly 5–8 PRs, with tests on real SQLite and mocked Cloud. It
keeps every existing screen as the expert path (ui-patterns Wizard: provide an expert
alternative).

### C: Transcript-first review

**Stance.** Review is where judgement happens, so make it the strongest surface. A
timecoded transcript plays from any line in Studio (audio via `ffplay`, already part of
the FFmpeg dependency). Flags pronunciation and caption issues at timecodes, fixes caption
text in place, and offers **Re-narrate this part… (paid)** through the existing receipt
and consent machinery. Approval waits until the notes are resolved or dismissed and the
playback reached the end.

![Review: current vs C](https://raw.githubusercontent.com/mothandgravel/.github/evidence/studio-sprint/studio-sprint/compare/7-transcript-review-before-after.png)

**Flow.** The step count does not change. It replaces the external player and subtitle
viewer, saving 2 surfaces, and turns "I found a problem" from a terminal/file excursion
into two clicks.

**Engine.**

- Caption overrides stored with provenance and re-applied to the retimed captions. Changed
  captions invalidate the old approval, as changed media already does.
- Per-part re-narration as a new preparation attempt, with the existing duplicate-charge
  rules.
- A small playback process manager.
- Video still opens externally, because embedded video in Tk is out of scope.

**Risk/effort.** Medium–high. It needs playback, caption editing and per-part versions.
It is best built after B, as B's Review stage.

### Ranked subtle changes (worth doing whatever is chosen)

1. **Never show raw exceptions.** Map `readiness.py` errors (`'audio_sha256'`) to one plain
   sentence plus *Details*.
2. **Stop the retry-loop guidance.** Rewrite `http_guidance` for 5xx/408/429/499, classify
   499, and show the attempt count and "billing unknown" on every narration failure.
3. **Engine spend guard.** Count uncertain attempts per part from receipts and refuse past
   the budget without a deliberate override (CLI and Studio).
4. **One brass action per view.** The readiness card's next action is the primary.
   *Inspect changes* and *Queue inspected output* move behind *More options…*.
5. **Separate stages from tools** and fix the selected-tab height jump.
6. **Upload copy on one page**: every field with Copy and its limit counter, and files with
   Copy path.
7. **Plain-language pass**: edition → *version*, recipe → *show settings*, preflight →
   *checks*, inspected output → *plan*, worker → *background producer*, prepared recording
   → *narrated note*, package → *upload folder*. Raw stage ids become sentences.
8. **Shelf shows every note with a "Next" column** and a *Needs me* filter. This covers the
   planned collection readiness and the single front door.
9. **Checkbox indicators**: bind variables and theme the indicator, so no ✕ or
   indeterminate squares appear.
10. **One-line status bar** instead of 2–3 hint lines. Drop the static route hint once a
    stepper exists.
11. **Night palette** from the site's Nightfall tokens, with an explicit toggle.
12. **Keyboard**: Ctrl+F search, Ctrl+Enter primary action, Ctrl+1/2/3 stages, and a check
    of the focus order.
13. **Remember the reviewer name**, and never the approval ticks.
14. **Empty states**: disable recipe controls when no episode is selected, and give one
    sentence and one button for "no narrated notes yet".
15. **Measured durations and a notification** when the user is needed.
16. **Distinct glyphs**: the waveform means *Produce* only. Queue, worker and batch get
    their own glyphs.

## 4. Recommendation

**Do the subtle changes now (items 1–3 first, because they are the incident), adopt B as
the target information architecture, and build C later as B's Review stage.** Concept A
on its own polishes the hub but leaves about 25 steps and 5 waits. The owner's "one shot"
comes from chaining the machine stages behind one honest pre-flight. That needs B's
chained plan and the spend guard, and the spend guard is overdue after today anyway.

Suggested order:

1. Spend guard, retry guidance and error mapping. These are engine and copy changes, with
   no new information architecture.
2. A's polish items: stepper, stage/tool split, one-page Release, Night, keyboard.
3. B's pre-flight, chained plan, work-list home and notification.
4. C's transcript review.

Each step ships on its own. The existing screens stay available as the expert path.

## 5. Decisions only the owner can make

1. **Spend guard default.** How many uncertain paid attempts per part, and per episode per
   day, before Studio and the CLI refuse? (Proposed: 2 per part, 4 per episode, per 24 h.)
2. **One consent for a whole "Make episode"**, covering the displayed narration and caption
   requests, or keep two separate prepare/produce confirmations?
3. **Export after approval.** Automatic (local, free), or a single click?
4. **Website/RSS from Studio.** May Studio run `promote`, and push the publication branch
   with `publish` behind a labelled button? It never merges.
5. **Investigate async Long Audio Synthesis** for narration, even if it means a voice or
   model change?
6. **Plain-language renames.** Approve the glossary in item 7, especially *edition →
   version*.
7. **Night appearance.** Follow the system setting where it can be detected, or offer only
   a manual toggle?
