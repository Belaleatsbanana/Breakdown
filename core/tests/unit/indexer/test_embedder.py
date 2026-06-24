from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from breakdown.config import Settings
from breakdown.indexer.embedder import create_embedder


def test_create_embedder_openai_returns_embedder() -> None:
    settings = Settings(openai_api_key="sk-test", embedding_provider="openai")
    embedder = create_embedder("openai", settings)
    assert hasattr(embedder, "embed")


def test_create_embedder_unknown_raises() -> None:
    settings = Settings()
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        create_embedder("banana", settings)


def test_openai_embedder_calls_api(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    monkeypatch.setattr(
        "openai.OpenAI.embeddings",
        property(lambda self: MagicMock(create=MagicMock(return_value=fake_response))),
    )

    from breakdown.indexer.embedder import _OpenAIEmbedder
    embedder = _OpenAIEmbedder(api_key="sk-test", model="text-embedding-3-small")

    with patch.object(embedder._client.embeddings, "create", return_value=fake_response):
        result = embedder.embed(["hello"])

    assert result == [[0.1, 0.2, 0.3]]
