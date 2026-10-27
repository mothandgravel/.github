"""Recordings longer than one caption job: local split, per-part paid jobs, join and resume."""

import argparse
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from field_notes_audio import audio, captions, judge, long_captions, spend_guard
from field_notes_audio.audio import digest
from field_notes_audio.storage import digest_file


def recognition(words, transcript):
    """A part's recognition in extract_recognition's shape, with times local to the part."""
    cues = [
        {"start": start, "end": end, "text": text, "speakers": []} for text, start, end in words
    ]
    return {
        "transcript": transcript,
        "words": [{"text": t, "start": s, "end": e, "speaker": None} for t, s, e in words],
        "cues": cues,
        "word_timing_status": "complete",
        "word_timing_issues": [],
        "caption_timing_adjustments": [],
        "caption_timing_omissions": [],
    }


def part_operation(uri, index):
    def stamp(value, vtt=False):
        return f"00:00:{value:02d}{'.' if vtt else ','}000"

    words = [(f"alpha{index}", 1, 2), (f"beta{index}", 10, 11)]
    srt = "\n\n".join(
        f"{n}\n{stamp(a)} --> {stamp(b)}\n{w}" for n, (w, a, b) in enumerate(words, 1)
    )
    vtt = "\n\n".join(f"{stamp(a, True)} --> {stamp(b, True)}\n{w}" for w, a, b in words)
    return {
        "name": f"projects/12345/locations/us/operations/part-{index}",
        "done": True,
        "response": {
            "results": {
                uri: {
                    "inlineResult": {
                        "transcript": {
                            "results": [
                                {
                                    "alternatives": [
                                        {
                                            "transcript": f"alpha{index} beta{index}",
                                            "words": [
                                                {
                                                    "word": w,
                                                    "startOffset": f"{a}s",
                                                    "endOffset": f"{b}s",
                                                }
                                                for w, a, b in words
                                            ],
                                        }
                                    ]
                                }
                            ]
                        },
                        "srtCaptions": srt + "\n",
                        "vttCaptions": "WEBVTT\n\n" + vtt + "\n",
                    }
                }
            }
        },
    }


class SplitAndJoinTests(unittest.TestCase):
    def test_fixed_cuts_overlap_when_no_pause_is_found(self):
        parts = long_captions.split_parts(2300, [])
        self.assertEqual(
            [(p["start"], p["end"], p["cut"]) for p in parts],
            [(0, 1140, "fixed"), (1135, 2275, "fixed"), (2270, 2300, "end")],
        )
        self.assertTrue(all(p["end"] - p["start"] <= long_captions.PART_SECONDS for p in parts))
        self.assertEqual(long_captions.boundaries(parts), [1137.5, 2272.5])

    def test_cuts_prefer_a_pause_near_the_limit(self):
        parts = long_captions.split_parts(2300, [(500, 510), (1100, 1110), (2200, 2210)])
        self.assertEqual(
            [(p["start"], p["end"], p["cut"]) for p in parts],
            [(0, 1105, "silence"), (1105, 2205, "silence"), (2205, 2300, "end")],
        )
        self.assertEqual(long_captions.boundaries(parts), [None, None])

    def test_overlap_words_are_kept_once_at_the_midpoint(self):
        parts = long_captions.split_parts(1300, [])  # [0, 1140] and [1135, 1300]
        first = recognition(
            [("one", 1130.0, 1131.0), ("two", 1136.0, 1137.0), ("three", 1138.0, 1139.0)],
            "one two three",
        )
        # The same speech heard again by part 2, which starts 1135 s in.
        second = recognition(
            [("two", 1.0, 2.0), ("three", 3.0, 4.0), ("four", 20.0, 21.0)], "two three four"
        )
        joined = long_captions.join(parts, [first, second], 1300)
        self.assertEqual(
            [(w["text"], w["start"]) for w in joined["words"]],
            [("one", 1130.0), ("two", 1136.0), ("three", 1138.0), ("four", 1155.0)],
        )
        self.assertEqual(joined["transcript"], "one two\n\nthree four")
        self.assertEqual([c["text"] for c in joined["cues"]], ["one", "two", "three", "four"])
        self.assertEqual(captions.parse_captions(joined["srt"], 1300)[-1]["start"], 1155.0)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools unavailable")
class LongCaptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixture_directory.name) / "long.mp3"
        # 2300 s of tone with pauses at 1100–1110 s and 2200–2210 s: three parts.
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=300:sample_rate=8000:duration=2300",
                "-af",
                "volume=0:enable='between(t,1100,1110)+between(t,2200,2210)'",
                "-ac",
                "1",
                "-b:a",
                "16k",
                str(cls.fixture),
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.fixture_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        log_root = patch.object(audio, "ROOT", self.root)
        log_root.start()
        self.addCleanup(log_root.stop)
        self.audio = self.root / "episode.mp3"
        shutil.copyfile(self.fixture, self.audio)
        self.script = "alpha1 beta1 alpha2 beta2 alpha3 beta3\n"
        (self.root / "transcript.txt").write_text(self.script)
        self.episode = "recording-" + digest(self.audio.read_bytes())[:12]
        self.submitted = []
        self.reject = set()
        self.lose = set()

    def args(self, **changes):
        values = dict(
            audio=self.audio,
            project="pilot-project",
            bucket="pilot-bucket",
            location="us",
            model="chirp_3",
            language="en-US",
            diarize=False,
            auth="gcloud",
            script=None,
            dry_run=False,
            wait=0,
            retry_uncertain=False,
            restart_failed=False,
        )
        values.update(changes)
        return argparse.Namespace(**values)

    def cloud(self, url, project, auth, data=None, media=False):
        self.assertIn(":batchRecognize", url)
        uri = data["files"][0]["uri"]
        parts = self.root.glob("captions/*/parts/part-*.mp3")
        index = next(int(p.stem[-2:]) for p in parts if uri.endswith("/" + digest_file(p) + ".mp3"))
        self.submitted.append(index)
        if index in self.lose:
            raise TimeoutError
        if index in self.reject:
            self.reject.discard(index)
            raise captions.CloudError({"http_status": 403, "provider_status": "PERMISSION_DENIED"})
        return part_operation(uri, index)

    def caption(self, **changes):
        with (
            patch.object(captions.shutil, "which", return_value="installed"),
            patch.object(long_captions.shutil, "which", return_value="installed"),
            patch.object(captions, "ensure_upload", return_value="1"),
            patch.object(captions, "cloud_json", side_effect=self.cloud),
            patch.object(spend_guard, "reserve", wraps=spend_guard.reserve) as reserve,
            redirect_stdout(io.StringIO()),
        ):
            return captions.run(self.args(**changes)), reserve.call_count

    def test_three_parts_join_with_offsets_into_one_caption_output(self):
        output, reserved = self.caption()
        self.assertEqual((self.submitted, reserved), ([1, 2, 3], 3))
        meta = json.loads((output / "captions.json").read_text())
        offsets = [p["start_seconds"] for p in meta["parts"]]
        self.assertEqual([p["cut"] for p in meta["parts"]], ["silence", "silence", "end"])
        # Cuts land inside the pauses at 1100–1110 s and 2200–2210 s; parts abut.
        self.assertEqual(offsets[0], 0)
        self.assertAlmostEqual(offsets[1], 1105, delta=1)
        self.assertAlmostEqual(offsets[2], 2205, delta=1)
        self.assertEqual([p["end_seconds"] for p in meta["parts"][:2]], offsets[1:])
        self.assertEqual(
            meta["parts"][2]["end_seconds"], round(captions.probe_audio(self.audio), 3)
        )
        expected = [
            (f"{word}{n}", round(offsets[n - 1] + local, 3))
            for n in (1, 2, 3)
            for word, local in (("alpha", 1), ("beta", 10))
        ]
        words = json.loads((output / "words.json").read_text())
        self.assertEqual(words["audio_sha256"], digest(self.audio.read_bytes()))
        self.assertEqual([(w["text"], w["start"]) for w in words["words"]], expected)
        self.assertTrue(all(w["end"] == w["start"] + 1 for w in words["words"]))
        self.assertEqual(words["timing_status"], "complete")
        cues = captions.parse_captions((output / "captions.vtt").read_text(), 2300, vtt=True)
        self.assertEqual([(c["text"], c["start"]) for c in cues], expected)
        srt = captions.parse_captions((output / "captions.srt").read_text(), 2300)
        self.assertEqual(srt, cues)
        self.assertEqual(
            json.loads((output / "cues.json").read_text())["cues"][2],
            {
                "start": expected[2][1],
                "end": round(expected[2][1] + 1, 3),
                "text": "alpha2",
                "speakers": [],
            },
        )
        transcript = (output / "transcript.txt").read_text()
        self.assertEqual(transcript.split(), self.script.split())
        # The script comparison and the transcript judge see the joined result.
        self.assertEqual(json.loads((output / "comparison.json").read_text())["differences"], [])
        self.assertTrue(judge.tail_present(self.script, transcript))
        self.assertEqual((output / "audio.mp3").read_bytes(), self.audio.read_bytes())
        self.assertIn("alpha3", (output / "listen.html").read_text())
        # A repeat neither re-splits, re-captions nor reserves again.
        before = {p.name: p.stat().st_mtime_ns for p in (output / "parts").glob("*.mp3")}
        self.assertEqual(self.caption(), (output, 0))
        self.assertEqual(self.submitted, [1, 2, 3])
        after = {p.name: p.stat().st_mtime_ns for p in (output / "parts").glob("*.mp3")}
        self.assertEqual(before, after)

    def test_failed_part_resumes_without_resubmitting_completed_parts(self):
        self.reject = {2}
        with self.assertRaises(captions.CloudError):
            self.caption()
        self.assertEqual(self.submitted, [1, 2])
        output, reserved = self.caption()
        self.assertEqual(self.submitted, [1, 2, 2, 3])
        self.assertEqual(reserved, 2)
        self.assertEqual((output / "transcript.txt").read_text().split(), self.script.split())

    def test_every_part_attempt_is_logged_through_the_spend_guard(self):
        self.reject = {2}
        with self.assertRaises(captions.CloudError):
            self.caption()
        self.caption()
        logged = spend_guard.attempts(self.root / "artifacts/audio", self.episode)
        self.assertEqual(len(logged), 4)
        self.assertEqual({a.part for a in logged}, {"captions"})
        self.assertEqual(
            [a.outcome for a in logged], ["acknowledged", "failed", "acknowledged", "acknowledged"]
        )
        entries = [
            json.loads(line)
            for line in (self.root / "artifacts/audio/attempts.jsonl").read_text().splitlines()
        ]
        self.assertEqual(sum(e.get("type") == "start" for e in entries), 4)

    def test_lost_part_acknowledgement_needs_explicit_retry(self):
        self.lose = {2}
        with self.assertRaisesRegex(RuntimeError, "no valid transcription operation"):
            self.caption()
        with self.assertRaisesRegex(ValueError, "no saved acknowledgement"):
            self.caption()
        self.assertEqual(self.submitted, [1, 2])

    def test_recordings_at_the_limit_are_one_ordinary_job(self):
        short = self.root / "short" / "episode.mp3"
        short.parent.mkdir()
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=300:sample_rate=8000:duration=1199",
                "-b:a",
                "16k",
                str(short),
            ],
            check=True,
        )
        uri = "gs://pilot-bucket/field-notes-input/" + digest(short.read_bytes()) + ".mp3"
        with (
            patch.object(captions.shutil, "which", return_value="installed"),
            patch.object(captions, "ensure_upload", return_value="1"),
            patch.object(captions, "cloud_json", return_value=part_operation(uri, 1)) as cloud,
            patch.object(long_captions, "run") as split,
            redirect_stdout(io.StringIO()),
        ):
            output = captions.run(self.args(audio=short))
        split.assert_not_called()
        self.assertEqual(cloud.call_count, 1)
        self.assertFalse((output / "parts").exists())
        self.assertNotIn("parts", json.loads((output / "captions.json").read_text()))
        self.assertEqual(json.loads((output / "plan.json").read_text())["audio_uri"], uri)


if __name__ == "__main__":
    unittest.main()
