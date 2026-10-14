# Moth & Gravel production studio

![A real episode in the Tkinter production workspace](workspace.png)

A Tkinter/ttk workspace for the existing local production engine. Choose a prepared
episode, inspect the consequences of pace/outro changes, queue an edition, listen
and check subtitles, then prepare the upload package. Record URLs and publication
dates for episodes you have already published separately from their production jobs.

## Run in Ubuntu / WSL

The first version runs **inside the existing Linux/WSL production checkout**.
The engine uses Linux process locks. On Windows 11, use WSLg to show the window;
native Windows packaging and a Windows-to-WSL transport are future work.

```bash
sudo apt-get update
sudo apt-get install -y python3-tk ffmpeg xdg-utils
python3 -m field_notes_studio
```

The checkout must already contain prepared episodes and their original media.
There are no additional pip dependencies for the studio. Video/thumbnail rendering
uses the existing Node 22+ / Remotion toolchain:

```bash
npm ci --prefix video
```

Use **Inspect changes**, then **Queue production**. Editing a control invalidates the
inspected plan. `audio` finishes an MP3 and retimed captions; `preview` also renders
the first ten seconds of video; `video` produces the full video and thumbnail;
`export` packages the selected completed full edition. Export ignores pace/outro
controls and refuses a changed edition pointer. Export does not upload anything.

**Listen** and **Check subtitles** open the latest local edition in system applications.
Playback is external in this version; there is no embedded player, seek bar or timeline.
The transcript tab shows the published transcript. Production always uses the preserved
source narration, including when the feed already contains finished audio. New editions
retain pending human review state. After listening and checking captions, use:

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
- The shelf restores the last queued pace/outro for each episode. Unqueued edits are
  drafts and are not saved. Other settings come from the production config.
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
| `presentation/` | Shelf, workspace, queue and theme; no workers or files |
| `controller.py` | UI intent, stale-plan protection and main-thread mailbox |
| `service.py` | Application use cases; no widgets or production internals |
| `repository.py` | Atomic SQLite jobs, events and publication records |
| `processes.py` | Detached worker launch and system file opening |
| `pipeline.py` | Existing engine adaptation and rebuild explanations |
| `worker.py` | Exclusive queue ownership, execution and reconciliation |
| `app.py` | Composition and Tk event-loop lifecycle |

The engine gains an optional structured stage observer. Existing CLI output and cache
identities are unchanged. The adapter requests one audio worker so callbacks stay in
the owning context. Views receive background results through a main-thread mailbox;
workers never receive widget references. Boundary tests enforce dependency direction.

Ideas borrowed from Kitronik Buggy: themed sections, asynchronous loading states,
bounded preview queues and the explorer's worker-to-queue-to-Tk pattern. Its combined
dashboard, camera/voice algorithms and Windows MCI playback are not copied. The first
studio has no frame stream; use a bounded latest-frame queue when adding previews.

## Validation and the first Field Note

```bash
python3 tools/check_audio.py
xvfb-run -a python3 -m unittest discover -s tests/studio -t . -v
```

CI covers real Tk editing, plan invalidation, queueing, reopening and publication
records, main-thread delivery, cross-window conflicts, uncertain recovery, cooperative
stopping and real FFmpeg cache reuse with retimed captions. No Cloud credentials.

The experiment is **one published episode, one inspectable rebuild decision, one
recovery question**: change an outro, produce it, close/reopen while the worker runs,
inspect its outcome and listen to the result. Keep the Field Note provisional until
a human has tried that workflow in their WSL setup.
