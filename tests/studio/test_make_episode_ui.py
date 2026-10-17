"""Make episode in the real Tk window: work list, one-confirm summary, run timeline,
website confirm. Every value is a controlled example; no job runs and nothing is sent.

Set STUDIO_SCREENSHOT_DIR to save captures (used for the prototype comparisons).
"""

import os
import time
import unittest
from unittest.mock import patch

from field_notes_studio.make_models import (
    Attempt,
    MakePlan,
    PlanStep,
    RunView,
    SpendState,
    TimelineRow,
)
from field_notes_studio.website import WebsitePlan, WebsiteResult
from field_notes_studio.work_list import WorkItem, WorkList
from tests.studio import test_ui

SPEND = SpendState(
    limits="Spend guard: at most 2 uncertain paid attempts per part and 4 per episode in 24 h.",
    part_limit=2,
    episode_limit=4,
    window_hours=24,
    episode_window=0,
    part_window=0,
    possible="no uncertain spend recorded in this window",
)
PLAN = MakePlan(
    episode="maritime-study",
    note="014",
    title="Maritime study",
    words=1964,
    checked_at="10:02",
    recipe_label="Pace 1.15×, motif intro (4 s), 5 s outro, −16 LUFS",
    steps=(
        PlanStep("narrate", "Narrate", "3 of 3 parts with the cloud voice", "paid"),
        PlanStep(
            "caption",
            "Caption",
            "Timed subtitles from the narration, about 14 min of audio; no local price",
            "paid",
        ),
        PlanStep(
            "sound", "Finish sound", "Pace 1.15×, motif intro (4 s), 5 s outro, −16 LUFS", "local"
        ),
        PlanStep("video", "Make video", "Full video and thumbnail", "local"),
        PlanStep("review", "Your review", "Watch once, check subtitles, approve", "you"),
        PlanStep("package", "Upload package", "Made automatically after you approve", "local"),
    ),
    spend=SPEND,
    reused=(),
    blockers=(),
    project="mothandgravel-audio",
    estimate_usd=0.12,
    request_json='{"note": "014"}',
    token="t" * 64,
)
COST = (
    "So far, by local estimate (not a bill): narration about $0.12 (3 saved parts); captions: "
    "no local estimate (1 submission, about 14 min of audio). Check the Cloud billing report "
    "for actual charges."
)
ATTEMPTS = (
    Attempt("17 Oct 10:07", "narration part 3", "HTTP 502", "about $0.04"),
    Attempt("17 Oct 11:02", "narration part 3", "HTTP 499", "about $0.04"),
)
WORK = WorkList(
    (
        WorkItem(
            "work-outlives-the-window",
            "013 · The work outlives the window",
            "Review full episode",
            "Made 21:12 · 14:32",
            "needs-you",
            "review",
            "Review",
            run="run-013",
        ),
        WorkItem(
            "maritime-study",
            "014 · Maritime study",
            "Narration paused · provider failing",
            "Spend guard stopped part 3",
            "needs-you",
            "health",
            "Open",
            run="run-014",
        ),
        WorkItem(
            "note-001",
            "011 · Specimen return",
            "Upload folder ready",
            "Not yet recorded as published",
            "needs-you",
            "package",
            "Release",
        ),
        WorkItem(
            "coastal-watch",
            "012 · Coastal watch",
            "Make video · working",
            "4 min elapsed · 6–9 min on this computer before",
            "working",
            "video",
            "Open",
            run="run-012",
        ),
        *(
            WorkItem(
                f"done-{n}",
                f"{n:03d} · Released note",
                "Released",
                "Release record saved",
                "done",
                "check",
                "Done",
            )
            for n in range(1, 11)
        ),
    ),
    not_started=3,
)


def rows(*states):
    names = ("Narrate", "Caption", "Finish sound", "Make video", "Your review", "Upload package")
    keys = ("narrate", "caption", "sound", "video", "review", "package")
    return tuple(
        TimelineRow(key, name, state, detail, kind)
        for key, name, (state, detail, kind) in zip(keys, names, states, strict=True)
    )


