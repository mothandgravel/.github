"""Protect edited controls from stale background plans; never touch Tk off-thread."""

import threading
import unittest
from types import SimpleNamespace

from field_notes_studio.controller import Controller


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class ControllerTests(unittest.TestCase):
    def test_a_b_a_navigation_rejects_old_settings_success_and_failure(self):
        loads = []
        publication = SimpleNamespace(loading_episode=lambda: None)
        workspace = SimpleNamespace(
            publication=publication,
            review=SimpleNamespace(clear=lambda: None),
            show_plan=lambda *_: None,
            load=lambda *args: loads.append(args),
        )
        controller = Controller(
            SimpleNamespace(settings=lambda _: None), SimpleNamespace(workspace=workspace)
        )
        self.addCleanup(controller.close)
        controller.episodes = {"a": "Episode A", "b": "Episode B"}
        pending = []
        controller.task = lambda operation, callback, on_error=None: pending.append(
            (callback, on_error)
        )
        controller.refresh_review = controller.refresh_release = lambda: None
        for identifier in ("a", "b", "a"):
            controller.select(identifier)
        pending[0][0]({"old": True})
        pending[0][1]("Old A read failed")
        pending[1][0]({"other": True})
        self.assertTrue(controller.loading)
        self.assertEqual(loads, [])
        pending[2][0]({"current": True})
        self.assertFalse(controller.loading)
        self.assertEqual(loads, [("Episode A", {"current": True})])

    def test_background_copy_error_does_not_unlock_unrelated_episode_loading_or_polling(self):
        controller = Controller(None, SimpleNamespace(status=lambda _: None))
        self.addCleanup(controller.close)
        controller.loading = controller.polling = True
        errors = []
        controller.mailbox.put(
            (lambda _: None, None, "Old release copy unavailable", errors.append)
        )
        controller.pump()
        self.assertTrue(controller.loading)
        self.assertTrue(controller.polling)
        self.assertEqual(errors, ["Old release copy unavailable"])

    def test_export_planning_ignores_unfinished_recipe_fields(self):
        planned = []
        workspace = SimpleNamespace(
            speed=Value("unfinished draft"),
            outro=Value(""),
            action=Value("export"),
            show_plan=lambda *args, **kwargs: None,
        )
        view = SimpleNamespace(workspace=workspace, status=lambda _: None)

        def plan(*args):
            planned.append(args)
            return {"edition": "saved"}, "Package the saved edition"

        controller = Controller(SimpleNamespace(plan=plan), view)
        self.addCleanup(controller.close)
        controller.selected = "note-001"
        controller.task = lambda operation, callback: callback(operation())
        controller.inspect()
        self.assertEqual(planned, [("note-001", "export", None, None)])
        self.assertEqual(controller.ready, ("note-001", "export", {"edition": "saved"}))

    def test_review_result_for_an_old_queue_selection_cannot_redirect_the_workspace(self):
        selection = Value("old-job")
        navigated = []
        view = SimpleNamespace(
            jobs=SimpleNamespace(selection=selection.get),
            shelf=SimpleNamespace(reveal=lambda identifier: navigated.append(identifier)),
            status=lambda _: None,
        )
        job = SimpleNamespace(episode="note-001", action="video", status="succeeded")
        studio = SimpleNamespace(repository=SimpleNamespace(get=lambda _: job))
        controller = Controller(studio, view)
        self.addCleanup(controller.close)
        controller.episodes = {"note-001": object()}
        pending = []
        controller.task = lambda operation, callback: pending.append((operation, callback))
        controller.review_job()
        selection.value = "another-job"
        operation, callback = pending.pop()
        callback(operation())
        self.assertEqual(navigated, [])
        self.assertIsNone(controller.selected)

    def test_queue_review_does_not_offer_preview_or_missing_episode_as_full_video(self):
        messages = []
        view = SimpleNamespace(
            jobs=SimpleNamespace(selection=lambda: "job"), status=messages.append
        )
        job = SimpleNamespace(episode="removed-episode", action="preview", status="succeeded")
        studio = SimpleNamespace(repository=SimpleNamespace(get=lambda _: job))
        controller = Controller(studio, view)
        self.addCleanup(controller.close)
        controller.task = lambda operation, callback: callback(operation())
        controller.review_job()
        self.assertIn("completed audio or full-video", messages[-1])
        job.action = "video"
        controller.review_job()
        self.assertIn("no longer", messages[-1])
        self.assertIsNone(controller.selected)

    def test_manual_episode_change_supersedes_pending_queue_review_navigation(self):
        navigated = []
        view = SimpleNamespace(
            jobs=SimpleNamespace(selection=lambda: "job"),
            shelf=SimpleNamespace(reveal=navigated.append),
            status=lambda _: None,
        )
        job = SimpleNamespace(episode="note-001", action="audio", status="succeeded")
        studio = SimpleNamespace(repository=SimpleNamespace(get=lambda _: job))
        controller = Controller(studio, view)
        self.addCleanup(controller.close)
        controller.episodes = {"note-001": object()}
        pending = []
        controller.task = lambda operation, callback: pending.append((operation, callback))
        controller.review_job()
        # A newer shelf selection invalidates the generation while the read is pending.
        controller.selected = "note-002"
        controller.generation += 1
        operation, callback = pending.pop()
        callback(operation())
        self.assertEqual(navigated, [])
        self.assertEqual(controller.selected, "note-002")

    def test_changed_controls_cannot_queue_an_old_plan(self):
        calls = []
        workspace = SimpleNamespace(
            speed=Value("1.15"),
            outro=Value("5"),
            action=Value("audio"),
            show_plan=lambda *args, **kwargs: calls.append(args),
        )
        view = SimpleNamespace(workspace=workspace, status=lambda text: calls.append(text))
        studio = SimpleNamespace(plan=lambda *_: ({"settings": {}}, "Old plan"))
        controller = Controller(studio, view)
        self.addCleanup(controller.close)
        controller.selected = "note-001"
        pending = []
        controller.task = lambda operation, callback: pending.append((operation, callback))
        controller.inspect()
        controller.changed()
        operation, callback = pending.pop()
        callback(operation())
        self.assertIsNone(controller.ready)
        controller.submit()
        self.assertFalse(pending)

    def test_background_completion_only_reaches_view_when_main_thread_pumps(self):
        caller = threading.get_ident()
        calls = []
        view = SimpleNamespace(status=lambda _: None)
        controller = Controller(None, view)
        self.addCleanup(controller.close)
        controller.task(lambda: 42, lambda value: calls.append((threading.get_ident(), value)))
        controller.executor.shutdown(wait=True)
        self.assertEqual(calls, [])
        controller.pump()
        self.assertEqual(calls, [(caller, 42)])
