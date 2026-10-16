# Moth & Gravel

**Drawn to light. Built for rough ground.**

Independent software and useful tools. Strange things, built properly.

Visit [mothandgravel.com](https://mothandgravel.com/) to explore the studio and its Field Notes.

This repository contains the [website](docs/), the [GitHub organization profile](profile/README.md), and the [visual identity assets](profile/assets/). The site's source is public; private product work is not included here.

The [Field Notes audio workflow](audio/README.md) covers every published note, a brisker comparison and a two-voice conversation. `python3 -m field_notes_audio make-all --publish` reuses or generates recordings, subtitles them, builds article listening controls and an archive queue, and pushes completed assets to a PR. Web playback defaults to 1.15×. The separate podcast feed is `notes/podcast.xml`; article RSS stays available. Google settings and job state remain local, and CI validates with synthetic clips without paid requests.

The [local production studio](studio/README.md) opens with `python3 -m field_notes_studio`
in Ubuntu/WSL. Its Tkinter workspace restores unfinished drafts, edits sound and publishing
copy, inspects individual or batch plans, and reconnects to durable production jobs.
[Field Note 013](docs/notes/013-work-outlives-the-window.html) follows the experiment
from a pipeline to a usable desktop workbench.

## Keeping the site useful

The [automated production stage](audio/production/README.md) adds reusable intro/outro music,
finished pacing, retimed subtitles and animated YouTube editions from existing narration.
`python3 -m field_notes_audio release all` uses local FFmpeg and a pinned Remotion
template and creates portable upload folders in `artifacts/uploads/<episode>/`, with full
videos, thumbnails, title/description/tag files and subtitles. Existing media is reused;
`export all` refreshes publishing copy without rendering. Topic tags are editable in
`audio/production/publishing.json`. The [ongoing release workflow](audio/production/PUBLISHING.md)
records listening review and prepares finished website/RSS editions through `promote`.
Finished editions default to 1× alongside originals at 1.15×. Local production makes
no Cloud requests; pushing a publication PR and uploading to YouTube remain separate steps.

The site ships readable HTML, local artwork and small progressive enhancements. The homepage includes its relevant styles in the initial response, generated from the authored `docs/assets/site.css`; article-only styles remain in the external stylesheet. Its studio and Field Notes identities are generated from the published catalog; unpublished research stays out of that catalog. Publication stamps are absent from the reading surfaces, while RSS retains publication metadata.

Run `python3 scripts/build_notes.py` after changing the catalog or discovery generator, then `python3 scripts/build_notes.py --check`, `python3 scripts/reading_output.test.py`, `python3 scripts/check_site.py` and `node --test scripts/notes_model.test.mjs`. Browser CI checks both appearances, narrow layouts, navigation and no-JavaScript access.

Field Note endings are generated inside `related-notes` slots. In `docs/assets/notes.json`, `nextReading` chooses a published `related` note by `id` and supplies a short `bridge` explaining the connection. Write that bridge for the question the reader has just encountered. Without this optional field, the first related note and its summary provide a usable continuation; independent notes retain the archive, specimens and enquiry exits. Related, thread and revisited links are deduplicated while preserving the most specific relationship. An optional `specimen` object (`href`, `label`) retains a direct return to a working specimen. Include `assets/reading-room.css` on new note pages; keep the ending outside the article so narration remains tied to the written study. Site validation rejects a missing stylesheet, a separate legacy ending or a coda inside narrated prose.

The performance workflow compares the PR's immutable base and candidate with three cold Lighthouse loads per mobile/desktop profile. It keeps full reports and gates the candidate's median first contentful paint at 1,000 ms, largest contentful paint at 2,500 ms, blocking time at 200 ms and layout shift at 0.1. These are controlled lab budgets, not promises about every connection or a guarantee of enquiries, search ranking or AI recommendations. Deployed-host measurements are recorded separately and need another pass after publication.

For a local performance comparison, install the pinned tools from `.github/workflows/site-performance.yml`, serve the candidate and base on ports 8793 and 8794, and run `node scripts/audit_performance.mjs`. The reports are development artifacts; no measurement script or analytics is added to visitors' pages.

## From a loose end to shared work

The [question sheet](docs/questions/index.html) helps visitors make an editable brief they can keep. Timing, budget and existing material are separate optional disclosures; unanswered ones stay out of the brief. Its final step, Send to Moth & Gravel, opens the visitor's own mail app with a prefilled message to hello@mothandgravel.com (the body is bounded at 1,800 characters, with Copy and Download keeping the full text); the page itself sends nothing. An explicit action carries a bounded draft in the same browser tab to the [example workbench](docs/workbench/index.html), where fictional sketches let visitors compare approaches, pin an observation and record a local draft choice. Every page shows hello@mothandgravel.com as a plain mailto link with a copy aid; the public GitHub conversation remains a tertiary route.

Run `node --test scripts/loose_end_model.test.mjs` for backward-compatible drafts and the complete brief capacity. Run `node scripts/audit_loose_end.mjs` against the same local server for the complete journey, responsive/accessibility checks, downloads, return/reload, cancellation, clearing and blocked-script/storage paths. The browser workflow runs it alongside the existing landing audit. See the [design and private-pilot handoff](design/loose-end-workbench.md) for the prototype boundary and the work required before real client access.