WORKING = RunView(
    "run-012",
    "coastal-watch",
    "",
    "10:04",
    "working",
    "working",
    "Make video · working",
    "",
    rows(
        ("Saved", "3 of 3 parts · 7 min · 10:04 – 10:11", "ok"),
        ("Saved", "2 min · 10:11 – 10:13", "ok"),
        ("Saved", "1 min · 10:13 – 10:14", "ok"),
        ("Working", "4 min elapsed · 6–9 min on this computer before", "run"),
        ("Next", "We will tell you when it is ready", "todo"),
        ("After review", "Local, automatic once approved", "todo"),
    ),
    job="job-1",
    current="video",
)
PAUSED = RunView(
    "run-014",
    "maritime-study",
    "",
    "10:04",
    "paused",
    "needs-you",
    "Narration paused · nothing will be sent until you choose",
    "Part 3 of 3 failed: a gateway error, then a cancelled request. Parts 1 and 2 are "
    "saved and safe. The spend guard stopped further attempts.",
    rows(
        ("Paused", "2 of 3 parts saved · part 3: provider failing", "warn"),
        ("Next", "Starts after narration", "todo"),
        ("Next", "Local", "todo"),
        ("Next", "Local", "todo"),
        ("Next", "We will tell you when it is ready", "todo"),
        ("After review", "Local, automatic once approved", "todo"),
    ),
    job="job-2",
    current="narrate",
)


