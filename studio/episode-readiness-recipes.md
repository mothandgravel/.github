# One checked episode, one next action

This pass implements the first three priorities from [progress research](progress-ux-research.md):
an episode-level overview, preflight at Produce/Export, and named show recipes with
visible overrides. A combined review player/timecoded corrections, completion
notifications and grouped batch outcomes are **not implemented by this pass**.

## Episode readiness

Choose a prepared recording. The sidebar's **Episode readiness** card checks the
preserved recording, full saved edition, human approval and upload package. Its
one contextual primary action is based on that evidence, not the latest job label:

| Checked condition | Primary action |
| --- | --- |
| No full episode, or the current recipe differs from the saved edition | **Produce episode** |
| Matching full episode without full-video approval | **Review full episode** |
| Approved full episode without a current matching upload package | **Export updated package** |
| Saved publishing title/description/tags changed since export | **Export updated package**, not another media review |
| Package media, approval and saved upload copy match | **Open upload package** |
| An active, queued or waiting job already owns this episode | **Show current job** |
| Another local read/export owns a media lock | **Check readiness**, not unnecessary reproduction |
| Inputs or action prerequisites cannot be verified | **Inspect blockers** |

The overview carries the primary emphasis. Produce/Release retain secondary shortcuts;
the Release toolbar no longer presents a numbered sequence that implies an already
approved episode needs reviewing again.

The card distinguishes a valid *saved* edition from a changed *draft*. Recipe,
source, custom-music bytes, renderer inputs and artwork participate in the current
content comparison. The existing engines' media checks remain authoritative.
An old approval stays attached to its original bytes; it is not moved to a new
recipe. A preview or an audio-only job never counts as the full episode.

The timestamp identifies a checked local snapshot. **Check** refreshes it, including
after work in another terminal. Recipe changes invalidate the old contextual
action. The UI reads in the background on selection, explicit check, relevant job
state transitions, metadata save and recorded approval. It does not hash media on
every queue poll or silently fill any review confirmation. Late results after
selection or recipe changes cannot unlock the old action. Repeated checks coalesce.

Every write action still rechecks its own captured inputs. **Open upload package**
rechecks readiness before navigating; existing file-open/copy guards then verify
the selected package. Export is local and explicit. None of these states means
that YouTube, the website or the podcast feed has been published.

**Already produced/reviewed episodes do not need to be regenerated for this UI
change.** Matching approval leads to export or the current package. A different
draft is reported as different, never applied to existing media automatically.

## Preflight where it is needed

Produce's preflight result appears beside its controls. Export's result appears
above the Release tabs. Full diagnostics are available through **Inspect blockers**
or the production inspector rather than consuming the compact form's height.

**Produce episode** and **Inspect changes → Queue inspected output** check the
preserved source hashes and validated captured recipe. Video/preview actions check
the existing renderer's installed Node/dependency versions and local artwork.
Audio-only checks do not require the video renderer. Nothing is installed
and no service request is made by inspection.

**Export updated package** verifies the current full edition and its approval,
saved publishing copy and existing export destination. It does not require Node,
Remotion or a new render. Existing unexpected destination files block export rather
than being deleted. Export checks do not depend on an unfinished optional pace
control; they use the exact saved full edition. An unfinished draft can block the overview's
recipe comparison; the explicit Export path still checks the saved edition. As in
the existing CLI, export reads saved publishing metadata again when it executes.
Preparation, production and publication authorization remain separate.

Preflight reports local prerequisites, not free disk capacity, billing, Cloud
availability or future tool success. The worker still verifies its request and
handles failures; an earlier preflight is not a guarantee or a persistent grant.

## Named show recipes

Open **Audio → Show recipes / overrides…**. **Save current as…** captures the current
complete production settings under a plain-text name. This includes pace, intro,
outro, music/credit, loudness and video settings already present in the recipe.
Saved recipes are **local to this checkout's Studio journal**, not uploaded to a
registry or silently written over the checked-in show defaults.

Select a recipe to compare every setting with the current episode. **Apply to
episode** copies that recipe into this episode's draft only. The Audio tab names
the captured recipe and its override count; the recipe window displays full
before → after differences, which update as controls change. **Undo apply** restores
the previous production draft without discarding publication-copy edits made
since application. It is one-level, current-session undo, not a separate history
or a backup feature.

Applying does not queue a job, update other episodes, change the selected batch,
rewrite saved media or remove approvals. The next production action validates and
captures the episode's entire recipe. Existing batch inspection uses each
selected episode's own draft, including its copied recipe and overrides; this is
not a new bulk-apply feature.

**Update selected…** requires confirmation. Another window's intervening library
change blocks stale apply/save until **Reload recipes**. Existing episodes retain
their captured settings when a library recipe changes; reopening the manager
identifies the newer library version rather than adopting it silently. Distinct
names are case-insensitively unique. Invalid names/settings and missing custom
music block the relevant save/apply. Missing music in one stored recipe does not
prevent listing other recipes. The library is bounded to 100 recipes.

Recipes, captured references and unfinished overrides survive ordinary Studio
restart through `artifacts/studio/studio.sqlite3`. Keep that journal and the media
artifacts. Guided backup/restore remains deferred.

## Dependency and validation boundaries

- `readiness.py` adapts existing engine source, media, review, metadata and preflight
  checks. It returns immutable `readiness_models.py` values. Fingerprint parity tests
  keep its read-only content comparisons aligned with the existing engines without
  changing production implementation hashes for a UI addition.
- `episode_controls.py` coordinates generation-guarded background reads and user
  intent; `presentation/readiness.py` contains only the small card and callbacks.
- `recipes.py` uses optimistic journal transactions and validated setting snapshots;
  `presentation/recipes.py` contains the native selection/confirmation/diff surface.

Tests use real local FFmpeg and media/review/package verification for readiness,
plus actual Tk controls for navigation, preflight feedback, immutable recipe capture,
stale results, undo, cross-window library conflicts and compact visibility. Synthetic
fixtures and mocked Cloud boundaries do not establish a human review, live-service
success or external publication. No operator-machine files or receipts are edited.
