from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from loguru import logger

from breakdown.config import Settings

if TYPE_CHECKING:
    from google.genai.types import EmbedContentResponse  # type: ignore[import-untyped]


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def create_embedder(provider: str, settings: Settings) -> Embedder:
    if provider == "openai":
        return _OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small",
        )
    if provider == "gemini":
        return _GeminiEmbedder(api_key=settings.gemini_api_key)
    if provider == "jina":
        return _JinaEmbedder(api_key=settings.jina_api_key)
    if provider == "local":
        return _LocalEmbedder()
    raise ValueError(
        f"Unknown embedding provider: {provider!r}. Choose 'openai', 'gemini', 'jina', or 'local'."
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


class _GeminiEmbedder:
    def __init__(self, api_key: str) -> None:
        from google import genai  # type: ignore[import-untyped]
        self._client = genai.Client(api_key=api_key)
        self._model = "gemini-embedding-001"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # batch in groups of 100, matching the OpenAI embedder's batching
        results: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            response = self._embed_batch(batch)
            if response.embeddings is None:
                raise RuntimeError("Gemini embedding response contained no embeddings")
            for embedding in response.embeddings:
                if embedding.values is None:
                    raise RuntimeError("Gemini embedding response contained an empty vector")
                results.append(embedding.values)
        return results

    def _embed_batch(self, batch: list[str]) -> EmbedContentResponse:
        from google.genai import errors  # type: ignore[import-untyped]
        from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

        def _is_rate_limited(exc: BaseException) -> bool:
            return isinstance(exc, errors.ClientError) and exc.code == 429

        @retry(
            retry=retry_if_exception(_is_rate_limited),
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=2, min=2, max=60),
            reraise=True,
        )
        def _call() -> EmbedContentResponse:
            return self._client.models.embed_content(model=self._model, contents=batch)

        try:
            return _call()
        except errors.ClientError as e:
            if e.code == 429:
                logger.error(
                    "Gemini embedding quota exhausted after retries. Check your usage/limits "
                    "at https://ai.dev/rate-limit or switch EMBEDDING_PROVIDER to 'openai' or "
                    "'local' in .env."
                )
            raise


class _JinaEmbedder:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._model = "jina-embeddings-v3"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # batch in groups of 100, matching the other embedders' batching
        results: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            results.extend(self._embed_batch(batch))
        return results

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        import time

        import httpx

        wait_seconds = 2.0
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            response = httpx.post(
                "https://api.jina.ai/v1/embeddings",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                json={"input": batch, "model": self._model, "task": "retrieval.passage"},
                timeout=30.0,
            )
            if response.status_code == 429 and attempt < max_attempts:
                logger.warning(
                    "Jina embedding rate limited, retrying in {:.0f}s (attempt {}/{})",
                    wait_seconds,
                    attempt,
                    max_attempts,
                )
                time.sleep(wait_seconds)
                wait_seconds *= 2
                continue
            response.raise_for_status()
            return [item["embedding"] for item in response.json()["data"]]
        raise RuntimeError("Jina embedding request failed after retries")


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
