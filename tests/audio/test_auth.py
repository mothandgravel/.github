"""Token refresh and credential-handling regressions without Google calls."""

import io
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib import error

from field_notes_audio import auth, captions


class TokenCacheTests(TestCase):
    def test_parallel_requests_acquire_only_one_token(self):
        cache = auth.TokenCache()
        load = Mock(return_value="private-token")
        barrier = threading.Barrier(8)

        def request_token(_):
            barrier.wait(timeout=5)
            return cache.get("gcloud", load)

        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(request_token, range(8))), ["private-token"] * 8)
        load.assert_called_once_with("gcloud")
        self.assertNotIn("private-token", repr(cache._tokens))

    def test_expiry_and_auth_modes_refresh_independently(self):
        cache = auth.TokenCache(ttl=300)
        load = Mock(side_effect=["first", "adc-token", "second"])
        with patch.object(auth.time, "monotonic", return_value=0):
            self.assertEqual(cache.get("gcloud", load), "first")
            self.assertEqual(cache.get("adc", load), "adc-token")
        with patch.object(auth.time, "monotonic", return_value=299):
            self.assertEqual(cache.get("gcloud", load), "first")
        with patch.object(auth.time, "monotonic", return_value=301):
            self.assertEqual(cache.get("gcloud", load), "second")
        self.assertEqual(load.call_count, 3)

    def test_rejected_token_is_discarded_and_failed_refresh_is_not_cached(self):
        cache = auth.TokenCache()
        load = Mock(side_effect=["first", RuntimeError("authentication failed"), "second"])
        self.assertEqual(cache.get("gcloud", load), "first")
        cache.invalidate("first")
        with self.assertRaises(RuntimeError):
            cache.get("gcloud", load)
        self.assertEqual(cache.get("gcloud", load), "second")

    def test_rejected_authentication_invalidates_token_without_resending_paid_submission(self):
        failure = error.HTTPError(
            "https://speech.googleapis.com", 401, "Unauthorized", {}, io.BytesIO(b"{}")
        )
        with (
            patch.object(captions, "access_token", return_value="private-token"),
            patch.object(captions, "invalidate_token") as invalidate,
            patch.object(captions.request, "urlopen", side_effect=failure) as call,
        ):
            with self.assertRaises(captions.CloudError):
                captions.cloud_json(
                    "https://speech.googleapis.com/v2/job:batchRecognize",
                    "project",
                    "gcloud",
                    {"files": []},
                )
        self.assertEqual(call.call_count, 1)
        invalidate.assert_called_once_with("private-token")
