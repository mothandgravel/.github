# Moth & Gravel production studio

![The native Tk studio with labelled pictograms and an inspected production plan](workspace.png)

Real desktop screenshot from the automated UI fixture; media and publication states
in these checks are controlled examples.

A Tkinter/ttk workspace for the existing local production engine. Use
[**Prepare new notes…**](preparation.md) to inspect and explicitly authorize durable
narration/caption preparation. Its verified recording joins the shelf privately,
without publishing or human approval. Choose a prepared episode, inspect the consequences of pace/outro changes, queue an edition, listen
and check subtitles, then prepare the upload package. Record URLs and publication
dates for episodes you have already published separately from their production jobs.

## One production job, one full-episode review

**Produce episode** is the primary action for a prepared recording. It validates
and captures the selected episode's current recipe, then queues **one full `video`
job**: audio finishing, retimed captions, full video and thumbnail. It does not
merely open a tab. Narration/captions are reused, not requested from Cloud again.
The button is available both in Produce and on a completed preparation job.

The optional output selector and **Inspect changes → Queue inspected output** are
for deliberate audio-only, preview or export work. Audio-only is not a prerequisite
for a full episode. See [the production-flow observation record](episode-production-flow.md).

**Review** defaults to the full episode. Watch with sound, confirm that combined
check, check subtitles, enter the reviewer name and record **one approval**. A
separate MP3 listen or audio-only approval is not required. Existing full approval
is not downgraded by an optional recheck of the same audio; changed media still
invalidates approval.

**Upload details** generates title, description, tags, hashtags and the written-note
link. **Published destination** records the actual external release URL/date after
publishing. Known feed data still prefills; new private recordings do not invent a
YouTube URL or publication date. **Use today** fills the date only when selected;
existing drafts and explicitly blank saved records are preserved.

## Episode readiness and show recipes

The sidebar's **Episode readiness** card verifies the current recording, full edition,
review and package, then offers one next action. A changed upload title requires
export, not another review; a changed production recipe is shown as a draft difference.
Preflight blockers appear beside Produce/Export. Use **Audio → Show recipes / overrides…**
to save and explicitly apply a named local recipe to one episode, with visible differences
and one-level undo. Existing saved media, approvals and other episode drafts remain intact.

See [readiness, inline preflight and show recipes](episode-readiness-recipes.md) for scope,
stale-check behavior and recovery. These checks run locally; no Cloud call, automatic
installation or publication occurs. The combined player/timecoded corrections,
notifications and grouped batch outcomes remain later work.

## Get an episode out

Open **Release** for the guided handoff:

**Produce → Review → Release** keeps each stage focused. Pace, outro and production
buttons appear in Produce; Review and Release use the space for their own controls.

1. **Review video** opens the saved-edition review with full audio/video scope.
2. **Inspect package** selects export and shows the plan. Use **Queue inspected output**
   to create the package after checking it.
3. **YouTube Studio** opens the upload destination in your system browser. Open
   **Release → Package files**, check the saved package, and select its video,
   thumbnail or subtitles. **Copy upload path** gives you a path to paste into the
   browser's file picker. Copy the title, description and tags from **Upload details**.
4. In **Published destination**, record the published link and its actual date.

Episode links and dates now fill from the existing podcast catalog. This is data
from the checkout, not a live check of YouTube or another platform. Dates preserve
the catalog timestamp's timezone. Saved user records always take precedence,
including intentionally blank dates/links; automatic defaults do not write records.
**Use podcast details** restores those defaults explicitly. Changing a link clears
an untouched suggested date, so a podcast date is not silently assigned to YouTube.
An explicitly edited date is preserved. **Use today** fills the local system date only
when clicked. Save remains an explicit action.
Unfinished publication fields stay with their episode when you switch away and back
and across closing Studio. Draft checkpoints preserve unfinished text; **Save publication
record** still records the actual release explicitly. Restoring podcast details remains
available even if upload-copy generation fails.

