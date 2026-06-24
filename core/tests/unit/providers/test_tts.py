from __future__ import annotations

import pytest

from breakdown.config import Settings
from breakdown.providers.tts import create_tts


def test_create_tts_openai_returns_tts() -> None:
    settings = Settings(openai_api_key="sk-test", tts_provider="openai")
    tts = create_tts(settings)
    assert hasattr(tts, "synthesize")


def test_create_tts_elevenlabs_requires_key() -> None:
    settings = Settings(tts_provider="elevenlabs", elevenlabs_api_key="")
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        create_tts(settings)
