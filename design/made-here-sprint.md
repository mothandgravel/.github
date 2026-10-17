# Made here, a Workbench playground and standing investigations: concepts

This sprint covers three additions:

- a **Made here** section;
- a real **Workbench playground**;
- named **standing investigations**.

This document holds concepts only, and the owner picks one before anything is built. No published page changes. The prototypes live in `design/prototypes/made-here-sprint/`, outside `docs/`, so GitHub Pages never serves them. Every prototype page also carries `noindex, nofollow`. None of them is in the sitemap or the navigation.

**To view the prototypes:**

1. From the repository root, run `python3 -m http.server 8790 --bind 127.0.0.1`.
2. Open `http://127.0.0.1:8790/design/prototypes/made-here-sprint/`.
3. After editing, rebuild with `python3 design/prototypes/made-here-sprint/build.py`.

The three home variants are generated from the live `docs/index.html`, with exactly one inserted block each. Everything around that block is the current home, byte for byte apart from the paths.

## Binding decisions applied

- **Studio:** one studio and one body of work. Everything made under the owner's GitHub organisations is presented as Moth & Gravel's own work. No organisation name appears on any prototype page. Product names stay as they are: Decision Docket, Raivari, Cyber Grid, SkyStack Builder and the rest.
- **Workbench:** the fictional mending notebook stays exactly as it is. The playground is a second room beside it, at a proposed `/workbench/playground/`, and the notebook is linked as room 01.
- **Decision Docket:** framed as "our own tool, in production for our own work". It is shown only through authored, fictional items, with no product or pricing language.
- **Excluded:** Vesuno, Cockpit and any price. The home page's existing `owner: duration/price pending` HTML comment is stripped from the prototype copies. It remains in the live source.
- **Standing identity:** the Menu sheet, its items and the Night/Afterlight switch are unchanged on every page.

## Critique of the current structure

