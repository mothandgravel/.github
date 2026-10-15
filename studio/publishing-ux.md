# Release handoff design study

Reviewed 15 October 2026 against official product documentation. These are patterns
from documented workflows; this was not an authenticated usability test of the products.

| Product | Documented pattern | Adaptation in this Studio |
|---|---|---|
| [Spotify for Creators](https://support.spotify.com/us/creators/article/publishing-a-saved-episode/) | Drafts expose title/description and a deliberate publish or schedule decision. | Provide the known copy first; keep recording publication explicit. We do not expose a scheduler without a publishing transport. |
| [Buzzsprout](https://www.buzzsprout.com/help/3-upload-audio) | Upload, add episode details, choose publication timing, then save; processing has a separate outcome. | A short Review → Package → Upload handoff, with saved production and publication records kept distinct. |
| [Descript](https://help.descript.com/export-and-share/youtube) | Its export panel exposes a destination alongside title, description, tags and export options. | Keep the destination near the package and the copy preview. Reuse known metadata; retain an explicit browser handoff. |
| [Transistor](https://transistor.fm/features/integrations/) | Connected destinations can handle distribution after initial setup. | Put the destination beside the completed package. Use a browser handoff until account-backed upload exists. |
| [Transistor API](https://developers.transistor.fm/) | Episode state, publication timestamp, sharing URL and YouTube URL are distinct fields. | Known podcast metadata is labelled with its source; a user-saved platform record takes precedence. A new link does not inherit an untouched date from a different destination. |

## Decision

Start with data we already have. The catalog supplies an episode link/date, and
publishing settings supply the title, description, tags, hashtags and disclosures.
Saved-edition verification supplies the music credit. None of those require a new
network service, model call or account connection.

The outer Release tab contains a compact, numbered handoff and two focused surfaces:
Upload details and Publication record. The latter keeps Save visible while form
content scrolls. Shared scrolling also serves Review, including keyboard focus reveal.
The controller handles intent and stale async responses; the application service
handles records; the pipeline adapter owns production metadata and verification.

## Trust and recovery

- Defaults come from this checkout and are not proof of current platform visibility.
- A saved override, including a blank value, is not replaced by an inferred value.
- Replacing a link clears a date that the user has not edited explicitly. Today is
  an action, not an assumed publication date.
- Copy refresh does not replace unsaved publication fields. Old episode responses
  cannot populate the selected episode.
- When a package exists, copy comes from its checksummed text files. This keeps the
  handoff consistent with the actual upload folder, including with older running
  workers. Export again and refresh to apply metadata changes. Copy checks do not
  claim to verify the package video or its human review.
- Opening YouTube Studio does not upload files or mark a job as published.

## Next question for a human session

Can someone take one existing episode through review, package inspection, copy/paste,
and recording its actual published URL without consulting a terminal or guessing which
date belongs to which destination?

Destination-specific multi-platform records, authenticated uploads and scheduling are
future integrations. No publishing status is simulated for those capabilities.

## Desktop design sprint

The critique found equal visual weight on primary and secondary actions, repeated
large headings, an unexplained search box, distant clipboard/save feedback and
little distinction between queue outcomes. The polish keeps the existing paper,
ink and brass palette, serif episode titles and native ttk controls.

| Benchmark or critique | Applied design decision |
|---|---|
| [Spotify's Details and Content checks](https://support.spotify.com/us/creators/article/publishing-audio-episodes/) separate preparation from publication. | Keep Produce, Review and Release focused; selected tabs use a dark surface and labelled pictograms. No inferred publication completion. |
| [Buzzsprout's short upload sequence](https://www.buzzsprout.com/help/3-upload-audio) gives each step a clear action. | Keep the three numbered release actions together, with a single brass browser handoff; approval and record saving have their own primary actions in their respective panels. |
| [Transistor's preparation checklist](https://transistor.fm/changelog/publishing-checklist/) makes missing requirements visible. Its linked screenshot illustrates an established pattern, not a verified current signed-in layout. | Show catalog suggestions, unsaved edits and saved-local records explicitly. Existing review checks remain explicit. |
| Actions lacked nearby feedback. | Copy changes briefly to a checkmark and “Copied”; Save confirms locally. Editing, selecting another field or refreshing cancels obsolete feedback. In-flight refresh and approval controls describe their work. |
| Dense controls competed for height. | Compact the application heading, soften borders, retain fixed footers and shorten queue commands. Minimum-window checks cover primary actions and feedback states. |
| Search and queue recovery were hard to scan. | Label search, report matches and explain empty results; Escape clears the query. Attention rows retain written status as well as color. |

Pictograms are original small stroke drawings rendered at the desktop scale, cached
per window and paired with text. No emoji, icon font, network assets or extra runtime
dependencies are needed. Hover, pressed and keyboard-focus states are shared styles.
The only timed effect is brief completion feedback; there is no decorative motion or
simulated progress. Timers cancel when a button is destroyed or its context changes.

These are design hypotheses backed by desktop layout and behavior checks. A human
episode-through-publication session is still needed to judge whether the handoff is
easier in practice. A screenshot or a green test does not establish that outcome.
