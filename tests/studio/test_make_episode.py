"""Make episode: one consent, chained jobs, resume after restart, package after approval.

Real SQLite, real preparation inspection and real narration/caption adapters with
every Cloud boundary mocked. Video rendering is replaced by a stub that writes a
saved directory, because Node/Remotion is not part of this test environment.
"""

import json
import tempfile
import unittest
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio
from field_notes_audio.storage import write_json
from field_notes_studio import make_plan, make_runs
from field_notes_studio.make_runs import AUTO_POLLS, Runs
from field_notes_studio.models import ReviewSnapshot
from field_notes_studio.repository import Repository
from field_notes_studio.service import Studio
from field_notes_studio.worker import advance_runs, execute
from tests.studio import test_preparation_execution as media_fixtures
from tests.studio.test_spend_guard_studio import uncertain


class Media:
    """The real preparation fixture: note 104 → episode studio-essay, one part."""

    def __init__(self, case):
        media_fixtures.PreparationExecutionTests.setUpClass()
        self.f = media_fixtures.PreparationExecutionTests()
        self.f.setUp()
        case.addCleanup(self.f.doCleanups)
        stack = ExitStack()
        case.addCleanup(stack.close)
        # No Node/Remotion here: tools and video artwork checks pass, nothing renders.
        stack.enter_context(patch("field_notes_studio.pipeline.runner.preflight"))
        stack.enter_context(patch("field_notes_studio.readiness.checked_assets"))
        self.launch = stack.enter_context(patch("field_notes_studio.service.launch_worker"))
        self.root = self.f.root
        self.studio = Studio(self.root)


class FakeVideo:
    """Stands in for the renderer: writes a saved edition directory."""

    def __init__(self, pipeline, root):
        self.pipeline, self.root, self.calls = pipeline, root, []

    def run(self, episode, action, request, directory, emit):
        self.calls.append(action)
        if action == "prepare":
            raise AssertionError("prepare runs through PreparationJobs")
        for stage in ("audio", "audio-complete") if action != "export" else ("export",):
            emit(stage, stage)
        if action == "video":
            emit("video", "Rendering")
            emit("video-complete", "Saved")
            target = self.root / "artifacts/production" / episode / "video-1"
            target.mkdir(parents=True, exist_ok=True)
            (target / "episode.mp4").write_bytes(b"video")
            return str(target)
        return str(self.root / "artifacts/uploads" / episode)


