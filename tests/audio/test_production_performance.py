"""Concurrency limits, failure cleanup and sound-preserving reuse."""

import math
import struct
import tempfile
import threading
import unittest
import wave
from pathlib import Path

from field_notes_audio.production.batch import completed_jobs
from field_notes_audio.production.sound import RATE, _motif_pcm, write_motif


class BatchTests(unittest.TestCase):
    def test_two_workers_overlap_without_exceeding_the_limit_and_keep_input_order(self):
        barrier = threading.Barrier(2, timeout=5)
        lock = threading.Lock()
        active = maximum = 0

        def job(index):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                if index < 2:
                    barrier.wait()
                return index
            finally:
                with lock:
                    active -= 1

        self.assertEqual(
            list(completed_jobs([lambda i=i: job(i) for i in range(5)], 2)), list(range(5))
        )
        self.assertEqual(maximum, 2)
        self.assertEqual(active, 0)

    def test_failure_waits_for_running_writes_and_retains_completed_work(self):
        barrier = threading.Barrier(2, timeout=5)
        finished = threading.Event()

        def fail():
            barrier.wait()
            raise RuntimeError("Failed edition")

        def finish():
            barrier.wait()
            finished.set()
            return "completed edition"

        with self.assertRaisesRegex(RuntimeError, "Failed edition"):
            list(completed_jobs([fail, finish], 2))
        self.assertTrue(finished.is_set())

    def test_invalid_worker_counts_fail_before_work_starts(self):
        for workers in (True, 0, 5, 1.5):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                list(completed_jobs([lambda: self.fail("Invalid job started")], workers))


class MotifTests(unittest.TestCase):
    def test_cached_motif_preserves_original_pcm_and_reuses_synthesis(self):
        _motif_pcm.cache_clear()
        duration = 0.7
        expected = bytearray()
        # Independent original channel-by-channel recipe, before shared math/cache.
        notes = [(0.08, 220.0, 0.28), (0.55, 329.63, 0.19), (1.18, 293.66, 0.15)]
        for index in range(round(duration * RATE)):
            t = index / RATE
            fade = min(1, t / 0.04, max(0, (duration - t) / min(1.5, duration)))
            channels = []
            for channel in (0, 1):
                value = 0.0
                for onset, frequency, gain in notes:
                    elapsed = t - onset
                    if elapsed >= 0:
                        envelope = (1 - math.exp(-elapsed * 100)) * math.exp(-elapsed * 1.65)
                        phase = 2 * math.pi * frequency * elapsed
                        tone = math.sin(phase) + 0.22 * math.sin(phase * 2.01 + channel * 0.12)
                        value += gain * envelope * tone
                channels.append(round(max(-1, min(1, value * fade)) * 32767))
            expected.extend(struct.pack("<hh", *channels))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "motif.wav"
            for _ in range(2):
                write_motif(path, duration)
                with wave.open(str(path), "rb") as output:
                    self.assertEqual(output.readframes(output.getnframes()), bytes(expected))
        self.assertEqual(_motif_pcm.cache_info().misses, 1)
        self.assertEqual(_motif_pcm.cache_info().hits, 1)

    def test_motif_cache_rejects_unbounded_or_invalid_durations(self):
        for duration in (0, -1, 18.1, float("nan")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                _motif_pcm(duration, False)
