# Prepare a written note

Open **Find / prepare a written note…** beside the main **Prepared recordings** search, or **Prepare new notes…** in the Studio header. The written-note window has its own title/number search and shows the newest notes first. Written notes appear before
recordings exist. Select a note, inspect its saved script and requests, explicitly
authorize the Cloud work, and queue preparation. Follow the job in Studio's main
queue. Closing either window does not cancel a persisted job or stop the worker.

The list joins `docs/assets/notes.json` to each episode's explicit
`publication.kind=note` / `publication.note_id` relationship. It does not guess the
next number or mistake an aggregate workbench episode for a dedicated narration.
The Studio essay was Note 013 at the #33 squash commit `d3a6a17`; resolve **The work
outlives the window** from the current catalog before a release rehearsal.

## Inspect before authorizing

**Inspect script · no service request** validates the source fingerprints, speakers,
script and narration-request boundaries with the existing engine. The tabs show
the saved script and the selected Cloud project, private working bucket, caption
model/region, narration model/endpoint, planning pace and request count. Local
cache records are inspected; the worker verifies their media before reuse.

Inspection does not authenticate, discover a project, install tools, change Cloud
resources, submit requests or check live billing. It does not assert current
service prices. The authorization checkbox starts clear and resets after changing
notes, refreshing, another inspection or an error. **Queue preparation** requires
both a current executable inspection and explicit authorization. Concurrent
windows cannot queue duplicate work for an active or waiting episode.

Setup is local to the checkout, not its Git branch. A missing setup message shows
the exact expected path. To reuse a previous production checkout, choose **Import
existing setup…**, select its `artifacts/audio/settings.json`, review the project,
bucket and regions, then confirm. This is local-only: no authentication, Cloud
setup or service request. It never overwrites existing settings, copies unrelated
keys/tokens or moves media caches/receipts. Cancel leaves the checkout unchanged.

Without a valid existing setup, use the explicit CLI setup. When necessary, in the same checkout:

```bash
python3 -m field_notes_audio setup --project YOUR_PROJECT_ID
```

That setup command is **not** an offline check: it authenticates and prepares the
project's APIs and private working bucket. Read its output and the audio guide.
Studio never invokes setup automatically. Preparation uses the validated saved
configuration in `artifacts/audio/settings.json`, not later environment defaults.
The journal captures only the necessary configuration and plan, never access
tokens or unrelated keys from the settings file. Google Cloud CLI, FFmpeg and
FFprobe must be installed before execution.

Sources and saved settings are checked again before queueing, when the worker
claims the job, and before the next synthesis request or caption stage/poll.
Changed inputs block the captured job rather than silently changing its recipe.
A single background inspection keeps Tk responsive; late results cannot populate
a different selection or a closed window. Queue acknowledgments still name the
original episode when selection changes after submission.

## What a preparation job does

The detached worker uses the existing narration and caption engines, their local
locks, checksums, request fingerprints and uncertain-outcome handling. It does not
run host command fragments saved by the UI.

1. Reuse a verified saved narration or complete missing narration chunks under
   the recording lock. A valid final MP3 and its matching metadata/script remain
   usable after intermediate WAV chunks have been pruned.
2. Reuse matching captions, submit missing caption work or poll its saved Cloud
   operation. Audio is uploaded only to the captured private working bucket.
3. Verify narration/caption provenance, media hashes, duration and SRT/VTT/cue
   consistency. Atomically expose a **private prepared recording** to production.

Queueing can authorize billable narration, storage and transcription operations.
There is no automatic retry of an uncertain synthesis/submission and no automatic
restart of a failed remote caption operation. After an error, inspect its history
and repair or deliberately resolve the original engine state; do not delete that
state merely to make a retry proceed.

## Waiting, stopping and recovery

| Queue state | Meaning and next action |
| --- | --- |
| Queued / Working | The captured job is durable. **Stop** requests a safe-boundary stop; it does not interrupt an in-flight transactional media write. |
| Awaiting captions | The bounded wait ended while the saved Cloud operation was still running. Choose **Resume** to poll that operation. Studio does not poll it indefinitely or call synthesis again. |
| Failed / Interrupted / Stopped | Read the visible error and choose **Inspect recovery** to open the same written note. Inspect its saved requests; normal authorization cannot silently resend an uncertain request. |
| Complete | A checked private recording is available to production. It is not human-reviewed, uploaded to a publishing destination or publicly released. |

**Resume** preserves the same job ID and journals the action. Its saved receipt
binds the caption operation name, request fingerprint and audio hash. Missing or
changed narration, a deleted/changed operation receipt or different caption
settings block resume; they never authorize a replacement request. Waiting work
continues to reserve the episode against duplicate jobs and remains visible even
when recent-history limits are reached. A worker restart marks claimed work as
interrupted, never inferred success; a waiting job stays waiting.

