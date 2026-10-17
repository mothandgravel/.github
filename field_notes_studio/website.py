"""Prepare website update: run the engine's ``promote`` then ``publish``; never merge.

What the two engine commands do (``field_notes_audio``):

- ``promote <episode>`` (production/promotion.py) checks the full-episode approval,
  then writes the reviewed MP3, captions, transcript and the regenerated notes
  pages and podcast feed under ``docs/``, and records them in
  ``artifacts/audio/release.json``. Local files only.
- ``publish --branch <name>`` (release.py ``_publish``) takes the publication lock,
  refuses Git changes other than those prepared files, rebuilds and checks the
  site, then on ``main``: ``git switch -c <name>``, commits only the prepared
  paths, and ``git push <remote> HEAD:refs/heads/<name>``. The remote is the
  branch's upstream remote, else ``origin``, and its URL must be GitHub
  ``mothandgravel/.github``. The push uses this checkout's own Git credentials
  (SSH key or credential helper). If ``gh`` is installed and signed in, it then
  looks for or opens a pull request into ``main`` with ``gh``'s own login.
  Nothing merges or deploys: merging stays a person's action on GitHub.

This runner adds its own refusals before anything runs, and repeats them right
before running: the checkout must be this repository at its top level, on
``main``, matching the last fetched ``<remote>/main``, with no uncommitted or
untracked files, and the new branch name must not exist. The only commands it
can run are the two in ``commands()``; there is no shell and no other argv.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = re.compile(
    r"(?:https://github\.com/|git@github\.com:)mothandgravel/\.github(?:\.git)?"
)
EPISODE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
BRANCH = re.compile(r"studio/field-notes-listening-\d{8}-\d{6}")
ENGINE_COMMANDS = frozenset({"promote", "publish"})
PULL_REQUEST = re.compile(r"https://github\.com/mothandgravel/\.github/pull/\d+")


@dataclass(frozen=True)
class WebsitePlan:
    episode: str
    root: str
    remote: str = ""
    remote_url: str = ""
    head: str = ""
    branch: str = ""
    commands: tuple[tuple[str, ...], ...] = ()
    refusals: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.refusals and bool(self.commands)

    def describe(self) -> str:
        """The dry-run text the confirm dialog shows, word for word what will run."""
        lines = [f"In {self.root}:"]
        lines += ["  " + " ".join(command[1:]) for command in self.commands]
        lines += [
            "",
            f"1. promote prepares the reviewed {self.episode} files for the website and "
            "podcast feed, in this checkout only.",
            f"2. publish commits them on a new branch {self.branch} (from main at "
            f"{self.head[:12]}) and pushes that branch to {self.remote} ({self.remote_url}) "
            "with this computer's Git login. If the GitHub CLI is signed in, it opens a "
            "pull request into main.",
            "",
            "Nothing is merged or deployed. You merge the pull request on GitHub when you "
            "are ready. Afterwards this checkout stays on the new branch.",
        ]
        return "\n".join(lines)


@dataclass(frozen=True)
class WebsiteResult:
    ok: bool
    summary: str
    branch: str = ""
    pull_request: str = ""
    output: tuple[str, ...] = field(default=(), repr=False)


def git(root: Path, *arguments: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return result.returncode, result.stdout.strip()


def commands(python: str, episode: str, branch: str) -> tuple[tuple[str, ...], ...]:
    return (
        (python, "-m", "field_notes_audio", "promote", episode),
        (python, "-m", "field_notes_audio", "publish", "--branch", branch),
    )


def plan(root: Path, episode: str, *, python: str = sys.executable, now=None) -> WebsitePlan:
    """Read-only checks; returns every refusal rather than stopping at the first."""
    root = root.resolve()
    refusals: list[str] = []
    if not EPISODE.fullmatch(episode or ""):
        return WebsitePlan(episode, str(root), refusals=("Choose an episode first.",))
    code, top = git(root, "rev-parse", "--show-toplevel")
    if code or Path(top).resolve() != root:
        return WebsitePlan(
            episode, str(root), refusals=("This Studio folder is not the top of a Git checkout.",)
        )
    code, current = git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if code or current != "main":
        refusals.append(
            f"The checkout is on {current or 'a detached commit'}, not main. "
            "Switch to main first; the update starts a new branch from it."
        )
    code, upstream = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "main@{u}")
    remote = upstream.split("/", 1)[0] if code == 0 and "/" in upstream else "origin"
    code, url = git(root, "remote", "get-url", remote)
    if code or not REPOSITORY.fullmatch(url):
        refusals.append(
            f"The {remote} remote is not GitHub mothandgravel/.github, so nothing will be pushed."
        )
    code, status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if code:
        refusals.append("Git status could not be read.")
    elif status:
        files = [line[3:] for line in status.splitlines()][:5]
        refusals.append(
            "This checkout has changes that are not committed: "
            + ", ".join(files)
            + (" …" if len(status.splitlines()) > 5 else "")
            + ". Commit or discard them first, so only the website update is pushed."
        )
    _, head = git(root, "rev-parse", "HEAD")
    code, tracked = git(root, "rev-parse", f"refs/remotes/{remote}/main")
    if code:
        refusals.append(f"{remote}/main is unknown here. Fetch first.")
    elif tracked != head:
        refusals.append(
            f"main is not the same as {remote}/main. Pull or push first, so the update "
            "starts from the published site."
        )
    moment = now or datetime.now(timezone.utc)
    branch = "studio/field-notes-listening-" + moment.strftime("%Y%m%d-%H%M%S")
    if git(root, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch)[0] == 0:
        refusals.append(f"A branch named {branch} already exists. Try again in a second.")
    return WebsitePlan(
        episode,
        str(root),
        remote,
        url,
        head,
        branch,
        commands(python, episode, branch),
        tuple(refusals),
    )


def _checked(plan: WebsitePlan) -> None:
    """The command list is fixed: two engine commands, no merge, no shell."""
    if len(plan.commands) != 2 or not BRANCH.fullmatch(plan.branch):
        raise ValueError("Unexpected website update plan")
    for command in plan.commands:
        if command[1:3] != ("-m", "field_notes_audio") or command[3] not in ENGINE_COMMANDS:
            raise ValueError("Unexpected website update command")
        if any("merge" in part for part in command):
            raise ValueError("Studio never merges")


def readable(lines: list[str]) -> str:
    for line in reversed(lines):
        if line.startswith("Audio setup: "):
            return line.removeprefix("Audio setup: ")
    meaningful = [line for line in lines if line.strip()]
    return meaningful[-1][:300] if meaningful else "It stopped without a message."


def run(
    shown: WebsitePlan,
    *,
    confirmed: bool,
    emit: Callable[[str], None],
) -> WebsiteResult:
    """Run promote, then publish, streaming output. Stops at the first failure."""
    if confirmed is not True:
        raise ValueError("Confirm the website update first; nothing ran.")
    _checked(shown)
    fresh = plan(Path(shown.root), shown.episode)
    if fresh.refusals:
        return WebsiteResult(False, "Nothing ran. " + " ".join(fresh.refusals))
    if (
        git(Path(shown.root), "rev-parse", "--verify", "--quiet", "refs/heads/" + shown.branch)[0]
        == 0
    ):
        return WebsiteResult(False, f"Nothing ran. {shown.branch} already exists.")
    if (fresh.head, fresh.remote, fresh.remote_url) != (
        shown.head,
        shown.remote,
        shown.remote_url,
    ):
        return WebsiteResult(False, "The checkout changed since you confirmed. Nothing ran.")
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1"}
    output: list[str] = []
    for index, command in enumerate(shown.commands):
        emit("$ " + " ".join(command[1:]))
        lines = []
        with subprocess.Popen(
            list(command),
            cwd=shown.root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
        ) as process:
            for line in process.stdout or ():
                line = line.rstrip("\n")
                lines.append(line)
                emit(line)
            code = process.wait()
        output += lines
        if code != 0:
            reason = readable(lines)
            if index == 0:
                return WebsiteResult(
                    False,
                    f"promote stopped: {reason} Nothing was committed or pushed.",
                    output=tuple(output),
                )
            return WebsiteResult(
                False,
                f"publish stopped: {reason} The files promote prepared are still in this "
                "checkout; check git status before trying again. Nothing was merged.",
                output=tuple(output),
            )
    _, current = git(Path(shown.root), "symbolic-ref", "--quiet", "--short", "HEAD")
    link = next((m.group(0) for line in output if (m := PULL_REQUEST.search(line))), "")
    return WebsiteResult(
        True,
        f"Pushed {shown.branch} to {shown.remote}. "
        + (f"Pull request: {link}. " if link else "Open a pull request on GitHub. ")
        + "Merge it on GitHub when ready; Studio never merges. This checkout is now on "
        + (current or shown.branch)
        + "; switch back to main before the next update.",
        branch=shown.branch,
        pull_request=link,
        output=tuple(output),
    )
