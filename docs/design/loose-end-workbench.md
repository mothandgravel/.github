# A loose end becomes shared work

The landing should help someone recognize their difficulty, articulate it and see how Moth & Gravel approaches work. The studio's existing materials and voice carry through: bone, charcoal, brass, direct language and room for uncertainty. Products across the pipeline remain sources of design questions; no single product defines the studio.

## The first usable slice

The public `/questions/` journey asks for a starting point, an intended change, the difficulty and people involved, a useful outcome and optional constraints. Only a few words describing the starting question are necessary. “I can’t quite name it yet” is a legitimate entrance. Guided stages enhance a complete static question sheet.

The result is an editable plain-text brief assembled from the visitor's words. It can be copied or downloaded without an account. Manual edits survive a return to the answers and a return from the example workbench. Rebuilding from answers is explicit. The studio has not received the brief; it is not a diagnosis, quote or agreed scope.

Choosing **Carry it to the workbench** places a bounded draft in browser session storage and opens `/workbench/` in the same tab. No answers are placed in URLs or sent to a server. Clearing removes the saved question and recorded preview actions. Closing the tab normally ends the session; browsers may restore session storage when restoring tabs. The page is not a secure vault. Downloaded copies remain with the visitor. If storage is unavailable, the brief remains available for download and the ordinary example can still be opened.

The workbench is a clearly labelled public example with a fictional visitor check-in problem. The visitor's own question appears separately; sample project artifacts do not pretend to answer it. Two source-native SVG sketches support comparison. Native radio controls, readable explanations and disclosure controls carry the interaction; there is no compulsory dragging, puzzle or spatial navigation.

- **On the bench:** compare two possible beginnings.
- **This feels wrong:** pin an observation against the inspected approach without needing design terminology. Cancel does not record it.
- **Your next decision:** prepare a choice, then explicitly record a local draft. “Keep the question open” remains possible. Radio selection is not acceptance or approval.
- **What we left aside:** keep a rejected approach with its reason and the evidence that could reopen it.
- **What resisted:** distinguish a working hypothesis from an observed result.
- **What we’re carrying forward:** inspect the recorded observation and download it with the draft choice and edited brief.

The public landing adds recognizable situations and routes to real Field Notes. The public GitHub conversation remains a direct alternative, with its account/publicity requirements disclosed. No private address is invented. The intake is search-indexable; the fictional workbench is marked `noindex` and excluded from the sitemap. That is editorial classification, not access control.

## Critique and choices

The first phone review put too much explanation before the questionnaire. The question sheet now precedes the supporting explanation at narrow widths. The initial carried-question panel pushed the actual artifacts down the page; its original answers and edited brief now use native disclosures around a concise question. Guided steps support browser Back/Forward without answers in the URL; cleared drafts cannot be recovered through that history. These choices make the task easier to reach while keeping the explanations available.

The first CI run found an Afterlight contrast failure on the direct-contact link after theme switching, reproducible locally as a retained Night inherited foreground on the light background. The link now uses an explicit theme accent token. The audit samples its rendered foreground/background and also runs axe, preserving failure details. Screenshots alone did not expose the transient style problem.

The style reuses the established site tokens, system fonts, masthead and appearance control. Journey styles and scripts are loaded only on these pages; the landing receives links and small copy changes. New illustrations are exact SVG sketches, labelled examples rather than fabricated screenshots.

When scripts are disabled or the journey module fails, the full question sheet, both sketches and the rejected approach remain readable. Guided controls are hidden until initialization. Plain text is inserted with `textContent`; carried drafts are versioned and bounded. Recorded actions report storage failure honestly. The preview can keep one observation and one draft choice; it is not a complete collaboration record.

## Optional ground, after the question

PR 13 made timing, money and existing material possible only inside one broad constraints answer. The follow-up separates them into three native disclosures, closed by default. The visitor decides which are relevant. A timing answer can distinguish a real deadline from a rough window; the budget can be an amount/range with any currency, or “not set yet”; existing material can be a description or a literal link. No fixed project packages or studio availability are implied. Links are not automatically fetched and attachments are not accepted by this static preview.

These details are optional at every entrance. Unanswered follow-ups are omitted from the brief and carried-answer list, keeping a short question short. Answered follow-ups survive download, explicit handoff and return. Earlier version-1 drafts remain readable. The expanded sheet uses a new module/model pair; the previously published modules remain intact for cached older HTML. The bounded brief capacity now covers every answer at its maximum length, including the final material, without silently truncating it. A cleared draft also closes the disclosures. The chosen entrance changes supporting prompts: exploring an idea, describing a failure, seeking another pair of eyes or starting with something unnamed. It does not invent a diagnosis or classify people into a commercial package.

