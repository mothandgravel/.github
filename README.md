# Moth & Gravel

**Drawn to light. Built for rough ground.**

Independent software and useful tools. Strange things, built properly.

Visit [mothandgravel.com](https://mothandgravel.com/) to explore the studio and its Field Notes.

This repository contains the [website](docs/), the [GitHub organization profile](profile/README.md), and the [visual identity assets](profile/assets/). The site's source is public; private product work is not included here.

The [Field Notes audio workflow](audio/README.md) covers every published note, a brisker comparison and a two-voice conversation. `python3 scripts/field_audio.py make-all --publish` reuses or generates recordings, subtitles them, builds article listening controls and an archive queue, and pushes completed assets to a PR. Web playback defaults to 1.15×. The separate podcast feed is `notes/podcast.xml`; article RSS stays available. Google settings and job state remain local, and CI validates with synthetic clips without paid requests.

## Keeping the site useful

The site ships readable HTML, local artwork and small progressive enhancements. The homepage includes its relevant styles in the initial response, generated from the authored `docs/assets/site.css`; article-only styles remain in the external stylesheet. Its studio and Field Notes identities are generated from the published catalog; unpublished research stays out of that catalog. Publication stamps are absent from the reading surfaces, while RSS retains publication metadata.

Run `python3 scripts/build_notes.py` after changing the catalog or discovery generator, then `python3 scripts/build_notes.py --check`, `python3 scripts/check_site.py` and `node --test scripts/notes_model.test.mjs`. Browser CI checks both appearances, narrow layouts, navigation and no-JavaScript access.

The performance workflow compares the PR's immutable base and candidate with three cold Lighthouse loads per mobile/desktop profile. It keeps full reports and gates the candidate's median first contentful paint at 1,000 ms, largest contentful paint at 2,500 ms, blocking time at 200 ms and layout shift at 0.1. These are controlled lab budgets, not promises about every connection or a guarantee of enquiries, search ranking or AI recommendations. Deployed-host measurements are recorded separately and need another pass after publication.

For a local performance comparison, install the pinned tools from `.github/workflows/site-performance.yml`, serve the candidate and base on ports 8793 and 8794, and run `node scripts/audit_performance.mjs`. The reports are development artifacts; no measurement script or analytics is added to visitors' pages.

## From a loose end to shared work

The [question sheet](docs/questions/index.html) helps visitors make an editable brief they can keep. Timing, budget and existing material are separate optional disclosures; unanswered ones stay out of the brief. It sends no enquiry. An explicit action carries a bounded draft in the same browser tab to the [example workbench](docs/workbench/index.html), where fictional sketches let visitors compare approaches, pin an observation and record a local draft choice. The public GitHub conversation remains the actual contact route until a verified private route is configured.

Run `node --test scripts/loose_end_model.test.mjs` for backward-compatible drafts and the complete brief capacity. Run `node scripts/audit_loose_end.mjs` against the same local server for the complete journey, responsive/accessibility checks, downloads, return/reload, cancellation, clearing and blocked-script/storage paths. The browser workflow runs it alongside the existing landing audit. See the [design and private-pilot handoff](docs/design/loose-end-workbench.md) for the prototype boundary and the work required before real client access.
