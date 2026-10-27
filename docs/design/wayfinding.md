# Studio wayfinding

`/specimens/` is the collection for the nine established specimen identities.
Seven have standalone family pages; Ajo and SkyStack remain homepage exhibits.
The five additional rooms belong to their parent specimens. TNT is inside 009.
The one published thread is named directly in the menu; there is no Threads archive.

The Field notes index leads with the featured writing and its existing specimen
relationship, then introduces two other specimen families. The complete archive
and listening edition keep their direct fragment routes. Search results and
the static fallback retain the same labelled specimen links. An investigation
link, such as note 015's, is not relabelled as a specimen.

## Authoring

- `assets/specimens.json` holds identities, destinations, descriptions, existing
  imagery and evidence captions. Preserve the distinction between a software
  capture, an illustration, a simulator record and measured observations.
- `assets/wayfinding.json` holds four peer menu routes, exactly three shortcuts
  and the studio utility routes. Listening episodes and published notes are
  different catalogues; a count from one must not describe the other.
- Published notes supply related-note links through their existing `specimen`
  relationship in `assets/notes.json`.
- `build_notes.py` resolves those relationships against `assets/specimens.json`
  for the Field notes index. The browser uses the same identities and destinations.
  Paired introductions select the latest linked note from two distinct families
  other than the featured family. Existing evidence captions accompany captures.
  If either catalogue fails, the complete authored archive remains available.
- `scripts/build_wayfinding.py` generates bounded masthead, footer, collection,
  parent and related-reading slots. It validates destinations and fragments.

Run `python3 scripts/build_notes.py` after changes. The same command with
`--check` detects drift, including the homepage's derived critical stylesheet
and discovery metadata. Run `python3 scripts/wayfinding_output.test.py` for
destination checks at every depth, including an unknown nested 404 address.

## Interaction and materials

The menu is a native, nonmodal disclosure. Its links exist in the first HTML
response and work when scripts are absent or fail. With enhancement, keyboard
activation moves focus to the first route. Pointer activation retains the
trigger. Escape and backward Tab from the first route return to the trigger;
forward focus leaving the sheet dismisses it without taking focus back.

All four numbered routes share one responsive type rule. The longer thread
title wraps within that rule. Persistent Specimens and Field notes links stay
outside the menu, including in a second masthead row on phones. Header space is
reserved before enhancement; there is no `nav-pending` layout variant.

Ancestor collection links use `aria-current="location"`; a collection's own
index uses `page`. Case content and custom footer palettes remain in their own
stylesheets. Only the permanently dark standard footer receives dark palette
overrides. Diagrams retain their original dark plates and remain fully visible.

## Verification

`audit_wayfinding.mjs` covers five widths in both themes, matching menu type,
keyboard entry and dismissal, native and failed-script routes, 320px captures,
and accessibility on the collection and deep specimen pages. Existing reading,
audio, specimen, workbench and cold-load suites remain required. The browser
workflow collects every audit result before returning failure; no performance
or accessibility thresholds are relaxed.

Claude Fable 5.1 reviewed the implementation and a second frozen correction
packet, accepting the corrections at `4b4663c` with runtime and visual limits.
Browser checks and owner visual inspection are independent evidence; a model
review does not establish unfamiliar-reader comprehension.