Upload copy reuses the same publishing settings and copy generator as export,
including shared/per-episode tags, hashtags, disclosures, the written-edition link
and music credit. With a local edition, credit comes from its verified saved recipe;
without one, the copy is labelled a draft using configured credit. Refreshing copy
does not replace unfinished publication edits. If an upload package exists, copy comes
from its checksummed title/description/tags/hashtags files. Export again to apply new
settings; then refresh the copy. Export retains its existing shared-settings behavior,
including for already-running workers.

No account connection is needed for this workflow. The browser handoff opens
YouTube Studio; file selection and publication happen there. Studio never infers
that an upload package or a saved URL means a platform publication was verified.
The UI research and adaptation choices are in [publishing-ux.md](publishing-ux.md).
Labelled pictograms, stronger selected tabs and a shared brass primary-action style
help distinguish stages. Copy and Save confirm beside the action; later edits clear
that feedback. Refresh controls show when work is in flight. Search reports matches
and explains empty results; Escape clears the query. Queue failures and interruptions
have written status and an attention tint. Icons scale with the desktop and require
no additional dependencies.

## Know which package you are uploading

**Package files** lists the video, thumbnail, both subtitle formats, podcast MP3 and
transcript with their sizes. **Open file** previews the selected saved asset;
**Open folder** opens the complete package. The panel distinguishes:

- No package yet, with the next production/export step.
- Checked files whose current full-video review is still pending.
- An older package, or one that needs exporting again to attach a newer approval.
- A package matching the current full edition and its approved human review.
- Intact portable files whose latest production edition cannot be verified.

“Ready for manual upload” describes those local checks. It does not establish that
anything has been uploaded or published. A stale or unverified package can still be
inspected, with its status visible. Missing or changed package files block file actions
until the package is repaired and checked again.

Checks run when opening or refreshing this panel, not on every queue poll. Refreshing
upload details or completing production invalidates old package checks. Before opening
an asset or copying its path, Studio checks that the package identity and selected file
still match. Checked package text also refreshes the copy fields without changing an
unfinished publication record.

