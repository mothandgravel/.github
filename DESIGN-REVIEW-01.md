# Moth & Gravel — Landing design sprint 01

**Date:** 12 October 2026  
**Stage:** Source-level audit and pre-TLS local-browser review. The canonical `mothandgravel.com` endpoint has not yet been independently inspected over HTTPS; certificate provisioning is outside this sprint.  
**Scope:** `mothandgravel/.github/docs`; the public site is still hosted as a GitHub Pages project site.

## Design brief

Make **Moth & Gravel** feel like an independent software studio with a tactile, nocturnal visual identity—not a generic productivity SaaS template and not only a T-shirt label.

The brand tension is intentional:

- **Moth:** nocturnal, curious, instinctive, drawn toward light.
- **Gravel:** rough, physical, unpolished, enduring.
- **Together:** strange things, built properly.

Primary audience: people discovering the maker/studio, collaborators, and prospective users of future tools. The site must communicate what the company does before visitors need to decode the brand symbolism.

## Divergent directions considered

| Design direction | Character | Strength | Liability | Decision |
| --- | --- | --- | --- | --- |
| A. Nocturnal specimen / editorial | Technical specimen, refined type, original moth/stone illustration | Memorable identity; clear visual hierarchy; supports software and apparel | Can feel abstract before products are public | **Continue and refine** |
| B. Brutalist developer terminal | Dense monospace, console motifs, ASCII ornament | Obvious development association | Too close to familiar developer brands; undermines surprising name | Reject as primary language |
| C. Full-bleed midnight fashion label | Photography, rich texture, dramatic motion | Strong apparel character | Slow/noisy; poor information scent for a software studio | Reserve for future capsule/merch pages |

**Convergence:** Keep direction A; retain one limited motion detail, restrained brass accents, a single typographic statement, and a recognizable moth mark. Do not add ornamental features without a navigational or communicative purpose.

## Findings, severity and action

| Priority | Finding | User impact | Resolution |
| --- | --- | --- | --- |
| P0 | Afterlight accent text on cream calculated ~2.9:1 contrast | Below WCAG AA for small text; theme becomes decorative rather than usable | Darken accent; use a separate contrasting CTA ink token; add ratio regression |
| P0 | Escape grabbed focus even when mobile menu was closed | Unexpected keyboard focus jumps | Only handle Escape while the menu is open |
| P1 | Header used textual `M✳G` rather than established icon | Weak identity continuity between GitHub, brand kit and site | Use cropped official moth SVG in masthead |
| P1 | Mobile navigation disappears entirely without JavaScript | Navigation dead end on progressive failure | Default nav visible; collapse only when JavaScript initializes |
| P1 | Hero's two CTAs were both internal jumps | Immediate absence of a tangible external next step | Keep internal exploration; change secondary CTA to actual organization |
| P1 | Menu did not close on outside click or breakpoint transition | Sticky open overlay after interaction | Close on pointer outside, Escape, selection, or desktop transition |
| P2 | Generic \"work\" cards describe themes, not public products | Makes studio feel less established | Explicitly wait until products are publishable; avoid fake case studies |
| P2 | System font fallback may change line breaks at 320/390/1024 widths | Brand typography could lose intended rhythm | Capture and review real rendered viewport screenshots |
| P2 | Social sharing currently lacks a raster Open Graph preview image | Uncontrolled previews on chat/social platforms | Add when final logo lockup is approved and HTTPS is active |

## Review acceptance criteria

- No horizontal scrolling at 320, 390, 768, 1024 or 1440 pixels.
- Theme toggle remains keyboard accessible and has a stable accessible name.
- Mobile menu is usable by touch, pointer, keyboard and without JS.
- Escape never steals focus from a closed menu.
- Text accent in both light/dark modes meets at least 4.5:1 for small text.
- The homepage's logo asset, primary CTA, nav anchors and local resources load.
- No nonessential third-party scripts, tracking, fabricated social proof, or listings of private products.
- Browser snapshots are saved for both themes and mobile-menu state on PRs; tests run against the code being reviewed, not TLS-dependent production.

## Sprint 01 verified results — 13 October 2026

**CI:** [Static validation](https://github.com/mothandgravel/.github/actions/runs/38310136241) and [browser design audit](https://github.com/mothandgravel/.github/actions/runs/38310136348) **both passed** after the final correction. Browser artifacts include both color themes, five viewport widths, mobile-menu state, and a JavaScript-disabled state.

| Verified behavior | Result |
| --- | --- |
| Viewport widths | 320, 390, 768, 1024, 1440 px |
| Horizontal overflow | None at the five tested widths |
| Headline | Three readable lines at all tested widths |
| Responsive work cards | 1 / 2 / 3 columns as designed |
| Brand assets | All browser images loaded |
| Mobile nav | Touch/keyboard, Escape focus, destination focus, no-JS fallback passed |
| WCAG axe sweep | No reported violations in night and Afterlight at tested desktop/phone widths |
| Computed work-card text contrast, night | 5.81–14.14:1 |
| Computed work-card text contrast, Afterlight | 5.15–12.41:1 |

**Original audit failure diagnosed:** The first audit ran axe on the same DOM before and immediately after switching themes, and axe reported stale *night-theme text values* against freshly updated light backgrounds. The Afterlight screenshot itself showed darker text. To eliminate this false positive **without weakening the accessibility gate**, the browser audit now reloads into the persisted Afterlight theme, performs a complete axe scan on the fresh document, and independently computes the foreground/background contrast of representative work-card text on **all five** viewports, requiring at least 4.5:1. This also tests that the theme preference survives a reload.

**Visual review:** Desktop hero, 390px Afterlight, 320px Night, mobile menu, and work-card regions were manually inspected from the successful browser-run screenshots. The moth/stone illustration remains legible, mobile headlines and cards do not clip, and navigation states are recognizable. These screenshots are local CI renders, **not** proof of production HTTPS behavior.

**Remaining production gate:** Inspect the deployed `https://mothandgravel.com/` and `www` redirect after TLS provisioning, then collect Lighthouse metrics on the live endpoint. DNS, Pages settings, private products, and a nonexistent contact mailbox were deliberately left unchanged.

## Next sprint after TLS

1. Inspect the **actual canonical HTTPS site**, the `www` redirect and real mobile viewport behavior.
2. Visually review screenshots side by side, not only automated assertions: type wrapping, proportion, image dominance, whitespace and surface contrast.
3. Run axe-core / Lighthouse with measured contrast, accessibility, LCP, CLS and network payload (no scores asserted yet).
4. Test page comprehension: 5-second brand/category read; whether users can find a real studio activity and contact route.
5. Once a public product or actual contact address exists, replace abstract work cards with concrete outcomes instead of inventing projects.

## Out of scope

Domain records, GitHub Pages SSL provisioning, private repository disclosures/transfers, external API integration, new illustration generation, merch storefront, and a contact form with no backend.

This is a **reviewable design iteration**, not a claim that a live production visual review has passed.
