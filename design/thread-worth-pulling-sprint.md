# A thread worth pulling / 01

## The missing connection

The studio has working specimens and an expanding archive. Its automatic recent-writing selection currently concentrates on SkyStack. Someone arriving with a difficulty needs a route by the question they recognise, as well as by project, topic or recency.

This sprint makes one complete editorial route: **Something happened. I can’t tell what.** It joins the LiveConnect measurement study, Ajo’s recorded lost-reply case and Field Note 005’s question of reassuring signals. The homepage and archive introduce it independently of the generated latest-note selection.

## Reading and handling

- The three paper labels form a native navigation map. Their illustrations are original code-native SVG drawings, explicitly editorial. A brass connection briefly darkens on hover or keyboard focus with a fine pointer; reduced motion and coarse pointers receive a still drawing. Reading, labels and hit areas never move.
- Each stop states what is being kept separate, connects that distinction to a possible next action and offers the original material. The full argument also reads continuously without opening those materials.
- The LiveConnect page returns to the Ajo stop; the homepage’s Ajo card returns to the signal stop; note 005 returns to the visitor’s own question. These routes are visible to every reader, without visited-state tracking or a dependency on browser Back.
- The ending asks for one actual moment and links to the existing question sheet. The fragment `#signals-context` reveals optional prompts in initial HTML through CSS `:target`. No thread script, query parsing, auto-filled answer, storage record or inferred diagnosis is introduced. Following the writing link hides the introductory prompt; browser Back restores it.
- Existing answers, edited briefs and workbench observations remain under the existing journey’s controls. The prompts are not included in brief generation or download. A plain visit to `/questions/` retains its usual introduction.
- The workbench preview and private Resend enquiry remain separate. This route prepares words and does not send an enquiry.

## Evidence boundaries

The route reuses published material; it introduces no new replay, telemetry, user result or production claim.

- LiveConnect: [source custody and authored fixtures](connection-study-provenance.json). The source-based helper distinguishes measurement freshness; the connection is an independent fixed fixture. Eighteen seconds is stale under this selected helper’s rule. A current sample does not establish picture usefulness.
- Ajo: [selected recorded simulator stages](working-specimens-provenance.json), artifact `ajo`. One original-operation attempt and one receiver application remain after the result query; dispatches increase from one to two. This is a saved controlled case, not a fresh agent run or a general recovery guarantee.
- Wider signals: [Field Note 005](../docs/notes/005-green-light.html). Its narrated article body, catalog identity and audio fingerprints remain unchanged; the new return route sits outside `article.note-prose`.

## Verification

`scripts/audit_thread.mjs` follows the complete route and checks native keyboard navigation, the inspection-clock detour, Ajo’s record, note continuation, the final prompt and literal brief download. It examines five widths in both themes, no JavaScript, failed scripts and denied storage. An existing edited draft and local workbench observation must survive the detour byte for byte; visitor material must never be requested or submitted.

Local verification passed: 266 thread assertions across 18 review states; the existing loose-end/workbench audit passed all 78 checks; all eight affected archive and brief model tests passed. Both themes were visually reviewed at desktop and narrow mobile widths. The thread’s script-free mobile masthead uses an in-flow index so it cannot cover the opening.

The standard site check validates the thread’s local destinations and fragments, sitemap and generated identity graph. `build_notes.py --check` also protects narrated-note consistency. The design workflow retains screenshots and measurements as CI artifacts. The performance workflow measures the thread independently with the existing secondary-page budgets: median FCP ≤1800 ms, LCP ≤2500 ms, TBT ≤200 ms and CLS ≤0.1. The homepage keeps its existing 1000 ms FCP budget.

## What this sprint cannot establish

Automated checks establish reading and interaction access, not whether the route makes a potential client recognise their own problem. The next human trial should ask someone to find a familiar difficulty, follow one piece of evidence and describe what they would bring to the studio. Observe where they hesitate, whether they confuse a study with a shipped client result, and whether the ending gives them a concrete beginning. No conversion or comprehension result is claimed here.


## PR 35 review

The follow-up audit corrected two editorial ambiguities before approval:

| Gap | Correction | Why it matters |
| --- | --- | --- |
| “How old is the view?” could imply frame age was measured. | “How old is the reading?” | The helper measures the sample’s freshness; picture usefulness remains open. |
| “No reply. No action.” could be scanned as a verdict. | “The action. Its reply.” plus an explicit missing-reply explanation. | The saved trace records one receiver application even while the host lacks the answer. |

The expanded browser audit follows keyboard focus into each stop and from the optional prompt into the first answer, then carries the literal brief into the workbench and returns to the ordinary question sheet. It also exercises the archive entry and nested masthead, verifies that the finite fine-pointer glint leaves the link rectangle unchanged, and checks that touch receives a still drawing. All 266 assertions passed locally. The original 78-check loose-end audit and eight affected model tests had already passed; no brief-generation, storage or workbench code changed.

The first PR revision’s performance CI passed all budgets. Median cold-load lab values (three navigations per profile) were: homepage mobile FCP 991.8 ms / LCP 1321.4 ms, thread mobile FCP 1352.2 ms / LCP 1577.2 ms, thread desktop FCP 324.8 ms / LCP 384.8 ms. TBT and CLS were zero in those medians. These are controlled Lighthouse results, not a promise about every device or connection. The audit revision reruns CI at its own head; the PR’s checks are the final status.
