# Pitch / Say what you don't know.

**Status: pitch, not a draft.** Nothing here is published. No note number yet: 015 is taken by
work in flight, so this gets a number only when the owner picks it. The reading edition, if
there is one, goes through `docs/notes/` and the catalog as usual. This file stays in `design/`.

## The angle

An interface that hides what it doesn't know still makes a claim. It's just one nobody checked.
This note follows a few small screens that say their limits out loud instead: "billing unknown",
"no local estimate", "missing is not zero", "link coming".
Each line costs a little polish and buys a reader the right to stop guessing.
The design question is how a limit can be stated plainly, near the number it qualifies, without
turning every screen into a disclaimer.

## Evidence from our own work

Everything below is shipped or recorded in this repository, apart from Vahti, which is desk
research only.

- **Field Notes studio: "billing unknown".** After the 17 October narration incident (a 502,
  then a 499, then timeouts across three runs), every paid narration or caption failure says
  **billing unknown**. It shows the attempt count for that part across runs, the episode total
  and the possible spend. It recommends stopping, and it never says to repeat the command.
  Sources: `studio/README.md` (Uncertain-spend guard and plain errors) and
  `studio/narration-502-incident.md`.
- **Uncertain-attempt counts.** The engine counts uncertain attempts, refuses further paid
  requests at 2 per part or 4 per episode in a rolling 24 hours, and names the count in the
  override itself: "Override once (N uncertain attempts…, billing unknown)". The uncertainty
  is counted and shown, never rounded to success or failure. Sources:
  `field_notes_audio/spend_guard.py` and `field_notes_studio/presentation/preparation.py`.
- **"no local estimate" (captions).** Caption attempts carry no local cost estimate. So in the
  inspection list, where a narration row says "up to about $…", a caption row says
  "no local estimate" instead of showing $0 or leaving a blank that reads as free. Sources:
  `field_notes_studio/preparation_jobs.py` and `field_notes_audio/captions.py`.
- **Vahti: "missing is not zero".** A gap in device readings is not a reading of zero.
  **Desk research only.** The note can discuss the principle and how the screens are designed.
  It can't show or describe device data unless that data has explicit provenance (which device,
  when, and who captured it).
- **"page coming" and "link coming" as honest limits.** On the homepage, two of the three
  standing questions are marked "01 / PAGE COMING" and "02 / PAGE COMING". In Made here,
  Cyber Grid is "Playable, link coming". Each status says what exists and what doesn't yet,
  instead of a dead link or a hidden row. Sources: `docs/index.html` and
  `docs/assets/made-here.mjs`.
- **Related, already published.** The Cyber Grid toy on the green-light page: "Running out is
  not a no." A search that runs out of steps reports that, not "no route".

## Which standing question

**03: What does a green light promise?** (`/investigations/green-light/`). The note is about
what a status line lets someone stop worrying about, and what it must not pretend to settle.
That is the green-light question, and the Cyber Grid "running out is not a no" toy already
sits there. Secondary link: **02, Did it happen, and can I take it back?** "Billing unknown"
is literally a "did it happen?" answer.

## Evidence still to capture

- **Studio screenshots** of a real uncertain attempt: the "billing unknown" failure row, the
  inspection list with one narration row (with an estimate) beside one caption row ("no local
  estimate"), and the override label with its count. These are captures of our own studio, with
  dates. Don't stage a new paid failure to get them. Use the October incident records, or a
  synthetic attempts log clearly labelled as one.
- **Vahti provenance decision:** whether Vahti may be named publicly (it isn't in Made here
  today), and whether any device capture with full provenance exists. Without that, the
  section stays a design study, with authored illustrations labelled as such.
- **"page coming" before and after.** The question 01 and 02 pages are being built now. Capture
  the homepage cards while they still say PAGE COMING, so the note can show the limit and its
  later resolution. Record the dates.
- **"link coming" for Cyber Grid:** confirm the status is still current at writing time.
- **A counter-example from our own work**, if one exists: a place where we showed a blank or
  a zero instead of "unknown", and what changed. Otherwise the note leans only on successes.

## Honesty rules for this note

No implied clients. No claims about other companies or studios. No compliance claims. No
prices: the dollar amounts in the studio's estimates are internal, so blur them or describe
them ("an estimate in dollars").