def run_next(media, pipeline):
    repository = media.studio.repository
    job = repository.claim()
    if job is None:
        return None
    execute(repository, pipeline, job)
    return repository.get(job.identifier)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.m = Media(self)

    def test_summary_separates_paid_local_and_reused_and_shows_the_spend_guard(self):
        plan = self.m.studio.make_plan(note="104")
        kinds = {step.key: step.kind for step in plan.steps}
        self.assertEqual(
            kinds,
            {
                "narrate": "paid",
                "caption": "paid",
                "sound": "local",
                "video": "local",
                "review": "you",
                "package": "local",
            },
        )
        narrate = next(s for s in plan.steps if s.key == "narrate")
        self.assertEqual(narrate.detail, "1 of 1 parts with the cloud voice")
        self.assertIn("Timed subtitles", next(s for s in plan.steps if s.key == "caption").detail)
        self.assertTrue(plan.paid)
        self.assertIsNotNone(plan.estimate_usd)
        self.assertEqual(plan.project, "fixture-project")
        self.assertEqual(plan.blockers, ())
        self.assertEqual(plan.spend.episode_window, 0)
        self.assertIn(
            "at most 2 uncertain paid attempts per part and 4 per episode", plan.spend.limits
        )
        self.assertIn("No uncertain paid attempts", plan.spend.sentence())
        self.assertRegex(plan.token, r"^[0-9a-f]{64}$")
        self.assertEqual(self.m.studio.repository.jobs(), [])

        # One uncertain attempt for this episode appears in the summary and changes it.
        uncertain(self.m.root, "studio-essay", "captions", 1, estimate=None)
        again = self.m.studio.make_plan(note="104")
        self.assertEqual(again.spend.episode_window, 1)
        self.assertEqual(len(again.spend.attempts), 1)
        self.assertIn("1 uncertain paid attempt(s)", again.spend.sentence())
        self.assertNotEqual(again.token, plan.token)
        self.assertEqual(again.blockers, ())

    def test_saved_parts_are_listed_as_reused_and_not_estimated(self):
        with self.m.f.cloud():
            self.m.f.run_adapter()
        plan = self.m.studio.make_plan(episode="studio-essay")
        kinds = {step.key: step.kind for step in plan.steps}
        self.assertEqual(kinds["narrate"], "reused")
        self.assertEqual(kinds["caption"], "reused")
        self.assertFalse(plan.paid)
        self.assertIsNone(plan.estimate_usd)
        self.assertEqual(plan.request_json, "")
        self.assertIn("narration", plan.reused)

    def test_one_confirm_needs_the_tick_and_queues_exactly_the_shown_request(self):
        plan = self.m.studio.make_plan(note="104")
        for value in (False, None, 1, "yes"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.studio.make_episode(plan, value)
        self.assertEqual(self.m.studio.repository.jobs(), [])
        self.m.launch.assert_not_called()
        run_id = self.m.studio.make_episode(plan, True)
        run = self.m.studio.repository.run(run_id)
        jobs = self.m.studio.repository.jobs()
        self.assertEqual([j.action for j in jobs], ["prepare"])
        self.assertEqual(json.loads(jobs[0].request), json.loads(plan.request_json))
        self.assertTrue(make_plan.FORBIDDEN.isdisjoint(json.loads(jobs[0].request)))
        consent = run["consent"]
        self.assertEqual(consent["token"], plan.token)
        self.assertEqual(len(consent["paid_steps"]), 2)
        self.assertIn("never an uncertain resend", consent["covers"])
        self.assertEqual(consent["spend_guard"]["uncertain_in_window"], 0)
        with self.assertRaisesRegex(ValueError, "work in progress|already has"):
            self.m.studio.make_episode(self.m.studio.make_plan(note="104"), True)

    def test_a_changed_summary_is_not_covered_by_the_earlier_confirm(self):
        plan = self.m.studio.make_plan(note="104")
        uncertain(self.m.root, "studio-essay", "captions", 1, estimate=None)
        with self.assertRaisesRegex(ValueError, "Something changed"):
            self.m.studio.make_episode(plan, True)
        self.m.f.text("audio/scripts/window.txt", "Hello world. A changed question.\n")
        with self.assertRaises(ValueError):
            self.m.studio.make_episode(plan, True)
        self.assertEqual(self.m.studio.repository.jobs(), [])

    def test_captions_only_never_reads_as_free(self):
        from field_notes_studio.preparation_models import CaptionsPending

        with self.m.f.cloud(pending=True), self.assertRaises(CaptionsPending):
            self.m.f.run_adapter()  # Narration saved; the caption operation is not done.
        plan = self.m.studio.make_plan(note="104")
        kinds = {step.key: step.kind for step in plan.steps}
        self.assertEqual((kinds["narrate"], kinds["caption"]), ("reused", "paid"))
        self.assertIsNone(plan.estimate_usd)
        self.assertEqual(plan.estimate_text, "no local estimate (captions)")
        self.assertIsNone(make_plan.consent_record(plan)["estimate_usd"])

    def test_an_open_run_is_never_replaced_silently(self):
        run_id = self.m.studio.make_episode(self.m.studio.make_plan(note="104"), True)
        repository = self.m.studio.repository
        job = repository.claim()
        repository.finish(job.identifier, "failed", error="No reply")
        plan = self.m.studio.make_plan(note="104")
        self.assertTrue(any("already has a Make episode run" in b for b in plan.blockers))
        with self.assertRaisesRegex(ValueError, "already has a Make episode run"):
            self.m.studio.make_episode(plan, True)
        self.assertFalse(repository.run(run_id)["closed"])

    def test_work_list_groups_by_who_acts_next(self):
        work = self.m.studio.work_list(check=False)
        note = next(i for i in work.items if i.identifier == "note:104")
        self.assertEqual((note.group, note.next), ("needs-you", "Make"))
        run_id = self.m.studio.make_episode(self.m.studio.make_plan(note="104"), True)
        work = self.m.studio.work_list(check=False)
        self.assertEqual(
            [(i.identifier, i.group, i.run) for i in work.items],
            [("studio-essay", "working", run_id)],
        )

    def test_a_reached_spend_guard_blocks_make_episode_without_an_override(self):
        uncertain(self.m.root, "studio-essay", "narration-1", 2)
        plan = self.m.studio.make_plan(note="104")
        self.assertTrue(plan.spend.blocked)
        self.assertTrue(any("spend guard" in b for b in plan.blockers))
        self.assertEqual(len(plan.spend.attempts), 2)
        with self.assertRaisesRegex(ValueError, "spend guard"):
            self.m.studio.make_episode(plan, True)
        self.assertEqual(self.m.studio.repository.jobs(), [])


class UncertainResendTests(unittest.TestCase):
    def setUp(self):
        self.m = Media(self)
        directory = self.m.f.adapter._recording(self.m.f.request["plan"])
        expected = audio.digest(
            json.dumps(self.m.f.request["plan"]["requests"][0], sort_keys=True).encode()
        )
        write_json(
            directory / "chunk-001.json",
            {"status": "uncertain", "request_sha256": expected, "http_status": 502},
        )

    def test_an_uncertain_part_is_never_covered_by_the_one_confirm(self):
        plan = self.m.studio.make_plan(note="104")
        self.assertEqual(plan.request_json, "")
        self.assertTrue(any("needs its own consent" in b for b in plan.blockers))
        self.assertEqual(plan.spend.episode_window, 1)
        with self.assertRaisesRegex(ValueError, "own consent"):
            self.m.studio.make_episode(plan, True)
        # Even a crafted plan carrying the recovery request is refused.
        snapshot = self.m.f.adapter.inspect("104")
        crafted = replace(plan, blockers=(), request_json=snapshot.recovery_json)
        with self.assertRaisesRegex(ValueError, "own consent"):
            make_plan.captured_request(crafted)
        self.assertEqual(self.m.studio.repository.jobs(), [])

    def test_the_expert_recovery_keeps_its_own_receipt_bound_consent(self):
        from field_notes_studio.preparation_service import PreparationService

        service = PreparationService(self.m.root)
        snapshot = service.inspect("104")
        with patch("field_notes_studio.preparation_service.launch_worker"):
            with self.assertRaisesRegex(
                ValueError, "separate explicit consent|authorize|explicitly allow"
            ):
                service.submit(snapshot, True)
            identifier = service.submit(snapshot, True, recover_uncertain=True)
        request = json.loads(self.m.studio.repository.get(identifier).request)
        self.assertIn("uncertain_chunks", request)


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.m = Media(self)
        self.video = FakeVideo(self.m.studio.pipeline, self.m.root)

    def start(self):
        return self.m.studio.make_episode(self.m.studio.make_plan(note="104"), True)

    def prepare_job(self):
        with self.m.f.cloud():
            return run_next(self.m, self.m.studio.pipeline)

    def test_prepare_then_video_survive_a_restart_and_never_double_queue(self):
        run_id = self.start()
        job = self.prepare_job()
        self.assertEqual(job.status, "succeeded", job.error)
        # Studio and the worker were closed here. A fresh process picks the run up.
        fresh = Studio(self.m.root)
        Runs(fresh).advance_all()
        Runs(Studio(self.m.root)).advance_all()
        steps = fresh.repository.run_steps(run_id)
        self.assertEqual([s["step"] for s in steps], ["prepare", "video"])
        self.assertEqual(
            [j.action for j in fresh.repository.jobs() if j.status == "queued"], ["video"]
        )
        view = fresh.runs().view(run_id)
        self.assertEqual(view.group, "working")
        self.assertEqual({r.key: r.state for r in view.rows}["narrate"], "Saved")
        states = {r.key: r.state for r in view.rows}
        self.assertEqual((states["sound"], states["video"]), ("Queued", "Waiting"))

        # The worker dies mid-render: recovery marks it interrupted, the run pauses.
        fresh.repository.claim()
        fresh.repository.recover()
        Runs(fresh).advance_all(verify_review=True)
        self.assertEqual(len(fresh.repository.run_steps(run_id)), 2)
        view = fresh.runs().view(run_id)
        self.assertEqual((view.phase, view.group), ("paused", "needs-you"))
        self.assertEqual(sum(j.status == "queued" for j in fresh.repository.jobs()), 0)

    def test_a_restarted_worker_continues_the_chain_to_review(self):
        from field_notes_studio.pipeline import Pipeline
        from field_notes_studio.worker import work

        run_id = self.start()
        self.prepare_job()  # The worker stopped before it could advance the run.
        fake = FakeVideo(None, self.m.root)
        with (
            patch.object(Pipeline, "run", lambda _self, *args: fake.run(*args)),
            patch("field_notes_studio.worker.launch_worker"),
        ):
            work(self.m.root, once=True)
        self.assertEqual(fake.calls, ["video"])
        steps = self.m.studio.repository.run_steps(run_id)
        self.assertEqual([s["step"] for s in steps], ["prepare", "video"])
        self.assertEqual(self.m.studio.repository.get(steps[-1]["job"]).status, "succeeded")
        view = self.m.studio.runs().view(run_id)
        self.assertEqual((view.phase, view.group), ("review", "needs-you"))
        self.assertEqual({r.key: r.state for r in view.rows}["video"], "Saved")

    def test_a_failed_paid_step_is_never_retried_by_the_run(self):
        run_id = self.start()
        with self.m.f.cloud() as calls:
            calls[1].side_effect = TimeoutError("No reply")
            job = run_next(self.m, self.m.studio.pipeline)
        self.assertEqual(job.status, "failed")
        for _ in range(3):
            advance_runs(self.m.root, verify_review=True)
        self.assertEqual(len(self.m.studio.repository.jobs()), 1)
        view = self.m.studio.runs().view(run_id)
        self.assertEqual(view.group, "needs-you")
        self.assertIn("nothing will be sent", view.headline)
        self.assertIn("Billing unknown", view.detail)
        with self.assertRaisesRegex(ValueError, "never resends"):
            self.m.studio.continue_run(run_id)
        self.assertEqual(len(self.m.studio.repository.jobs()), 1)
        # The next attempt needs the expert path's own receipt-bound consent.
        self.assertFalse(self.m.f.adapter.inspect("104").request_json)

    def test_runs_only_ever_queue_local_work(self):
        run_id = self.start()
        runs = self.m.studio.runs()
        run = self.m.studio.repository.run(run_id)
        with self.assertRaisesRegex(ValueError, "local, free work"):
            runs._queue(run, "prepare", "prepare", {}, "x")
        self.assertEqual(make_runs.LOCAL_ACTIONS, frozenset({"video", "export"}))

    def test_expert_recovery_job_is_followed_and_the_chain_continues_locally(self):
        run_id = self.start()
        with self.m.f.cloud() as calls:
            calls[1].side_effect = TimeoutError("No reply")
            run_next(self.m, self.m.studio.pipeline)
        # The person recovers on the expert path, with its separate consent.
        from field_notes_studio.preparation_service import PreparationService

        service = PreparationService(self.m.root)
        snapshot = service.inspect("104")
        with patch("field_notes_studio.preparation_service.launch_worker"):
            service.submit(snapshot, True, recover_uncertain=True)
        with self.m.f.cloud():
            job = run_next(self.m, self.m.studio.pipeline)
        self.assertEqual(job.status, "succeeded", job.error)
        self.m.studio.runs().advance_all()
        self.assertEqual(
            [s["step"] for s in self.m.studio.repository.run_steps(run_id)],
            ["prepare", "prepare", "video"],
        )

    def test_stop_after_this_step_and_continue(self):
        run_id = self.start()
        self.m.studio.stop_after_step(run_id)
        self.prepare_job()
        self.m.studio.runs().advance_all()
        self.assertEqual(len(self.m.studio.repository.run_steps(run_id)), 1)
        view = self.m.studio.runs().view(run_id)
        self.assertEqual((view.phase, view.group), ("stopped", "needs-you"))
        self.m.studio.continue_run(run_id)
        self.assertEqual(
            [s["step"] for s in self.m.studio.repository.run_steps(run_id)], ["prepare", "video"]
        )

    def test_waiting_captions_are_polled_without_a_new_request_and_bounded(self):
        run_id = self.start()
        with self.m.f.cloud(pending=True) as calls:
            job = run_next(self.m, self.m.studio.pipeline)
            self.assertEqual(job.status, "waiting")
            submitted = calls[3].call_count
        repository = self.m.studio.repository
        runs = self.m.studio.runs()
        runs.advance_all()
        self.assertEqual(repository.get(job.identifier).status, "waiting")  # too soon
        later = datetime.now(timezone.utc) + timedelta(seconds=make_runs.POLL_PAUSE_SECONDS + 1)
        with patch.object(make_runs, "datetime") as clock:
            clock.now.return_value = later
            clock.fromisoformat = datetime.fromisoformat
            runs.advance_all()
        self.assertEqual(repository.get(job.identifier).status, "queued")
        self.assertEqual(repository.get(job.identifier).stage, "resume")
        request = json.loads(repository.get(job.identifier).request)
        self.assertIn("resume", request)
        self.assertNotIn("uncertain_chunks", request)
        self.assertEqual(len(repository.jobs()), 1)
        self.assertEqual(calls[3].call_count, submitted)
        view = runs.view(run_id)
        self.assertEqual(view.group, "working")
        # Bounded: after AUTO_POLLS checks the run stops polling and asks the person.
        for _ in range(AUTO_POLLS):
            repository.event(job.identifier, "resume", "poll")
        with repository.connection() as db:
            db.execute("UPDATE jobs SET status='waiting' WHERE identifier=?", (job.identifier,))
        later = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(make_runs, "datetime") as clock:
            clock.now.return_value = later
            clock.fromisoformat = datetime.fromisoformat
            runs.advance_all()
        self.assertEqual(repository.get(job.identifier).status, "waiting")
        view = runs.view(run_id)
        self.assertEqual((view.phase, view.group), ("paused", "needs-you"))
        self.assertIn("Check again", view.detail)

    def test_durations_are_measured_and_shown_as_history(self):
        repository = self.m.studio.repository
        identifier = repository.submit("x", "video", {})
        job = repository.claim()
        repository.event(identifier, "video", "Rendering")
        repository.finish(identifier, "succeeded", result="/r")
        with repository.connection() as db:
            db.execute(
                "UPDATE events SET time=? WHERE job=? AND stage='video'",
                ((datetime.now(timezone.utc) - timedelta(minutes=7)).isoformat(), job.identifier),
            )
        repository.event(identifier, "video-complete", "Saved")
        runs = self.m.studio.runs()
        runs.record_durations(repository.get(identifier))
        runs.record_durations(repository.get(identifier))
        self.assertEqual(len(repository.durations("video")), 1)
        self.assertEqual(runs._estimate("video"), "about 7 min on this computer before")
        self.assertEqual(runs._estimate("sound"), "")


class PackageAfterApprovalTests(unittest.TestCase):
    """Approval of the run's own full video queues the local upload package."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = Repository(self.root / "artifacts/studio/studio.sqlite3")
        self.video_dir = self.root / "artifacts/production/ep/video-1"
        self.video_dir.mkdir(parents=True)
        test = self

        class Pipeline:
            approved = True
            preflight_error = None
            requests = []

            def review_snapshot(self, episode, full_video=False):
                return ReviewSnapshot(
                    "identity",
                    "",
                    video=str(test.video_dir / "episode.mp4"),
                    full_video=True,
                    approved=self.approved,
                )

            def request(self, episode, action, *args, **kwargs):
                self.requests.append(action)
                return {"action": action}

            def preflight(self, episode, action, request):
                if self.preflight_error:
                    raise self.preflight_error

            def approve(self, *_):
                pass

        class StudioStub:
            repository = self.repository
            pipeline = Pipeline()
            root = self.root

            def spend_summary(self, episode):
                return ""

        self.studio = StudioStub()
        self.runs = Runs(self.studio)
        self.run_id = self.repository.start_run(
            "ep", "", {"reused": []}, {}, ("video", "video", {"settings": {}})
        )
        job = self.repository.claim()
        self.repository.finish(job.identifier, "succeeded", result=str(self.video_dir))

    def steps(self):
        return [s["step"] for s in self.repository.run_steps(self.run_id)]

    def test_approval_queues_the_package_once(self):
        self.studio.pipeline.approved = False
        self.assertIsNone(self.runs.queue_package(self.run_id))
        self.assertEqual(self.runs.view(self.run_id).phase, "review")
        self.studio.pipeline.approved = True
        job = self.runs.queue_package(self.run_id)
        self.assertIsNotNone(job)
        self.assertEqual(self.repository.get(job).action, "export")
        self.assertIsNone(self.runs.queue_package(self.run_id))
        self.assertEqual(self.steps(), ["video", "export"])

    def test_service_approve_triggers_packaging(self):
        studio = Studio.__new__(Studio)
        studio.root, studio.repository, studio.pipeline = (
            self.root,
            self.repository,
            self.studio.pipeline,
        )
        with patch("field_notes_studio.service.launch_worker"):
            studio.approve("ep", ReviewSnapshot("identity", "", full_video=True), "Reviewer")
        self.assertEqual(self.steps(), ["video", "export"])

    def test_a_changed_edition_is_not_packaged(self):
        # The saved episode is no longer the video this run made.
        self.video_dir = self.root / "artifacts/production/ep/video-2"
        self.assertIsNone(self.runs.queue_package(self.run_id))
        self.assertEqual(self.steps(), ["video"])

    def test_preflight_refusal_pauses_the_run_with_a_reason(self):
        self.studio.pipeline.preflight_error = ValueError(
            "Saved edition changed during preflight. Inspect export again."
        )
        self.assertIsNone(self.runs.queue_package(self.run_id))
        view = self.runs.view(self.run_id)
        self.assertEqual((view.phase, view.group), ("paused", "needs-you"))
        self.assertIn("Saved edition changed", view.detail)

    def test_a_failed_local_step_can_simply_run_again(self):
        job = self.runs.queue_package(self.run_id)
        self.repository.claim()
        self.repository.finish(job, "failed", error="Disk full")
        view = self.runs.view(self.run_id)
        self.assertEqual(view.group, "needs-you")
        self.assertTrue(view.retry_free)
        again = self.runs.continue_run(self.run_id)
        self.assertEqual(self.repository.get(again).action, "export")
        self.assertEqual(self.steps(), ["video", "export", "export"])

    def test_a_failed_video_is_queued_again_but_never_a_paid_step(self):
        run_id = self.repository.start_run(
            "ep2",
            "",
            {"reused": []},
            {"speed": 1.0, "outro": 5, "sound": {}, "base": None},
            ("video", "video", {"settings": {}}),
        )
        job = self.repository.claim()
        self.repository.finish(job.identifier, "failed", error="Renderer crashed")
        again = self.runs.continue_run(run_id)
        self.assertEqual(self.repository.get(again).action, "video")
        self.repository.claim()
        self.repository.finish(again, "succeeded", result="/r")
        paid = self.repository.start_run(
            "ep3", "001", {"reused": []}, {}, ("prepare", "prepare", {"note": "001"})
        )
        job = self.repository.claim()
        self.repository.finish(job.identifier, "failed", error="HTTP 502")
        self.assertFalse(self.runs.view(paid).retry_free)
        with self.assertRaisesRegex(ValueError, "never resends"):
            self.runs.continue_run(paid)

    def test_following_an_expert_job_with_other_settings_is_recorded(self):
        identifier = self.repository.submit(
            "ep", "video", {"settings": {"speed": 1.3, "outro_seconds": 2}}
        )
        self.assertTrue(self.runs.adopt(self.run_id))
        notes = self.repository.run(self.run_id)["consent"]["notes"]
        self.assertEqual(len(notes), 1)
        self.assertIn(f"Followed video job {identifier[:12]}", notes[0])
        self.assertIn("different from the ones consented to", notes[0])

    def test_a_run_with_an_active_step_cannot_be_closed(self):
        job = self.runs.queue_package(self.run_id)
        with self.assertRaisesRegex(ValueError, "Stop the running step"):
            self.runs.close(self.run_id)
        self.assertFalse(self.repository.run(self.run_id)["closed"])
        self.repository.claim()
        self.repository.finish(job, "failed", error="Disk full")
        self.runs.close(self.run_id)
        self.assertTrue(self.repository.run(self.run_id)["closed"])

    def test_package_done_is_ready_then_done_after_the_release_record(self):
        job = self.runs.queue_package(self.run_id)
        self.repository.claim()
        self.repository.finish(job, "succeeded", result=str(self.root / "artifacts/uploads/ep"))
        view = self.runs.view(self.run_id)
        self.assertEqual((view.phase, view.group), ("ready", "needs-you"))
        self.assertEqual({r.key: r.state for r in view.rows}["review"], "Approved")
        self.repository.publication("ep", "https://example.com/watch", "2026-10-17")
        self.assertEqual(self.runs.view(self.run_id).group, "done")


if __name__ == "__main__":
    unittest.main()
