"""Make episode pre-flight: what will happen, what it may cost, and the one consent.

Read-only until ``start``. The summary is built from the same preparation
inspection the expert path uses, plus the engine's attempts log, so it shows:

- the paid steps (narration parts and captions) with the local estimate,
  separated from the local steps and from the saved work that is reused for free;
- the spend guard: its limits and every uncertain paid attempt in its window.

The single consent covers exactly the captured preparation request on display and
the local steps after it. It never covers an uncertain resend or a spend-guard
override: a summary with an uncertain part or a reached limit is blocked here, and
the request it captures can contain neither (``FORBIDDEN``). Those keep their own
consent on the expert path. At run time every paid request still goes through
``spend_guard.reserve()`` inside the engine.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime

from field_notes_audio import spend_guard
from field_notes_studio.make_models import Attempt, MakePlan, PlanStep, SpendState
from field_notes_studio.preparation_jobs import PreparationJobs
from field_notes_studio.readiness_models import plain

# Request keys only the expert recovery path may set, each behind its own consent.
FORBIDDEN = frozenset({"uncertain_chunks", "spend_override", "resume"})
ACTIVE = {"queued", "running", "waiting"}


def money(value: float | None) -> str:
    if value is None:
        return "no local estimate"
    if value < 0.01:
        return "under $0.01"
    return f"about ${value:.2f}"


def minutes_text(seconds: list[float]) -> str:
    """ "6–9 min on this computer before", only from measured history."""
    if not seconds:
        return ""
    low, high = min(seconds) / 60, max(seconds) / 60
    if high < 1:
        return "under a minute on this computer before"
    if round(low) == round(high):
        return f"about {max(1, round(high))} min on this computer before"
    return f"{max(1, round(low))}–{round(high)} min on this computer before"


def recipe_label(recipe: dict) -> str:
    sound = recipe.get("sound") or {}
    parts = [f"Pace {float(recipe['speed']):g}×"]
    mode = sound.get("music_mode")
    intro = sound.get("intro_seconds")
    if mode == "motif":
        parts.append("motif intro")
    elif mode == "file":
        parts.append("music file")
    elif mode == "none":
        parts.append("no music")
    if intro is not None and mode != "none":
        parts[-1] += f" ({float(intro):g} s)"
    parts.append(f"{float(recipe['outro']):g} s outro")
    if sound.get("target_lufs") is not None:
        parts.append(f"{float(sound['target_lufs']):g} LUFS".replace("-", "−"))
    return ", ".join(parts)


def spend_state(root, episode: str, parts: list[str]) -> SpendState:
    """The guard as it stands for the parts this run would request (read-only)."""
    audio_root = root / "artifacts/audio"
    tallies = [spend_guard.tally(audio_root, episode, part) for part in parts or ["captions"]]
    worst = max(tallies, key=lambda t: (t.blocked, t.part_window))
    attempts = tuple(
        Attempt(
            a.at.astimezone().strftime("%d %b %H:%M"),
            spend_guard.part_label(a.part),
            a.detail or "no outcome recorded",
            money(a.estimate_usd) if a.estimate_usd is not None else "no local estimate",
        )
        for a in worst.attempts
        if a.outcome == spend_guard.UNCERTAIN
    )
    return SpendState(
        limits=spend_guard.limits_text(worst.limits),
        part_limit=worst.limits.part,
        episode_limit=worst.limits.episode,
        window_hours=worst.limits.window_hours,
        episode_window=worst.episode_window,
        part_window=worst.part_window,
        possible=worst.spend_text(),
        attempts=attempts,
        blocked=any(t.blocked for t in tallies),
        guard_token=worst.token,
    )


def token(plan: MakePlan) -> str:
    """Digest of every fact the person consents to; any change needs a fresh look."""
    facts = {
        "episode": plan.episode,
        "note": plan.note,
        "steps": [[s.key, s.kind, s.detail] for s in plan.steps],
        "estimate": plan.estimate_usd,
        "request": hashlib.sha256(plan.request_json.encode()).hexdigest(),
        "spend": [
            plan.spend.episode_window,
            plan.spend.part_window,
            plan.spend.part_limit,
            plan.spend.episode_limit,
            plan.spend.window_hours,
            plan.spend.guard_token,
        ],
        "reused": list(plan.reused),
        "recipe": [list(item) for item in plan.recipe],
        "blockers": list(plan.blockers),
    }
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()


def _note_for(adapter: PreparationJobs, episode: str) -> str:
    for item in adapter.preparation.catalog():
        if item.episode == episode:
            return item.note
    return ""


def build(studio, *, note: str = "", episode: str = "") -> MakePlan:
    """Inspect a written note or a narrated episode; never sends or queues anything."""
    root = studio.root
    adapter = PreparationJobs(root)
    ready = adapter.ready_episodes()
    snapshot = None
    if note:
        snapshot = adapter.inspect(note)
        episode = snapshot.episode
    elif episode not in ready:
        note = _note_for(adapter, episode)
        if not note:
            raise ValueError("Choose a written note or a narrated episode to make.")
        snapshot = adapter.inspect(note)
    prepared = episode in ready
    inputs = studio.recipe_inputs(episode)
    blockers: list[str] = []
    reused: list[str] = []
    steps: list[PlanStep] = []
    estimate: float | None = 0.0
    paid_parts: list[str] = []
    captions_minutes = 0.0
    request_json = ""
    title, words, project = "", 0, ""

    if prepared and snapshot is None:
        entry = studio.pipeline.source(episode)
        title = entry["title"]
        captions_minutes = float(entry.get("duration_seconds") or 0) / 60
    if prepared:
        reused += ["narration", "captions"]
        steps += [
            PlanStep("narrate", "Narrate", "Saved narration is reused; no charge", "reused"),
            PlanStep("caption", "Caption", "Saved subtitles are reused; no charge", "reused"),
        ]
    if snapshot is not None:
        title, words, project = snapshot.title, snapshot.word_count, snapshot.project
        captions_minutes = captions_minutes or snapshot.minutes
    if snapshot is not None and not prepared:
        missing = snapshot.parts_total - snapshot.parts_saved
        if snapshot.recording_saved or missing == 0:
            reused.append("narration")
            steps.append(
                PlanStep(
                    "narrate",
                    "Narrate",
                    f"All {snapshot.parts_total} parts are saved; reused, no charge",
                    "reused",
                )
            )
        else:
            detail = f"{missing} of {snapshot.parts_total} parts with the cloud voice"
            if snapshot.parts_saved:
                detail += f"; {snapshot.parts_saved} saved parts reused"
                reused.append(f"{snapshot.parts_saved} narration parts")
            steps.append(PlanStep("narrate", "Narrate", detail, "paid"))
            estimate = snapshot.narration_estimate_usd
            paid_parts += [f"narration-{index}" for index in snapshot.missing_parts]
        if snapshot.captions_status == "complete":
            reused.append("captions")
            steps.append(
                PlanStep("caption", "Caption", "Saved subtitles are reused; no charge", "reused")
            )
        else:
            steps.append(
                PlanStep(
                    "caption",
                    "Caption",
                    f"Timed subtitles from the narration, about {snapshot.minutes:.0f} min",
                    "paid",
                )
            )
            paid_parts.append("captions")
        if snapshot.uncertain_parts:
            blockers.append(
                "Narration part "
                + ", ".join(snapshot.uncertain_parts)
                + " has an earlier attempt with no saved result, and billing is unknown. "
                "Sending it again can charge twice, so it needs its own consent: use "
                "More options… → Check recovery. Make episode never resends it."
            )
        blockers.extend(snapshot.blockers)
        if snapshot.spend_blocked:
            blockers.append(
                "The spend guard has reached its limit for this episode, so Make episode "
                "sends nothing. Stop and wait; the limit lifts as attempts age out."
            )
        request_json = snapshot.request_json
        if not request_json and not blockers:
            blockers.append(
                snapshot.summary.split("\n", 1)[0]
                if "No service request was made" in snapshot.summary
                else "Preparation could not be captured. Open More options… → Prepare."
            )
        if request_json and FORBIDDEN & set(json.loads(request_json)):
            blockers.append("The captured request carries a recovery or override; refused.")
    paid = any(step.kind == "paid" for step in steps)
    if not paid:
        request_json = ""
    steps += [
        PlanStep("sound", "Finish sound", recipe_label(inputs), "local"),
        PlanStep("video", "Make video", "Full video and thumbnail", "local"),
        PlanStep("review", "Your review", "Watch once, check subtitles, approve", "you"),
        PlanStep("package", "Upload package", "Made automatically after you approve", "local"),
    ]
    if any(job.episode == episode and job.status in ACTIVE for job in studio.repository.jobs()):
        blockers.append("This episode already has work in progress. Open it from the work list.")
    try:
        if prepared:
            request = studio.pipeline.request(
                episode, "video", inputs["speed"], inputs["outro"], inputs["sound"], inputs["base"]
            )
            studio.pipeline.preflight(episode, "video", request)
        else:
            studio.pipeline.tools_check(full_video=True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        blockers.append(
            "Video can't be made on this computer yet, so nothing paid is started: "
            + plain(exc, "preflight")
        )
    spend = spend_state(root, episode, paid_parts)
    plan = MakePlan(
        episode=episode,
        note=note,
        title=title,
        words=words,
        checked_at=datetime.now().astimezone().strftime("%H:%M"),
        recipe_label=recipe_label(inputs),
        steps=tuple(steps),
        spend=spend,
        reused=tuple(reused),
        blockers=tuple(dict.fromkeys(blockers)),
        project=project,
        estimate_usd=estimate if paid else None,
        captions_minutes=captions_minutes,
        request_json=request_json,
        recipe=tuple(
            sorted((key, json.dumps(value, sort_keys=True)) for key, value in inputs.items())
        ),
    )
    return replace(plan, token=token(plan))


def consent_record(plan: MakePlan) -> dict:
    """What the run keeps as evidence of the one confirm."""
    return {
        "token": plan.token,
        "title": plan.title,
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "paid_steps": [s.name + ": " + s.detail for s in plan.steps if s.kind == "paid"],
        "local_steps": [s.name for s in plan.steps if s.kind == "local"],
        "reused": list(plan.reused),
        "estimate_usd": plan.estimate_usd,
        "spend_guard": {
            "limits": plan.spend.limits,
            "uncertain_in_window": plan.spend.episode_window,
            "token": plan.spend.guard_token,
        },
        "request_sha256": hashlib.sha256(plan.request_json.encode()).hexdigest()
        if plan.request_json
        else "",
        "covers": "the displayed preparation request and the local steps after it; "
        "never an uncertain resend or a spend-guard override",
    }


def captured_request(plan: MakePlan) -> dict:
    """The preparation request the consent covers; refuses anything it does not cover."""
    request = json.loads(plan.request_json)
    if not isinstance(request, dict) or FORBIDDEN & set(request):
        raise ValueError(
            "An uncertain resend or a spend-guard override needs its own consent; "
            "Make episode cannot send it. Nothing was queued."
        )
    return request
