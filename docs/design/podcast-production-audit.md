# Podcast production audit — PR #28

The audit covers the production CLI, settings, audio mixing and measurement,
caption retiming, cache identities and replacement, output discovery, video
layout, local dependencies and hosted validation. Original narration, recognized
text, public media and the podcast feed remain separate from review editions.

## Findings and fixes

| Finding | Impact | Resolution and evidence |
| --- | --- | --- |
| FFmpeg logs after the JSON report were parsed as JSON | The user's `Extra data: line 13 column 1` stopped note 001 | Decode one JSON object; regression includes appended progress/size lines. Hotfix `70da340`. |
| Successful encoding could produce inconsistent output durations | Reproduced note 003: 427.952 s planned, 380.952 s encoded. Captions correctly rejected the shortened output | Stream PCM/MP3 through bounded buffers; write WAV with its final frame count from the first write. Check decoded narration, master and MP3 durations. A deliberately truncated successful stream is rejected. |
| Audio-only or preview runs overwrote the full-video pointer | A completed render became undiscoverable through `latest.json` | Separate full `video` and `preview` fields. Audio-only preserves both for unchanged sound; sound changes invalidate them. Regression covers all transitions. |
| A failed renderer left no pointer to completed audio | Users could not discover the reusable audio after a video error | Record audio before rendering; regression injects a renderer failure. |
| Cache repair removed independently rendered videos; replacement had no rollback | Corrupt audio could discard expensive renders; interruption could strand the previous directory | Preserve nested video caches during repair and roll back on rename failure/interruption. Video identity includes actual master/cue hashes and timeline. Regression verifies retained renders and interrupted replacement. |
| Description cache omitted source URL/type; renderer dependencies were checked late | Stale links/types could survive, and audio work preceded a missing Node/dependency error | Include ID, kind and slug in identity. Check Node 22+, matching pinned dependencies and supplied browser before processing media. |
| Thumbnail summaries and short previews lacked layout coverage | Summary copy could crowd the footer; short previews selected an unsettled thumbnail frame | Use a smaller thumbnail summary and select its frame from the full timeline. Heading/caption bounds are checked during rendering; CI covers every title, artwork and thumbnail. |
| CI rendered only the first recording | Collection-specific timing/layout failures were outside the gate | CI finishes all 13 recordings, renders a six-second review of each and asserts cache reuse. |
| Long titles depended on a character-count heuristic | Actual fonts/line breaks overflowed: local note 003 and hosted note 006 | Fit measured title height within a bounded font range; retain the overflow guard. All caption pages are also checked during thumbnail export. |
| Serial finishing repeated motif synthesis and toolchain inspection | Idle native processing capacity and duplicated Python work across 13 episodes | Bounded 1–4 audio jobs; immutable per-invocation toolchain identity; bounded memoized motifs with shared stereo calculations. Original PCM and all seven output hashes remain identical in the measured collection. |
| Every video rebuilt its bundle and copied the master twice | Repeated compilation and large WAV transfers | Verify/reuse the bundle across episodes and runs, switch episode assets under a lock, use links with copy fallback, and rebuild corrupt bundles. Node regressions cover asset switching, corruption and interrupted compilation. |

The shortened-output symptom was reproduced independently of the JSON parser
failure. WAV headers with provisional frame counts were also observed during
local diagnosis. The revised writer avoids seek-back header finalization rather
than assuming an encoder exit code proves completeness. This does not establish
that every FFmpeg version or host has the same failure; duration guards remain
necessary even when the writer behaves correctly.

## Validation boundaries

The local quality gate includes 119 Python tests, Ruff, original source/media
checks and both subtitle formats. Focused checks cover real custom music,
successful-but-truncated encoding, caption diagnostics, missing dependencies,
cache repair/rollback and full-versus-preview output discovery. Node tests cover
caption boundary lookup, video duration rounding and bundle reuse/repair. Real collection and hosted
results are recorded in the PR description for the final reviewed commit.

Music/narration listening approval, pronunciation and recognition fidelity remain
human review tasks. No paid generation, transcription, feed promotion, YouTube
upload or PR merge is part of this audit. A finished 1.15× MP3 should play at 1×;
website promotion must update the manifest, timed transcript and player default
together.

## Performance evidence

The [Ajo Python development skill](https://github.com/navivra/ajo/blob/main/.agents/skills/ajo-python-development/SKILL.md)
was read at blob `1f86dad9a2214c51efba84eb81bf1956bd2abb5f`. Its applicable
guidance informed owning modules, typed boundaries, immutable toolchain identity,
bounded resources, boundary validation and regression evidence. Ajo-specific
contracts and Python version requirements were not transplanted into this project.

On the local Linux runner (8 CPU quota, 8 GiB memory), finishing all 13 recordings
(73.5 minutes of finished sound) initially totalled 428.345 seconds of per-edition
processing. The optimized two-worker batch completed in 202.885 seconds wall time,
and a repeat verification completed in 203.765 seconds: approximately 2.1× faster.
The pre-optimization warm collection run took 2.169 seconds under `cProfile`.
All seven output hashes per episode matched before/after optimization, including
MP3, WAV and captions. These are single-host observations, not a cross-platform
benchmark guarantee. The four-worker and full-video final validation results are
recorded in the PR description.

All 13 six-second 720p videos/thumbnails passed, and every caption page passed
actual layout bounds after the title correction. A full 1080p episode is also
checked separately; previews do not establish full-collection video throughput.
The local sandbox needs a loopback-only network-interface adapter for Remotion;
that adapter is not shipped. Hosted CI runs the normal renderer.

`tools/benchmark_production.py --jobs 1 2 4` repeats cold audio finishing into
separate temporary directories and verifies warm reuse without changing completed
editions. FFmpeg performs the heavy audio processing natively; these measurements
do not measure Google TTS latency or imply that replacing Python would speed up
the remote synthesis service.

References: [Remotion bundle reuse](https://www.remotion.dev/docs/bundle),
[Remotion performance guidance](https://www.remotion.dev/docs/performance).

## Run the PR in WSL

Requires Python 3.10+, FFmpeg and Node 22+. A fresh clone already includes the
13 prepared recordings, so Cloud setup and `make-all` are unnecessary for this
production pass.

```bash
mkdir -p "$HOME/source/repos"
cd "$HOME/source/repos"
git clone --branch studio/podcast-production --single-branch \
  https://github.com/mothandgravel/.github.git mothandgravel-production
cd mothandgravel-production
npm ci --prefix video
python3 scripts/field_audio.py produce all
```

From an existing checkout of this PR:

```bash
git switch studio/podcast-production
git pull --ff-only origin studio/podcast-production
npm ci --prefix video
python3 scripts/field_audio.py produce all
```

Use `produce all --audio-only` to finish sound first; repeat `produce all` later
to reuse that audio and add videos. `all` currently means 11 primary notes plus
the conversation and brisk comparison. Outputs live under `artifacts/production/`;
each episode's `latest.json` points to completed files. The full command can be
repeated safely to validate/reuse completed stages.
