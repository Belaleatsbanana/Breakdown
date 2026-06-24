from pathlib import Path

from breakdown.indexer.chunker import Chunk
from breakdown.indexer.store import create_store


def _dummy_embedding(dim: int = 4) -> list[float]:
    return [0.1] * dim


def test_add_and_search_returns_chunk(tmp_path: Path) -> None:
    store = create_store("lancedb", tmp_path / "db")
    chunk = Chunk(
        file="src/foo.py",
        start_line=1,
        end_line=5,
        text="def foo(): pass",
        type="function",
        name="foo",
    )
    ids = store.add([chunk], [_dummy_embedding()])
    assert len(ids) == 1
    results = store.search(_dummy_embedding(), k=1)
    assert len(results) == 1
    assert results[0].name == "foo"
    store.close()


def test_delete_removes_chunk(tmp_path: Path) -> None:
    store = create_store("lancedb", tmp_path / "db")
    chunk = Chunk(
        file="src/foo.py",
        start_line=1,
        end_line=5,
        text="def foo(): pass",
        type="function",
        name="foo",
    )
    ids = store.add([chunk], [_dummy_embedding()])
    store.delete(ids)
    results = store.search(_dummy_embedding(), k=10)
    assert all(r.name != "foo" for r in results)
    store.close()


def test_empty_store_search_returns_empty(tmp_path: Path) -> None:
    store = create_store("lancedb", tmp_path / "db")
    results = store.search(_dummy_embedding(), k=5)
    assert results == []
    store.close()
