"""Reuse short-lived Google access tokens in memory within one CLI run."""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from field_notes_audio.progress import timed


@dataclass(frozen=True)
class _Token:
    value: str = field(repr=False)
    acquired_at: float


class TokenCache:
    """Serialize refreshes; separate gcloud and ADC identities and never persist tokens."""

    def __init__(self, ttl: float = 300) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._tokens: dict[str, _Token] = {}

    def get(self, auth: str, load: Callable[[str], str]) -> str:
        with self._lock:
            token = self._tokens.get(auth)
            if token is None or time.monotonic() - token.acquired_at >= self._ttl:
                with timed("authentication"):
                    value = load(auth)
                if not value:
                    raise RuntimeError("Google returned an empty access token")
                token = _Token(value, time.monotonic())
                self._tokens[auth] = token
            return token.value

    def invalidate(self, value: str) -> None:
        with self._lock:
            self._tokens = {
                key: token for key, token in self._tokens.items() if token.value != value
            }


def _load_token(auth: str) -> str:
    if auth not in {"gcloud", "adc"}:
        raise ValueError("Unknown Google authentication mode")
    command = ["gcloud", "auth"]
    if auth == "adc":
        command.append("application-default")
    command.append("print-access-token")
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError(
            "Google authentication failed. Authorize Cloud Shell, or run gcloud auth login locally."
        )
    return result.stdout.strip()


_cache = TokenCache()


def access_token(auth: str) -> str:
    return _cache.get(auth, _load_token)


def invalidate_token(token: str) -> None:
    """Discard a rejected token without automatically resending a paid request."""
    _cache.invalidate(token)