On WSL, **Copy upload path** uses `wslpath -w` to create a Windows-compatible path,
including for files stored inside Linux. It does not copy or move the media. On a Linux
desktop it copies the native path. If WSL translation fails, Studio explains the failure
and keeps folder access available. This follows Microsoft's documented
[WSL path translation](https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop#path-translation).

## Run in Ubuntu / WSL

The first version runs **inside the existing Linux/WSL production checkout**.
The engine uses Linux process locks. On Windows 11, use WSLg to show the window;
native Windows packaging and a Windows-to-WSL transport are future work.

```bash
sudo apt-get update
sudo apt-get install -y python3-tk ffmpeg xdg-utils
python3 -m field_notes_studio
```

Existing episodes need their original media. Newly written notes can enter through
**Prepare new notes…** with a saved narration script and explicit Cloud setup; see
the [preparation and recovery guide](preparation.md).
There are no additional pip dependencies for the studio. Video/thumbnail rendering
uses the existing Node 22+ / Remotion toolchain:

```bash
npm ci --prefix video
```

The studio launches the worker itself; no terminal production command is needed.
The selected episode shows its verified saved-edition status. Output guidance explains
the next step for audio, preview, full video or export.

Use **Produce episode** for the complete edition, or deliberately choose an optional
output, **Inspect changes**, then **Queue inspected output**. Editing a control
invalidates the inspected plan. `audio` finishes an MP3 and retimed captions; `preview` also renders
the first ten seconds of video; `video` produces the full video and thumbnail;
`export` packages the selected completed full edition. Narration/caption `prepare`
jobs are queued only through the separate authorized preparation window, not this
output selector. Export ignores pace/outro
controls and refuses a changed edition pointer. Export does not upload anything.
The worker repeats the pointer check under the production lock before packaging.
Pace and outro controls are disabled while export is selected.

The queue shows running, waiting and failed/interrupted job counts. Select a row to
see its captured recipe, latest stage or error, and the next useful action:

- **Listen to saved audio**, **Watch preview** or **Watch saved video** opens that
  job's exact saved output, even when a newer edition has since been produced.
- **Open upload package** opens the selected export job's folder.
- **Review latest** selects the job's episode and opens Review with audio
  or full-video scope. It clears a shelf filter if needed. Review always verifies
  the latest saved edition, which may be newer than the selected job.
- **Request stop** is available for queued/running jobs until a stop is requested.
  **Retry** is available for failed, interrupted or stopped jobs when that
  episode has no active job. **History** retains the detailed stage journal.

Previews can be watched from the queue; they cannot be approved as full videos.

**Listen** and **Check subtitles** open the latest local edition in system applications.
**Watch video** opens the saved full video. Playback is external in this version;
there is no embedded player, seek bar or timeline.
The transcript tab shows the published transcript. Production always uses the preserved
source narration, including when the feed already contains finished audio. New editions
retain pending human review state. In the **Review** tab:

1. Keep the default **Full video and audio** for a complete episode. **Audio and
   captions** is an explicit audio-only alternative, not a preceding review step.
2. **Watch video** with sound and **Check subtitles**. **Listen separately** is optional.
3. Confirm watching/listening and subtitle checks, enter your name, then
   **Record approval** once for the full episode.
4. For a full edition, choose **export**, inspect changes and queue the upload package.

Review is attached to the exact verified media, independently of your draft pace/outro
controls. Approval revalidates hashes and source identity under the production lock;
changed editions and changed media are rejected. Switching episode or scope, refreshing
or producing another edition clears the confirmations. A preview cannot be approved as
a full video. The studio refreshes after job state changes without hashing media on
every queue poll. Use **Refresh edition** after production or review in another terminal.

The equivalent terminal command remains available:

```bash
python3 -m field_notes_audio review note-001 --audio-only --approve --reviewer "Your name"
# For a completed full video, omit --audio-only and check the video too.
```

## What survives closing the window

- The independent worker continues processing the queue; it is not a Tk thread.
- Recipes, source identities, results, stage events and publication records live in
  `artifacts/studio/studio.sqlite3`. Media remains in `artifacts/production`.
- Each job captures its recipe. Later edits cannot change that job. A changed source
  blocks it; retry keeps the original recipe and source identity.
- Raw production, sound, publishing-editor and publication-record drafts checkpoint
  locally after a short pause, on episode switches and before closing. Partially typed
  numbers and dates survive. A failed close checkpoint keeps the window open.
- Studio restores the selected episode, workspace/release tabs, search and window size.
  It does not restore inspected plans, review confirmations or approval checkboxes.
  Without a draft, settings recall the last queued recipe, then configured defaults.
- A worker restart takes its exclusive OS lock before marking previously running jobs
  **interrupted**. This means an unknown outcome, never assumed success. Reopen the
  studio to restart a crashed worker, inspect outputs and retry explicitly.
- Retry creates a new job. The engine validates and reuses completed caches; it does
  not promise resumption within an interrupted FFmpeg/render operation.
- Stop is cooperative: a running stage finishes its transactional writes before the
  next boundary stops the job. Its row shows **stop requested** while waiting.

One worker serializes media jobs. Distinct episodes queue behind each other; duplicate
active jobs for an episode are rejected across windows. The queue allows 32 pending
jobs. The UI polls durable snapshots once per second; stage events are structured,
not parsed from terminal text. Fine-grained encoder progress is not available yet.
Active jobs remain visible even when the recent-history limit is reached; recipe
recall searches the full journal.

Inspect the journal without a display, or drain pending work explicitly:

```bash
python3 -m field_notes_studio jobs
python3 -m field_notes_studio worker --once
```

The worker is a checkout-scoped local process, not a system service. It stays idle
after the GUI closes to accept later jobs. Repeated launches are fenced by its OS lock.
Its diagnostic log is `artifacts/studio/worker.log`.

## Separation of concerns

| Module | Responsibility |
|---|---|
| `models.py` | Episode/job values and states |
| `presentation/` | Shelf, workspace, queue, release/review forms, shared scrolling and theme; no workers or files |
| `controller.py` | UI intent, stale-plan protection and main-thread mailbox |
| `service.py` | Application use cases; no widgets or production internals |
| `repository.py` | Atomic SQLite jobs, events and publication records |
| `processes.py` | Detached worker launch and system file opening |
| `pipeline.py` | Existing engine adaptation and rebuild explanations |
| `worker.py` | Exclusive queue ownership, execution and reconciliation |
| `preparation_service.py` / `preparation_jobs.py` | Explicit authorization and captured narration/caption engine adaptation |
| `field_notes_audio/production/sources.py` | Verified private recording adoption and production-source resolution |
| `app.py` | Composition and Tk event-loop lifecycle |

The engine gains an optional structured stage observer. Existing CLI behavior is preserved; production implementation changes correctly
participate in the engine’s cache identity. The adapter requests one audio worker so callbacks stay in
the owning context. Views receive background results through a main-thread mailbox;
workers never receive widget references. Boundary tests enforce dependency direction.

Ideas borrowed from Kitronik Buggy: themed sections, asynchronous loading states,
bounded preview queues and the explorer's worker-to-queue-to-Tk pattern. Its combined
dashboard, camera/voice algorithms and Windows MCI playback are not copied. The first
studio has no frame stream; use a bounded latest-frame queue when adding previews.

## Validation

```bash
python3 tools/check_audio.py
xvfb-run -a python3 -m unittest discover -s tests/studio -t . -v
```

CI covers real Tk editing, plan invalidation, queueing, reopening and publication
records, main-thread delivery, cross-window conflicts, uncertain recovery, cooperative
stopping and real FFmpeg cache reuse with retimed captions. No Cloud credentials.

For a desktop smoke check, change an outro, inspect and queue it, close/reopen while
the worker runs, review the saved media, export, check the package and try its upload
paths in your browser. External players and the browser handoff depend on the desktop.

## Sound and publishing editors

**Audio** exposes intro, music overlap, music level, loudness, peak ceiling, music
mode, custom file selection and music credit/license. Pace and outro stay in Produce.
Inspection uses the production engine's shared validation, including numeric ranges
and custom-music requirements. Jobs capture the complete recipe; later edits cannot
change queued work. Export packages saved media and ignores unfinished sound controls.

**Release → Publishing editor** edits the episode title, multiline summary, additional
tags/hashtags and reusable show defaults. Shared and episode tags combine using the
existing publishing generator. Saving validates settings and generated copy for the
prepared catalog, then atomically replaces `audio/production/publishing.json`.
A file-identity check rejects stale saves from another window or editor. **Reload saved
settings** deliberately replaces this editor's draft with current file values.
Saving does not rewrite an existing upload package; export again to apply it. Existing
queued exports use the publishing file at execution, as the CLI does.

## Batch inspection

Choose **Batch**, select episodes and **Inspect selected episodes**. Output follows
Produce. Inspection shows a separate plan for each episode using its checkpointed
draft, last queued recipe or configured defaults. Invalid unfinished fields block the
inspection; nothing is queued. Editing the current recipe or episode checklist clears
the inspected batch. **Queue inspected batch** commits all requests in one SQLite
transaction: any active episode conflict or insufficient capacity leaves the whole
batch unqueued. Each job keeps its inspected recipe and source identity.

## Health and worker upgrades

**Health** checks the actual worker lock, heartbeat, loaded/checkout code identities,
audio/video preflight, settings, FFmpeg/FFprobe/Node versions and video dependencies.
Missing or stale video dependencies include the existing install command. No tools are
installed automatically. The log path is shown for diagnosis.

**Start / restart worker** starts a stopped worker or requests a handoff after the
current job finishes. Updated workers also detect changed Python code between jobs,
release the lock and launch the checkout's code; they never unload a running media
stage. An older worker without heartbeat/control support can be restarted only when
no job runs. That path fences new claims in a database transaction, verifies the actual
lock-owning process command/root/checkout, and uses a Linux process handle to avoid PID
reuse. Unverifiable identities and busy legacy workers are left running with an
explanation. Refresh health to verify the replacement heartbeat.

Embedded playback, native Windows packaging and authenticated publishing remain
larger integrations outside this local production workflow.


## A second window and the next episode

Episode drafts carry the identity of the checkpoint each window loaded. A stale
window cannot silently replace a newer draft. The conflict panel keeps the local
text open and offers **Load saved draft**, **Keep my draft** and **Open recovery
copies**. Recovery JSON under `artifacts/studio/draft-recovery/` preserves both
versions when resolving a conflict. An unchanged window can close without rewriting
the shared draft. Use updated Studio windows together; old running GUI processes do
not gain this protection until reopened.

[Field Note 013: The work outlives the window](../docs/notes/013-work-outlives-the-window.html)
documents the experiment with a real desktop fixture capture and pinned first-pass
validation. Its source-preserving narration candidate and publishing tags are ready;
no narration request or new podcast publication was made for the written release.

The next useful passes, in order:

1. **A new note into the shelf:** [durable preparation](preparation.md) now connects
   saved-script inspection, explicit authorization, narration/caption cache recovery
   and private recording adoption. Missing-script authoring and guided resolution
   of uncertain caption operations remain future work. Receipt-bound uncertain
   narration recovery now requires separate duplicate-charge consent.
2. **A human release rehearsal:** resolve *The work outlives the window* from the
   current catalog, then take it through narration, caption checks,
   production, media review and the actual browser handoff. Record decisions and
   interruptions; automated layout checks do not establish everyday usability.
3. **Collection readiness:** show which episodes need audio, full video, review or
   re-export without opening each episode. Keep cached local state distinct from
   verified external publication.
4. **Destination records and recovery portability:** keep separate release histories
   per destination and provide a guided backup/restore of the local journal and
   settings. The current publication form holds one editable release record, and
   SQLite durability still depends on preserving the checkout's artifacts directory.

Embedded playback and direct authenticated uploads remain later integration choices.

## First-run navigation and recovery

The main shelf is **Prepared recordings**; new written notes are reached through
**Find / prepare a written note…** beside its search, or the header action. The
written-note window supports title/number search and a deliberate **Import existing
setup…** from an earlier checkout. Failed preparation offers **Inspect recovery**,
not a blind resend. On a completed preparation job, **Produce episode** validates
and queues one full audio/video edition. It never approves or publishes media.
The preparation window's **Open in production** is navigation only. See [preparation and recovery](preparation.md)
and the [operator-observation record](usability-rehearsal.md), including the explicit
consent required to resend a receipt-bound uncertain narration request.


## Uncertain-spend guard and plain errors

After the 17 October incident (502, then 499, then timeouts across three runs), every
paid narration or caption failure says **billing unknown**, shows the attempt count for
that part across runs, the episode's total and the possible spend, and recommends
stopping and waiting. It never says to repeat the same command. 499 is classified as
CANCELLED and treated as uncertain.

The engine refuses another paid request at **2 uncertain attempts per part or 4 per
episode in a rolling 24 h**, counted from the append-only `artifacts/audio/attempts.jsonl`
and older receipts. The CLI and Studio hit the same limit. In **Prepare a written
note**, inspection lists the uncertain attempts with time, status, attempt ID and
estimate. Past the limit, queueing needs **Override the spend guard for one run** and a
logged reason, bound to the count shown. A failed preparation row in the main queue shows
the uncertain total and possible spend. A queued override covers one run; Retry does not
reuse it. Limits, the log and the 360-second narration timeout are described in
[audio/README.md](../audio/README.md#uncertain-spend-guard).

The readiness card and Preflight line show one plain sentence with the next step, such as
"Recording details are incomplete. Prepare the note again." Exception
text such as `KeyError: 'audio_sha256'` is kept behind **Details** on the card.

## Job progress and tab navigation

[Progress design and podcast-tool comparison](progress-ux-research.md) documents the
new Saved / Working / Waiting / Next milestones, evidence boundaries and next ideas.
Select a queue job to see its audio/video or narration/caption stages. A saved job
is not a fresh artifact check or a publication confirmation. Audio (previously Sound),
Batch and Health now have labelled, desktop-scaled pictograms like the other tabs.
