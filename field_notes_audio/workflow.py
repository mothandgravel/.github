"""Saved defaults and a resumable local episode workflow. No credential storage."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import webbrowser
import zipfile
from pathlib import Path

from field_notes_audio import audio, captions, judge, spend_guard
from field_notes_audio.progress import raise_if_stopped, report, timed
from field_notes_audio.storage import read_object

DEFAULTS = {"endpoint": "global", "location": "us", "model": "gemini-2.5-pro-tts", "auth": "gcloud"}
SETUP_VERSION = 1


def settings_path() -> Path:
    return audio.ROOT / "artifacts/audio/settings.json"


def read_settings() -> dict:
    path = settings_path()
    return read_object(path) if path.exists() else {}


def gcloud(arguments: list[str]) -> str:
    result = subprocess.run(
        ["gcloud", *arguments, "--quiet"], capture_output=True, text=True, timeout=180
    )
    if result.returncode:
        # These are configuration commands, never commands that print credentials.
        raise RuntimeError(
            f"gcloud {' '.join(arguments[:3])} failed: {result.stderr.strip()[-600:]}"
        )
    return result.stdout.strip()


def resolve_defaults(args: argparse.Namespace, discover_project: bool = True) -> argparse.Namespace:
    saved = read_settings()
    project = (
        getattr(args, "project", None)
        or os.environ.get("FIELD_AUDIO_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or saved.get("project")
    )
    if not project and discover_project and shutil.which("gcloud"):
        project = gcloud(["config", "get-value", "project"])
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project or ""):
        raise ValueError(
            'Set the project once: python3 scripts/field_audio.py setup --project "$FIELD_AUDIO_PROJECT"'
        )
    args.project = project
    # Never borrow a saved bucket from another project after an explicit project switch.
    same_project = saved.get("project") == project
    for name, fallback in DEFAULTS.items():
        if name == "model" and args.command == "captions":
            fallback = "chirp_3"
            saved_value = saved.get("caption_model")
        else:
            saved_value = saved.get(name)
        setattr(args, name, getattr(args, name, None) or saved_value or fallback)
    args.bucket = (
        getattr(args, "bucket", None)
        or os.environ.get("FIELD_AUDIO_BUCKET")
        or (
            saved.get("bucket")
            if same_project and args.location == saved.get("location", "us")
            else None
        )
    )
    if not args.bucket:
        suffix = "-eu" if args.location == "eu" else ""
        args.bucket = f"{project}-field-notes-audio{suffix}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]", args.bucket):
        raise ValueError("Use a bucket name of 3–63 characters without gs:// or dots")
    if (
        args.endpoint not in audio.ENDPOINTS
        or args.location not in {"us", "eu", "global"}
        or args.auth not in {"gcloud", "adc"}
    ):
        raise ValueError(
            "Invalid endpoint, caption location or authentication method in saved settings"
        )
    allowed_models = {"chirp_3", "long"} if args.command == "captions" else audio.MODELS
    if args.model not in allowed_models:
        raise ValueError("Invalid model in saved settings")
    return args


def resource_key(args: argparse.Namespace) -> dict:
    return {
        "version": SETUP_VERSION,
        "project": args.project,
        "bucket": args.bucket,
        "location": args.location,
    }


def setup(args: argparse.Namespace) -> None:
    missing = [name for name in ("gcloud", "ffmpeg", "ffprobe") if not shutil.which(name)]
    if missing:
        hint = (
            " Install FFmpeg with: sudo apt-get update && sudo apt-get install -y ffmpeg."
            if "gcloud" not in missing
            else " Install the Google Cloud CLI, or use Cloud Shell."
        )
        raise ValueError(f"Missing tools: {', '.join(missing)}.{hint}")
    # Authenticate before making any resource changes; tokens never reach the settings file.
    audio.access_token(args.auth)
    report(f"Prepare Google Cloud project: {args.project}", flush=True)
    try:
        billing = gcloud(
            ["billing", "projects", "describe", args.project, "--format=value(billingEnabled)"]
        )
    except RuntimeError:
        report(
            "Billing status is not readable by this account; continuing with the existing project.",
            flush=True,
        )
    else:
        if billing.lower() == "false":
            raise ValueError(
                f"Billing is disabled. Link billing in https://console.cloud.google.com/billing/linkedaccount?project={args.project}, then repeat this command."
            )
    number = gcloud(["projects", "describe", args.project, "--format=value(projectNumber)"])
    if not re.fullmatch(r"[0-9]+", number):
        raise ValueError("Google did not return the selected project's number")
    report("Enable speech generation, transcription and storage APIs (safe to repeat).", flush=True)
    gcloud(
        [
            "services",
            "enable",
            "texttospeech.googleapis.com",
            "aiplatform.googleapis.com",
            "speech.googleapis.com",
            "storage.googleapis.com",
            f"--project={args.project}",
        ]
    )
    bucket_url = f"https://storage.googleapis.com/storage/v1/b/{args.bucket}"
    try:
        info = captions.cloud_json(bucket_url, args.project, args.auth)
    except captions.CloudError as exc:
        if exc.code != 404:
            raise
        report(f"Create private working bucket: gs://{args.bucket}", flush=True)
        body = {
            "name": args.bucket,
            "location": "EU" if args.location == "eu" else "US",
            "iamConfiguration": {
                "uniformBucketLevelAccess": {"enabled": True},
                "publicAccessPrevention": "enforced",
            },
        }
        try:
            info = captions.cloud_json(
                f"https://storage.googleapis.com/storage/v1/b?project={args.project}",
                args.project,
                args.auth,
                body,
            )
        except captions.CloudError as conflict:
            if conflict.code != 409:
                raise
            info = captions.cloud_json(bucket_url, args.project, args.auth)
    if str(info.get("projectNumber")) != number:
        raise ValueError(
            "The working bucket belongs to another project; choose a different --bucket name"
        )
    if info.get("iamConfiguration", {}).get("publicAccessPrevention") != "enforced":
        raise ValueError(
            "The existing bucket lacks enforced public access prevention. Choose a new dedicated --bucket; its policy was not changed."
        )
    if (
        args.location == "eu"
        and info.get("location", "").upper() != "EU"
        and not info.get("location", "").lower().startswith("europe-")
    ):
        raise ValueError(
            "EU transcription requires an EU/European working bucket; choose a new --bucket name"
        )
    saved = read_settings()
    settings = {
        "version": 1,
        "project": args.project,
        "bucket": args.bucket,
        "endpoint": args.endpoint,
        "location": args.location,
        "auth": args.auth,
        "model": args.model
        if args.command != "captions"
        else saved.get("model", DEFAULTS["model"]),
        "caption_model": args.model
        if args.command == "captions"
        else saved.get("caption_model", "chirp_3"),
        "prepared": resource_key(args),
    }
    audio.write_json(settings_path(), settings)
    report(
        f"Saved defaults: TTS {args.endpoint}; captions {args.location}; private bucket {args.bucket}."
    )
    report("Ready. Next: python3 scripts/field_audio.py make workbench-001")


def ensure_setup(args: argparse.Namespace) -> None:
    if read_settings().get("prepared") != resource_key(args):
        setup(args)


def find_audio(identifier: str) -> Path:
    # Lookup is local. Metadata/hash checks prevent silently captioning a changed MP3.
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier):
        raise ValueError("Provide an episode ID or an existing MP3 path")
    candidates = []
    for path in (audio.ROOT / "artifacts/audio" / identifier).glob("*/episode.json"):
        metadata = read_object(path)
        if metadata.get("id") == identifier and path.with_name("episode.mp3").exists():
            candidates.append((metadata.get("generated_at", ""), path))
    if not candidates:
        raise ValueError(
            f"No recording for {identifier}. Run: python3 scripts/field_audio.py make {identifier}"
        )
    path = max(candidates, key=lambda item: (item[0], str(item[1])))[1].with_name("episode.mp3")
    metadata = read_object(path.with_name("episode.json"))
    if audio.digest_file(path) != metadata.get("audio_sha256"):
        raise ValueError(
            "The latest saved MP3 changed; identify the correct recording with an explicit MP3 path"
        )
    return path


def prepare_captions(args: argparse.Namespace) -> argparse.Namespace:
    supplied = Path(args.audio).expanduser()
    args.audio = (
        supplied
        if supplied.exists() or supplied.suffix.lower() == ".mp3"
        else find_audio(str(args.audio))
    )
    metadata_path = args.audio.with_name("episode.json")
    metadata = read_object(metadata_path) if metadata_path.exists() else {}
    args.language = getattr(args, "language", None) or metadata.get("language", "en-US")
    if getattr(args, "diarize", None) is None:
        args.diarize = (
            args.model == "chirp_3"
            and args.language.startswith("en-")
            and len(metadata.get("speakers", [])) == 2
        )
    return args


def bundle(directory: Path) -> Path:
    """A portable listening folder: unzip once, open listen.html with its adjacent MP3."""
    recording = directory.parent.parent
    # Generated episodes have a stable bundle path even when the voice/run changes.
    parent = (
        recording.parent if recording.parent.parent == audio.ROOT / "artifacts/audio" else recording
    )
    target = parent / "episode.zip"
    names = [
        "listen.html",
        "audio.mp3",
        "captions.srt",
        "captions.vtt",
        "transcript.txt",
        "words.json",
        "cues.json",
        "comparison.json",
        "captions.json",
    ]
    with tempfile.NamedTemporaryFile(dir=parent, suffix=".tmp.zip", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in names:
                archive.write(directory / name, name)
            for name in ("episode.json", "transcript.txt"):
                source = recording / name
                if source.exists():
                    archive.write(
                        source, "episode.json" if name == "episode.json" else "input-script.txt"
                    )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    report(f"Portable listening bundle: {target}")
    return target


def open_listening(path: Path) -> None:
    try:
        if shutil.which("wslview"):
            subprocess.Popen(
                ["wslview", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return
        if shutil.which("explorer.exe") and shutil.which("wslpath"):
            result = subprocess.run(
                ["wslpath", "-w", str(path)], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                subprocess.Popen(
                    ["explorer.exe", result.stdout.strip()],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
        # Don't launch text browsers in Cloud Shell or a headless terminal.
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            webbrowser.open(path.as_uri())
    except (OSError, subprocess.SubprocessError, webbrowser.Error):
        report(f"Open the listening page manually: {path}")


def finish(directory: Path | None, no_open: bool) -> None:
    if directory is None:
        return
    bundle(directory)
    if not no_open:
        open_listening(directory / "listen.html")


def script_gate(args: argparse.Namespace, plan: dict) -> None:
    """Show the script check; a blocking finding stops paid narration unless accepted."""
    result = judge.episode_script_check(
        audio.ROOT, plan["episode"]["id"], plan["script"], getattr(args, "judge", "standard")
    )
    report(result.text(), flush=True)
    recording = audio.ROOT / "artifacts/audio" / plan["episode"]["id"] / plan["fingerprint"][:16]
    if (recording / "episode.mp3").is_file():
        return  # Narration is already saved; nothing paid is decided here.
    accepted = judge.check_override(result, getattr(args, "accept_script", None), "Paid narration")
    if accepted:
        report(f"Script findings accepted: {accepted['override_reason']}", flush=True)


def make(args: argparse.Namespace) -> Path | None:
    # Validate the reviewed source before preparing Cloud resources.
    script_gate(args, audio.make_plan(args.episode, args.model, args.endpoint))
    caption_model(args)
    ensure_setup(args)
    raise_if_stopped(args)
    with timed("generation_and_encoding"):
        path = audio.generate(args)
    raise_if_stopped(args)
    return caption_recording(path, args)


def caption_recording(path: Path, args: argparse.Namespace) -> Path | None:
    """Submit or resume captions for this recording without calling synthesis."""
    model = caption_model(args)
    caption_args = argparse.Namespace(
        command="captions",
        audio=path,
        project=args.project,
        bucket=args.bucket,
        location=args.location,
        model=model,
        language=None,
        diarize=None,
        auth=args.auth,
        script=None,
        dry_run=False,
        wait=args.wait,
        retry_uncertain=args.retry_uncertain,
        restart_failed=args.restart_failed,
        allow_spend_over_limit=getattr(args, "allow_spend_over_limit", None),
        spend_token=getattr(args, "spend_token", None),
    )
    prepare_captions(caption_args)
    caption_args._cancel_event = getattr(args, "_cancel_event", None)
    with timed("captioning_and_wait"):
        directory = captions.run(caption_args)
    finish(directory, args.no_open)
    return directory


def caption_model(args: argparse.Namespace) -> str:
    """Freeze a validated model across the batch's submission and polling phases."""
    model = getattr(args, "_caption_model", None) or read_settings().get("caption_model", "chirp_3")
    if model not in {"chirp_3", "long"} or (model == "chirp_3" and args.location == "global"):
        raise ValueError(
            "Saved caption model/location is unsupported; use Chirp 3 in us/eu or long in global"
        )
    return model


def add_arguments(commands: argparse._SubParsersAction) -> None:
    for name in ("setup", "make"):
        sub = commands.add_parser(
            name,
            help="Prepare and remember Cloud settings"
            if name == "setup"
            else "Generate/reuse audio, caption it and open a listening review",
        )
        if name == "make":
            sub.add_argument("episode")
            sub.add_argument("--wait", type=int, default=900)
            sub.add_argument("--no-open", action="store_true")
            sub.add_argument("--retry-uncertain", action="store_true")
            sub.add_argument("--restart-failed", action="store_true")
            spend_guard.add_override_argument(sub)
            audio.add_timeout_argument(sub)
            judge.add_arguments(
                sub,
                override="--accept-script",
                help_text="Narrate a script with a blocking script-check finding anyway",
            )
        sub.add_argument("--project")
        sub.add_argument("--bucket")
        sub.add_argument("--endpoint", choices=audio.ENDPOINTS)
        sub.add_argument(
            "--location",
            choices=("us", "eu"),
            help="Caption region; default us, independent of global TTS",
        )
        sub.add_argument("--model", choices=audio.MODELS)
        sub.add_argument("--auth", choices=("gcloud", "adc"))
