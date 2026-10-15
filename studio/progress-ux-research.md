# Progress that explains the next action

Research date: 16 October 2026. Baseline: PR #39 at `2aa83d12`.

The operator asked for more intuitive progress and icons on the audio, batch and
health tabs after the first live episode rehearsal. This continues the findings in
[episode-production-flow.md](episode-production-flow.md). It does not claim that
the operator has uploaded or published the episode.

## External research: documented product behavior

The sample covers established recording, editing, processing and hosting tools:
Riverside, Descript, Auphonic, Spotify for Creators, Buzzsprout and Adobe Audition.
It is a purposeful comparison, not a measured market-share ranking or a signed-in
usability test. Hosting tools are not interchangeable with production editors.
The following observations come from official help documentation; the adaptation
column is our design judgment, not a feature claimed by the source.

| Source and supported observation | Adaptation for this Studio |
| --- | --- |
| [Riverside: recording statuses](https://support.riverside.com/hc/en-us/articles/5457425335965-Recordings-status-guide) separates recording, uploading, processing and ready; individual tracks can be at different stages. | Show named milestones for the selected job, and retain saved stages when another stage fails. Do not use one ambiguous Working/Failed label for all its outputs. |
| [Riverside: upload completion](https://support.riverside.com/hc/en-us/articles/5460933431453-Has-my-recording-finished-uploading) describes an expandable upload status and, on mobile, a checklist that becomes recording-ready after uploading/processing. | Put Saved/Working/Waiting/Next beside each named phase. Our worker is detached: unlike Riverside's in-progress local upload instructions, closing this Studio window does not cancel the job. Do not copy their shutdown rules. |
| [Descript: web-link export](https://help.descript.com/hc/en-us/articles/10255817744653-Export-and-publish-content-with-Descript-web-links) identifies the destination, preserves the URL on Update, and explains that a download reflects the last export; unsynced files can block export with an explanation. | Keep current recipe, saved edition and exported package distinct. Display the next applicable action rather than making people infer which artifact is current. A future compact preflight should explain blockers at the primary action. |
| [Auphonic: presets](https://auphonic.com/help/web/preset.html) includes shared production settings and a Review before Publishing option; [batch production](https://auphonic.com/help/web/batch.html) applies an existing preset to multiple inputs with metadata overrides. | Preserve one full-episode action and one review. Next, consider named reusable production recipes with visible per-episode differences; keep batch scope explicit. Do not silently apply the currently selected episode's settings to other jobs. |
| [Spotify: video publishing](https://support.spotify.com/us/creators/article/publishing-videos/) separates Details, Content checks and publication timing, saves drafts, and reports transcoding completion separately. | Separate production success, human review, package readiness and real publication. Do not show a fake Publish/Schedule control without a publishing integration. |
| [Buzzsprout: processing](https://www.buzzsprout.com/help/36-processing-length) describes processing as a distinct stage and sends a completion email; [upload flow](https://www.buzzsprout.com/help/3-upload-audio) collects metadata and timing before saving. | A completion should become an actionable ready state. A later opt-in completion notification would be useful for long local jobs; notifications are not implemented in this pass. |
| [Adobe Audition: Match Loudness](https://helpx.adobe.com/audition/desktop/editing-audio-files/match-loudness.html) separates scanning from the settings and Run action. | Show audio readiness and analysis results beside controls rather than hiding them in the global Health report. Do not turn an analysis result into listening approval. |

## Implemented in this pass

A compact progress strip accompanies the selected queue job. Every marker combines
an original pictogram with a text state, so its meaning does not depend on color.
The normal full-episode view is:

**Audio + captions: Saved → Full video: Working → Save edition: Next**

Preparation uses **Narration → Captions → Save recording**. Audio-only, preview and
export jobs have their own scopes; an audio-only job never pretends a video was
rendered. A bounded caption wait is **Waiting**, not indefinitely Working, and its
next action remains **Resume** for the recorded operation.

The pure progress reducer reads only the job and journal stage identifiers. It
uses explicit `*-complete` events or that job's successful terminal result, not
provider prose, elapsed time or an assumption that reaching a later stage proves
an earlier one completed. Repeated narration-completion events do not inflate the
chunk count. The title counts only distinct chunk-completion events in the returned
job history; it is not a fresh media/cache scan. Unknown stages stay unverified.

The existing elapsed narration wait now also covers local audio/video/export stages
and the active caption stage. Detailed errors remain visible. No invented ETA,
overall percentage, completion forecast, remote-progress polling, decorative
spinner or new timer is introduced. Unequal phases are shown as milestones, not
thirds of elapsed work. Selecting a different job clears the previous strip before
its asynchronous evidence loads.

A successful preparation says **Produce episode next**. A successful full video
says **Review full episode once**, then export. If the currently checked full-video
approval matches that job's saved output directory, it instead says **already
reviewed; inspect/export next** without restoring any confirmation checkbox. A successful export directs the user
to check package files and upload manually. These are saved job milestones, not a
fresh integrity check or proof of review/publication; existing review/package
checks remain authoritative. Historical failed attempts are never rewritten as
successful or offered as new recovery instructions.

All workspace tabs now have labelled icons. **Sound** is labelled **Audio** with
headphones, **Batch** uses stacked checked sheets, and **Health** uses a diagnostic
pulse. Health's icon is navigation, not a claim that the machine is healthy. Icons
have selected-state contrast, scale with Tk and reuse the existing per-window cache;
there is no icon font, network asset or new runtime dependency.

Adding progress initially squeezed the Produce inspector at 1050×760. The layout
fix removes redundant folder shortcuts from that tab (files remain accessible
through Release and the job toolbar) and removes repeated output guidance. It does
not increase the minimum window size or shrink text. Compact tests require useful
inspector height as well as visible tab/queue controls.

## Follow-up implementation

The first three candidates below are implemented by the [episode readiness, inline
preflight and named-recipe follow-up](episode-readiness-recipes.md). The historical
progress pass described above did not include them. Combined review playback,
timecoded corrections, notifications and grouped batch outcomes remain deferred.

## Design candidates recorded by the progress pass

1. **One episode readiness overview.** Surface narrative/caption readiness, current
   full edition, approval and package identity on one episode card, with a single
   contextual action. Derive it from verified identities; do not use the latest job
   status alone to assert that old output is still current.
2. **Preflight at the action.** Show missing video dependencies, source errors and
   stale packages near Produce/Export, with direct routes to Health or repair.
   Avoid making every click trigger slow media hashing or automatic installation.
3. **Named show recipes and visible differences.** Reuse known audio/music/artwork
   settings and highlight per-episode overrides, with explicit batch application.
4. **Focused review player and timecoded fixes.** Prefer one playback surface for
   sound, video and captions, with a short list of timestamps needing correction.
   This is a larger media-player integration, not additional approval checkboxes.
5. **Optional completion notification and grouped batch outcomes.** Distinguish
   running, waiting for a person, ready for review and historical failure. Notify
   only on a real state transition; never claim upload success from an export.

## Acceptance and limits

Unit checks cover queued, running, waiting, safe-stop, interrupted, failed,
historical and successful jobs; duplicate chunk events; missing earlier events;
unknown stages; and the difference between preview, full video and export.
Native Tk checks exercise all seven icon-labelled tabs at minimum width, real
journal-to-progress updates, no implicit approval/publication, retained diagnostics,
useful inspector height, and image/timer reuse over repeated updates.

Fixture screenshots illustrate controlled test states. They are not screenshots
of the operator's machine or evidence of a new live production or publication.
This pass does not modify provider requests, receipts, cached media, consent rules,
production recipes, review identity or the one-action full-video contract.