class Runs:
    def __init__(self, views):
        self.views = views

    def view(self, run_id):
        return self.views[run_id]


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tk integration requires DISPLAY or xvfb-run")
class MakeEpisodeUITests(unittest.TestCase):
    # The shared Tk fixture, without re-running UITests' own tests.
    wait = test_ui.UITests.wait
    capture = test_ui.UITests.capture

    def setUp(self):
        views = {"run-012": WORKING, "run-014": PAUSED}
        for target in (
            patch("field_notes_studio.service.Studio.work_list", return_value=WORK),
            patch("field_notes_studio.service.Studio.make_plan", return_value=PLAN),
            patch("field_notes_studio.service.Studio.runs", return_value=Runs(views)),
            patch("field_notes_studio.service.Studio.spend_state", return_value=SPEND),
            patch("field_notes_studio.service.Studio.cost_line", return_value=COST),
            patch(
                "field_notes_studio.repository.Repository.run",
                side_effect=lambda run_id: {"note": run_id.split("-")[1], "episode": "x"},
            ),
        ):
            target.start()
            self.addCleanup(target.stop)
        test_ui.UITests.setUp(self)
        self.root.geometry("1280x760")
        self.app.show_view("home")
        self.wait(lambda: self.app.home.work is not None)

    def settle(self, seconds=0.3):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)

    def test_home_groups_by_who_acts_next_with_one_brass_action(self):
        home = self.app.home
        headings = [
            w.cget("text")
            for w in home.content.winfo_children()
            if str(w.cget("style") if "style" in w.keys() else "") == "Heading.TLabel"
        ]
        self.assertEqual(headings, ["NEEDS YOU", "WORKING"])
        self.assertEqual(
            list(home.rows),
            ["work-outlives-the-window", "maritime-study", "note-001", "coastal-watch"],
        )
        self.assertEqual(str(self.app.prepare_button.cget("style")), "Accent.TButton")
        self.assertFalse(self.app.home_button.winfo_manager())
        self.settle()
        self.capture("b-home-work-list")
        home.toggle_done()
        self.assertEqual(len(home.rows), 14)
        # Keyboard: the first Open is focusable; Ctrl+H returns home from the expert view.
        self.app.show_view("episodes")
        self.assertTrue(self.app.home_button.winfo_manager())
        self.app.root.event_generate("<Control-h>")
        self.settle()
        self.assertEqual(self.app.view_name, "home")

    def test_preflight_shows_cost_and_needs_the_tick(self):
        self.app.flow.open_preflight(note="014")
        dialog = self.app.flow.preflight
        self.wait(lambda: dialog.plan is not None)
        self.settle()
        self.assertEqual(dialog.title.cget("text"), "Make Field Note 014 into an episode")
        self.assertEqual(str(dialog.make_button["state"]), "disabled")
        texts = [w.cget("text") for w in dialog.plan_card.winfo_children() if "text" in w.keys()]
        for expected in ("Narrate", "Paid", "Local", "You", "Made automatically after you approve"):
            self.assertIn(expected, texts)
        money = [w.cget("text") for w in dialog.money_card.winfo_children() if "text" in w.keys()]
        self.assertIn("about $0.12", money)
        self.assertEqual(PLAN.estimate_text, "about $0.12")
        self.assertIn("0 uncertain attempts recorded", money)
        self.assertIn("mothandgravel-audio", money)
        dialog.window.geometry("1180x640")
        self.settle()
        self.capture_window(dialog.window, "b-make-episode-preflight")
        dialog.consent.invoke()
        self.assertEqual(str(dialog.make_button["state"]), "normal")
        with patch(
            "field_notes_studio.service.Studio.make_episode", return_value="run-012"
        ) as start:
            dialog.make_button.invoke()
            self.wait(lambda: self.app.view_name == "run")
        start.assert_called_once_with(PLAN, True, "")

    def test_blocked_summary_offers_no_confirm(self):
        blocked = PLAN.__class__(
            **{
                **PLAN.__dict__,
                "blockers": (
                    "Narration part 3 has an earlier attempt with no saved result. Sending it "
                    "again can charge twice, so it needs its own consent.",
                ),
            }
        )
        with patch("field_notes_studio.service.Studio.make_plan", return_value=blocked):
            self.app.flow.open_preflight(note="014")
            dialog = self.app.flow.preflight
            self.wait(lambda: dialog.plan is not None)
        self.assertFalse(dialog.consent.winfo_ismapped())
        self.assertEqual(str(dialog.make_button["state"]), "disabled")
        dialog.confirm()
        dialog.window.event_generate("<Escape>")
        self.settle()
        self.assertFalse(dialog.window.winfo_exists())

    def test_run_timeline_and_paused_ledger(self):
        self.app.flow.show_run("run-012")
        panel = self.app.run_panel
        self.wait(lambda: panel.view is not None)
        self.settle()
        self.assertEqual(self.app.brand.cget("text"), "MOTH & GRAVEL  /  MAKE EPISODE")
        self.assertEqual(panel.title.cget("text"), "Field Note 012 · Coastal watch")
        self.assertEqual(
            self.app.activity.cget("text").strip(), "Making the video for Field Note 012 · 4 min"
        )
        self.assertNotIn("left", self.app.message_text)
        self.assertEqual(panel.cost.cget("text"), COST)
        self.assertEqual(panel.cells[3][2].cget("text"), "Working")
        self.assertIn("6–9 min on this computer before", panel.cells[3][3].cget("text"))
        self.assertEqual(str(panel.stop_button["state"]), "normal")
        self.assertFalse(panel.alert.winfo_ismapped())
        self.capture("b-progress-timeline")
        failing = patch(
            "field_notes_studio.service.Studio.spend_state",
            return_value=SpendState(**{**SPEND.__dict__, "attempts": ATTEMPTS}),
        )
        failing.start()
        self.addCleanup(failing.stop)
        self.app.flow.show_run("run-014")
        self.wait(lambda: panel.view is PAUSED)
        self.root.geometry("1280x860")
        self.settle()
        self.assertTrue(panel.alert.winfo_ismapped())
        self.assertEqual(len(panel.ledger.get_children()), 2)
        self.assertEqual(panel.retry_button.cget("text"), "Try narration part 3 once more…")
        self.capture("b-provider-failure-spend-guard")
        with patch.object(self.app, "open_preparation") as recover:
            panel.retry_button.invoke()
        recover.assert_called_once_with(note="014")
        self.app.root.event_generate("<Control-h>")
        self.settle()
        self.assertEqual(self.app.view_name, "home")

    def test_a_failed_local_step_runs_again_and_a_run_can_be_closed(self):
        failed = RunView(
            **{
                **PAUSED.__dict__,
                "identifier": "run-012",
                "detail": "Renderer crashed.",
                "retry_free": True,
            }
        )
        views = {"run-012": failed}
        with (
            patch("field_notes_studio.service.Studio.runs", return_value=Runs(views)),
            patch("field_notes_studio.service.Studio.continue_run") as again,
            patch("field_notes_studio.service.Studio.close_run") as close,
        ):
            self.app.flow.show_run("run-012")
            panel = self.app.run_panel
            self.wait(lambda: panel.view is failed)
            self.settle()
            self.assertEqual(panel.retry_button.cget("text"), "Run this step again (free)")
            panel.retry_button.invoke()
            self.wait(lambda: again.called)
            again.assert_called_once_with("run-012")
            panel.close_link.command()
            self.wait(lambda: self.app.view_name == "home")
            close.assert_called_once_with("run-012")

    def test_release_shows_the_cost_so_far(self):
        self.app.show_episode("note-001", stage=2)
        publication = self.app.workspace.publication
        self.wait(lambda: publication.cost.cget("text") == COST)
        self.assertIn("not a bill", publication.cost.cget("text"))
        self.root.geometry("1280x860")
        self.settle()
        self.capture("release-cost-so-far")

    def test_website_confirm_shows_the_dry_run_and_refusals(self):
        plan = WebsitePlan(
            "note-001",
            "/checkout",
            "origin",
            "git@github.com:mothandgravel/.github.git",
            "0123456789abcdef",
            "studio/field-notes-listening-20261017-120000",
            ("git@github.com:mothandgravel/.github.git",),
            (
                ("python3", "-m", "field_notes_audio", "promote", "note-001"),
                (
                    "python3",
                    "-m",
                    "field_notes_audio",
                    "publish",
                    "--branch",
                    "studio/field-notes-listening-20261017-120000",
                ),
            ),
        )
        with patch("field_notes_studio.service.Studio.website_plan", return_value=plan):
            self.app.open_website("note-001")
            dialog = self.app.flow.website
            self.wait(lambda: dialog.plan is not None)
        self.settle()
        text = dialog.output.get("1.0", "end")
        self.assertIn("-m field_notes_audio publish --branch studio/", text)
        self.assertIn("Nothing is merged or deployed", text)
        self.assertEqual(str(dialog.confirm_button["state"]), "normal")
        self.capture_window(dialog.window, "b-website-confirm")
        result = WebsiteResult(True, "Pushed the branch. Studio never merges.", plan.branch)

        def update(shown, *, confirmed, emit):
            self.assertIs(confirmed, True)
            emit("$ -m field_notes_audio promote note-001")
            emit("Prepared 1 reviewed finished editions.")
            return result

        with patch("field_notes_studio.service.Studio.website_update", side_effect=update):
            dialog.confirm_button.invoke()
            self.wait(lambda: not dialog.running and "Prepared" in dialog.output.get("1.0", "end"))
        self.assertEqual(dialog.heading.cget("text"), "Branch pushed for review")
        refused = WebsitePlan(
            **{**plan.__dict__, "refusals": ("The checkout is on feature, not main.",)}
        )
        with patch("field_notes_studio.service.Studio.website_plan", return_value=refused):
            self.app.open_website("note-001")
            self.wait(lambda: dialog.plan is refused)
        self.assertEqual(str(dialog.confirm_button["state"]), "disabled")
        self.assertTrue(dialog.refusals.winfo_ismapped())
        # A late plan for another episode never replaces the one asked for last.
        dialog.show(WebsitePlan(**{**plan.__dict__, "episode": "other-episode"}))
        self.assertIs(dialog.plan, refused)

    def capture_window(self, window, name):
        destination = os.environ.get("STUDIO_SCREENSHOT_DIR")
        if not destination:
            return
        import subprocess
        from pathlib import Path

        window.update()
        Path(destination).mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "x11grab",
                "-draw_mouse",
                "0",
                "-video_size",
                f"{window.winfo_width()}x{window.winfo_height()}",
                "-i",
                f"{os.environ['DISPLAY']}+{window.winfo_rootx()},{window.winfo_rooty()}",
                "-frames:v",
                "1",
                "-update",
                "1",
                "-y",
                str(Path(destination) / f"{name}.png"),
            ],
            check=True,
            timeout=15,
            stdout=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    unittest.main()
