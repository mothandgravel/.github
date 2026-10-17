"""``python3 -m field_notes_studio make-episode``: the Make episode flow without a window.

The same summary, consent and run as Studio's Make episode, so an agent or a
terminal works under exactly the rules a person sees:

- Without ``--confirm`` it only inspects: it prints the paid steps with the local
  estimate, the local steps, what is reused for free, the spend guard and the
  summary's digest. Nothing is sent or queued.
- ``--confirm DIGEST`` starts the run only when DIGEST equals the digest of a
  summary built afresh at that moment. Any change since (files, saved work, a
  new uncertain attempt, the spend guard) changes the digest, and nothing starts.
- There is deliberately no override and no resend option. A summary with an
  uncertain part or a reached spend-guard limit is blocked here exactly as in
  Studio; those keep their own consent on the expert path. Every paid request
  still goes through ``spend_guard.reserve()`` inside the engine, and a run never
  retries a paid step.
- ``--status`` prints the episode's open run timeline (read-only).
"""

from __future__ import annotations

import re
import sys

DIGEST = re.compile(r"[0-9a-f]{64}")
TAGS = {"paid": "Paid", "local": "Local", "you": "You", "reused": "Reused, free"}


def target(identifier: str) -> dict:
    """A written-note number (014) or an episode id (maritime-study)."""
    if re.fullmatch(r"\d{3,}", identifier):
        return {"note": identifier}
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier):
        return {"episode": identifier}
    raise ValueError("Give a note number such as 014 or an episode id such as maritime-study")


def summary(plan) -> str:
    """The pre-flight summary as text: the same facts as Studio's dialog."""
    name = f"Field Note {plan.note}" if plan.note else plan.episode
    lines = [f"Make {name} into an episode" + (f" · {plan.title}" if plan.title else "")]
    details = []
    if plan.words:
        details.append(f"{plan.words:,} words")
    details.append(f"show settings: {plan.recipe_label}")
    lines += ["  " + " · ".join(details), "", "What will happen:"]
    width = max(len(step.name) for step in plan.steps)
    for step in plan.steps:
        lines.append(f"  {step.name:<{width}}  {TAGS[step.kind]:<12}  {step.detail}")
    lines += [
        "",
        "Reused if already saved: " + (", ".join(plan.reused) or "nothing yet") + ".",
        "",
        "Cloud spending:",
        f"  Project: {plan.project or 'none needed'}",
        f"  Estimate: {plan.estimate_text}",
        "  " + plan.spend.limits,
        "  " + plan.spend.sentence(),
    ]
    lines += [
        f"    {a.when} · {a.part} · {a.detail} · billing unknown · {a.estimate}"
        for a in plan.spend.attempts
    ]
    lines.append("  Failed attempts may still be billed; nothing retries a paid step on its own.")
    if plan.blockers:
        lines += ["", "Can't start yet:"] + [f"  - {blocker}" for blocker in plan.blockers]
    lines += ["", f"Digest: {plan.token}"]
    return "\n".join(lines)


def timeline(view, cost: str) -> str:
    lines = [f"{view.episode} · started {view.started} · {view.headline}"]
    if view.detail:
        lines.append("  " + view.detail.replace("\n", "\n  "))
    width = max(len(row.name) for row in view.rows)
    lines += [f"  {row.name:<{width}}  {row.state:<12}  {row.detail}" for row in view.rows]
    lines += ["", cost]
    return "\n".join(lines)


def run(studio, identifier: str, *, confirm: str | None, status: bool, out=None) -> int:
    out = out or sys.stdout
    chosen = target(identifier)
    if status:
        episode = chosen.get("episode") or studio.make_plan(**chosen).episode
        view = studio.runs().run_for(episode)
        if view is None:
            print(f"No open Make episode run for {episode}.", file=out)
            return 1
        print(timeline(view, studio.cost_line(episode)), file=out)
        return 0
    plan = studio.make_plan(**chosen)
    if confirm is None:
        print(summary(plan), file=out)
        if plan.blockers:
            return 1
        print(
            "\nNothing was sent or queued. To start exactly this, run:\n"
            f"  python3 -m field_notes_studio make-episode {identifier} --confirm {plan.token}",
            file=out,
        )
        return 0
    if not DIGEST.fullmatch(confirm):
        raise ValueError("--confirm needs the full 64-character digest printed by the summary")
    if studio.consent_used(plan.episode, confirm):
        raise ValueError("This digest was already used; run without --confirm for a new summary.")
    if confirm != plan.token:
        raise ValueError(
            "The digest does not match the summary as it is now: something changed since it "
            "was printed (files, saved work or the spend guard). Nothing was queued; run "
            "make-episode again without --confirm to see the new summary."
        )
    if plan.blockers:
        raise ValueError(plan.blockers[0])
    # The digest covers the paid steps shown, so it is the consent to them; it never
    # covers an uncertain resend or an override (those block the summary above).
    run_id = studio.make_episode(plan, plan.paid)
    print(
        f"Started Make episode run {run_id} for {plan.episode}. Nothing is published; you "
        f"review first. Follow it with: python3 -m field_notes_studio make-episode "
        f"{identifier} --status",
        file=out,
    )
    return 0
