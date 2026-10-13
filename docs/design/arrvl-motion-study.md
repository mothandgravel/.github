# A room with a little life / ARRVL study

The owner asked what else gives ARRVL its crisp, almost three-dimensional feel before commissioning a proper 3D moth. This study extends the first specimen handling pass. Its next step is a browser sprint on light, arrivals and small responses. The existing moth scene in PR #24 is a separate 2.5D performance; this document does not implement a volumetric replacement.

## What was inspected

Source: [ARRVL’s homepage](https://arrvl.studio/), inspected on 2026-10-13 in a desktop cloud browser. Followed the hero’s explore link, interlude and work links; focused a project with the keyboard; opened and closed the menu; switched the service disclosure to Motion. Screenshots sampled these states. Read-only DOM inspection checked the focused project image’s computed transform and transition.

| Observed at ARRVL | Reading for this study |
| --- | --- |
| Orange grid introduction, then a dark hero with broad white highlights, grain and oversized flat type. | Light and contrasting surfaces suggest depth before any object moves. |
| A glyph-textured interlude separates the hero from a pale work area. | Changing material and density creates a passage between rooms. |
| Project name bars sit separately above clipped image panels, with small floating category pills. | Frame, image and label occupy distinct planes. |
| The focused Facet image had a computed scale of 1.025 and a 0.45-second custom easing transition; its three dots appeared orange. | A small, coordinated response acknowledges inspection. This is a style/state observation, not a measured playback duration. |
| The menu arrives as a pale sheet with large links and a divided contact area. | Opening navigation changes the composition, not just an icon. |
| Switching service rows closes Design, opens Motion and changes the plus/minus state. Letter fragments appeared in sampled titles. | State changes have character. Text effects also need scrutiny for readability. |

These are observations of rendered states, not a reverse-engineered animation system. Pointer hover was not exercised independently. Exact easing performance, mobile behaviour, reduced-motion handling and loading cost were not measured. The impression of depth is an interpretation; it does not establish which surfaces use actual 3D rendering.

## What belongs in Moth & Gravel

### 1. One light, several materials

The studio already has paper, charcoal, brass, organic wings and gravel. Give them a shared light direction, provisionally from above-left. Paper gets a narrow edge and soft contact shadow. Gravel gets broad, uneven tonal facets. Brass receives a restrained highlight. Avoid applying the same glossy treatment to all three.

Start at `.work-specimen`: inspect whether its edge, shadow and existing tilt agree about the position of the light. The current bounded tilt is already implemented in #23; do not add a second movement to the whole card. Titles, scope labels and working-record controls stay on the reading plane. A shadow can change while the printed question stays put.

This is the first priority because it gives the future moth somewhere believable to land. Compare the composition at rest as well as in motion. A static room should still have depth.

### 2. Arrivals with an ending

Give one below-fold specimen group a short, finite arrival: its brass rule resolves, then the material settles. Provisionally test 6–10 pixels of movement over 280–420 ms, with at most 40–60 ms between the three objects. These are starting values for our prototype, not timings copied from ARRVL.

Keep all content visible before enhancement. Never gate a headline, evidence caption or next action behind a reveal. Run the arrival once per page visit; scrolling back should find a quiet bench. Reduced motion keeps the completed composition. Skip the entrance if the user reaches it by keyboard, a hash link or a restored page position and movement would disrupt inspection.

Judge a short deceleration rather than a springy bounce. The useful feeling is something being placed carefully, not everything floating.

### 3. A small vocabulary for actions

Use the same response for the homepage’s question buttons, field-note links and working records: a brass edge or underline acknowledges the action, a decorative arrow travels only a few pixels, then rests. Keep label geometry and hit areas fixed. Focus gets a clear stationary outline; touch gets an intelligible pressed state without a hover dependency.

For native working records, make the open marker and edge state agree. Existing disclosure lighting is the starting point. Do not animate the evidence text or replace native disclosure behaviour just to animate height. The question sheet and workbench should eventually speak this same motion language, while keeping their data and private-enquiry boundaries separate.

### 4. Rooms with different pressures

The homepage already has editorial sections, specimen plates and a bounded invitation. Strengthen their contrast through spacing, framing and one deliberate change of material. A dense specimen area can lead into an open question, then a compact sheet describing the first piece of work.

Prototype this at the boundary between Working Specimens and the interlude prepared in #24. Use composition and a still-lit surface first. Keep the normal scroll path and the existing section order. A passage should help someone understand where they are, not require them to finish a cinematic tour before reading.

### 5. Typography can carry tension while staying still

Our condensed lettering and italic questions already provide a useful contrast: firm statements beside softer curiosity. Try one asymmetric line placement or a rule crossing open space in the next visual pass. Preserve real selectable text, a single reading order and intact line wrapping on phones.

Reserve animation for a decorative rule or marker. Scrambled letters, moving body copy and repeated word-by-word reveals would make design questions harder to read. The voice comes from the wording and composition; motion should let the question arrive intact.

## Focused sprint before the 3D moth

Build one coherent browser prototype spanning a specimen plate, its working record, the next question and its action. Compare it with the current resting composition. Keep the moth performance in #24 intact during this comparison.

| Order | Concrete output | Review question |
| --- | --- | --- |
| 1 | One shared light direction applied to a specimen plate and its brass detail. | Can you tell paper, stone and metal apart at rest? |
| 2 | One finite arrival and matching link/disclosure feedback. | Does each response explain what changed and then become quiet? |
| 3 | One refined specimen-to-question boundary, tested in both themes. | Does the page feel like a place without slowing the reading journey? |
| 4 | A material and lighting brief for the volumetric moth. | Does the creature belong to that place at the size people will actually see it? |

Browser review must cover narrow and wide layouts, keyboard routes, touch, reduced motion, interruption and failed enhancement. Confirm that text and controls remain stable, that resting/offscreen states have no continuous animation clock, and that opening requests and the existing cold-load budget are preserved. Add checks for actual new behaviour; documentation alone does not justify rerunning every motion test.

Ask a few readers where they would go next, which object feels inspectable and whether anything interrupts their reading. Scripted accessibility and performance checks cannot answer those questions. Those human observations have not been conducted.

## What the proper 3D moth needs from this

Carry forward the original uneven silhouette and recognisable soft/gravel split. Establish the camera and real display size before adding surface detail. Specify paper-like wing thinness, porous stone facets and a restrained brass moon; evaluate them under the room’s chosen light. Close wing pivots, near/far separation, a cast shadow and convincing contact with the perch matter more than a glossy render.

Make a still pose, lift, bank and landing studies before building the complete flight. Compare a short rendered asset with a runtime scene using visual quality, transfer/decode cost, mobile playback and controllability; the medium remains undecided. Keep a source-derived resting mark and the real question route available while the richer asset loads or fails. Pause, finish, replay and quiet-state behaviour from #24 remain requirements.

The orange intro and lettering effects are useful reference observations, but they do not become our next feature list. Moth & Gravel’s liveliness should come from a room being handled, a question receiving attention and a creature briefly choosing to investigate.
