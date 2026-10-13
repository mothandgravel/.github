# In passing / the moth interlude

The owner approved a brief scene after the #23 audit: emerge from the studio mark, flutter toward a question, settle, then disappear. Motion and animation reviewers helped develop the rig, choreography and browser critique. The scene sits between Working Specimens and the bounded first-engagement invitation, with a real route to the question sheet.

## Material and direction

The rig separates the existing emblem into organic fore/hind wings, gravel fore/hind wings, body and antennae. All 55 creature geometry elements are preserved; the moon stays in the source mark. Its square whitespace is removed from the flying rig’s viewBox, so the source-to-traveller scale follows the visible creature. No stock footage, generated photo, external font, 3D library or remote API is used.

This is expressive 2.5D graphic flight: pivoted wing compression/shear, delayed gravel-side cadence, a small difference in light, body heading and a faint shadow. It is not a volumetric model or a claim of physically accurate flight. Extra legs, loose stone particles and a glossy finish were rejected because they made the small silhouette less recognisable. The hero’s endless float is retired; the finite scene owns this movement.

## Choreography / 4.8 seconds

| Passage | Time | Behaviour |
| --- | --- | --- |
| Emergence | 0–0.36 s | An uneven wing pulse; the moon stays behind. |
| Lift | 0.36–0.92 s | Leave the faint imprint and become a traveller. |
| Flight | 0.92–2.30 s | A bowed route toward the question, with asymmetric wings. |
| Inspection | 2.30–2.75 s | One corrective hook before committing to the perch. |
| Landing | 2.75–3.25 s | Decelerate, fold and align with the brass line. |
| Settlement | 3.25–4.01 s | A final adjustment, then a genuinely still pose. |
| Departure | 4.01–4.80 s | Rise back through open space and fade; restore the mark. |

The first path was rejected because the rotating silhouette grazed question space during inspection/departure. The final desktop perch reserves a fixed gap beside the question; the phone perch stays above its ink. Departure returns into the source–perch corridor. The runtime samples the whole rotated envelope before playback. Tight layouts keep the resting composition rather than crossing text. This gate supplements actual browser collision measurements; a finite sampled check is not a proof for arbitrary future layouts.

## Interaction and quiet states

The scene’s module, choreography, rig and motion CSS are loaded only when this below-fold room is reached. Autoplay gets one opportunity per tab/session, requires at least 70% of the stage in view and safe geometry, and respects reduced motion. Visiting with reduced motion or a tight layout consumes that opportunity too, so resizing or changing a preference does not spring an animation on the reader. Only a local session flag is stored; no visitor data is transmitted.

Watch again replays. If its controls are visible but the stage is not sufficiently in view, the explicit action first centres the stage. Pause freezes the rendered pose; Resume continues from that time. Finish and Escape restore the mark. Leaving the stage, window focus loss, pagehide, hidden-document notification or resize ends the passage rather than resuming in a new position. Relevant control focus returns to replay, or to the real question link when replay is unavailable; unrelated keyboard focus is left alone.

Independent runtime review found a queued-replay seam: cancelling the centring scroll could leave a pending request that played on a later return. Complete stage exit, wheel/touch movement, scroll-navigation keys and outside pointer/focus now cancel that request. The browser regression aborts centring, returns to the room and verifies it remains quiet until replay is explicitly requested again.

The question, caption and link stay still, above noninteractive decorative flight layers. Reduced motion retains the mark. With script disabled, or a failed module/rig/stylesheet, the mark and actual question route remain readable; dead controls stay hidden. The scene has no perpetual clock after completion.

## Critique and verification

Motion reviewers inspected desktop/phone flight and settle captures, a recorded browser passage and close frames around the hook/landing. They found the wing roots attached, original asymmetry legible, visible contact with the perch and a deliberate correction followed by quiet. The slight dip below the perch reads as inspection; it is the chosen expressive direction. The gravel wing was darkened a further six percent in travel to clarify near/far separation, with equal resting tones restored.

The browser audit performs all phases at widths 320, 390, 768, 901, 1024 and 1440 in both themes, independently samples the rendered silhouette for stage/text collisions, checks stationary question geometry, pause/resume, completion and same-tab replay behaviour, keyboard access and accessibility. Additional cases cover interruptions, the real question route, reduced motion, script-free reading, failed resources and an equivalent narrow zoom view. Blur/pagehide cleanup uses dispatched lifecycle events; it does not establish every OS/browser implementation. Required static, journey and cold-load checks remain gates.

Recordings and captures are review artifacts, not production assets. Human interest, comprehension, motion comfort and conversions have not been measured. The provided YouTube reference could not be retrieved; this scene follows the approved brief and the studio’s own emblem, without claiming an exact recreation.
