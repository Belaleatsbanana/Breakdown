from __future__ import annotations

from typing import Protocol, runtime_checkable

from loguru import logger

from breakdown.config import Settings


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def create_embedder(provider: str, settings: Settings) -> Embedder:
    if provider == "openai":
        return _OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small",
        )
    if provider == "local":
        return _LocalEmbedder()
    raise ValueError(
        f"Unknown embedding provider: {provider!r}. Choose 'openai' or 'local'."
    )


class _OpenAIEmbedder:
    def __init__(self, api_key: str, model: str) -> None:
        import openai  # type: ignore[import-untyped]
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # batch in groups of 100 to stay within API limits
        results: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            response = self._client.embeddings.create(input=batch, model=self._model)
            results.extend(item.embedding for item in response.data)
        return results


class _LocalEmbedder:
    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: uv sync --extra local-embeddings"
            ) from e
        logger.info("Loading local embedding model BAAI/bge-code-v1 (first run downloads ~117MB)")
        self._model = SentenceTransformer("BAAI/bge-code-v1")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, show_progress_bar=False)
        return [v.tolist() for v in vectors]
