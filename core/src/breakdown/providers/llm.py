from __future__ import annotations

from breakdown.config import Settings


def create_llm(settings: Settings) -> object:
    from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]

    # Use LiveKit's OpenAI plugin as the base; route through LiteLLM for
    # non-OpenAI models by setting the base_url and api_key appropriately.
    # LiteLLM proxy is not used -- we call litellm.completion directly in the
    # agent when needed for non-streaming cases.
    return lk_openai.LLM(
        model=settings.llm_model,
        api_key=settings.openai_api_key or "placeholder",
    )
