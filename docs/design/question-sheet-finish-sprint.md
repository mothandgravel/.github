# A question with a little shape

The question sheet already asks the right things. Its presentation made two
moments harder to read: the local-only boundary moved below the form on narrow
screens, and the finished brief presented keeping, revising and exploring as
one cluster of competing actions.

This sprint gives that passage the studio's existing light and handling:

- A short boundary before the first prompt: a brief to keep, nothing sent;
  only the starting question needs words.
- A still progress line beside the existing numbered stage. It is decorative;
  the text names the stage. No new navigation or moving questions.
- A paper plane for the editable brief, with download and copy first, revision
  below, then a separately introduced fictional workbench.
- Visible feedback beside keeping, handoff and clearing, with one polite live
  region. Source controls locate messages even when clicks do not move focus.
- The public GitHub route names its public nature in the link itself.

Answers, limits, literal links, browser history, the explicit session-storage
handoff and the fictional mending study keep their existing contracts. No
server submission or private enquiry is introduced. The complete native
question sheet and optional disclosures remain available if the module fails
or JavaScript is disabled. Narrow native navigation keeps its links visible and
hides unpowered menu and theme controls. The synchronous JavaScript marker
keeps that fallback from flashing open before normal deferred navigation starts;
a script error explicitly activates it. The loading audit delays and blocks
the site script to cover both paths. Cached older HTML still works with the shared module;
the new progress element is optional to that module.

## Review evidence

`scripts/audit_loose_end.mjs` covers five widths (320–1440 px), both themes,
required-answer focus, optional material, edited brief preservation, exact text
exports, browser history, clear, hostile input, explicit local handoff, denied
storage, copy success and failure, and native fallbacks. New checks assert the
progress endpoints and action-local feedback, including unfocused clicks.

The shared module also requires `audit_workbench_finish.mjs`,
`audit_thread.mjs` and `audit_reading.mjs`: feedback routing must preserve the
room, and editorial entrances must preserve the visitor's literal draft.
Screenshots and axe results are retained by the existing browser CI.

The question page joins the existing cold-load CI: three runs per mobile and
desktop profile, median FCP ≤1800 ms, LCP ≤2500 ms, TBT ≤200 ms, CLS ≤0.1,
performance ≥90 and technical SEO ≥95. The homepage's 1000 ms FCP budget stays.
These are lab checks, not evidence of enquiries or human comprehension.
