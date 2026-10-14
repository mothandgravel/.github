# Automated production editions

Finish existing narration locally. No editor, Cloud credentials, new synthesis,
transcription job, paid video generation or upload is involved.

```bash
# Once, for video rendering (Node 22+)
npm ci --prefix video

# Finished MP3, WAV master, SRT/VTT, transcript, MP4, thumbnail and description
python3 -m field_notes_audio produce note-001

# Every prepared episode; completed results are checked and reused
python3 -m field_notes_audio produce all

# More parallel work on a host with spare CPU and memory
python3 -m field_notes_audio produce all --audio-jobs 4 --video-workers 4

# Audio alone needs Python 3.10+ and FFmpeg; no Node dependency
python3 -m field_notes_audio produce all --audio-only

# A quick video check; the audio edition remains full length
python3 -m field_notes_audio produce note-001 --preview-seconds 12
```

The compatibility launcher supports the same commands:
`python3 scripts/field_audio.py produce note-001`. Run `make-all` first if a new
note has no recording yet. Source fingerprints, audio hashes and caption assets
must validate before finishing starts.

## Where work belongs

| Location | Purpose |
| --- | --- |
| `audio/production/settings.json` | Shared sound, pacing and video settings |
| `audio/production/episodes/<id>.json` | Optional partial overrides for one episode |
| `field_notes_audio/production/` | Owning modules for editions, bounded batches, toolchain identity, mixing, motif, retiming and video staging |
| `video/src/` | Reusable React/Remotion composition and caption lookup |
| `video/render.mjs` | Bounded renderer and thumbnail export |
| `tests/audio/test_production.py`, `video/test/` | Production behavior checks |
| `tools/benchmark_production.py` | Offline cold-run and cache-reuse measurements |
| `artifacts/production/<id>/latest.json` | Paths to the latest completed local review |
| `artifacts/production/<id>/<fingerprint>/` | Finished sound and provenance |
| `.../<fingerprint>/video/<video-fingerprint>/` | Finished or explicitly marked preview video |

Outputs are ignored by Git. Paths in `latest.json` are relative to its episode
directory. Its `video` field always identifies a full episode; `preview` and
`preview_seconds` identify a separate preview. An audio-only run or a preview
does not erase the full-video link. New audio invalidates links to older sound.
Finished audio is recorded before video starts and survives a failed render;
repeat the command after correcting the error.

## Edit the sound without regenerating speech

Edit the shared settings or add a partial override such as
`audio/production/episodes/note-001.json`:

```json
{
  "speed": 1.15,
  "intro_seconds": 4,
  "outro_seconds": 5,
  "music_gain_db": -15,
  "video": {"width": 1280, "height": 720}
}
```

The default motif is a short, deterministic plucked/metallic phrase synthesized
from this repository's recipe. It plays at the opening and closing. The opening
can overlap the first sentence; music automatically lowers beneath speech. The
body otherwise has no music bed. This is an initial sound direction for review.

To substitute selected music:

```json
{
  "music_mode": "file",
  "music_file": "music/studio-theme.wav",
  "music_credit": "Artist — Track. License and attribution details."
}
```

Music paths resolve relative to the **shared settings file**, including in
overrides. Absolute local paths also work. Short material loops to fill each
bookend, with fades. Choose permission covering both podcast/audio distribution
and video; retain license evidence. Credits enter the episode description; the
software cannot establish usage rights.

Use `"music_mode": "none"` and `"music_file": null` for silence. Set a bookend's
duration to zero to remove it. Speed accepts 0.75–1.5; bookends accept 0–15 seconds;
overlap accepts 0–3 seconds; music gain accepts −40–0 dB. Video dimensions must be
even and 16:9, within 640×360–1920×1080; frame rate accepts 12–30 and concurrency
1–8. Unknown settings fail rather than being ignored.

