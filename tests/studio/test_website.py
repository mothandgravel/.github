"""Prepare website update: refusals, the dry-run text, streaming and never merging.

Every test uses a temporary Git checkout whose GitHub remote URL is rewritten for
pushes to a local bare repository (``url.<bare>.pushInsteadOf``). SSH is disabled
for the whole test process, so a broken rewrite fails instead of reaching GitHub.
"""

import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio, release
from field_notes_studio import website

GITHUB = "git@github.com:mothandgravel/.github.git"
NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
BRANCH = "studio/field-notes-listening-20261017-120000"

FAKE_ENGINE = """#!{python}
import os, subprocess, sys
args = sys.argv[1:]
assert args[:2] == ["-m", "field_notes_audio"], args
command = args[2]
if command == "promote":
    print("Checking the review of", args[3], flush=True)
    if os.environ.get("FAKE_PROMOTE_FAIL"):
        print("Audio setup: ep: listen and approve this finished edition before promotion")
        sys.exit(1)
    os.makedirs("docs/notes", exist_ok=True)
    open("docs/notes/ep.html", "w").write("<p>new</p>\\n")
    print("Prepared 1 reviewed finished editions.")
elif command == "publish":
    branch = args[args.index("--branch") + 1]
    for step in (["switch", "-c", branch], ["add", "docs"], ["commit", "-qm", "Publish"],
                 ["push", "-q", "origin", "HEAD:refs/heads/" + branch]):
        subprocess.run(["git", *step], check=True)
    print("https://github.com/mothandgravel/.github/pull/77")
else:
    sys.exit(2)
"""

FAKE_GH = """#!/bin/sh
echo "$@" >> "{log}"
case "$2" in
  list) echo "[]" ;;
  create) echo "https://github.com/mothandgravel/.github/pull/78" ;;
esac
"""


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


