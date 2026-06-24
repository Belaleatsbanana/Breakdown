from __future__ import annotations

from breakdown.config import Settings


def create_llm(settings: Settings) -> object:
    if settings.llm_provider == "mistral":
        if not settings.mistral_api_key:
            raise ValueError("MISTRAL_API_KEY is required when LLM_PROVIDER=mistral")
        from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
        return lk_openai.LLM(
            model=settings.llm_model,
            api_key=settings.mistral_api_key,
            base_url="https://api.mistral.ai/v1",
        )

    from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
    return lk_openai.LLM(
        model=settings.llm_model,
        api_key=settings.openai_api_key or "placeholder",
    )
