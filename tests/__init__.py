"""Offline repository checks."""

import os

# Tests never call the Claude API, even when the owner's shell exports the key.
os.environ.pop("FIELD_AUDIO_ANTHROPIC_API_KEY", None)
