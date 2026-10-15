# Prepare a written note

Open **Prepare new notes…** in the Studio header. This separate, read-only surface
shows written notes before their recordings exist. The main production shelf still
contains the recorded-episode catalog; existing production jobs and approvals are
unchanged.

The list joins `docs/assets/notes.json` to each episode's explicit
`publication.kind=note` / `publication.note_id` relationship. It does not guess the
next number, depend on a `note-013` literal, or mistake a workbench episode that
mentions several notes for a dedicated narration of each one. At the baseline main
commit `dd0f06a`, Coastal watch is Note 012 and *The work outlives the window* is Note
013 on the Studio branch. Future work should identify the note from the current
catalog rather than carry that number forward blindly.

## What the list establishes

| State | Meaning |
| --- | --- |
| Needs script | No dedicated episode registration, or its saved script is missing/empty. |
| Inspect script | A script file is present; it is not yet verified by this panel. |
| Needs repair | An ambiguous registration, unsafe path or missing article blocks inspection. |
| On production shelf | A recording is listed in the checkout's audio catalog. This is not a media-integrity or external-publication check. |

Select a scripted note and choose **Inspect script · no service request**. The
existing narration engine checks the source fingerprints, speakers, script and
request boundaries. The two tabs show the exact saved narration script and its
bounded request count, selected model/endpoint, planning pace and approximate
spoken duration. Saved settings are read locally; there is no credential lookup,
project discovery, tool installation or Cloud resource preparation.

A source/settings change during the read rejects the result. Switching notes,
refreshing or encountering an error clears the displayed script and snapshot.
Closing the window discards the inspection; it is not an approval and is not
restored as one. One background read runs at a time, and late results never update
a different selection or a closed window.

## Deliberate stopping point

**This panel does not execute narration or captions yet.** It also does not create
or edit scripts, resolve uncertain remote requests, adopt local caption outputs,
or update the public recording catalog. Local recordings not registered in that
catalog may already exist; the panel explicitly does not classify them as absent.
No service cost or media approval is inferred from an offline plan.

The next implementation must use a durable, explicitly authorized preparation job
with captured script/settings identity, existing uncertain-outcome handling and
safe-boundary cancellation. It must inspect/reuse saved narration and caption jobs
before submitting anything remotely, keep credentials out of the journal, and
adopt a prepared recording locally without treating adoption as publication.

## Release rehearsal: identify the note, not its historical number

Use the current catalog entry titled **The work outlives the window** as the
rehearsal specimen. Record the resolved note ID and source identity at the start.
The complete rehearsal is still pending: inspect and authorize narration; obtain
and check the captions; bring the recording into the production shelf; produce;
listen/watch and approve the exact media; export; inspect the upload package; then
complete the manual browser handoff and explicitly record the actual destination.

Automated fixtures can establish selection safety and layout, not human listening
quality or a successful platform publication. Do not mark those steps complete
from fixture screenshots, a generated package or a saved URL.
