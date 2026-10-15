# The last line leaves a question

## What the review exposed

The archive already had search, subjects, ordering, a recent stack and a listening edition. On a phone, reaching those different entrances required passing through the earlier material. At the end of a note, a prominent generic archive exit came before related titles that gave no account of their connection.

This pass concentrates on that reading journey. It changes the archive entrance and the endings of the thirteen published notes.

## Editorial decision

Each ending gives one next question its own paper surface and a short editorial bridge. Studio production leads into the meaning of a reassuring signal; the Coastal watch study leads into the unknown space on a robot’s map. The relation is deliberately chosen in the catalog rather than inferred from recency or clicks.

Other connections remain available beside that continuation, followed by the archive and working specimens. Coastal watch keeps its direct specimen return. The existing Field Note 005 route into the editorial thread also remains available. A separate, quieter invitation opens the question sheet with the reader’s own words.

The archive entrance offers ordinary links to the reading selection, search and listening section. The selection and search anchors support native keyboard focus. A failed catalog request still leaves the complete static archive. These changes add no browser JavaScript or images; their stylesheet is limited to the archive and written notes.

## Authorship and maintenance

`nextReading` contains an `id` from the note’s `related` list and a `bridge`. Existing relations, thread entries and superseding notes are deduplicated in the generated coda. Future notes can omit the optional choice: the first relation and its summary remain a working fallback. `specimen` preserves an optional direct return. The generator owns the existing `related-notes` slot, including the end marker and general exits.

All article bodies and listening blocks remain byte-for-byte identical to the sprint’s base revision. No public date, new recording, tracking or reading history is introduced.

## Verification

`scripts/audit_reading.mjs` reviews the entrance and two different endings at five widths and both appearances, checks accessibility with axe, follows all thirteen recommendations with the keyboard, and exercises URL-based archive restoration, specimen return, preservation of an existing question draft, no-script reading and catalog failure. Screenshots and measurements are CI artifacts.

The existing visual and editorial-thread audits cover the surrounding journey. The performance audit now includes the archive and Studio article, with three cold loads per mobile/desktop profile. They use the existing secondary-page budgets: FCP ≤1800 ms, LCP ≤2500 ms, TBT ≤200 ms, CLS ≤0.1, performance ≥90 and technical SEO ≥95. The homepage retains its 1000 ms FCP budget.

This is an authored design decision supported by layout and interaction checks. Reader comprehension and whether the chosen bridges prompt worthwhile further reading still need observation with people.

## Audit follow-up

The review found two authoring regressions beyond the currently published catalog. The browser audit assumed every note supplied the optional `nextReading` choice, and relationship deduplication consumed a revised study under general related reading before it could be labelled as a revisit.

The audit now uses the same navigation checks for current notes and generated authoring fixtures: no explicit choice, no relationships, a thread without a primary continuation, an overlapping revision/thread/relation, and a featured revision. An independent ending uses one column and keeps its general exits. A thread-only ending retains its heading hierarchy. Revisited studies retain their specific label, including when they are the primary continuation; thread relationships take precedence over general related reading.

The integrity check also enforces one reading stylesheet and one generated ending outside narrated prose, including nested article material. This catches new pages copied from older templates before a duplicate ending or unstyled coda can ship. The archive's stylesheet is checked as well.

Verification adds eight authoring-contract tests and ten browser fixture reviews. The expanded reading audit passes 313 assertions across 40 responsive/theme/fixture states. The fixture relationships remain test material and never enter the public catalog or narration.