A successful atomic adoption wins over a late stop request. Stop requests that
arrive earlier preserve finished narration/caption caches. Closing a window does
not restore authorization checkboxes or manufacture a media approval.

## Uncertain narration recovery

An uncertain chunk has no confirmed local result. This does not establish whether
the service processed or billed it. **Do not delete receipts, reset the run or
change its model merely to remove the block.**

Choose **Inspect recovery** on the failed job, then **Inspect script · no service
request**. The recovery reason and available structured diagnostic appear first.
The project and bucket remain visible. When recovery is offered, read its scope,
check the general Cloud authorization and separately confirm **Also resend the
uncertain chunk(s); I accept possible duplicate charges**. Only then does **Queue
recovery** enable. Declining either confirmation sends nothing.

This resends only uncertain receipts that still match the inspection, reuses
verified completed chunks and proceeds with other missing work. A changed or
deleted receipt blocks the action. A second uncertain attempt requires fresh
inspection and consent; the previous consent cannot authorize another send. The
old diagnostic is retained under `recovery-<chunk>-<receipt-hash>.json`. Caption
uncertainty is not included in narration resend consent; its existing operation
checks and separate recovery requirements remain unchanged.

## Private handoff, not publication

Verified media and a manifest live under:

```text
artifacts/studio/prepared/<episode>/<content-identity>/
artifacts/studio/prepared/<episode>/latest.json
artifacts/studio/studio.sqlite3
```

Production resolves a separate `studio-prepared/…` media namespace. The public
site reader still accepts only its original public asset paths. Private manifests
carry pending review and no publication timestamp. Symbolic-link and path-escape
checks apply to private inputs. Later explicit public publication takes precedence
rather than being silently replaced by local preparation.

A completed job refreshes the main shelf without reloading another selected
episode's unfinished controls, publication draft, filter or batch choices. **Open
prepared files** opens the selected job's saved folder. The new episode can then
use **Open in production** in written-note discovery or **Produce episode** on its completed queue row, followed by ordinary **Produce → Review → Release**. These navigation actions do not queue production or approve media. Its public-link/date defaults are
empty. Human approval remains attached to the exact saved finished media, not the
preparation job. YouTube handoff and recording the actual destination remain
explicit actions. The existing public `promote` command remains scoped to entries
already in the public catalog; preparation does not secretly expand that scope.

No files under `docs/` or `audio/`, website/podcast feeds, or publication records
are changed by private adoption. Preserve the checkout's artifacts directory to
retain the journal, receipts and prepared media.

## Release rehearsal and remaining work

The automated checks use synthetic narration and mocked Cloud boundaries, then
real local encoding, caption validation, adoption and production. Native Tk checks
cover actual consent/queue controls and preserve a labelled fixture screenshot.
They are not evidence of speech quality, live Cloud account readiness or a human
release rehearsal.

For **The work outlives the window**, record the current note/episode identity;
inspect and authorize its real narration; check the actual captions; produce and
listen/watch the finished edition; explicitly approve the exact media; export;
inspect the package; complete the browser handoff; and record the real destination.
**The first operator attempt reached narration, then stopped with one of three
cache records complete and chunk 2 uncertain. The full rehearsal is not complete.**
See the observation record below; the original failure cause is not established
by that offline inspection.

Creating/editing a missing narration script, a guided uncertain-caption recovery
editor, collection-wide readiness, destination-specific release histories and
backup/restore remain separate follow-ups. An absent script is shown with guidance,
not silently generated or approved.

See [the first-run usability observations and regression cases](usability-rehearsal.md).

## Narration response timeouts

A narration chunk may take several minutes to return. Newly inspected Studio
jobs capture a **600-second (10-minute) client socket timeout**. Inspect script
shows this policy before authorization. It is not a completion estimate: Python
applies the timeout to blocking socket operations, not the whole episode or a
strict end-to-end deadline. The queue's elapsed waiting display is measured
locally and does not pretend to know provider progress. Stop takes effect at the
next safe boundary, not by aborting a request whose remote result is unknown.

Older queued jobs lacking a captured timeout keep their original 180-second
policy. After updating and reopening Studio, use **Inspect recovery → Inspect
script** to capture the new policy. For the reported Note 013 failure, verified
chunks 1 and 2 can be reused; only the uncertain chunk 3 needs a new narration
request. Both preparation consent and the possible-duplicate-charge consent are
still required. A new timeout requires another deliberate inspection/decision.
Do not delete the receipts or regenerate the entire episode.

The transport timeout is separate from the script/request/cache fingerprint, so
this update does not move the recording directory or invalidate saved WAV chunks.
It does not require Cloud setup, new credentials, or settings-file edits. It does
not prove Google finished or billed the previous request, or guarantee that a
longer wait will succeed. The synchronous response cannot be recovered by the
caption **Resume** action; that action is only for saved caption operations.
