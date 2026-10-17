"""Same fixture state on both trees: run from a checkout root with STUDIO_SCREENSHOT_DIR set.

Mocked Cloud only: two narration chunks of note 104 fail with HTTP 502 across two runs
(the second an explicitly authorized recovery), then the windows are captured.
"""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, os.getcwd())

from field_notes_studio.preparation_service import PreparationService  # noqa: E402
from field_notes_studio.worker import execute  # noqa: E402
from tests.studio import test_preparation_app as app_fixtures  # noqa: E402
from tests.studio import test_preparation_execution as media_fixtures  # noqa: E402
from tests.studio import test_ui as ui_fixtures  # noqa: E402


def gateway():
    body = b'{"error": {"status": "UNAVAILABLE", "message": "upstream connect error"}}'
    return HTTPError("https://service.invalid", 502, "Bad Gateway", {}, io.BytesIO(body))


def grab(window, name, geometry):
    import subprocess

    window.geometry(geometry + "+0+0")
    window.lift()
    for _ in range(20):
        window.update()
    out = Path(os.environ["STUDIO_SCREENSHOT_DIR"])
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "x11grab", "-draw_mouse", "0",
         "-video_size", f"{window.winfo_width()}x{window.winfo_height()}",
         "-i", f"{os.environ['DISPLAY']}+{window.winfo_rootx()},{window.winfo_rooty()}",
         "-frames:v", "1", "-update", "1", "-y", str(out / f"{name}.png")],
        check=True, timeout=15,
    )


class Capture(unittest.TestCase):
    def test_readiness_card(self):
        h = ui_fixtures.UITests()
        h.setUp()
        self.addCleanup(h.doCleanups)
        h.root.geometry("1050x760+0+0")
        h.app.controller.episode_controls.refresh()
        card = h.app.readiness
        h.wait(lambda: card.snapshot is not None)
        h.capture("1-readiness-card")
        if hasattr(card, "details_button"):
            card.details_button.invoke()
            h.capture("1b-readiness-card-details")

    def test_failure_row_and_recovery(self):
        media_fixtures.PreparationExecutionTests.setUpClass()
        h = app_fixtures.PreparationApplicationTests()
        h.setUp()
        self.addCleanup(h.doCleanups)
        f, app = h.fixture, h.app
        f.text(
            "audio/scripts/window.txt",
            "\n\n".join(w + " " + "Hello world. " * 160 for w in ("One.", "Two.", "Three.")),
        )
        request = json.loads(f.adapter.inspect("104").request_json)
        service = PreparationService(f.root)
        f.repository.submit("studio-essay", "prepare", request)
        with f.cloud() as calls:
            calls[1].side_effect = [f.wav, gateway()]
            execute(f.repository, f.pipeline, f.repository.claim())
        with patch("field_notes_studio.preparation_service.launch_worker"):
            identifier = service.submit(service.inspect("104"), True, recover_uncertain=True)
        with f.cloud() as calls:
            calls[1].side_effect = [gateway()]
            execute(f.repository, f.pipeline, f.repository.claim())
        app.preparation.close()
        app.root.geometry("1050x760+0+0")
        app.jobs.render(f.repository.jobs())
        app.jobs.tree.selection_set(identifier)
        app.controller.job_detail()
        h.wait(lambda: "HTTP 502" in app.jobs.detail.cget("text"))
        ui_fixtures.UITests.capture(h, "2-failure-row")
        app.prepare_button.invoke()
        h.wait(lambda: app.preparation.view.tree.exists("104"))
        view = app.preparation.view
        h.view = view
        view.tree.selection_set("104")
        app.root.update()
        view.inspect_button.invoke()
        h.wait(lambda: view.snapshot is not None)
        view.authorization.invoke()
        view.recovery_consent.invoke()
        app.root.update()
        grab(view.window, "3-recovery-before-override", "1050x760")
        if getattr(view.snapshot, "spend_blocked", False):
            view.spend_override.invoke()
            view.spend_reason.set("Checked status page and billing report")
        grab(view.window, "3-recovery", "1050x760")
        grab(view.window, "3-recovery-minimum", "760x580")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"])
