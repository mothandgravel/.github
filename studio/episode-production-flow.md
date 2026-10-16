# One episode, not an audio/video checklist

## Operator observations after preparation succeeded

Note 013's reported live preparation completed on 2026-10-15 at 20:47:01 UTC.
The supplied history shows chunks 1 and 2 reused, chunk 3 saved after about 86
seconds, captions saved and a private recording returned. This is user-supplied
execution evidence, not an independent read of the operator's machine.

The next interactions exposed three additional product problems:

| Observation | Correction |
| --- | --- |
| Produce episode appeared to do nothing; the operator ran audio and video separately. | The button now validates and queues a single full-episode job. It shows checking, queue acknowledgement, errors and the job selection. The underlying video job includes audio, retimed captions, full video and thumbnail. |
| The operator reviewed audio and video separately. | Full-episode review is the default. One explicit watch-and-listen confirmation plus a subtitle check allows one approval for all media. Audio-only review is an alternative. An optional recheck of identical audio cannot remove an existing fuller approval. |
| Publication link/date appeared to need data the application should already know. | Generated upload copy includes the written-note link. Published destination is explicitly separate: an actual platform URL and release date, not the article URL or production completion time. Existing feed details and saved drafts remain intact; Use today is explicit. |
| Old failed narration rows continued to count as current attention after success. | Earlier failures covered by a later success are labelled historical, excluded from current attention and do not offer retry. Their original events and errors are retained. A newer failure is still actionable. |

## Action contract

**Produce episode** acts on the chosen prepared recording and its own current
recipe, including unsaved pace, outro and sound values. It does not borrow controls
from a different episode. A stale asynchronous inspection or failed settings read
queues nothing and explains the problem. Duplicate clicks are suppressed while
loading/planning/queueing; the repository also prevents duplicate active jobs
across windows. Subsequent edits cannot change the captured queued recipe.

This local production action does not issue narration requests, approve output,
export automatically, or publish. Preparation remains the explicit, separately
consented Cloud stage. **Open in production** is intentionally navigation only;
its label differs from the action **Produce episode**.

For the complete episode the intended path is:

**Produce episode → Review full episode once → inspect/export package → upload → record destination.**

Full review confirms watching AND listening through one labelled user action;
subtitle confirmation remains separate. Loading a snapshot, changing scope,
switching episodes or closing never restores review confirmations. A preview is
not a full video. Approval continues to recheck the exact saved media under its
production lock. Existing completed editions need not be regenerated merely to
adopt these UI improvements.

The optional inspected output selector is retained for audio-only editions,
previews and exports. Those are alternatives, not mandatory audio-then-video
steps. A full video job reuses an existing matching audio edition where valid.

## Previously delivered diagnostics

The pending [502 diagnostic correction](narration-502-incident.md) is included in
this change: bounded readable provider text instead of CSS, attempt/receipt
identity, historical job labels and refresh of an already-open preparation window.
That fixes diagnostics, not the provider's upstream 502. No timeout, voice, script,
chunk boundary, credential, bucket, receipt or remote retry policy changes here.
The diagnostic incident note describes an earlier point in the rehearsal; the
successful preparation reported above supersedes its pending-narration status.

## Validation and boundaries

Regression tests exercise actual Tk buttons and SQLite jobs: full-production
queueing, recipe capture, duplicate/stale actions, cross-episode loading, combined
review, generated written links, explicit date selection, draft preservation and
historical attention. Real local-media tests verify that one full approval covers
audio and video and an audio-only recheck does not downgrade it. Small-window
checks test natural widths and unobscured controls, with labelled fixture captures.

No tests authorize real Cloud calls or record a real human media approval. The
operator reports that the separate audio/video actions worked and both were
reviewed; that does not establish export, website/feed release or platform upload.
