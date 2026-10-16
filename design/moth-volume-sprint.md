# A little weight in the wings / volumetric moth sprint

The owner approved the proper 3D moth after the finite interlude and the shared light/handling pass in #24. The room, question and journey stay intact. A small sculptural creature carries the studio's soft wing / hard ground contrast through the existing emergence, flight, inspection, landing and departure.

## Material and camera decisions

The four wing contours and all 37 separated gravel shapes come from the studio's source-derived SVG rig. The standard-library build tool samples its authored Bézier contours into a seven-kilobyte model record, bound to the rig's SHA-256. The generator is development tooling outside the published site. The original mark and articulated SVG remain source assets and a complete fallback.

Paper wings have curved front/back surfaces, thin closed edges and raised veins. Gravel pieces have backs, thickness, bevels and individual peaks rather than flat image cards. A lathed head and tapered, segmented body reinterpret the source silhouette; tubular antennae retain the source branches. This is a studio sculpture, not a biological simulation. The mesh uses 4,250 triangles across six articulated groups. There are no downloaded models, bitmap textures, generated animal images or external rendering dependencies.

A fixed orthographic camera favours a readable specimen at small sizes. Hinges move the wings in depth; near/far surfaces and bank reveal their volume. Six percent of camera padding reserves room for the wing tips during articulation. The landing offset accounts for that camera and the settled body orientation. The source's moon remains in the studio mark.

Surface normals drive matte directional lighting from above-left. The light direction follows the room while the moth changes heading, so it does not rotate with the artwork. A restrained surface grain and bevel tones distinguish paper from gravel. The alpha silhouette casts the existing down/right drop shadow, with a soft contact shadow near the perch. There is no shadow-map pass or claim of photorealistic flight.

The grain uses bounded trigonometric inputs with matching explicit precision in both shader stages. It does not depend on desktop precision exceeding the mobile `mediump` minimum; the edge term is clamped before squaring.

## Runtime and quiet states

The existing interlude loads a small native WebGL renderer and model only after the below-fold room is reached. Reduced-motion entry does not fetch those resources or create a GPU surface. The canvas is transparent, decorative and pointer-inert. The question and controls remain HTML on their original reading plane.

The renderer owns no timer. The interlude's finite clock sends up to six mesh draws per changed pose; identical settled poses are retained without GPU draws. Drawing buffers are capped at two device pixels per CSS pixel and 216 × 124 pixels at current layouts. The frame buffer is preserved so pausing holds actual pixels without a continuous redraw. This deliberate choice applies to the bounded glyph, not a full-window canvas. CPU mesh arrays are released after upload; buffers/programs are deleted when the renderer is disposed.

Optional 3D setup has a 1.8-second deadline. A stalled module or model releases the SVG controls; aborted or late responses cannot install a canvas afterward. Startup interruptions consume the automatic opportunity, including while core resources are still loading. Automatic flight also requires document focus. The original once-per-tab opportunity, pause/resume, finish, abandoned replay cancellation and focus rules remain in force.

Unavailable WebGL, a failed module or model, malformed coordinates or topology, shader setup failure and GPU upload errors leave the source-derived SVG performance available with the same controls. Model validation bounds input sizes, coordinates and triangle count and rejects nonfinite geometry. The initial GPU surface is one pixel; its first draw and subsequent buffer resizes are checked for errors. Actual context loss or a failed first draw ends the passage, restores the mark and keeps subsequent explicit replay on that fallback. It does not silently restart or upgrade again. Disposal removes its listeners, unbinds the resources and deletes buffers/programs. Missing core scene CSS/rig/module still uses the original static question route.

## Review evidence and limits

Initial close renders compared rest, lift, bank and approach, followed by actual phone/desktop room captures. Gravel reads as separate pieces with mass; the folded paper side remains visibly different, with attached roots and a thin edge. The original asymmetry survives at the actual display size. The full wing pulse and course correction retain the expressive timing approved for the 2.5D scene.

The animation reviewer found the first paper treatment too dark and khaki at actual phone size. A small ambient lift is now applied only to the soft-wing groups, keeping the directional key and gravel facets intact. It lightens the folded paper rather than adding gloss or flattening the whole sculpture.

The same review found that the first volume renderer omitted the source choreography's slight body lag and final antenna adjustment. Those are now articulated separately, with the antenna transform following the body so their roots stay attached. The final still pose remains the calibrated landing pose.

The motion reviewer identified a further join seam: a phase-based attitude switch snapped bank by about 22 degrees at the start of landing. Bank and pitch now come from continuous choreography values, easing into lift, blending toward rest through landing and easing back into departure. Boundary tests check both sides of every join. The reviewer inspected extracted browser frames rather than claiming continuous video playback. The first recording stopped short of complete restoration; the renewed review passage includes departure, idle and the returned mark.

The volume audit exercises an actual WebGL drawing context using Chromium's SwiftShader software renderer. It checks nonblank GPU output and errors, bounded buffer size, pixel-preserving pause without draw calls, changed articulated poses, measured opaque-pixel proximity to the perch, idle draw cessation and all six widths in both themes. A separate 301-pose pixel readback checks that the whole animated model stays inside its drawing surface. Failure cases include actual WEBGL_lose_context, unavailable context, rejected shader, blocked renderer/mesh/model and malformed model data. Reduced entry verifies the absence of 3D requests and allocation. Existing landing, journey, moth lifecycle, handling and cold-load gates remain required.

These checks verify the browser implementation, not every mobile GPU, thermal condition or frame rate. Headless software rendering is not physical-device evidence. Human motion comfort, interest and comprehension have not been measured. The code keeps the finite, bounded fallback while those observations remain to be gathered.

The follow-up [PR #26 audit](moth-volume-audit.md) records reproduced startup, failure and integration gaps, their fixes and regression evidence.

Primary implementation references: [WebGL specification](https://registry.khronos.org/webgl/specs/latest/1.0/), [context-loss extension](https://registry.khronos.org/webgl/extensions/WEBGL_lose_context/), [WebGL best practices](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices) and [model/view/projection](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_model_view_projection).
