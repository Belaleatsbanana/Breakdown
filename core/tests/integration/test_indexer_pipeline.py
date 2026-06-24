from __future__ import annotations

# Full pipeline: ignore -> parse -> chunk -> embed -> store -> search.
# Uses a real fixture codebase but mocks the OpenAI embedding call.
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from breakdown.config import Settings
from breakdown.indexer.chunker import chunk_tree
from breakdown.indexer.embedder import create_embedder
from breakdown.indexer.ignore import IgnoreFilter
from breakdown.indexer.manifest import Manifest
from breakdown.indexer.parser import parse_file
from breakdown.indexer.registry import LanguageRegistry
from breakdown.indexer.store import create_store


@pytest.mark.integration
def test_full_index_pipeline(fixtures_dir: Path, tmp_path: Path) -> None:
    root = fixtures_dir / "sample_project"
    settings = Settings(openai_api_key="sk-test", embedding_provider="openai")

    ignore = IgnoreFilter(root)
    registry = LanguageRegistry()
    manifest = Manifest(tmp_path / "manifest.json")
    store = create_store("lancedb", tmp_path / "db")

    fake_embedding = [0.1] * 1536  # text-embedding-3-small dimension

    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=fake_embedding)]
        mock_client.embeddings.create.return_value = mock_response

        embedder = create_embedder("openai", settings)

        files = [f for f in root.rglob("*") if f.is_file() and not ignore.is_ignored(f)]
        assert len(files) > 0

        total_chunks = 0
        for file in files:
            tree, source = parse_file(file, registry)
            rel = str(file.relative_to(root))
            chunks = chunk_tree(tree, source, rel, window_lines=50)
            if chunks:
                # return one embedding per chunk
                mock_response.data = [MagicMock(embedding=fake_embedding) for _ in chunks]
                embeddings = embedder.embed([c.text for c in chunks])
                ids = store.add(chunks, embeddings)
                manifest.update(file, ids)
                total_chunks += len(chunks)

        manifest.save()
        assert total_chunks > 0

        results = store.search(fake_embedding, k=3)
        assert len(results) > 0
        assert any(r.file.endswith(".py") or r.file.endswith(".xyz") for r in results)

    store.close()
