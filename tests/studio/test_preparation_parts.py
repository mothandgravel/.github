"""Studio pending check and Resume for a recording captioned in parts (mocked Cloud)."""

import json
import re
from contextlib import ExitStack
from unittest.mock import patch

from field_notes_audio import captions, long_captions
from field_notes_audio.production import sources
from field_notes_audio.storage import read_object, write_json
from field_notes_studio.service import Studio
from field_notes_studio.worker import execute
from tests.audio.test_captions import operation
from tests.studio import test_preparation_execution as execution


class PreparationPartsTests(execution.PreparationExecutionTests):
    """The 4 s fixture narration is split into two overlapping parts by shrinking the limits."""

    def setUp(self):
        super().setUp()
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, value in (("PART_SECONDS", 2.5), ("SEARCH_SECONDS", 1.0)):
            stack.enter_context(patch.object(long_captions, name, value))
        stack.enter_context(patch.object(long_captions, "OVERLAP_SECONDS", 0.5))
        stack.enter_context(patch.object(captions, "CAPTION_LIMIT_SECONDS", 3))
        self.submissions = []
        self.done = set()

    def submit(self, url, project, auth, payload):
        uri = payload["files"][0]["uri"]
        index = len(self.submissions) + 1
        self.submissions.append(uri)
        result = operation(uri, done=index in self.done)
        result["name"] = f"projects/12345/locations/us/operations/part-{index}"
        return result

    def poll(self, url, project, auth):
        index = int(re.search(r"part-(\d+)$", url)[1])
        result = operation(self.submissions[index - 1])
        result["name"] = f"projects/12345/locations/us/operations/part-{index}"
        return result

    def first_run(self, calls):
        calls[3].side_effect = self.submit
        calls[4].side_effect = self.poll
        self.done = {1}  # part 1 finishes at once; part 2 is still transcribing
        identifier = self.repository.submit("studio-essay", "prepare", self.request)
        execute(self.repository, self.pipeline, self.repository.claim())
        job = self.repository.get(identifier)
        self.assertEqual(job.status, "waiting", job.error)
        return identifier

    def caption_directory(self):
        return next(self.adapter._recording(self.request["plan"]).glob("captions/*/parts")).parent

    def resume(self, identifier):
        with patch("field_notes_studio.service.launch_worker"):
            Studio(self.root).retry(identifier)
        execute(self.repository, self.pipeline, self.repository.claim())
        return self.repository.get(identifier)

    def test_resume_polls_only_the_unfinished_part_and_adopts_the_joined_captions(self):
        with self.cloud(pending=True) as calls:
            identifier = self.first_run(calls)
            saved = json.loads(self.repository.get(identifier).request)["resume"]
            self.assertEqual(saved["operation"], ["projects/12345/locations/us/operations/part-2"])
            self.assertIn(
                "running (part 1 complete, part 2 running)", self.adapter.inspect("104").summary
            )
            job = self.resume(identifier)
            self.assertEqual(job.status, "succeeded", job.error)
            self.assertEqual(len(self.submissions), 2)
            polled = [c.args[0] for c in calls[4].call_args_list]
            self.assertTrue(polled and all(u.endswith("/part-2") for u in polled))
        directory = self.caption_directory()
        meta = read_object(directory / "captions.json")
        self.assertEqual([p["index"] for p in meta["parts"]], [1, 2])
        self.assertEqual(read_object(directory / "state.json")["status"], "complete")
        self.assertEqual([e["id"] for e in sources.load_entries(self.root)], ["studio-essay"])

    def test_pending_check_blocks_on_an_uncertain_part(self):
        with self.cloud(pending=True) as calls:
            self.first_run(calls)
        part = long_captions.part_states(
            self.adapter._caption_args(
                self.request["plan"],
                self.request["configuration"],
                self.adapter._recording(self.request["plan"]) / "episode.mp3",
            ),
            self.caption_directory(),
        )["parts"][1]
        write_json(part["state"], {**read_object(part["state"]), "status": "uncertain"})
        snapshot = self.adapter.inspect("104")
        self.assertIn("part 2 uncertain", snapshot.summary)
        self.assertIn("Caption work needs explicit recovery", snapshot.summary)

    def test_lost_part_receipt_cannot_turn_resume_into_a_new_submission(self):
        with self.cloud(pending=True) as calls:
            identifier = self.first_run(calls)
            for state in self.caption_directory().glob("parts/captions/*/state.json"):
                if read_object(state).get("status") == "running":
                    state.unlink()
            job = self.resume(identifier)
            self.assertEqual(job.status, "failed")
            self.assertIn("will not create a new submission", job.error)
            self.assertEqual(len(self.submissions), 2)


# Run only the tests defined here, not the inherited suite again.
for _name in [n for n in vars(execution.PreparationExecutionTests) if n.startswith("test_")]:
    setattr(PreparationPartsTests, _name, None)
del _name
