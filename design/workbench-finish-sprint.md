# The room, properly handled

## Continuing from the question sheet

The October 27 pass distinguishes the visitor's carried brief and local margin
with paper, while the fictional sketches stay on a dark inspection mount.
Native Look, Notice and Leave a direction links provide a route through the
first visit. The explicit carry lands on the visitor's own brief, with separate
links to inspect the fictional study or revise their words. The study does not
adapt to that brief.

The sketch controls now share their mount. A saved observation has an explicit
inspection return: it selects and focuses its original sketch without changing
the note. A pin appears only on that sketch; its reserved slot prevents the
comparison from shifting. The first visit's working doubt precedes the draft
direction. Clear has its own housekeeping scope, after its explanation.

The return visit presents Changed, Kept and Still open beside its opening,
with the carried brief collapsed separately. Its fixed drawings, revision guard
and local-note history retain their contracts. Export adds an explicit section
label before the unchanged carried brief. Neither visit claims a studio response
to the visitor's actual words or a usability result.

## The quality gap

The workbench and staged return already supported comparison, revision-anchored observations and local draft directions. The live review found that those capabilities were presented as similarly weighted boxes: the specimen was small, the local record was distant, and the second visit felt like another demonstration. The next finish pass concentrates on the experience of inspecting and returning.

## Material and hierarchy

Both visits share a small room index, a shorter opening and an original SVG illustration of the fictional mending question. The specimen occupies the wider reading plane. Bone paper sits on a charcoal mount under the established upper-left light; brass marks the revised option and the notes beside it. A first-visit observation appears in the adjacent margin. The proposed direction and the retained doubt have distinct positions rather than another row of equally weighted cards.

The fictional study, public preview and local-draft boundary remain explicit. No real client result, upload feature, studio reply, account or shared state is introduced. The visitor's own question remains separate from the specimen. Resend and the real client-room pilot are outside this change.

## Interaction corrections

- All three return sketches and both first-visit sketches use the same canvas size. The original revisions also retain identical drawing geometry, labels and controls across visits. Captions reserve their reading space, so switching does not shift the comparison surface or its controls.
- Opening an observation hides its opener until save or cancel. Switching the inspected sketch preserves the editor's original anchor and its unrecorded text.
- Return directions concern revision 2. While an older revision is inspected, a visible explanation and explicit return action replace the ability to submit that direction. Unrecorded choice and reason stay in place. The submit handler also enforces the revision boundary if disabled controls are bypassed.
- Recording, export, clear and storage-limit feedback appears in the work area where the action happened. One visually hidden live status still announces the result; the local copies do not create duplicate announcements.
- Selecting the current visit uses a same-document anchor, preserving an open editor instead of reloading the page. Moving to the other visit remains an ordinary link.
- The return sketch's native accessibility label now says “a loose seam,” matching its visible content and model. It previously said “a delivery.” The return description also identifies the return journey rather than repeating the first visit.
- Clear actions state their scope. Clearing the first visit still clears the carried question and first-visit draft; clearing the return visit still preserves them. Existing storage keys, versions, record limits, exports and recorded history remain compatible.

The older `specimen-return.css` asset stays available for previously cached page HTML, while current pages use the combined room stylesheet. No framework, icon dependency or additional browser script is introduced.

## Review and evidence

`audit_workbench_finish.mjs` reviews both pages at 320, 390, 768, 1024 and 1440 CSS pixels in both themes. It checks stable comparison geometry, note anchoring, in-place feedback, keyboard return, wrong-revision submission, preservation of unrecorded words, denied storage and native fallbacks. Screenshots and results remain CI artifacts. The existing specimen-return, loose-end and editorial-thread audits cover the surrounding journeys and storage isolation.

The site integrity check now includes the return page's destinations and anchors. The performance workflow measures each preview independently with the existing secondary-page budgets: median FCP 1800 ms, LCP 2500 ms, TBT 200 ms and CLS 0.1. Their deliberate `noindex` directive is excluded only from the SEO-score gate. The homepage's 1000 ms FCP budget and the published pages' SEO gate are unchanged.

These checks establish the inspected layout and behavior. They do not establish whether a person recognises the right next action, understands a revision anchor or finds the room welcoming. The next human trial should observe those three things using one complete first visit and return.
