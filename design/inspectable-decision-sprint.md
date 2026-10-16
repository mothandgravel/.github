# One specimen, one inspectable decision, one next question

## Selection

The owner asked for a new specimen from more ambitious projects and excluded SkyStack from this sprint. Read the entry points of all eight candidates, then inspect the contracts behind the strongest questions:

| Project | Possible design question | Selection |
| --- | --- | --- |
| Decision Docket | Does reviewing a cue look like verifying a decision? | Strong continuation; attention design explicitly separates these acts. |
| Ajo | Can we find a missing reply without repeating an action? | The existing saved simulator specimen becomes the next question. |
| Geaidnu | How do we show activity without implying accepted proof? | Strong workspace study; several recovery requirements are still open. |
| flutter-test-rs | How do we explain reuse while making clear that tests still execute? | Useful developer-facing study; avoid private application evidence. |
| Paja | A job has started. What lets someone know it finished? | Clear typed outcomes, more operational than the chosen visual distinction. |
| Raivari RPC | Does permission look like approval of this particular change? | Rich action-boundary study; would need more context for this short first specimen. |
| Cyber Grid / Neural Pathfinder | When does help preserve discovery, and when does it give the puzzle away? | Read game logic, state hook and documented help mode. A different play study remains possible. |
| WebRTC Multistream / LiveConnect | Can a connected label hide an old measurement? | Chosen: connection and diagnostic freshness have separate source representations. |

The WebRTC repository has no root README. Its package, documentation index, source tree, connection helper, viewer stage, measurement helper, diagnostics type and sampling hook were inspected. The runtime is parked; this sprint neither starts it nor claims a live deployment. Exact source paths, revision, blobs and fixture scope are recorded in `connection-study-provenance.json`.

## The decision

Keep connection state, measurement state and sample age distinct. A historical number can stay inspectable while its stale status travels with it. The source helper uses a 15-second freshness window; exactly fifteen seconds remains current. Missing or incomplete measurements are unavailable, distinct from a measured zero.

Two authored sketches inspect the same inputs. Sketch A places a rate beside one connected label without an age. Sketch B gives the rate its own measurement label and age. Neither is presented as an earlier or shipped LiveConnect interface. The fixed fixture holds connection at connected; the page does not import LiveKit or prove a reconnection.

The tradeoff is additional reading. The next human observation should ask what a visitor knows at eighteen seconds and what they would do next, then compare how they answer across the sketches. Source replay and browser checks do not establish comprehension or a usability win.

## Critique and implementation

- A video simulation could imply a recorded stream or camera activity. Use explicitly authored readings and clearly labelled conceptual illustrations. The initial typography-only pass left the visual story too thin; the follow-up critique below corrects it.
- Automatic ageing would make the exhibit harder to compare and create a continuous clock. The visitor owns a bounded native range control; nothing advances by itself.
- A green success badge could collapse the distinction before the copy explains it. Keep the existing brass material and use explicit labels, age and different rules, readable without colour.
- Questions and controls stay in their places. Only the measurement labels, rate and clock mark respond; there is no motion loop or new dependency. The static vector drawing is local and reserved in the layout.
- The source helper is preserved under `tools/specimens/source/` and emitted into browser JavaScript by stripping TypeScript types. Its body is unchanged. The builder verifies its recorded SHA-256; the generated output and boundary cases are checked in CI.
- Fixture times and inputs are authored and frozen. There is no captured telemetry, media request, AI call, form submission or stored visitor choice. Theme storage is the existing site behavior.
- A native disclosure contains all three fixed readings without JavaScript. Enhancement controls remain hidden until initialization succeeds, including when a module fails to load.
- Public reading copy contains project names and source scope, without organization identifiers or commit hashes. Source custody remains in the development record.

## Editorial continuation

The homepage has a featured fourth specimen above the existing three plates. The consolidated specimen provenance indexes its separate source record. Its dedicated public route is `/specimens/connected-to-what/`, with canonical/social metadata, generated studio identity, a breadcrumb and sitemap entry. It is a specimen, not a new numbered Field Note; audio and editorial catalogues remain untouched.

The ending explains why Ajo comes next: losing a current view differs from losing a reply after an action may already have happened. It links directly to the saved recovery trace on the bench, followed by the existing Field Note about reassuring signals. A rough question of the visitor's own leads to the existing loose-end journey. Private enquiry and the fictional shared workbench remain separate.

## Validation

Source checks cover the exact freshness boundary, missing/incomplete readings, unknown sources, invalid/future timestamps, a measured zero, all thirty-one inspection clock positions and every declared public fixture. Browser checks cover both themes at 320, 390, 768 and 1440 pixels, native keyboard inspection, touch inputs, fixed question/control positions, unavailable-state recovery, native records, accessibility, reduced motion, failed modules, JavaScript-free reading, the homepage entry, the next question and browser Back. They also assert that the study makes no external or effect requests.

The first cold-load CI gate measured a 1.10-second mobile first paint and refused the one-second budget. The homepage entry reuses existing sheet components. Its conceptual SVG is lazy-loaded with explicit dimensions; the stylesheet adds one small image rule. Structured identity remains in the initial HTML, after the reading content. Full landing, handling and room/index audits and the cold-load budget remain regression gates. Review captures are development artifacts. Physical device testing and human comprehension observations remain outstanding.


## Illustration sprint — 14 October follow-up

The owner identified the absence of illustration in the first review. Three gaps were confirmed: the opening had no visual anchor; state comparison depended on labels and numbers; the homepage entry resembled a text summary rather than a piece of work.

| Critique | Change | Review criterion |
| --- | --- | --- |
| Nothing to turn the opening question into an image | Original charcoal-mounted SVG: a joined brass cable beside a retained paper sample and ghost outlines | Readable silhouettes at 320 px; the material vocabulary belongs to the established studio |
| Current, stale and missing looked too similar | Both sketches get the same sample symbol; only the explicit sketch adds a dashed stale edge. Missing removes the drawn measurement marks and leaves an empty outline | Shape and wording carry the distinction without relying on colour; missing never becomes zero |
| Sample age lacked a clear relationship to its threshold | One continuous graphic shows the solid window through 15 seconds, a dashed remainder and the selected age | Marker matches the fixed clock and disappears without a sample; exact 15-second rule remains unchanged |
| The new bench entry did not preview the specimen | Reuse the conceptual illustration in the homepage entry, with a concrete stale-reading caption | Lazy local SVG; declared dimensions; no added eager homepage media request |
| The comparison numbers did not align after the first visual pass | Reserve the absent second label's space in Sketch A; remove the duplicate miniature clock from Sketch B | Both readings share a baseline while the inspection controls remain fixed |

The graphic is an original code-native vector asset, not generated footage or a source screenshot. Its internal marks are authored. The public caption, alternative text and development provenance all preserve that scope. No source freshness rule, product runtime or private record changed. The existing generic social card remains a studio identity image, not an illustration of the specimen.

The first local illustrated pass passed all 1,182 existing specimen checks. Desktop Night and phone Afterlight screenshots were inspected, then the alignment and duplicate-clock findings above were corrected. The browser audit now checks image decoding, threshold-marker geometry, stale versus unchanged edges, missing-sample marks and static illustration availability when scripts fail. CI captures the opening art, full reading page, stale comparison and unavailable comparison for desktop/phone review. The final local specimen run passed 1,233 checks with zero failures, alongside 21 model tests and the static/generated/source-integrity checks. The age-marker geometry check waits for the painted position after rapid native keyboard input; it retains a bounded failure timeout rather than adding a fixed sleep.

Human comprehension and physical-device trials remain outstanding; illustration review does not establish either.
