"""Offline behavior checks; no credentials or Google requests are used."""
import argparse
from contextlib import redirect_stdout
import io
import json
import math
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib import error
import wave

import field_audio as audio


def wav_bytes(seconds=.15, rate=24000, channels=1):
    target = io.BytesIO()
    with wave.open(target, "wb") as wav:
        wav.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        wav.writeframes(b"".join(struct.pack("<h", int(2000 * math.sin(index * .1))) * channels
                                 for index in range(int(seconds * rate))))
    return target.getvalue()


class AudioTests(unittest.TestCase):
    def narration(self):
        return {"speakers": [{"alias": "Narrator", "voice": "Charon"}], "prompt": "Read precisely."}

    def dialogue(self):
        return {"speakers": [{"alias": "Explore", "voice": "Kore"},
                              {"alias": "Question", "voice": "Charon"}], "prompt": "Speak the dialogue."}

    def test_unicode_chunking_preserves_every_word(self):
        text = "\n\n".join(["Kysymys jää avoimeksi. " * 120,
                              "Known, unknown, refused. " * 100])
        chunks = audio.chunk_script(self.narration(), text)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(text.split()), " ".join(" ".join(chunks).split()))
        self.assertTrue(all(len(c.encode("utf-8")) <= 3000 for c in chunks))

    def test_oversize_single_word_fails_instead_of_truncating(self):
        with self.assertRaisesRegex(ValueError, "single script word"):
            audio.chunk_script(self.narration(), "ä" * 3000)

    def test_dialogue_preserves_speaker_on_split_turns(self):
        first = "Maybe, maybe not. " * 260
        text = f"Explore: {first}\n\nQuestion: We still need evidence."
        chunks = audio.chunk_script(self.dialogue(), text)
        turns = [line for c in chunks for line in c.splitlines() if line]
        explore = " ".join(line.split(": ", 1)[1] for line in turns if line.startswith("Explore:"))
        self.assertEqual(" ".join(first.split()), explore)
        self.assertEqual(turns[-1], "Question: We still need evidence.")
        self.assertTrue(all(line.startswith(("Explore:", "Question:")) for line in turns))

    def test_unknown_or_missing_speaker_is_rejected(self):
        for text in ["Explore: Hello.\nOther: Hello.", "Explore: Just me.", "Unlabelled turn."]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                audio.chunk_script(self.dialogue(), text)

    def test_short_paragraphs_and_speaker_turns_remain_intact(self):
        paragraph = "One clear sentence. A second sentence belongs to the same thought."
        self.assertEqual(audio.chunk_script(self.narration(), paragraph), [paragraph])
        dialogue = "Explore: " + paragraph + "\n\nQuestion: What does it establish?"
        self.assertEqual(audio.chunk_script(self.dialogue(), dialogue), [dialogue])

    def test_source_revision_blocks_stale_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "audio/scripts").mkdir(parents=True)
            (root / "docs/assets").mkdir(parents=True)
            (root / "docs/notes").mkdir(parents=True)
            shutil.copy(audio.ROOT / "audio/episodes.json", root / "audio/episodes.json")
            shutil.copy(audio.ROOT / "audio/scripts/note-001.txt", root / "audio/scripts/note-001.txt")
            shutil.copy(audio.ROOT / "docs/assets/notes.json", root / "docs/assets/notes.json")
            note = audio.catalog(audio.ROOT)["001"]
            article = root / "docs/notes" / note["slug"]
            shutil.copy(audio.ROOT / "docs/notes" / note["slug"], article)
            audio.load_episode("note-001", root)
            article.write_text(article.read_text().replace("Resistance tells you", "An updated note tells you"))
            with self.assertRaisesRegex(ValueError, "changed"):
                audio.load_episode("note-001", root)

    def test_html_extraction_decodes_entities_and_omits_svg(self):
        reader = audio.ProseReader()
        reader.feed('<h2>Room &amp; doubt.</h2><p>Keep <em>unknown</em> visible.</p>'
                    '<svg><text>Decoration</text></svg><p>Read<br>on.</p>')
        self.assertEqual(reader.text(), "Room & doubt.\n\nKeep unknown visible.\n\nRead on.")

    def test_wav_join_has_valid_samples_and_boundary_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = [root / "a.wav", root / "b.wav"]
            for part in parts:
                part.write_bytes(wav_bytes())
            duration = audio.combine_wavs(parts, root / "joined.wav")
            self.assertAlmostEqual(duration, .5)
            self.assertAlmostEqual(audio.validate_wav((root / "joined.wav").read_bytes()), .5)
        with self.assertRaisesRegex(ValueError, "Expected"):
            audio.validate_wav(wav_bytes(rate=22050))

    def generate_args(self):
        return argparse.Namespace(episode="note-001", model="gemini-2.5-pro-tts", endpoint="eu",
                                  project="audio-pilot-project", auth="gcloud", retry_uncertain=False)

    def run_context(self, root):
        plan = audio.make_plan("note-001", "gemini-2.5-pro-tts", "eu")
        return plan, root / "artifacts/audio/note-001" / plan["fingerprint"][:16]

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
    def test_saved_chunks_reused_and_corruption_blocks_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, output = self.run_context(root)
            with patch.object(audio, "ROOT", root), patch.object(audio, "make_plan", return_value=plan), \
                 patch.object(audio.shutil, "which", return_value="installed"), \
                 patch.object(audio, "access_token", return_value="in-memory-token") as auth, \
                 patch.object(audio, "synthesize", return_value=wav_bytes()) as synth, redirect_stdout(io.StringIO()):
                audio.generate(self.generate_args())
                audio.generate(self.generate_args())
                self.assertEqual(synth.call_count, 1)
                self.assertEqual(auth.call_count, 1)
                metadata = json.loads((output / "episode.json").read_text())
                self.assertEqual(metadata["listening_review"], "pending")
                self.assertEqual(metadata["audio_sha256"], audio.digest((output / "episode.mp3").read_bytes()))
                self.assertNotIn("in-memory-token", "".join(p.read_text() for p in output.glob("*.json")))
                self.assertEqual((output / "transcript.txt").read_text().strip(), plan["script"])
                (output / "chunk-001.wav").write_bytes(b"broken")
                with self.assertRaisesRegex(ValueError, "missing or changed"):
                    audio.generate(self.generate_args())
                self.assertEqual(synth.call_count, 1)

    def test_uncertain_request_is_not_repeated_automatically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, output = self.run_context(root)
            with patch.object(audio, "ROOT", root), patch.object(audio, "make_plan", return_value=plan), \
                 patch.object(audio.shutil, "which", return_value="installed"), \
                 patch.object(audio, "access_token", return_value="in-memory-token"), \
                 patch.object(audio, "synthesize", side_effect=TimeoutError) as synth, redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "No completed audio"):
                    audio.generate(self.generate_args())
                self.assertEqual(json.loads((output / "chunk-001.json").read_text())["status"], "uncertain")
                with self.assertRaisesRegex(ValueError, "uncertain prior attempt"):
                    audio.generate(self.generate_args())
                self.assertEqual(synth.call_count, 1)

    def test_provider_rejection_is_recorded_without_echoing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan, output = self.run_context(root)
            rejection = error.HTTPError("https://example.test", 403, "Forbidden", {}, None)
            with patch.object(audio, "ROOT", root), patch.object(audio, "make_plan", return_value=plan), \
                 patch.object(audio.shutil, "which", return_value="installed"), \
                 patch.object(audio, "access_token", return_value="in-memory-token"), \
                 patch.object(audio, "synthesize", side_effect=rejection), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                    audio.generate(self.generate_args())
                state = json.loads((output / "chunk-001.json").read_text())
                self.assertEqual(state["status"], "failed")
                self.assertEqual(state["http_status"], 403)


if __name__ == "__main__":
    unittest.main()
