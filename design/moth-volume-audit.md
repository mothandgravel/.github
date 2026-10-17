# Volumetric moth / PR #26 audit

The functional review covered the published head `096bfc7768461c0208c8920d0aecbd4e81d28e99`, then integrated main at `28c010603f694ff446dbd4716f93be0784bcbf07`. It followed startup, automatic and explicit flight, pause, interruption, completion, setup failure and context loss through the actual browser controls. Fault injection checked behaviour rather than relying only on source guards.

## Findings and corrections

| Gap | Evidence before correction | Correction and regression |
| --- | --- | --- |
| Optional setup could strand the SVG controls | Holding the model response kept readiness unset and Watch hidden despite a loaded core rig. A held renderer import had the same dependency. | A 1.8-second deadline aborts optional setup and releases the SVG path. Tests hold both resources past the deadline, release them afterward and verify no late canvas, upgrade or unhandled error. |
| Interrupted startup could autoplay afterward | Blur during a held model request was followed by a playing WebGL scene on release. | Startup blur, pagehide, Escape, hidden visibility and preference changes consume the automatic opportunity and cancel optional setup. Early handlers also cover a held core rig. Tests verify idle restoration and subsequent explicit replay; autoplay additionally requires focus. |
| GPU allocation failure could leave a blank creature | Injected upload failure left a playing WebGL scene with zero occupied pixels. | Upload checks retain SVG; first-draw or resize errors dispose the renderer and end the passage before explicit SVG replay. Tests inject upload and framebuffer failures and check controls, visible fallback and cleanup. |
| Malformed model coordinates could reach rendering | A nonnumeric hinge coordinate produced nonfinite vertices while the browser still reported a WebGL flight. | Validate identifiers, coordinates, polygon area, input sizes, complete branches and generated finite geometry within the triangle budget. CPU tests cover damaged inputs; the browser verifies visible SVG recovery for a malformed hinge. |
| Fragment arithmetic exceeded minimum mobile precision | The old grain multiplied by 43758.5453; dot-product inputs could also exceed the guaranteed `mediump` range. This is source/specification evidence, not a reproduced phone failure. | Bound the grain inputs, match varying precision explicitly and clamp the edge term before squaring. Actual-render tests verify nonblank pixels, articulation and all 301 sampled poses after the shader change. Physical GPU validation remains outstanding. |
| Current main conflicted with validation | The merged Field Notes audio work changed the same static-site workflow. | Preserve audio's media-inspection tools, paths, model tests and syntax checks alongside the moth checks. Merge current main without changing the published recordings or listening implementation. |

## Verification

The expanded volume audit passes 218 checks at 320, 390, 768, 901, 1024 and 1440 pixels in both themes, using an actual WebGL context in Chromium SwiftShader. It includes the failures above, original blocked resources and rejected shader, actual context loss, reduced-motion entry, fractional and capped device-pixel ratios, preserved pause pixels without draws, static perch draw cessation, contact distance and complete restoration. A 301-pose readback has no empty or clipped poses. The original lifecycle suite passes 261 checks.

Generated editorial data and the model are current; site integrity and all 15 selected model tests pass. Phone and desktop flight/settle captures retain attached roots, separate paper/gravel surfaces and clear stationary questions. The PR's current-head workflow runs provide the remaining landing, journey, handling and cold-load integration evidence; their status belongs in the PR description rather than being inferred from older runs.

This evidence establishes the exercised browser paths. It does not establish every hardware GPU, mobile heat condition, frame rate or human comfort response. The original SVG and static question routes remain the recovery paths.

Primary precision reference: [OpenGL ES Shading Language 1.00, sections 4.5.2–4.5.3](https://www.khronos.org/files/opengles_shading_language.pdf). Implementation context: [WebGL best practices](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices).
