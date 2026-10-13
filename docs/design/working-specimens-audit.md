# Working specimens / audit of #23

Reviewed #23 at head `76cd38a79e0fbbac7d0069bc0ec9bff3ab4d9764`, tree `31b52e58a6a625a73632536ae774ea5198cd8eda`. The same tree was squash-merged as `611f88749d6cacf95bfc15865a4a96191c7a6980` before this audit; fixes belong to the follow-up branch. No review threads were outstanding.

## Findings and corrections

- **P2 / focus moved the reading surface.** The previous `.work-card:focus-within` lift survived the new hover override. Keyboard focus moved the heading and disclosure control four pixels. Override both hover and focus transforms; assert heading/control geometry after focus and give native disclosures an explicit focus outline. A direct browser reproduction now shows stationary text/control, `transform:none` and a visible outline.
- **P3 / anchor description disagreed with the graphic.** The SVG described gold dots; the rendered anchors are dark with bone outlines. Correct the description and record the new asset hash.

Window focus loss now also settles handled material. The browser audit adds pointer-cancellation, offscreen reset, blur and pagehide cleanup checks. Blur/pagehide are dispatched lifecycle-handler checks in the headless harness; they do not claim observation of every browser/OS focus or back-forward-cache implementation. Reduced-motion changes and coarse-pointer behaviour remain covered.

## Evidence and boundaries

The independent reviewer checked expanded records at widths 320, 390, 660, 661, 900, 1100, 1101, 1199 and 1440, with no clipped text or overflow. Every computed property of the specimen descendants matched the full authored stylesheet. Regeneration and static integrity passed.

The reviewer independently recompiled the unmodified SkyStack headers and reproduced all four recorded footprints, bounds and duplicate results, with source and harness hashes matching provenance. Kitronik’s existing render/hash/provenance and source-state distinctions agree. The primary reviewer re-read the full pinned Ajo conformance record: the selected OCaml lost-query stages are outcome unknown → succeeded, dispatches 1 → 2, original attempts 1 → 1, receiver applications 1 → 1, requests 1 → 1, phases start → start/query. This verifies the selected historical record, not a new deployed recovery run.

No additional verified runtime or evidence defect was found in the reviewed scope. The prior CI passed static, browser/journey and cold-load checks; the follow-up repeats required checks after corrections. Source scope stays visible, and organisation identifiers/source revisions remain in provenance rather than reading copy. No employer or visitor-management material is introduced. Human comprehension, credibility and conversion observations remain unperformed.
