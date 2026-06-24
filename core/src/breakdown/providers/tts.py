from __future__ import annotations

from breakdown.config import Settings


def create_tts(settings: Settings) -> object:
    if settings.tts_provider == "openai":
        from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
        return lk_openai.TTS(
            api_key=settings.openai_api_key or "placeholder",
            voice="alloy",
        )

    if settings.tts_provider == "elevenlabs":
        if not settings.elevenlabs_api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is required when TTS_PROVIDER=elevenlabs"
            )
        from livekit.plugins import elevenlabs  # type: ignore[import-untyped]
        return elevenlabs.TTS(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
        )

    if settings.tts_provider == "deepgram":
        if not settings.deepgram_api_key:
            raise ValueError(
                "DEEPGRAM_API_KEY is required when TTS_PROVIDER=deepgram"
            )
        from livekit.plugins import deepgram  # type: ignore[import-untyped]
        return deepgram.TTS(
            model=settings.deepgram_tts_model,
            api_key=settings.deepgram_api_key,
        )

    raise ValueError(
        f"Unknown TTS provider: {settings.tts_provider!r}. Choose 'openai', 'elevenlabs', or 'deepgram'."
    )