Pitch-preserving FFmpeg tempo adjustment precedes 48 kHz stereo mixing. PCM is
streamed through bounded buffers, spooled locally and written with its final WAV
frame count known up front. MP3 uses streamed constant-bitrate encoding. Decoded
narration, WAV master and encoded MP3 durations must match the intended timeline;
shortened output cannot be accepted merely because the encoder exited successfully.
Two-pass
normalization targets −16 LUFS and −1.5 dB true peak by default. The encoded MP3 is
measured again: over 1 LU from target or true peak above −0.5 dB fails production.
The WAV master is retained for video. Caption times apply the baked speed and
intro offset; recognized wording stays unchanged. Long on-screen cues use
proportional pages within original cue bounds, not word-aligned karaoke timing.

## Video, caching and setup

The template uses the existing studio mark, charcoal/bone/brass palette, bold
heading and italic serif contrast. A brief arrival settles, light moves slowly,
and timed captions accompany the voice. Local article illustrations are selected
when available; otherwise the cover is labelled as studio artwork. No remote
images or fonts are fetched during rendering.

Sound and video have separate caches. Changing the video settings, artwork or
React template reuses finished audio. Sound changes invalidate audio and its
video. Media, settings, implementation and pinned video dependencies participate
in identities. Cached output hashes are checked; incomplete stages are never
recorded as complete. Audio finishing uses two bounded jobs by default, before
the video phase. `--audio-jobs 1` selects serial finishing; 2–4 overlap native
FFmpeg work. Already running jobs finish their writes if another job fails;
completed editions remain discoverable and reusable. Identical procedural
bookends share a bounded in-process PCM cache. Encoder/code identity is inspected
once per invocation. Changing only CLI scheduling does not invalidate sound.

Two video frame workers are the default; `--video-workers 1` through `8` override
the configured concurrency. One renderer runs at a time. The compiled bundle is
hashed and reused under `artifacts/production/.renderer/`, including across CLI
runs; corrupt bundles are rebuilt. Read-only links avoid copying the master WAV
through staging and bundling; unsupported filesystems fall back to copying.
Episode assets are switched under the renderer lock and removed afterward.
Increase worker counts after measuring your host's memory and render time.

To compare cold audio finishing and verified reuse on your host:

```bash
python3 tools/benchmark_production.py --jobs 1 2 4
```

The benchmark uses separate temporary output directories, removes its generated
media and writes `artifacts/benchmarks/production.json`. It makes no Cloud calls.

Remotion downloads Chrome Headless Shell on first use if needed. An existing
installation can be selected with `--browser-executable /path/to/headless_shell`.
Run `npm test --prefix video` for timeline and bundle-cache checks. CI finishes
all 13 prepared recordings, renders each title/artwork/thumbnail, and checks
every caption page's actual text bounds without rendering every full episode.
Long titles fit the installed font within a bounded size range; overflow still
fails the render. No Google requests are made. Review outputs are preserved as a
workflow artifact. See
[Remotion licensing](https://www.remotion.dev/docs/license/pricing) for use beyond
individuals and organizations of up to three people.

## Review and publication

Listen to the opening, transition, pronunciation, captions and ending before
approval. Every new edition starts with review status `pending`.

`produce` does **not** replace public recordings, rebuild the podcast feed, push
Git changes or upload to YouTube. Public listening still uses the original
recordings and a web default of 1.15×. Finished MP3s have that pace baked in and
should start at 1×. Website publication must update the playback default, media
manifest and timed transcript together.

For custom YouTube visuals, upload the full `episode.mp4` to the podcast playlist,
upload `thumbnail.png` and `captions.srt`, and copy `description.txt` with credits.
Do not upload previews as full episodes or import duplicate episodes through RSS.
RSS ingestion produces static-art videos. Changing an ingested episode's MP3 does
not update its YouTube video; that requires re-ingestion.

References: [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html),
[Remotion renderer](https://www.remotion.dev/docs/renderer/render-media),
[YouTube podcast playlists](https://support.google.com/youtube/answer/12751636),
[YouTube RSS ingestion](https://support.google.com/youtube/answer/13525207).