1. **One word, two places.** The masthead's "Workbench" link goes to `#work` (Working specimens). Meanwhile `/workbench/` is the fictional example study. A playground called "the Workbench playground" would make this collision worse. It breaks [NN/g heuristic 4, consistency and standards](https://www.nngroup.com/articles/ten-usability-heuristics/), and the label's [information scent](https://www.nngroup.com/articles/information-scent/) points to two different things. None of the concepts change the menu, so this stays an owner question (Q1).
2. **Nowhere says what exists.** The home page shows questions (services), writing (Field Notes) and evidence (specimens), but a visitor cannot answer "what has this studio made, and can I use any of it?" The single playable product, Cyber Grid, is not mentioned. Specimens are deliberately partial, so their status is scattered across captions and disclosures. Each concept gives every project a one-line status in a fixed vocabulary, closer to [recognition over recall](https://ui-patterns.com/patterns/Recognition-over-recall) than reading six captions.
3. **Topics carry almost no scent.** Ten of the fourteen notes have exactly "Interface · Interaction · Making". The archive's topic filter therefore separates almost nothing. Tags only help when they differentiate ([ui-patterns: Tagging](https://ui-patterns.com/patterns/Tag), [Categorization](https://ui-patterns.com/patterns/categorization)). The standing investigations are the facet the archive is missing.
4. **The thread is already an investigation.** "Something happened. I can't tell what." (`/threads/something-happened/`) runs through LiveConnect, Ajo and note 005, which is the shape a standing investigation needs. It is a one-off, though: you can only reach it from one aside on the home page and one in the archive. Concepts A and B both grow investigations out of this pattern rather than inventing a new one.
5. **The home page's density lives in disclosures.** The home page already uses many `<details>`: the stack, specimen records, studio answers and the drawer. [Progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/) works when the primary layer stands alone. A twelve-row Made here list must therefore be readable without opening anything, and none of the concepts hides a status behind a disclosure. Accordion guidance ([uxpatterns.dev: Accordion](https://uxpatterns.dev/patterns/content-management/accordion)) warns against hiding content people need to compare. That is why concept C's drawers live on a subpage, not on the home page.
6. **The budget leaves no room on the home page.** Home first paint sits at about 1,092 ms against the 1,100 ms mobile budget. Every concept therefore keeps scripts off the home page. The inserted blocks are static HTML and CSS, and all three toys load only on playground and investigation pages, when scrolled into view.

## The three concepts

### A / The ledger: the things come first

- **Home:** a new "Made here. *Said plainly.*" section sits before Field Notes. It is a twelve-row ledger with four columns: the name, one honest line, a status and the questions the project keeps asking. A legend explains the five statuses. The rows are not cards, because they need to be compared ([uxpatterns.dev: List View](https://uxpatterns.dev/patterns/data-display/list-view), [Comparison Table](https://uxpatterns.dev/patterns/data-display/comparison-table)).
- **Playground:** `/workbench/playground/` holds all three toys on one bench. It has room tabs, with the notebook as room 01.
- **Investigations:** light collection pages, one per question, listing the things made here, the field notes and the specimens. They work like an [Archive](https://ui-patterns.com/patterns/Archive) filtered by question. Notes and specimens hang off them only as links.
- **Voice:** an inventory, said plainly. It tells a visitor the most in the fewest clicks.

### B / Standing questions: the questions come first

- **Home:** a new "Three questions. *Still open.*" section sits after Field Notes. It holds three large question cards. Each card shows how many notes and specimens it gathers, and the things made here that ask it. A fourth question is shown as "forming", with one note so far. "Made here" appears as a compact three-column roll beneath: name and status only.
- **Investigations:** an index page, plus one thread-style page per question that reuses `thread.css`. Each page opens with its toy ("Try it first"), then states what we keep separate, then walks through every project that asks the question, with its status. It ends with the notes, the specimens and "your version".
- **Playground:** the same three toys gathered on one bench, each labelled with its question.
- **Voice:** most like the Field Notes. The studio's thinking becomes the navigation.

### C / The open drawer: hands on first

- **Home:** no new section. The Working specimens section grows two pieces before the existing studio-status ledger:
  - an "Also on *the shelf.*" list, two columns of name, status and one line;
  - two room doors: room 01, the mending notebook; room 02, the playground.
- **Playground:** the investigations live here, as drawers. Each drawer is a native `<details>` holding the question, a toy, and "the notes behind it": the things that ask it, the notes and the specimens. The first drawer is open by default. Drawer 04 is empty and says why.
- **Pages:** C has no separate investigation pages. It is the smallest change to the IA.
- **Voice:** playful and tactile. It is the closest match to "Less presentation. More making."

## Comparison

| | A / The ledger | B / Standing questions | C / The open drawer |
|---|---|---|---|
| **Strengths** | It answers "what have you made?" at once. The status vocabulary is the most honest single surface. Each row is short. The investigation pages are cheap to build. | It is the most distinctive: questions as navigation, not a portfolio. It gives the archive its missing facet and scales as notes accrue. The toys sit inside an argument, so the scope of each toy is clearest here. | It is the smallest home-page change, with no new section and no renumbering. The playground becomes a real destination beside the notebook. Toys and notes are filed together. |
| **Risks** | It is the longest home addition: about 3,500 px tall at 390 px wide. A ledger can read like a client portfolio if it grows. The investigation pages are thin and may feel like tag pages. | It is the most new IA: an index and three pages, each needing upkeep. It sits close to the existing thread aside, so the two must be reconciled. Its "Made here" is terse and could look like an afterthought. | The investigations are hidden inside one subpage: no URL per question, so they are hard to cite or link from notes. Drawers hide content until opened. "Also on the shelf" sits low on the home page. |
| **Home first paint** | Static HTML and CSS only, but the most bytes, and it needs a cold-load measurement. | Static, medium. | Static, smallest. |
| **Effort to build** | M: home block, playground, four collection pages, and archive facets if wanted. About 2–3 days with checks. | L: home block, index, three thread pages, playground, thread reconciliation, and catalog fields for `investigation`. About 4–5 days. | S–M: home block and one playground page. About 1.5–2 days. |

All three need the same follow-up work:

- inline the new home CSS through the existing home builder;
- add `investigations` to `notes.json` and validate it in `check_site.py`;
- run the browser audits;
- run Lighthouse against the 1,100 ms budget.

The effort figures are planning estimates, not commitments.

## Recommendation

**Build B's spine with A's ledger copy, and ship it in two steps.**

1. **First step:** A's ledger as the home section, unchanged, because it answers the question the home page currently can't. Add the B-style investigation pages, but only for "What does a green light promise?", built from the existing thread pattern and opening with the Cyber Grid solver. Add the playground as room 02, with the stamp toy and the solver.
2. **Second step:** add the other two investigation pages and the Docket week toy. Promote investigations to an archive facet once each question has at least three notes.

If the owner wants a single concept unchanged, pick **B**. It does the most for the site's distinctiveness. The extra effort goes into pages that compound as notes are added.

## Copy (studio voice)

The prototypes use the copy below. It is calm and concrete, and every status is stated plainly.

**Status vocabulary:**

- In production for our own work
- Playable today
- Prototype
- Study
- Internal tool

**Made here:**

| Name | Status | Line |
|---|---|---|
| Decision Docket | In production for our own work | A workspace for the decisions and evidence behind software work. Our own tool, in production for our own work. *Shown with synthetic captures only. The real workspace holds private work.* |
| Cyber Grid | Playable today | A daily logic puzzle: visit every node once, in jumps. Each day's board is checked for a route before anyone plays it. |
| Raivari | Prototype | The framework under our maritime study and Coastal watch. |
| Ajo | Prototype | Checked plans for agents, with their execution recorded. A lost reply is not a no. |
| SkyStack Builder | Prototype | An island builder for Windows. One intended gesture should come back with one undo. |
| Geaidnu | Prototype | A calm cockpit for work in progress. A finished task is not yet a proven one. |
| LiveConnect | Study | A streaming study, parked. The connection came back; did the picture? |
| Kitronik buggy | Study | A small robot in a cardboard arena, and the maps it leaves behind. |
| raivari-rpc | Study | An exploration of host and agent. An agent may ask; the host decides. |
| flutter-test-rs | Prototype | A Flutter test runner that minds the machine it runs on. |
| paja | Internal tool | Spare machines on one network, building together. |
| Field Notes studio | In production for our own work | The desktop workbench that makes the recordings of these notes. |

**Investigations.** The leads are in `build.py` (`INVESTIGATIONS`).

| No. | Question | Things made here that ask it | Status |
|---|---|---|---|
| 01 | How old is what I'm seeing? | Raivari (maritime study, Coastal watch), LiveConnect, Decision Docket, Kitronik buggy | standing |
| 02 | Did it happen, and can I take it back? | Ajo, SkyStack Builder, Decision Docket, raivari-rpc, paja | standing |
| 03 | What does a green light promise? | Geaidnu, flutter-test-rs, Decision Docket, Cyber Grid, plus note 005 | standing |
| 04 | What survives closing the window? | note 013 only | forming: "it becomes a standing question when a second piece of work asks it" |

## The toys

All three toys are vanilla ES modules. A small `lazy.js` loads each one with IntersectionObserver when its bench approaches the viewport. None of them uses canvas, and there is no dependency.

**Controls and accessibility, common to all three:**

- Controls are native radios in a `fieldset` with a `legend`, `select`s and buttons, with 44 px targets.
- Cells use roving tabindex with arrow keys and Enter.
- Results go to a polite status region.
- There is no animation, so reduced motion needs no special path; a reduce rule is included anyway.

**SkyStack, "One gesture. One undo."** (`stamp.mjs`, 9.5 KB raw / 3.4 KB gzip)

- The stamps are single, 2 × 2 platform, a three-cell line and a three-cell run.
- The whole proposal is checked before anything is spent: water, something already standing, the height limit and blocks in hand.
- A placement is one history entry. Undo checks that each placed block is still on top, and otherwise reports "Undo failed … the history entry stays".
- "Let the wind take one block" demonstrates that refusal.
- The toy is a rules sketch written from the Field Note 008 source study. It uses no game code or art.

**Cyber Grid, "Can this board be finished?"** (`grid.mjs`, 9.9 KB raw / 3.6 KB gzip)

- It is a 5 × 5 reduction. It ports the game's jump rule (three straight or two diagonal), the shape checks and the route search, with fewest-exits ordering and a node budget.
- It gives four verdicts:
  - ruled out before searching;
  - a route exists, with every jump numbered so it can be checked;
  - no route, after an exhaustive search;
  - no answer yet, when the budget runs out: "That is not a no."
- The game treats the last two the same way, conservatively. The toy separates them, because that distinction is the investigation.
- Presets show each verdict. A 40-step budget makes the third preset run out.
- Visitors can also try a route by hand.

**Decision Docket, "The same week, two shapes."** (`week.mjs`, 6.9 KB raw / 2.6 KB gzip)

- Six authored fictional items with synthetic revisions, drawn as a river and as a circle, following the Docket Recap prototype's vocabulary: captured source, person-authored decision, "Merged · not verified" and waiting on you.
- The list is the interface. The SVG is `aria-hidden` and only follows the list.
- It uses no repository, people or private data.

## Verification

All checks ran on 17 Oct 2026 against the local server.

- **Screenshots:** 9 views × 1440/390 × Night/Afterlight, 36 captures, on the orphan branch `evidence/made-here-sprint`.
  - Home captures crop to the inserted block.
  - Subpages are full-page.
  - Capture-only CSS makes the sticky header static and hides the skip link, which Playwright's full-page capture otherwise paints. In a normal viewport the skip link stays off-screen, which was checked.
- **Errors and overflow:** no page errors, no console errors and no horizontal overflow at either width in either theme.
- **Keyboard and logic, checked with Playwright:**
  - placing a stamp with arrows and Enter;
  - Undo refusing after the wind;
  - a refusal when the proposal touches water;
  - all four solver verdicts;
  - choosing a week item by keyboard.
- **Published site:** `python3 scripts/check_site.py` passes, and `docs/` is unchanged.
- **Not done:**
  - axe and Lighthouse runs, because no home page or published page changes;
  - comprehension sessions with people.

These checks show the prototypes work. They do not show that visitors understand them.

## Questions for the owner

1. **Menu.** The menu's "Workbench" item points to the specimens section (`#work`). Once a playground exists, should the item point to `/workbench/` with two rooms, and should Working specimens be relabelled? None of the concepts touches the menu.
2. **Cyber Grid link.** Should the site link directly to the live Cyber Grid on its Cloud Run address? The game has leaderboards and telemetry, so the link would need a privacy line or a nicer domain first. The prototypes include the link.
3. **Statuses.** Are Geaidnu (shown as Prototype), paja (Internal tool) and the Field Notes studio (In production for our own work) stated correctly? Is "Study (parked)" right for LiveConnect?
4. **The thread page.** In concept B, should "Something happened. I can't tell what." become investigation 02's page, keeping its URL as a redirect, or stay as a separate essay?
5. **Investigation 04.** Should "What survives closing the window?" appear as "forming", or be held back until a second piece of work asks it?
6. **Studio voice.** With all orgs under one umbrella, is "Made here" the right phrasing, or should it be "Made at this bench" or "Our own work"?
