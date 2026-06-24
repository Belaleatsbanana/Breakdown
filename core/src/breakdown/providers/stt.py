from __future__ import annotations

from breakdown.config import Settings


def create_stt(settings: Settings) -> object:
    if settings.stt_provider == "openai":
        from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
        return lk_openai.STT(
            api_key=settings.openai_api_key or "placeholder",
        )

    if settings.stt_provider == "deepgram":
        if not settings.deepgram_api_key:
            raise ValueError(
                "DEEPGRAM_API_KEY is required when STT_PROVIDER=deepgram"
            )
        from livekit.plugins import deepgram  # type: ignore[import-untyped]
        return deepgram.STT(api_key=settings.deepgram_api_key)

    raise ValueError(
        f"Unknown STT provider: {settings.stt_provider!r}. Choose 'openai' or 'deepgram'."
    )
