"""Make episode runs: chain prepare → full video → (review) → upload package.

A run is the consent record plus an ordered list of ordinary jobs in the studio
journal. Advancing is idempotent and safe to repeat from any process: the next
job is queued in the same transaction that checks the run's latest job, so a
restart, a second window or the worker can all call ``advance`` without queueing
twice. Everything survives closing Studio, because nothing lives in memory.

Invariants (each is checked in code, not only documented):

- ``advance`` only ever queues local, free work: ``LOCAL_ACTIONS``. The one paid
  job of a run is its first ``prepare`` job, queued by ``make_plan`` under the
  single consent. A failed, interrupted or stopped job is never retried here.
- An uncertain resend or a spend-guard override is never queued by a run. When a
  person recovers on the expert path, with that path's own consent, the run
  follows the newer job (``adopt``) and continues with local steps only.
- Polling a saved caption operation is not a request: ``resume_preparation``
  only polls it, and a run does so at most ``AUTO_POLLS`` times.
- Packaging needs a verified full-episode approval of the exact video the run
  made; the export job re-checks the approval and edition under its own lock.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from field_notes_studio.make_models import RunView, TimelineRow
from field_notes_studio.make_plan import minutes_text
from field_notes_studio.models import TERMINAL
from field_notes_studio.readiness_models import plain

LOCAL_ACTIONS = frozenset({"video", "export"})
STEP_FOR_ACTION = {"prepare": "prepare", "video": "video", "export": "export"}
AUTO_POLLS = 30
POLL_PAUSE_SECONDS = 30
FAILED = {"failed", "interrupted", "cancelled"}

# Timeline rows: key, name, the job step and the journal stage that measures it.
ROWS = (
    ("narrate", "Narrate", "prepare", "narration"),
    ("caption", "Caption", "prepare", "captions"),
    ("sound", "Finish sound", "video", "audio"),
    ("video", "Make video", "video", "video"),
    ("review", "Your review", "", ""),
    ("package", "Upload package", "export", "export"),
)


def parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def clock(value: str) -> str:
    parsed = parse(value)
    return parsed.astimezone().strftime("%H:%M") if parsed else ""


def span(seconds: float) -> str:
    if seconds < 60:
        return f"{max(0, round(seconds))} s"
    return f"{round(seconds / 60)} min"


def stage_times(events: list[dict], stage: str) -> tuple[str, str]:
    """First start and the completion time of one journal stage, if observed."""
    start = next(
        (e["time"] for e in events if e["stage"] == stage or e["stage"].startswith(stage + "-")),
        "",
    )
    done = next((e["time"] for e in events if e["stage"] == stage + "-complete"), "")
    return start, done


class Runs:
    def __init__(self, studio, launch=None):
        self.studio = studio
        self.repository = studio.repository
        self.pipeline = studio.pipeline
        self.launch = launch

    # -- advancing ------------------------------------------------------------------

    def advance_all(self, *, verify_review: bool = False) -> None:
        for run in self.repository.runs():
            self.advance(run["identifier"], verify_review=verify_review)

    def _latest(self, run_id: str) -> tuple[dict, dict, object] | None:
        run = self.repository.run(run_id)
        steps = self.repository.run_steps(run_id)
        if run["closed"] or not steps:
            return None
        last = steps[-1]
        return run, last, self.repository.get(last["job"])

    def adopt(self, run_id: str) -> bool:
        """Follow a newer job for the same episode queued on the expert path."""
        latest = self._latest(run_id)
        if latest is None:
            return False
        run, last, _job = latest
        newer = self.repository.newer_jobs(run["episode"], last["job"])
        newer = [job for job in newer if job.action in STEP_FOR_ACTION]
        if not newer:
            return False
        job = newer[-1]
        adopted = self.repository.adopt_step(
            run_id, STEP_FOR_ACTION[job.action], job.identifier, after=last["job"]
        )
        if adopted:
            self.repository.note_run(run_id, self._adoption_note(run, job))
        return adopted

    @staticmethod
    def _adoption_note(run: dict, job) -> str:
        """The consent record says when the run followed someone else's job."""
        request = json.loads(job.request)
        note = f"Followed {job.action} job {job.identifier[:12]} queued on the expert path"
        if job.action == "prepare":
            return (
                note
                + " with its own consent"
                + (" (uncertain resend)" if request.get("uncertain_chunks") else "")
            )
        settings = request.get("settings") or {}
        recipe = run["recipe"]
        if job.action == "video" and (
            settings.get("speed") != recipe.get("speed")
            or settings.get("outro_seconds") != recipe.get("outro")
            or any(settings.get(k) != v for k, v in (recipe.get("sound") or {}).items())
        ):
            note += ", with show settings different from the ones consented to"
        return note

    def advance(self, run_id: str, *, verify_review: bool = False) -> str | None:
        """Queue the next local job when the latest one succeeded. Returns its id."""
        self.adopt(run_id)
        latest = self._latest(run_id)
        if latest is None:
            return None
        run, last, job = latest
        if job.status == "waiting" and job.action == "prepare":
            self._poll_captions(job)
            return None
        if job.status != "succeeded" or run["stop_after"]:
            return None
        if last["step"] == "prepare":
            return self._queue_video(run, job)
        if last["step"] == "video" and verify_review:
            return self.queue_package(run["identifier"])
        return None

    def _queue(self, run: dict, step: str, action: str, request: dict, after: str) -> str | None:
        if action not in LOCAL_ACTIONS:
            raise ValueError("A run only queues local, free work after its consent")
        if self.launch is not None:
            self.launch()
        job = self.repository.add_step(run["identifier"], step, action, request, after=after)
        if job is not None:
            self.repository.update_run(run["identifier"], blocked="")
        return job

    def _queue_video(self, run: dict, prepared) -> str | None:
        recipe = run["recipe"]
        try:
            request = self.pipeline.request(
                run["episode"],
                "video",
                recipe["speed"],
                recipe["outro"],
                recipe["sound"],
                recipe["base"],
            )
            self.pipeline.preflight(run["episode"], "video", request)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.repository.update_run(
                run["identifier"],
                blocked="The video could not start: " + plain(exc, "preflight"),
            )
            return None
        try:
            return self._queue(run, "video", "video", request, prepared.identifier)
        except ValueError as exc:
            self.repository.update_run(run["identifier"], blocked=str(exc))
            return None

    def queue_package(self, run_id: str) -> str | None:
        """Make the upload package once the run's own full video is approved."""
        latest = self._latest(run_id)
        if latest is None:
            return None
        run, last, job = latest
        if last["step"] not in {"video", "export"} or job.status not in TERMINAL:
            return None
        video_job = job
        if last["step"] == "export":
            video = [s for s in self.repository.run_steps(run_id) if s["step"] == "video"]
            if not video:
                return None
            video_job = self.repository.get(video[-1]["job"])
        if video_job.status != "succeeded" or not video_job.result:
            return None
        episode = run["episode"]
        snapshot = self.pipeline.review_snapshot(episode, full_video=True)
        if (
            not snapshot.approved
            or not snapshot.video
            or Path(snapshot.video).parent.resolve() != Path(video_job.result).resolve()
        ):
            # Not approved, or the saved episode is no longer the one this run made.
            return None
        try:
            request = self.pipeline.request(episode, "export", None, None)
            self.pipeline.preflight(episode, "export", request)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.repository.update_run(
                run_id, blocked="The upload package could not start: " + plain(exc, "package")
            )
            return None
        try:
            return self._queue(run, "export", "export", request, job.identifier)
        except ValueError as exc:
            self.repository.update_run(run_id, blocked=str(exc))
            return None

    def _poll_captions(self, job) -> None:
        """Check the saved caption operation again; this sends no new request."""
        events = self.repository.events(job.identifier)
        polls = sum(e["stage"] == "resume" for e in events)
        waited = parse(events[-1]["time"]) if events else None
        if polls >= AUTO_POLLS or waited is None:
            return
        if (datetime.now(timezone.utc) - waited).total_seconds() < POLL_PAUSE_SECONDS:
            return
        try:
            if self.launch is not None:
                self.launch()
            self.repository.resume_preparation(job.identifier)
        except ValueError:
            return

    # -- person-initiated -------------------------------------------------------------

    def stop_after_step(self, run_id: str) -> None:
        self.repository.update_run(run_id, stop_after=True)

    def continue_run(self, run_id: str) -> str | None:
        """Continue a stopped run, or re-run a failed local step; never a paid one."""
        latest = self._latest(run_id)
        if latest is None:
            raise ValueError("This run is closed. Start Make episode again.")
        run, last, job = latest
        if job.status in FAILED and job.action not in LOCAL_ACTIONS:
            raise ValueError(
                "The last step did not finish. Check recovery on the expert path; "
                "Make episode never resends a paid request on its own."
            )
        self.repository.update_run(run_id, stop_after=False, blocked="")
        if job.status in FAILED and job.action == "video":
            # Local and free: queue the same full video again after the failed job.
            return self._queue_video(self.repository.run(run_id), job)
        if job.status in FAILED and job.action == "export":
            return self.queue_package(run_id)
        return self.advance(run_id, verify_review=True)

    def close(self, run_id: str) -> None:
        # The active-step check and the close are one transaction in the repository.
        self.repository.close_run(run_id)

    # -- durations ----------------------------------------------------------------------

    def record_durations(self, job) -> None:
        """Measured local stage times for "x–y min on this computer before"."""
        if job.status != "succeeded":
            return
        events = self.repository.events(job.identifier)
        for key, _name, step, stage in ROWS:
            if not stage or STEP_FOR_ACTION.get(job.action) != step:
                continue
            start, done = stage_times(events, stage)
            if start and done and parse(start) and parse(done):
                self.repository.record_duration(
                    key, (parse(done) - parse(start)).total_seconds(), job.identifier
                )

    # -- views --------------------------------------------------------------------------

    def views(self) -> list[RunView]:
        return [self.view(run["identifier"]) for run in self.repository.runs()]

    def run_for(self, episode: str) -> RunView | None:
        for run in self.repository.runs():
            if run["episode"] == episode:
                return self.view(run["identifier"])
        return None

    def view(self, run_id: str, title: str = "") -> RunView:
        run = self.repository.run(run_id)
        steps = self.repository.run_steps(run_id)
        jobs = {s["step"]: self.repository.get(s["job"]) for s in steps}
        last = self.repository.get(steps[-1]["job"]) if steps else None
        last_step = steps[-1]["step"] if steps else ""
        consent = run["consent"]
        reused = set(consent.get("reused", []))
        now = datetime.now(timezone.utc)
        rows: list[TimelineRow] = []
        current = ""
        for key, name, step, stage in ROWS:
            job = jobs.get(step)
            if key == "review":
                rows.append(self._review_row(jobs))
                continue
            if job is None:
                if key in {"narrate", "caption"} and (
                    ("narration" if key == "narrate" else "captions") in reused
                ):
                    rows.append(TimelineRow(key, name, "Reused", "Saved earlier; no charge", "ok"))
                elif key == "package":
                    rows.append(
                        TimelineRow(
                            key, name, "After review", "Local, automatic once approved", "todo"
                        )
                    )
                else:
                    rows.append(TimelineRow(key, name, "Next", self._estimate(key), "todo"))
                continue
            events = self.repository.events(job.identifier)
            start, done = stage_times(events, stage)
            if done or job.status == "succeeded":
                detail = clock(start) + (" – " + clock(done) if done else "")
                if start and done:
                    detail = span((parse(done) - parse(start)).total_seconds()) + " · " + detail
                if key == "narrate":
                    parts = [e for e in events if e["stage"].startswith("narration-")]
                    total = next((e["stage"].rsplit("-of-", 1)[1].split("-")[0] for e in parts), "")
                    detail = (f"{total} of {total} parts · " if total else "") + detail
                rows.append(TimelineRow(key, name, "Saved", detail.strip(" ·"), "ok"))
            elif (
                job.status in {"queued", "running"}
                and not current
                and (start or job.status == "queued")
            ):
                if job.status == "queued":
                    rows.append(TimelineRow(key, name, "Queued", "Waiting for the producer", "run"))
                else:
                    elapsed = (now - parse(start)).total_seconds() if parse(start) else 0
                    estimate = self._estimate(key)
                    rows.append(
                        TimelineRow(
                            key,
                            name,
                            "Stopping" if job.cancel_requested else "Working",
                            f"{span(elapsed)} elapsed" + (" · " + estimate if estimate else ""),
                            "run",
                        )
                    )
                current = current or key
            elif job.status == "waiting" and key == "caption":
                rows.append(
                    TimelineRow(
                        key,
                        name,
                        "Waiting",
                        "The caption service is still working; Studio checks again, no new request",
                        "run",
                    )
                )
                current = current or key
            elif job.status in FAILED and (start or not current):
                state = {"failed": "Paused", "interrupted": "Uncertain", "cancelled": "Stopped"}
                rows.append(TimelineRow(key, name, state[job.status], self._failure(job), "warn"))
                current = current or key
            else:
                rows.append(
                    TimelineRow(
                        key,
                        name,
                        "Waiting" if job.status in {"queued", "running"} else "Next",
                        "Starts after the step before",
                        "todo",
                    )
                )
        phase, group, headline, detail = self._phase(run, last, last_step, rows)
        return RunView(
            identifier=run_id,
            episode=run["episode"],
            title=title,
            started=clock(run["created"]),
            phase=phase,
            group=group,
            headline=headline,
            detail=detail,
            rows=tuple(rows),
            job=last.identifier if last else "",
            stop_after=bool(run["stop_after"]),
            current=current,
            retry_free=last is not None
            and last.status in FAILED
            and last.action in LOCAL_ACTIONS
            and not run["closed"],
        )

    def _estimate(self, key: str) -> str:
        return minutes_text(self.repository.durations(key))

    def _review_row(self, jobs: dict) -> TimelineRow:
        video, export = jobs.get("video"), jobs.get("export")
        if export is not None:
            return TimelineRow("review", "Your review", "Approved", "Full episode approved", "ok")
        if video is not None and video.status == "succeeded":
            return TimelineRow(
                "review", "Your review", "Needs you", "Watch once, check subtitles, approve", "you"
            )
        return TimelineRow(
            "review", "Your review", "Next", "We will tell you when it is ready", "todo"
        )

    def _failure(self, job) -> str:
        reason = (job.error or "").strip().split("\n", 1)[0]
        if len(reason) > 160:
            reason = reason[:157].rsplit(" ", 1)[0] + "…"
        return reason or "Stopped before saving a result"

    def _phase(self, run, last, last_step, rows) -> tuple[str, str, str, str]:
        if last is None:
            return "paused", "needs-you", "Nothing was queued", ""
        if run["blocked"]:
            return "paused", "needs-you", "Paused before the next step", run["blocked"]
        if last.status in {"queued", "running"}:
            row = next((r for r in rows if r.kind == "run"), None)
            return (
                "working",
                "working",
                (row.name + " · " + row.state.lower()) if row else "Working",
                row.detail if row else "",
            )
        if last.status == "waiting":
            polls = sum(e["stage"] == "resume" for e in self.repository.events(last.identifier))
            if polls >= AUTO_POLLS:
                return (
                    "paused",
                    "needs-you",
                    "Captions are taking longer than usual",
                    "Use Check again; it only asks about the saved caption operation.",
                )
            return "working", "working", "Waiting for captions", "Checked again automatically"
        if last.status in FAILED:
            if last.action == "prepare":
                spend = self.studio.spend_summary(run["episode"])
                return (
                    "paused",
                    "needs-you",
                    "Narration paused · nothing will be sent until you choose",
                    (spend + "\n" if spend else "") + self._failure(last),
                )
            return "paused", "needs-you", "Stopped before finishing", self._failure(last)
        if run["stop_after"]:
            return "stopped", "needs-you", "Stopped after this step", "Continue when ready."
        if last_step == "prepare":
            return "working", "working", "Starting the video", ""
        if last_step == "video":
            return (
                "review",
                "needs-you",
                "Review full episode",
                "Watch once, check subtitles, approve.",
            )
        if self.studio.repository.publications().get(run["episode"]):
            return "done", "done", "Released", "Release record saved."
        return (
            "ready",
            "needs-you",
            "Upload folder ready",
            "Upload it, then record where it went live.",
        )
