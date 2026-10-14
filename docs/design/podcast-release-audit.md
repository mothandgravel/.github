# Podcast release audit — PR #30

The audit starts from `ec1449f` and covers source/edition identity, upload copy,
review records, publication, collection locking, failure recovery and browser
playback. It reproduced failures rather than treating the original green CI as
proof of complete coverage. No real recording was approved, promoted, uploaded
or sent to a paid provider during this audit.

## Findings and fixes

| Finding | Reproduction / impact | Fix and evidence |
| --- | --- | --- |
| Upload reuse trusted the upload manifest's own hashes and did not compare its review fields | Editing `title.txt` and updating its saved hash left the wrong title in a successful export. A cached manifest could also claim an unearned approval or wrong playback rate. | Reuse compares authoritative production hashes, current publishing text and the entire expected upload manifest. Regression verifies repaired text and review/rate fields. |
| Folder replacement discarded unrelated user files | Adding `keep-me.txt` and changing an episode title silently deleted that file. Symlinks could remain in ostensibly portable outputs. | Preflight rejects unexpected files, symlinks and non-directory destinations before updates. Publication updates only explicitly owned files; tests preserve the unrelated file and symlink. |
| Inventory validation happened after package replacement | Malformed `index.json` could fail after replacing completed folders and show copy. | Inventory schema, IDs, duplicates, titles and folder mapping validate before changes. Upload files, show metadata and inventory share one transaction. |
| In-memory rollback did not survive abrupt process termination | Exception tests could not establish recovery after a process exits without running cleanup. | Write-ahead journals retain original bytes and every authorized intermediate hash. Real subprocesses use `os._exit(19)` between writes and before cleanup. The next locked command restores an incomplete release; a committed release remains intact. Later user edits or damaged backups stop recovery instead of being overwritten. Temporary data stays outside public docs. |
| Re-preparing original narration dropped retained finished assets from the publication journal | `promote`, then `prepare_publication`, preserved the manifest but omitted the finished MP3/captions from `release.json`; subsequent publication could reject those generated files. The finished-release classification was also lost. | Retained referenced assets are included in the journal and finished classification survives. Changed original caption hashes now invalidate preservation and require a new finished review. Tests cover both transitions. |
| Audio promotion depended on an unused video | Deleting a full MP4 blocked promotion of otherwise approved audio. | Promotion validates sound/captions independently. `review --audio-only` explicitly reviews sound without approving a video. YouTube export still requires a validated full video. |
| Export/review relied on saved MP3 duration and incomplete video facts | A shortened MP3 with an updated saved hash could pass export. A video's actual frame rate was not compared with render metadata. | Native inspection checks actual MP3 duration and MP4 duration, H.264/AAC streams, dimensions and frame rate. Tests use shortened media and contradictory render metadata; malformed state becomes an actionable validation error. |
| Description bounds counted characters rather than UTF-8 bytes; show titles lacked equivalent validation | A 2,000-character CJK description exceeded YouTube's byte limit while satisfying the old character guard. | Descriptions obey 5,000 UTF-8 bytes, including the exported trailing newline. Show/episode titles are single plain-text lines. Tag accounting includes commas and multiword quotes. One validated metadata snapshot is used per command. |
| Published review timestamps were not validated | A finished public manifest could contain an invalid review date while passing media checks. | Published review records require a parseable timestamp with a timezone, in addition to their media/hash bindings. |

## Validation

Focused tests cover the reproduced failures, abrupt exit and recovery, repeated
updates to one file, a crash after the commit marker, later edits, forged journal
paths, interrupted replacement, source-caption changes, metadata-only reuse and
original/finished publication transitions. The existing tests continue to cover
previews, legacy render adoption, stale source/media, approval identity,
content-addressed assets and source-preserving production.

The contributor gate runs the whole Python suite, Ruff, original script/source
checks and actual published-media validation. Browser checks cover original and
mixed 1×/1.15× collections, native/custom speed persistence, transcript seeking,
queue boundaries, narrow layouts, both themes and no-JavaScript access. Hosted
production finishes all 13 recordings and checks every title, artwork, thumbnail
and caption page. Current check results and source revision are recorded in the
PR description.

Audio/renderer identity files remain unchanged from #28. Publishing metadata and
transaction changes do not require another synthesis, transcription, encode or
render. Unchanged output files keep their timestamps; metadata edits leave large
MP3/MP4 files in place. Original collection publication now streams MP3 hashes
and copies instead of retaining the whole archive's recordings in memory.

The recovery evidence concerns abrupt process termination on the supported
Linux/WSL filesystem. It is not a claim about every storage system or power-loss
scenario. Human pronunciation/listening review and actual YouTube publication
remain separate from these automated checks.

References: [YouTube video metadata limits](https://developers.google.com/youtube/v3/docs/videos),
[release workflow](../../audio/production/PUBLISHING.md).