## What is still missing

| Piece | Current boundary | Next concrete work |
| --- | --- | --- |
| Private enquiry delivery | Brief stays in the browser; public GitHub remains the actual contact route | Connect a verified private inbox/endpoint and provide an explicit review-and-send action. Avoid collecting contact details before there is a destination. |
| Delivery acknowledgement | No send is attempted by this prototype | Distinguish received, failed and unknown outcomes; keep the brief available and avoid duplicate enquiries when retrying. |
| First engagement | No fixed offer, price, availability or response promise is published | Agree the first bounded deliverable and explain what the client leaves with: a focused review, tested prototype or technical investigation are candidates. |
| Real project room | Public fictional example, one local observation and one local draft choice | Authenticated membership, private project data, multiple artifact revisions, conversations and a durable decision record. |
| Return and progress | Same-tab draft restoration is available | Show meaningful changes since the client's last visit, unresolved questions and one clear next action. |
| Evidence with real people | Browser behavior is checked; commercial and human usefulness are unmeasured | Try the intake and one real project room, then revise using observed confusion and the quality of the resulting conversations. |

Private delivery and real client access are the highest-priority steps after the public intake. They need an actual verified destination and project access system; the current owner instruction keeps the disclosed GitHub route until a private channel is supplied. Public copy should keep naming what the present action does. An invitation to make a brief must not silently become a promise that the studio received it.

## The private pilot that follows

Build one real project room around an agreed, bounded question. Its first visit should answer: what are we trying to resolve, what can I inspect, what do you need from me, and what happens next? Subsequent visits should show the meaningful changes since the client's last visit, unresolved observations and the evidence behind decisions. The room remains useful when there is no new activity.

The first actual engagement needs an agreed deliverable and boundary. Candidates to choose with the studio owner are a focused design review, a tested prototype or a technical investigation. The public prototype does not publish fixed pricing, availability, response times or an unchosen service package.

Before collecting real enquiries, configure a verified private delivery route and confirmation that distinguishes received, failed and unknown submission outcomes. Provide a direct message alternative. Do not turn the current browser draft into an unacknowledged inbox or a public GitHub issue.

Before inviting a client into a real room, implement authenticated access and server-enforced project membership; keep client drafts and artifacts outside public Pages files and public source history. An unlisted URL or `noindex` is not private access. Invitations, access removal, bounded attachment handling, durable comment/decision records and recovery from interrupted saves belong to that private implementation. Preserve the client’s original words and distinguish proposed, accepted, superseded and unresolved decisions. Client acceptance must identify the artifact revision it concerns.

Public Field Notes remain a separate editorial decision. A private client's observation does not automatically become studio content. The pilot should establish which information clients need to revisit before adding dashboards, invoices or broader account machinery.

## Pilot questions and evidence

Try the intake with someone carrying an unclear idea and someone carrying an existing problem. Can each describe the difficulty without producing a polished specification? Can they tell whether anything was sent? Is the brief useful enough to keep? Observe where they abandon the steps rather than assuming a longer form improves enquiry quality.

Try the room with an artifact that needs a real decision. Can the client compare approaches, flag a discomfort, distinguish preparation from commitment, understand the consequences and return with enough context? The preview's synthetic fixture can establish interaction behavior, not usefulness with real clients.

Success should be assessed through useful enquiries, fewer clarification loops, clearer decisions and the client's ability to resume work. No conversion uplift, usability result or commercial outcome is claimed by shipping the prototype.

Browser verification lives in `scripts/audit_loose_end.mjs`: the real journey, empty-answer focus, editable/downloaded briefs, same-tab handoff/reload/return, cancellation, explicit commitment, clearing, storage refusal, literal hostile text and request inspection. Both appearances and 320/390/768/1024/1440 px layouts receive automated accessibility/overflow checks. No-JavaScript and failed-module paths remain inspectable. Full screenshots are reviewed separately; automated axe checks do not establish assistive-technology speech or cross-browser acceptance.

The landing's existing static, browser and cold-load budgets remain required. The prototype is proposed through a PR; live-site publication and a real private pilot are separate outcomes.

Primary form guidance: [GOV.UK question pages](https://design-system.service.gov.uk/patterns/question-pages/) and [structuring forms](https://www.gov.uk/service-manual/design/form-structure). The relevant principles are necessary questions, legitimate uncertainty, focused stages and useful branching when answers change the questions asked. This first slice uses the same short question sequence across the four entrances; there is no invented branching or generated assessment.
