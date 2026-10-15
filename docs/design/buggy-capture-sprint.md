# A room, through several eyes

## Direction

The recorded continuation after the LiveConnect specimen was Ajo's missing-reply question. The owner supplied eight buggy captures and asked for a more inspired mapping/workbench sprint. This sprint uses the physical cardboard arena as the visual anchor and makes the evidence in the different views inspectable.

**One specimen:** Kitronik buggy camera and mapping captures.

**One decision:** keep the view's source beside the picture and expose its original detail without redrawing the readings.

**One next question:** which position or representation does a reader trust, and what would change their mind?

## Selection

All eight supplied images were inspected. The received date is 14 October 2026, not a verified capture date.

| Capture | Decision | Reason |
| --- | --- | --- |
| `python_vUVpIXIsH5(1).jpg` | Camera/physical anchor | The buggy, cardboard arena, scan rays and estimate marks connect the physical experiment to its software picture. The SCANNING label is clearer than the overlapping HUD in the alternative overlay. |
| `python_W3S0or6b6p(1).png` | Local-grid study | COVER_DRIVE, accumulated points, path, scan and an explicitly local grid create a concrete source-reading question. |
| `python_IZD2MetWJA(1).png` | Onboard-grid study | DRIVING and the explicitly onboard grid make another representation available. The dense point/pose cluster is interesting to inspect, not proof of a better or worse run. |
| `python_tmOgBT9L4G(1).jpg` | Retain as research | Less legible, overlapping HUD and less distinct scan-ray shape. |
| `python_AeKPOuJvMO(1).png` | Retain as research | A quieter NAV_DRIVE capture, but less useful than the selected local/onboard pairing for this specific question. |
| `python_cBN4pSwReW(1).png` | Retain as research | The COMPLETE label and dense coverage shape invite claims that the capture alone cannot establish. A separate completion/coverage study could use it. |
| `ApplicationFrameHost_fsDAclEGBq(1).png` | Retain as research | Split desktop and partial camera view compete for attention. |
| `python_o4ja74DMP3(1).png` | Telemetry follow-up | Unavailable rear reading and battery/status details concern a different question. They are not used to explain these mapping captures. |

## Critique and treatment

A contact sheet of tiny screenshots would make the evidence decorative. The study instead gives the physical setting one wide plate, then two separately labelled captures with native controls for whole capture, world map, current scan and grid. A fixed viewport keeps the controls and reading surface stable as the inspected region changes. Each source stays available at full resolution.

The screenshot colours, axes, values, labels and internal geometry are evidence. They remain intact. The original camera JPEG is copied byte-for-byte and stays linked. Its display uses responsive WebP delivery previews; the PNG maps are encoded as lossless WebP at their original dimensions, with decoded RGB identity verified. The visual tweaks are charcoal mounts, editorial hierarchy, framing, captions and accessible crop inspection. Camera delivery previews retain the complete frame at 960/1920 px and quality 90; these are compressed display derivatives, not pixel-identical evidence files. SVG viewBox/clip rectangles change the view, not the asset. There is no generated replacement imagery, recolouring, sharpening, fake telemetry or reconstructed map.

The two mapping images are different captures. They are not a timeline, a synchronized comparison, a paired benchmark or a repaired result. Their capture times, raw sessions, firmware revisions and calibration are not supplied. The inspected source confirms what the local/onboard title distinction means in that viewer, but does not bind the supplied images to an executable revision.

## Integration

The Kitronik card uses the new camera capture as its main image and leads to `/specimens/whose-map/`. Its native working record retains the older twelve-reading replay as a historical link. The existing related Field Note route and the surrounding specimen order remain intact.

Field Note 006 gains a clearly labelled visual addendum with camera and map imagery plus a route to the detailed study. The addendum follows the introduction, giving the new captures a visible entry before the original reading. It sits outside `article.note-prose`. The original narrated article bytes and published episode fingerprints remain unchanged. The conceptual cover and original offline replay retain their original scope. This is not a silent rewrite of an already published podcast episode.

The separate specimen gets its own canonical/social identity, studio/breadcrumb metadata and sitemap entry. The numbered Field Notes catalogue does not acquire a fictional new note. The supplied captures are recorded in `buggy-captures-provenance.json`, including original and exported hashes. The source/asset integrity check verifies the public files.

## Next observation

Ask a reader to locate unobserved space and explain which position they trust. Observe whether the source label and readable detail help them ask another view a useful question. Then preserve matched camera, pose and grid data from one run, with timestamps and calibration. Still images do not establish map accuracy, safe navigation, coverage, physical position or reader comprehension.

## Verification

The initial responsive run passed 546 checks across both appearances at 320/390/768/1440 px, plus JavaScript-free and failed-module reading. The first run found a dark-mount link inheriting the Afterlight accent; the mount now has an explicit light brass link. Review includes desktop grids and the phone page. Twenty-one existing model tests and generated/static checks pass. The original Field Note 006 narrated body was compared byte-for-byte with the base and is unchanged. Capture hashes and the maps' decoded RGB identity were checked before integration.

The working-copy inspection also clarified the colour distinction: world-point colours encode confidence; the occupancy grid uses a separate blue/neutral-grey/red scale. The public study explains that difference without repainting the source.

## PR 32 boundary audit

The end-to-end review found and fixed two interaction seams and one delivery gap:

- Browser Back restored a native radio selection after the module's initial render, leaving the selected label, crop and caption inconsistent. The study now reconciles them on `pageshow`, including returns from the Field Note and the full-resolution image.
- A failed map request left inspection controls over an empty plot. Controls now become available after the source decodes. Failure hides the empty viewport and controls, explains the retry route and retains the source link; the other capture remains usable.
- The new study was absent from the existing homepage performance gate. Three cold mobile runs of the study showed a 4052 ms median LCP and performance score 87. Responsive camera previews and high fetch priority reduce the same local measurement to 2402 ms LCP and score 97, with zero median TBT/CLS. The original JPEG and full-resolution maps remain unchanged and linked. The performance audit now separately measures and gates the study, while retaining the homepage’s existing budget.

The strengthened browser audit passed **600 checks with zero failures** in Chromium: both themes at 320/390/768/1440 px, all eight labelled detail views, keyboard and actual touch activation, stable viewport geometry, history restoration, image failure, module failure and JavaScript-free reading. It also checks the Field Note addendum's two decoded images, reflow and automated accessibility in every theme/width combination. Route entry from the workbench, source links and return anchors are exercised. Detail screenshots were visually reviewed for retained titles, axes and framing; the region rectangles are presentation crops of complete source files.

Original/export hashes, file sizes, dimensions and all three captures' decoded RGB pixels were independently checked against the supplied files. The narrated article was again compared byte-for-byte with base revision `045261d22abc6b11f3692cba9ba5b0b682b3893a`. Generated/static checks and JavaScript syntax checks pass. CI runs the expanded audit alongside the existing site, audio and performance gates.

This closes the reproduced interaction gaps within the tested scope. Firefox, Safari, physical-device operation, screen-reader announcements and human comprehension have not been verified by this Chromium/axe run. Capture timestamps, matched raw sessions, executable revisions and calibration remain unknown; the public record states those limits. Neither the audit nor the screenshots establish robot accuracy or safe navigation.
