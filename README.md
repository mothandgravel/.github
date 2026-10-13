# Moth & Gravel

**Drawn to light. Built for rough ground.**

Independent software and useful tools. Strange things, built properly.

Visit [mothandgravel.com](https://mothandgravel.com/) to explore the studio and its Field Notes.

This repository contains the [website](docs/), the [GitHub organization profile](profile/README.md), and the [visual identity assets](profile/assets/). The site's source is public; private product work is not included here.

## Keeping the site useful

The site ships readable HTML, local artwork and small progressive enhancements. Its studio and Field Notes identities are generated from the published catalog; unpublished research stays out of that catalog. Publication stamps are absent from the reading surfaces, while RSS retains publication metadata.

Run `python3 scripts/build_notes.py` after changing the catalog or discovery generator, then `python3 scripts/build_notes.py --check`, `python3 scripts/check_site.py` and `node --test scripts/notes_model.test.mjs`. Browser CI checks both appearances, narrow layouts, navigation and no-JavaScript access.

The performance workflow compares the PR's immutable base and candidate with three cold Lighthouse loads per mobile/desktop profile. It keeps full reports and gates the candidate's median first contentful paint at 1,000 ms, largest contentful paint at 2,500 ms, blocking time at 200 ms and layout shift at 0.1. These are controlled lab budgets, not promises about every connection or a guarantee of enquiries, search ranking or AI recommendations. Deployed-host measurements are recorded separately and need another pass after publication.

For a local performance comparison, install the pinned tools from `.github/workflows/site-performance.yml`, serve the candidate and base on ports 8793 and 8794, and run `node scripts/audit_performance.mjs`. The reports are development artifacts; no measurement script or analytics is added to visitors' pages.