class Checkout:
    def __init__(self, case):
        temporary = tempfile.TemporaryDirectory()
        case.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.bare, self.work = base / "remote.git", base / "work"
        environment = patch.dict(
            os.environ,
            {
                "GIT_SSH_COMMAND": "false",
                "GIT_CONFIG_GLOBAL": str(base / "gitconfig"),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            },
        )
        environment.start()
        case.addCleanup(environment.stop)
        git(base, "init", "-q", "--bare", "-b", "main", str(self.bare))
        git(base, "init", "-q", "-b", "main", str(self.work))
        (self.work / ".gitignore").write_text("artifacts/\nengine\n")
        (self.work / "README.md").write_text("site\n")
        git(self.work, "add", ".")
        git(self.work, "commit", "-qm", "Start")
        git(self.work, "remote", "add", "origin", GITHUB)
        git(self.work, "config", f"url.{self.bare}.pushInsteadOf", GITHUB)
        git(self.work, "push", "-q", "origin", "main")
        git(self.work, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(self.work, "config", "branch.main.remote", "origin")
        git(self.work, "config", "branch.main.merge", "refs/heads/main")
        self.main = git(self.bare, "rev-parse", "main")
        self.engine = self.work / "engine"
        self.engine.write_text(FAKE_ENGINE.format(python=sys.executable))
        self.engine.chmod(self.engine.stat().st_mode | stat.S_IEXEC)

    def plan(self, episode="ep"):
        return website.plan(self.work, episode, python=str(self.engine), now=NOW)

    def remote_branches(self):
        return git(self.bare, "for-each-ref", "--format=%(refname:short)", "refs/heads")


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.c = Checkout(self)

    def test_clean_main_plan_shows_exactly_what_will_run(self):
        plan = self.c.plan()
        self.assertEqual(plan.refusals, ())
        self.assertEqual(plan.branch, BRANCH)
        self.assertEqual((plan.remote, plan.remote_url), ("origin", GITHUB))
        self.assertEqual(
            plan.commands,
            (
                (str(self.c.engine), "-m", "field_notes_audio", "promote", "ep"),
                (str(self.c.engine), "-m", "field_notes_audio", "publish", "--branch", BRANCH),
            ),
        )
        text = plan.describe()
        self.assertIn("python3 -m field_notes_audio promote ep", text)
        self.assertIn("-m field_notes_audio publish --branch " + BRANCH, text)
        self.assertIn(f"pushes that branch to origin ({GITHUB})", text)
        self.assertIn("Nothing is merged or deployed", text)
        self.assertFalse(any("merge" in part for command in plan.commands for part in command))

    def test_dirty_tree_refuses(self):
        (self.c.work / "notes.txt").write_text("draft")
        plan = self.c.plan()
        self.assertTrue(any("not committed: notes.txt" in r for r in plan.refusals))

    def test_wrong_branch_refuses(self):
        git(self.c.work, "switch", "-q", "-c", "feature")
        self.assertTrue(any("not main" in r for r in self.c.plan().refusals))

    def test_wrong_repository_refuses(self):
        git(self.c.work, "remote", "set-url", "origin", "git@github.com:someone/else.git")
        self.assertTrue(
            any("not GitHub mothandgravel/.github" in r for r in self.c.plan().refusals)
        )

    def test_main_behind_or_ahead_of_the_remote_refuses(self):
        (self.c.work / "README.md").write_text("changed\n")
        git(self.c.work, "commit", "-qam", "Local only")
        self.assertTrue(any("not the same as origin/main" in r for r in self.c.plan().refusals))

    def test_not_the_checkout_top_or_bad_episode_refuses(self):
        (self.c.work / "sub").mkdir()
        self.assertTrue(website.plan(self.c.work / "sub", "ep").refusals)
        self.assertTrue(website.plan(self.c.work, "../ep").refusals)

    def test_nothing_runs_without_confirm_or_with_a_changed_command_list(self):
        plan = self.c.plan()
        with self.assertRaisesRegex(ValueError, "Confirm"):
            website.run(plan, confirmed=False, emit=print)
        for commands in (
            plan.commands + (("x", "-m", "field_notes_audio", "promote", "ep"),),
            ((str(self.c.engine), "-m", "field_notes_audio", "merge", "ep"), plan.commands[1]),
            (plan.commands[0], ("gh", "pr", "merge", "--auto", "1", "x", "y")),
        ):
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                website.run(
                    website.WebsitePlan(**{**plan.__dict__, "commands": commands}),
                    confirmed=True,
                    emit=print,
                )
        self.assertEqual(self.c.remote_branches(), "main")

    def test_a_refusal_found_at_run_time_stops_before_anything_runs(self):
        plan = self.c.plan()
        (self.c.work / "notes.txt").write_text("draft")
        result = website.run(plan, confirmed=True, emit=lambda _line: None)
        self.assertFalse(result.ok)
        self.assertIn("Nothing ran", result.summary)
        self.assertFalse((self.c.work / "docs").exists())


class RunTests(unittest.TestCase):
    def setUp(self):
        self.c = Checkout(self)

    def test_streams_output_pushes_a_new_branch_and_never_touches_main(self):
        lines = []
        result = website.run(self.c.plan(), confirmed=True, emit=lines.append)
        self.assertTrue(result.ok, result.summary)
        self.assertEqual(lines[0], "$ -m field_notes_audio promote ep")
        self.assertIn("Prepared 1 reviewed finished editions.", lines)
        self.assertIn(f"$ -m field_notes_audio publish --branch {BRANCH}", lines)
        self.assertEqual(result.pull_request, "https://github.com/mothandgravel/.github/pull/77")
        self.assertIn("Studio never merges", result.summary)
        self.assertEqual(sorted(self.c.remote_branches().split()), ["main", BRANCH])
        self.assertEqual(git(self.c.bare, "rev-parse", "main"), self.c.main)
        self.assertEqual(git(self.c.work, "branch", "--show-current"), BRANCH)

    def test_promote_failure_is_readable_and_publish_never_runs(self):
        lines = []
        with patch.dict(os.environ, {"FAKE_PROMOTE_FAIL": "1"}):
            result = website.run(self.c.plan(), confirmed=True, emit=lines.append)
        self.assertFalse(result.ok)
        self.assertEqual(
            result.summary,
            "promote stopped: ep: listen and approve this finished edition before promotion "
            "Nothing was committed or pushed.",
        )
        self.assertFalse(any("publish" in line for line in lines))
        self.assertEqual(self.c.remote_branches(), "main")


class EnginePublishTests(unittest.TestCase):
    """The real ``release.publish`` against the temporary checkout and bare remote."""

    def setUp(self):
        self.c = Checkout(self)
        self.log = self.c.work.parent / "gh.log"
        bin_dir = self.c.work.parent / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH.format(log=self.log))
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        path = patch.dict(os.environ, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})
        path.start()
        self.addCleanup(path.stop)
        (self.c.work / "docs/notes").mkdir(parents=True)
        page = self.c.work / "docs/notes/ep.html"
        page.write_text("<p>new</p>\n")
        journal = self.c.work / "artifacts/audio/release.json"
        journal.parent.mkdir(parents=True)
        journal.write_text(
            json.dumps(
                {
                    "version": 1,
                    "phase": "complete",
                    "edition": "finished",
                    "files": {"docs/notes/ep.html": audio.digest_file(page)},
                }
            )
        )
        for target in (
            patch.object(release.audio, "ROOT", self.c.work),
            patch.object(release.build_audio, "build"),
        ):
            target.start()
            self.addCleanup(target.stop)

    def test_publish_pushes_only_the_named_branch_and_opens_a_pull_request(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            release.publish(BRANCH)
        self.assertEqual(sorted(self.c.remote_branches().split()), ["main", BRANCH])
        self.assertEqual(git(self.c.bare, "rev-parse", "main"), self.c.main)
        self.assertEqual(git(self.c.bare, "show", f"{BRANCH}:docs/notes/ep.html"), "<p>new</p>")
        calls = self.log.read_text().splitlines()
        self.assertEqual([c.split()[:2] for c in calls], [["pr", "list"], ["pr", "create"]])
        self.assertIn("--base main", calls[1])
        self.assertFalse(any("merge" in call for call in calls))
        self.assertIn("pull/78", output.getvalue())

    def test_branch_option_is_validated_and_only_starts_from_main(self):
        with self.assertRaisesRegex(Exception, "studio/field-notes-listening"):
            release.publication_branch("main")
        git(self.c.work, "switch", "-q", "-c", "other")
        with self.assertRaisesRegex(ValueError, "switch to main"):
            release.publish(BRANCH)
        self.assertEqual(self.c.remote_branches(), "main")
        self.assertFalse(self.log.exists())

    def test_engine_and_runner_never_merge(self):
        self.assertNotIn('"merge"', Path(release.__file__).read_text())
        for path in (Path(release.__file__), Path(website.__file__)):
            source = path.read_text()
            self.assertNotIn('"pr", "merge"', source)
            self.assertNotIn('"git", "merge"', source)
            self.assertNotIn("--auto", source)


if __name__ == "__main__":
    unittest.main()
