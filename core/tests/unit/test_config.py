import os
from unittest.mock import patch

from breakdown.config import Settings


def test_settings_loads_from_env() -> None:
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o"}):
        s = Settings()
        assert s.llm_model == "gpt-4o"
        assert s.openai_api_key == "sk-test"


def test_settings_default_tts_provider() -> None:
    s = Settings()
    assert s.tts_provider == "openai"


def test_settings_default_index_backend() -> None:
    s = Settings()
    assert s.index_backend == "lancedb"


def test_settings_context_window_lines_default() -> None:
    s = Settings()
    assert s.context_window_lines == 50


def test_settings_history_budget_pct_default() -> None:
    s = Settings()
    assert s.history_budget_pct == 0.8
