from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LiveKit
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_context_window: int = 128_000
    llm_base_url: str = ""  # override base URL for any OpenAI-compatible provider
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    mistral_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    together_api_key: str = ""
    perplexity_api_key: str = ""

    # TTS
    tts_provider: Literal["openai", "elevenlabs", "deepgram"] = "openai"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "Rachel"
    deepgram_tts_model: str = "aura-2-andromeda-en"

    # STT
    stt_provider: Literal["openai", "deepgram"] = "openai"
    deepgram_api_key: str = ""

    # Embeddings
    embedding_provider: Literal["openai", "local"] = "openai"

    # Index
    index_backend: Literal["lancedb", "chromadb"] = "lancedb"
    context_window_lines: int = Field(default=50, ge=10, le=500)
    index_debounce_seconds: float = 3.0
    index_respect_gitignore: bool = True

    # Session
    history_budget_pct: float = Field(default=0.8, gt=0.0, le=1.0)

    # Token server
    token_server_port_start: int = 7890


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
