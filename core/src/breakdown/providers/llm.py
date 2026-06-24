from __future__ import annotations

from breakdown.config import Settings

# Providers that use an OpenAI-compatible API and route through livekit's openai plugin
_OPENAI_COMPAT = {
    "mistral": ("https://api.mistral.ai/v1", "mistral_api_key"),
    "groq": ("https://api.groq.com/openai/v1", "groq_api_key"),
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter_api_key"),
    "together": ("https://api.together.xyz/v1", "together_api_key"),
    "perplexity": ("https://api.perplexity.ai", "perplexity_api_key"),
}


def create_llm(settings: Settings) -> object:
    provider = settings.llm_provider

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        from livekit.plugins import anthropic as lk_anthropic  # type: ignore[import-untyped]
        return lk_anthropic.LLM(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
        )

    if provider in _OPENAI_COMPAT:
        base_url, key_attr = _OPENAI_COMPAT[provider]
        api_key: str = getattr(settings, key_attr, "") or ""
        if not api_key:
            raise ValueError(
                f"{key_attr.upper()} is required when LLM_PROVIDER={provider}"
            )
        from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
        return lk_openai.LLM(
            model=settings.llm_model,
            api_key=api_key,
            base_url=base_url,
        )

    # Default: OpenAI (or any custom base_url via llm_base_url)
    from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
    kwargs: dict[str, object] = {
        "model": settings.llm_model,
        "api_key": settings.openai_api_key or "placeholder",
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return lk_openai.LLM(**kwargs)  # type: ignore[arg-type]
