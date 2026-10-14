# From a Field Note to a published episode

Publish the written note first. Its title, summary and complete prose supply the
narrated episode. Keep one persistent WSL generation checkout with its ignored
`artifacts/audio/` cache and saved Google settings. After updating that checkout
from `main`, create a batch branch, run `sync` and inspect the new scripts in
`audio/scripts/` before paid generation:

```bash
git switch main
git pull --ff-only origin main
git switch -c "studio/audio-$(date +%Y%m%d-%H%M%S)"
python3 -m field_notes_audio sync
python3 -m field_notes_audio check
# Inspect new narration scripts before continuing.
python3 -m field_notes_audio make-all --jobs 3
npm ci --prefix video
python3 -m field_notes_audio release all --audio-jobs 2 --video-workers 4
```

`make-all` generates missing speech and captions using the saved Google project;
completed local work is reused. Its generation cache and Cloud operation journal
are not included in a fresh clone, so retain that original checkout. `release`
uses prepared media and makes no Cloud requests. It finishes sound, renders full
videos and prepares upload folders. It does not generate missing narration,
upload to YouTube or push Git changes. Separate conversation editions remain
explicitly configured extras.

## Find the upload material

Every completed episode has a stable folder such as
`artifacts/uploads/note-001/`:

| File | YouTube use |
| --- | --- |
| `episode.mp4` | Full video to upload |
| `title.txt` | Video title |
| `description.txt` | Summary, written-note link, AI narration disclosure, music credits and hashtags |
| `tags.txt` | Comma-separated keywords for Studio's Tags field |
| `hashtags.txt` | Visible hashtags, also included in the description |
| `thumbnail.png` | Episode thumbnail |
| `captions.srt`, `captions.vtt` | Retimed subtitles; choose English / With timing in Studio |
| `episode.mp3`, `transcript.txt` | Finished audio and recognized transcript |
| `upload.json` | Exact output hashes and review status |

The root folder contains `podcast-title.txt`, `podcast-description.txt`,
`podcast-cover.png` and `index.json` for show setup and episode inventory.
Open it from WSL:

```bash
explorer.exe "$(wslpath -w "$PWD/artifacts/uploads")"
```

Folders contain portable copies, so editing or moving them cannot corrupt
production caches. Warm exports verify and reuse unchanged folders. Metadata
updates reuse verified media inside the upload area without another encode or
large copy where hard links are supported; other filesystems fall back to copying.

## Edit titles, descriptions and tags

`audio/production/publishing.json` contains the shared studio tags and the
episode-specific tags for notes 001–011 and both configured extras. New notes
inherit the shared tags; add their actual topic tags in this file. An episode
can override `title`, `description`, `tags` and `hashtags`. These are publishing
fields: changing them does not change the spoken wording or video artwork.

To refresh completed upload folders without another production run:

```bash
python3 -m field_notes_audio export all
```

For editions produced before this feature, run `produce all` once to verify and
adopt render provenance; compatible MP3/MP4 files are reused. `release` does this
automatically. Exports require full videos. Previews and audio-only editions
cannot be substituted for full episodes. Invalid publishing copy and output
locations fail before `release` starts processing. A failed replacement restores
the previous upload folder and leaves completed production media available.

## Record listening review

Passing tests does not approve narration. Check pronunciation, full sentences,
captions, opening/ending and the finished video, then record the episode you
actually reviewed:

```bash
python3 -m field_notes_audio review note-001
python3 -m field_notes_audio review note-001 --approve --reviewer "Perttu"
python3 -m field_notes_audio export note-001
```

Use `review all --approve --reviewer "Perttu"` only after checking every selected
edition. Review records bind the person and timestamp to exact audio/caption
hashes and, when present, full-video hashes. Changed media needs fresh review;
publishing metadata edits alone do not invalidate media review. The reviewer name
is included in published provenance when finished audio is promoted.

Upload the MP4, thumbnail and subtitles to your existing YouTube podcast playlist.
Copy the title, description and tags into their respective Studio fields. Check
the upload privately before publishing. Use full episodes, and avoid importing
the same episodes through RSS as well as uploading the custom videos.

## Publish finished audio on the website and RSS

```bash
python3 -m field_notes_audio promote note-001
# Or, after reviewing every selected finished audio edition:
python3 -m field_notes_audio promote all

# Push prepared changes to a publication PR branch, then review/merge its PR:
python3 -m field_notes_audio publish
# After GitHub Pages deployment:
python3 -m field_notes_audio verify-live
```

Promotion updates content-addressed MP3s, actual duration, retimed subtitles,
timed transcripts, media manifest, article/queue defaults and RSS together.
Finished recordings start at 1×; untouched originals start at 1.15×. A listener's
manual speed choice takes precedence in a mixed queue. Episode GUIDs and original
publication dates are retained. Original recording assets remain available as
provenance. Future `produce` runs always finish the preserved source, avoiding
repeated pacing or music. Later `make-all` preparation preserves reviewed finished
public editions when their original speech source is unchanged.

All selected editions validate and require explicit audio review before any
public-file changes. Preparation failures restore the old manifest, HTML, RSS
and release journal, and remove newly copied assets. `promote` only prepares local
changes; `publish` is the separate push operation. Neither uploads to YouTube or
automatically merges a PR. Audio-only editions can be reviewed/promoted without
a video; YouTube export still requires a validated full video.
