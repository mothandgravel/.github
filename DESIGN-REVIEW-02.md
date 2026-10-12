# Moth & Gravel — Design Sprint 02

**Theme:** From brand to studio  
**Date:** 13 October 2026  
**Repository:** `mothandgravel/.github` / GitHub Pages `docs/`  
**State:** Reviewable implementation; browser evidence and final acceptance must be recorded before merging.

## Problem

The initial landing establishes personality, but visitors arrive at three abstract themes—software, experiments and objects—without any visible examples of actual public work. Its most prominent destination is the GitHub organization overview, which cannot yet support a portfolio claim. Social shares have no consistent branded image.

The goal is not to simulate a full software studio. It is to make the current work intelligible **without publishing private products or inventing customers, awards, launch dates, collaborators or a contact mailbox**.

## Discovery and divergence

| Direction | Five-second reading | Benefit | Liability | Decision |
| --- | --- | --- | --- | --- |
| **A. Open Workbench / Field Notes** | Independent software studio with a public record of making | Three real destinations and a credible growing story | Early public work is still mostly about the studio itself | **Use now. Say so plainly.** |
| B. Conventional SaaS portfolio | Lots of product tiles, metrics, fake case studies | Familiar information scent | Would overclaim public products and lose brand personality | Reject until real product releases |
| C. Cinematic after-dark showroom | Large animated moth, no text until scroll | Dramatic brand-first launch | Doesn't answer what the studio does; slower on mobile | Reject; keep restrained specimen visual |

**Convergence:** Preserve the nocturnal specimen aesthetic. Replace abstractions with proof, use one public field note to explain decisions, and reserve future product slots without empty calls to action.

## Implemented content and behavior

1. **Positioning first:** Hero says that the studio designs and builds independent software and useful tools.
2. **A real workbench:** Three labeled, actionable items: this site's public source, Field Note 001, and the brand marks. Each points to an existing asset or a new actual page.
3. **Clear public/private boundary:** Early-days status explains why the website doesn't advertise unreleased software yet.
4. **Field Notes:** A readable second page, `/notes/001-curiosity-with-calluses.html`, with a canonical URL, accessible landmarks and working route back. No invented founding history.
5. **Social:** Branded 1200×630 PNG with the known moth/stone mark and exact name; homepage and field note have Open Graph and Twitter large-card metadata.
6. **Useful micro-interactions:** Workbench links visibly respond to hover **and keyboard focus**; focus-within outlines the whole card. No JavaScript-driven visual theater, no new external dependencies and reduced-motion preferences remain respected.
7. **Search presence:** The note is included in `sitemap.xml`; robots rules stay unchanged.

## What we're explicitly not shipping

- Public product claims about Decision Docket, Ajo or unreleased repositories.
- Contact form or `hello@` address until mailbox delivery exists.
- Analytics, cookies, third-party font services, embedded videos or heavy JS.
- A newsletter sign-up without a mailing list.
- DNS, registrar, TLS, GitHub Pages settings, or the existing homepage's deployment while the PR is in review.
- An invented establishment date or unsupported company credentials.

## Design critique

| Finding | Severity | Response / evidence |
| --- | --- | --- |
| Work cards have no destination | P0 | Replace with source, field note, and mark links; verify each destination |
| Software studio category is vague | P0 | Name independent software explicitly above the fold |
| No genuinely useful content to return to | P1 | Publish the first concise Field Note, rather than a pretend blog archive |
| Social previews render inconsistently | P1 | Commit PNG; validate magic bytes, dimensions and meta tags |
| Hover-only card affordance | P1 | Keyboard focus gets the same link/card feedback |
| Long note could overflow or become illegible on phone | P1 | Dedicated reading widths, typography, focus/contrast and mobile browser screenshots |
| Absence of real released product case studies | P2 | Describe the workbench status honestly; revisit when public material is available |
| Decorative moon/engraving distracts from task | P2 | No new site-wide glow, particle layers, pointers or animations |

## Quality gate — run in the PR

- [ ] `python3 scripts/check_site.py` succeeds and checks both HTML pages, real PNG, links and sitemap.
- [ ] `node --check docs/assets/site.js` and syntax check of design audit succeed.
- [ ] Desktop/phone screenshots in both Night and Afterlight, plus 320 px narrow-phone screens.
- [ ] Homepage nav, note back link and three workbench links are usable.
- [ ] No horizontal overflow or clipped titles on 320, 390, 768, 1024, 1440.
- [ ] Axe WCAG 2A, 2AA, 2.1AA, 2.2AA sees no violations on homepage and Field Note (1440 and 390).
- [ ] Dark/light theme persists on both pages after reload.
- [ ] No-JS homepage navigation remains available.
- [ ] Reduced motion does not hide content or strand focus.
- [ ] Actual production checks wait until TLS is stable; do not claim Lighthouse/INP scores from local CI.

## Review after HTTPS

Verify `https://mothandgravel.com/` and `https://www.mothandgravel.com/` response, canonical redirects, certificate, live Open Graph scraper result, mobile tap targets and network performance. Record measured Lighthouse and accessibility results rather than assuming CI screenshots equal production.

**Exit:** Maintain the current public site until the new branch passes the design and CI gates and the PR is consciously merged.
