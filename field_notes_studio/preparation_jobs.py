"""Captured narration/caption execution through existing, fail-closed engine APIs."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

from field_notes_audio import audio, captions, spend_guard
from field_notes_audio.locks import run_lock
from field_notes_audio.production import sources
from field_notes_audio.storage import digest_file, read_object
from field_notes_studio.models import StopRequested
from field_notes_studio.preparation import Preparation
from field_notes_studio.preparation_models import CaptionsPending
from field_notes_studio.preparation_setup import load_configuration


class PreparationJobs:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.preparation = Preparation(self.root)

    def configuration(self) -> dict:
        return load_configuration(self.root)

    def ready_episodes(self) -> set[str]:
        return {entry["id"] for entry in sources.load_entries(self.root)}

    def _recording(self, plan: dict) -> Path:
        return sources.private_path(
            self.root, f"artifacts/audio/{plan['episode']['id']}/{plan['fingerprint'][:16]}"
        )

    def _saved_recording(self, plan: dict, directory: Path) -> Path | None:
        path, metadata = directory / "episode.mp3", directory / "episode.json"
        if not metadata.exists():
            return None
        saved = read_object(metadata)
        script = directory / "transcript.txt"
        if (
            not path.is_file()
            or not script.is_file()
            or saved.get("id") != plan["episode"]["id"]
            or saved.get("fingerprint") != plan["fingerprint"]
            or saved.get("model") != plan["model"]
            or saved.get("endpoint") != plan["endpoint"]
            or saved.get("language") != plan["episode"]["language"]
            or saved.get("speakers") != plan["episode"]["speakers"]
            or saved.get("title") != plan["episode"]["title"]
            or saved.get("script_sha256") != plan["script_sha256"]
            or saved.get("source_sha256") != plan["episode"]["source_sha256"]
            or saved.get("audio_sha256") != digest_file(path)
            or audio.digest(script.read_text(encoding="utf-8").strip().encode())
            != plan["script_sha256"]
        ):
            raise ValueError("Saved narration is missing or changed; repair it before preparation")
        return path

    @staticmethod
    def _caption_args(plan: dict, config: dict, path: Path) -> argparse.Namespace:
        language = plan["episode"]["language"]
        model = config["caption_model"]
        return argparse.Namespace(
            audio=path,
            project=config["project"],
            bucket=config["bucket"],
            model=model,
            location=config["location"],
            language=language,
            diarize=model == "chirp_3"
            and language.startswith("en-")
            and len(plan["episode"]["speakers"]) == 2,
            auth=config["auth"],
            script=None,
            wait=60,
            dry_run=False,
            retry_uncertain=False,
            restart_failed=False,
        )

    def inspect(self, note: str):
        snapshot = self.preparation.inspect(note)
        # Keep script inspection available even when the machine is not Cloud-ready.
        intro = snapshot.summary.split("Before production:", 1)[0]
        try:
            config = self.configuration()
        except ValueError as exc:
            return replace(
                snapshot, summary=str(exc) + "\nNo service request was made.\n\n" + intro
            )
        plan = audio.make_plan(snapshot.episode, config["model"], config["endpoint"], self.root)
        if self.preparation.inspect(note).identity != snapshot.identity:
            raise ValueError(
                "Sources or settings changed. Check again before allowing the narration."
            )
        request = {
            "version": 1,
            "note": note,
            "episode": snapshot.episode,
            "source_identity": snapshot.identity,
            "configuration": config,
            "plan": plan,
            # Captured operational policy, intentionally outside the synthesis plan/hash.
            "tts_timeout_seconds": audio.tts_timeout_seconds(),
        }
        directory = self._recording(plan)
        self._check_cache_paths(directory)
        saved_recording = self._saved_recording(plan, directory)
        complete, blockers, uncertain, missing = 0, [], {}, []
        diagnostics = []
        for index in range(1, len(plan["requests"]) + 1):
            path = sources.private_path(
                self.root, str((directory / f"chunk-{index:03d}.json").relative_to(self.root))
            )
            state = read_object(path) if path.exists() else {}
            complete += state.get("status") == "complete"
            if state.get("status") != "complete":
                missing.append(index)
            if not saved_recording and state.get("status") in {"requesting", "uncertain"}:
                expected = audio.digest(
                    json.dumps(plan["requests"][index - 1], sort_keys=True).encode()
                )
                if state.get("request_sha256") != expected:
                    blockers.append(
                        f"Narration part {index} receipt does not match this script. Check its saved evidence; do not delete it."
                    )
                else:
                    uncertain[str(index)] = digest_file(path)
                    diagnostics.append(
                        f"Part {index}: "
                        + narration_diagnostic(state)
                        + "\nCurrent receipt: "
                        + str(path.relative_to(self.root))
                    )
        caption_state = "No matching local caption state checked yet."
        captions_status = ""
        if (directory / "episode.mp3").exists():
            args = self._caption_args(plan, config, directory / "episode.mp3")
            directory2 = captions.recording_plan(args)[0]
            state_path = sources.private_path(
                self.root, str((directory2 / "state.json").relative_to(self.root))
            )
            state = read_object(state_path) if state_path.exists() else {}
            captions_status = state.get("status", "not submitted")
            caption_state = "Matching caption state: " + captions_status + "."
            if state.get("status") in {"requesting", "uncertain", "failed"}:
                blockers.append(
                    "Caption work needs explicit recovery; a new submission is not authorized by Resume."
                )
        if any(e["id"] == snapshot.episode for e in self.preparation._catalogs()[2].values()):
            blockers.append(
                "This episode is already on the public catalog. This new-note path does not replace it."
            )
        spend = self._spend(snapshot.episode, plan, directory, saved_recording)
        spend_summary = spend["summary"]
        recovery = ""
        recovery_summary = ""
        if uncertain:
            recovery_summary = (
                "Narration outcome unknown for part(s) " + ", ".join(uncertain) + ". "
                "Google may already have processed those requests. Resending can charge twice. "
                "Completed audio is kept and verified; other missing parts are still part of the narration. "
                "No retry happens without both authorizations below."
            )
            if not blockers:
                recovery = json.dumps({**request, "uncertain_chunks": uncertain}, sort_keys=True)
        summary = (
            (
                "Recovery needed: " + recovery_summary + "\n" + "\n".join(diagnostics) + "\n\n"
                if uncertain
                else ""
            )
            + (spend_summary + "\n\n" if spend_summary else "")
            + f"Cloud project: {config['project']}\n"
            f"Private working bucket: {config['bucket']}\n"
            "Charges may apply to missing narration and caption requests.\n"
            f"Client narration socket timeout: {request['tts_timeout_seconds']}s ({request['tts_timeout_seconds'] / 60:g} minutes). "
            "This is a wait policy, not a completion promise or automatic retry.\n"
            f"Captions: {config['caption_model']} · {config['location']}. Authentication: {config['auth']}.\n"
            f"{complete}/{len(plan['requests'])} narration parts report completion; the background producer verifies their bytes.\n"
            f"{caption_state}\n\n"
            "Queueing authorizes missing narration requests, private audio upload and caption submission/polling. "
            "These services can incur charges; this is not a price quote or live billing check.\n"
            "Completed work is reused. Uncertain requests and failed caption operations are never silently restarted.\n"
            "Successful narration adds a private narrated note to the shelf; no public files, approvals or release records are changed.\n"
            "This check sent no service request.\n\n" + intro
        )
        if saved_recording:
            summary += "\nVerified saved narration is available; no synthesis is needed.\n"
        if blockers:
            summary += "\n\nBlocked: " + " ".join(blockers)
        return replace(
            snapshot,
            summary=summary,
            request_json="" if blockers or uncertain else json.dumps(request, sort_keys=True),
            recovery_json=recovery,
            recovery_summary=recovery_summary if recovery else "",
            scope_summary=(
                f"Project: {config['project']} · Captions: {config['location']} · Narration: {config['endpoint']}\n"
                f"Private bucket: {config['bucket']}"
            ),
            spend_summary=spend_summary,
            spend_blocked=spend["blocked"] and not blockers,
            spend_count=spend["count"],
            spend_token=spend["token"],
            spend_label=spend["label"],
            spend_overridable=spend["overridable"],
            parts_total=len(plan["requests"]),
            parts_saved=len(plan["requests"]) if saved_recording else complete,
            missing_parts=() if saved_recording else tuple(missing),
            narration_estimate_usd=0.0 if saved_recording else self._estimate(plan, missing),
            recording_saved=saved_recording is not None,
            captions_status=captions_status,
            word_count=plan["word_count"],
            minutes=plan["estimated_minutes"],
            project=config["project"],
            blockers=tuple(blockers),
            uncertain_parts=tuple(uncertain),
        )

    @staticmethod
    def _estimate(plan: dict, missing: list[int]) -> float | None:
        """Speech-output estimate for the parts without a complete saved receipt."""
        shares = [audio.chunk_estimate(plan, index) for index in missing]
        return None if None in shares else round(sum(shares), 4)

    def _spend(self, episode, plan, directory, saved_recording) -> dict:
        """Read-only ledger view for the inspection and the override control."""
        audio_root = self.root / "artifacts/audio"
        parts = (
            []
            if saved_recording
            else [
                f"narration-{index}"
                for index in range(1, len(plan["requests"]) + 1)
                if not (directory / f"chunk-{index:03d}.json").exists()
                or read_object(directory / f"chunk-{index:03d}.json").get("status") != "complete"
            ]
        )
        tallies = [spend_guard.tally(audio_root, episode, part) for part in parts or ["captions"]]
        blocked = [t for t in tallies if t.blocked]
        first = blocked[0] if blocked else max(tallies, key=lambda t: t.part_window)
        empty = {
            "summary": "",
            "blocked": False,
            "count": 0,
            "token": "",
            "label": "",
            "overridable": False,
        }
        if not first.episode_total:
            return empty
        lines = ["Uncertain spend: " + first.sentence()]
        for attempt in first.attempts:
            if attempt.outcome != "uncertain":
                continue
            money = (
                f"up to about ${attempt.estimate_usd:.4f}"
                if attempt.estimate_usd is not None
                else "no local estimate"
            )
            lines.append(
                f"  {attempt.at.strftime('%Y-%m-%d %H:%M UTC')} · "
                f"{spend_guard.part_label(attempt.part)} · {attempt.detail or 'no outcome'} · "
                f"billing unknown · {money} · attempt {attempt.attempt_id[:12]}"
            )
        overridden = spend_guard.overridden_recently(audio_root, episode, first.part, first.limits)
        lines.append(spend_guard.limits_text(first.limits))
        if blocked and overridden:
            lines.append(
                f"Spend guard: {spend_guard.part_label(first.part)} was already overridden "
                "once in this window. Studio will not queue more paid work for it. Stop and "
                "wait for the window to pass."
            )
        elif blocked:
            lines.append(
                "Spend guard: Studio will not queue more paid work for this episode now. "
                "Stop and wait; the limit lifts as attempts age out of the window. To spend "
                "anyway, tick the override below and give a reason. It is logged and works "
                "once per part per window."
            )
        else:
            lines.append(
                "Stop and wait before another paid try: check the Google Cloud status page "
                "and the billing report first."
            )
        money = first.spend_text().removesuffix("; billing unknown")
        return {
            "summary": "\n".join(lines),
            "blocked": bool(blocked),
            "count": first.episode_window,
            "token": first.token,
            "label": (
                f"{first.episode_window} uncertain attempts in {first.limits.window_hours:g} h, "
                f"{money.replace(' in speech output', '')}, billing unknown"
            ),
            "overridable": bool(blocked) and not overridden,
        }

    def validate(self, request: dict) -> dict:
        if (
            not isinstance(request, dict)
            or (
                set(request)
                - {"resume", "uncertain_chunks", "tts_timeout_seconds", "spend_override"}
            )
            != {"version", "note", "episode", "source_identity", "configuration", "plan"}
            or type(request["version"]) is not int
            or request["version"] != 1
        ):
            raise ValueError("Invalid captured preparation request")
        audio.validate_tts_timeout(
            request.get("tts_timeout_seconds", audio.LEGACY_TTS_TIMEOUT_SECONDS)
        )
        snapshot = self.preparation.inspect(request["note"])
        if (
            snapshot.episode != request["episode"]
            or snapshot.identity != request["source_identity"]
        ):
            raise ValueError(
                "Sources or settings changed after the narration was checked. Check a fresh plan."
            )
        config = self.configuration()
        plan = audio.make_plan(snapshot.episode, config["model"], config["endpoint"], self.root)
        if config != request["configuration"] or sources.identity(plan) != sources.identity(
            request["plan"]
        ):
            raise ValueError("The captured narration plan or configuration changed")
        override = request.get("spend_override")
        if override is not None and (
            not isinstance(override, dict)
            or set(override) != {"reason", "token"}
            or not isinstance(override["token"], str)
            or not re.fullmatch(r"[0-9a-f]{12}", override["token"])
        ):
            raise ValueError("Invalid spend-limit override")
        if override is not None:
            spend_guard.validate_reason(override["reason"])
        receipts = request.get("uncertain_chunks", {})
        if (
            not isinstance(receipts, dict)
            or ("uncertain_chunks" in request and not receipts)
            or (receipts and "resume" in request)
            or any(
                key not in {str(i) for i in range(1, len(plan["requests"]) + 1)}
                or not isinstance(value, str)
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
                for key, value in receipts.items()
            )
        ):
            raise ValueError("Invalid uncertain-chunk authorization")
        return plan

    def validate_recovery(self, request):
        plan = self.validate(request)
        directory = self._recording(plan)
        self._check_cache_paths(directory)
        for index, receipt in request.get("uncertain_chunks", {}).items():
            path = directory / f"chunk-{int(index):03d}.json"
            if not path.is_file() or digest_file(path) != receipt:
                raise ValueError("Recovery receipt changed or disappeared. Check recovery again.")
            state = read_object(path)
            expected = audio.digest(
                json.dumps(plan["requests"][int(index) - 1], sort_keys=True).encode()
            )
            if (
                state.get("status") not in {"requesting", "uncertain"}
                or state.get("request_sha256") != expected
            ):
                raise ValueError(
                    "Recovery receipt no longer describes the checked uncertain request"
                )

    def run(self, request: dict, emit, stopped) -> str:
        plan = self.validate(request)
        config = request["configuration"]
        directory = self._recording(plan)

        def check():
            if stopped():
                raise StopRequested
            # Source checks are local and occur before each next request/poll.
            self.validate(request)

        class Guard:
            def is_set(self):
                check()
                return False

        check()
        missing = [name for name in ("gcloud", "ffmpeg", "ffprobe") if not shutil.which(name)]
        if missing:
            raise ValueError("Preparation tools are missing: " + ", ".join(missing))
        self._check_cache_paths(directory)
        directory.mkdir(parents=True, exist_ok=True)
        args = argparse.Namespace(
            episode=request["episode"],
            **config,
            retry_uncertain=False,
            # Legacy queued jobs retain their original policy. Reinspection captures 600s.
            tts_timeout_seconds=request.get(
                "tts_timeout_seconds", audio.LEGACY_TTS_TIMEOUT_SECONDS
            ),
            retry_receipts=request.get("uncertain_chunks", {}),
            _cancel_event=Guard(),
            retry_hint="use Check recovery in Studio to try this part",
            allow_spend_over_limit=(request.get("spend_override") or {}).get("reason"),
            spend_token=(request.get("spend_override") or {}).get("token"),
        )
        emit(
            "narration",
            "Reusing verified narration parts or making explicitly allowed requests",
        )
        with run_lock(directory, "audio"):
            self._check_cache_paths(directory)
            recording = self._saved_recording(plan, directory)
            if recording is None and request.get("resume"):
                raise ValueError(
                    "The saved narration for caption Resume is missing; no resynthesis was authorized"
                )
            if recording is None:
                recording = audio.generate_locked(args, plan, directory, root=self.root)
            emit(
                "narration-complete", "Narration is saved; caption work follows without resynthesis"
            )
            check()
            caption_args = self._caption_args(plan, config, recording)
            caption_args._cancel_event = Guard()
            caption_args.allow_spend_over_limit = args.allow_spend_over_limit
            caption_args.spend_token = args.spend_token
            caption_args.retry_hint = "use Check recovery in Studio"
            # Validate containment of all existing cache files before the engine opens them.
            cap_directory, caption_plan, *_ = captions.recording_plan(caption_args)
            self._check_cache_paths(directory)
            sources.private_path(self.root, str(cap_directory.relative_to(self.root)))
            emit(
                "captions",
                "Submitting missing captions or polling the saved operation; uncertain retry disabled",
            )
            receipt = request.get("resume")
            if receipt is not None and (
                not isinstance(receipt, dict)
                or set(receipt) != {"operation", "fingerprint", "audio_sha256"}
                or receipt["fingerprint"] != caption_plan["fingerprint"]
                or receipt["audio_sha256"] != caption_plan["audio_sha256"]
            ):
                raise ValueError("Saved caption Resume identity disagrees with this narration")
            if receipt is not None:
                captions.operation_url(receipt["operation"], config["location"], config["project"])
            completed = captions.run(
                caption_args, expected_operation=receipt["operation"] if receipt else None
            )
            if completed is None:
                if stopped():
                    raise StopRequested
                state = read_object(cap_directory / "state.json")
                captions.operation_url(
                    state.get("operation"), config["location"], config["project"]
                )
                raise CaptionsPending(
                    "Captions are still running. Resume polls the saved operation without resynthesis or a new submission.",
                    {
                        "operation": state["operation"],
                        "fingerprint": caption_plan["fingerprint"],
                        "audio_sha256": caption_plan["audio_sha256"],
                    },
                )
            if completed != cap_directory:
                raise ValueError("Caption result does not match the captured request")
            emit("captions-complete", "Narration and caption outputs are saved")
            check()
            # Caption locking protects adoption from a concurrent CLI rewrite.
            with run_lock(completed, "caption adoption"):
                result = sources.adopt(self.root, plan, completed)
        # A successful atomic adoption wins over a stop arriving afterwards.
        return str(result)

    def spend_summary(self, episode: str) -> str:
        return spend_guard.summary_line(self.root / "artifacts/audio", episode)

    def _check_cache_paths(self, directory: Path) -> None:
        for path in directory.rglob("*"):
            sources.private_path(self.root, str(path.relative_to(self.root)))


def narration_diagnostic(state: dict) -> str:
    """Only render bounded structured diagnostics, never headers or credential strings."""
    import re

    parts = []
    if type(state.get("http_status")) is int:
        parts.append(f"HTTP {state['http_status']}")
        if state["http_status"] == 502:
            parts.append("Bad Gateway: server/gateway error, not a client socket timeout")
        elif state["http_status"] == 499:
            parts.append("CANCELLED: the request was cancelled; never retry it automatically")
    for key in ("provider_status", "failure_kind"):
        value = state.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", value):
            parts.append(value)
    elapsed = state.get("attempt_seconds")
    if isinstance(elapsed, int | float) and not isinstance(elapsed, bool) and 0 <= elapsed <= 86400:
        parts.append(f"after {elapsed:g}s")
    timeout = state.get("timeout_seconds")
    if type(timeout) is int and 60 <= timeout <= 900:
        parts.append(f"client socket timeout {timeout}s")
    if state.get("status") in {"requesting", "uncertain"}:
        parts.append("response not confirmed; remote processing/billing unknown")
    attempt = state.get("attempt_id")
    if isinstance(attempt, str) and re.fullmatch(r"[a-f0-9]{32}", attempt):
        parts.append(f"saved attempt {attempt[:8]}")
    return (
        "; ".join(parts)
        if parts
        else "No provider result was confirmed. Read the job history for the original error."
    )
