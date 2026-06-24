from __future__ import annotations

from breakdown.config import Settings
from breakdown.providers.llm import create_llm


def test_create_llm_returns_object_with_chat() -> None:
    settings = Settings(openai_api_key="sk-test", llm_model="gpt-4o")
    llm = create_llm(settings)
    assert hasattr(llm, "chat")


def test_create_llm_unsupported_model_does_not_raise() -> None:
    # LiteLLM accepts any model string; invalid ones fail at call time, not creation
    settings = Settings(openai_api_key="sk-test", llm_model="gpt-99-nonexistent")
    llm = create_llm(settings)
    assert llm is not None
