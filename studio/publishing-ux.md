# Release handoff design study

Reviewed 15 October 2026 against official product documentation. These are patterns
from documented workflows; this was not an authenticated usability test of the products.

| Product | Documented pattern | Adaptation in this Studio |
|---|---|---|
| [Spotify for Creators](https://support.spotify.com/us/creators/article/publishing-a-saved-episode/) | Drafts expose title/description and a deliberate publish or schedule decision. | Provide the known copy first; keep recording publication explicit. We do not expose a scheduler without a publishing transport. |
| [Buzzsprout](https://www.buzzsprout.com/help/3-upload-audio) | Upload, add episode details, choose publication timing, then save; processing has a separate outcome. | A short Review → Package → Upload handoff, with saved production and publication records kept distinct. |
| [Descript](https://help.descript.com/descript-tour/publish-tools) | Publishing preparation includes titles, descriptions and show notes after editing. | Reuse the existing deterministic copy generator, rather than asking for another title, summary or set of tags. Copy buttons sit beside a readable preview. |
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
