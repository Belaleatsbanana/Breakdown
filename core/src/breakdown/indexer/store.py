from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol, runtime_checkable

from breakdown.indexer.chunker import Chunk


@runtime_checkable
class VectorStore(Protocol):
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]: ...
    def search(self, embedding: list[float], k: int) -> list[Chunk]: ...
    def delete(self, chunk_ids: list[str]) -> None: ...
    def close(self) -> None: ...


def create_store(backend: str, db_path: Path) -> VectorStore:
    if backend == "lancedb":
        return _LanceDBStore(db_path)
    if backend == "chromadb":
        return _ChromaDBStore(db_path)
    raise ValueError(f"Unknown index backend: {backend!r}. Choose 'lancedb' or 'chromadb'.")


class _LanceDBStore:
    _TABLE = "chunks"

    def __init__(self, db_path: Path) -> None:
        import lancedb  # type: ignore[import-untyped]

        db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(db_path))
        self._table_created = self._TABLE in list(self._db.list_tables())  # type: ignore[reportOperatorIssue]
        if self._table_created:
            self._table = self._db.open_table(self._TABLE)
        else:
            self._table = None

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
        ids = [str(uuid.uuid4()) for _ in chunks]
        rows = [
            {
                "id": cid,
                "file": c.file,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "text": c.text,
                "type": c.type,
                "name": c.name,
                "vector": emb,
            }
            for cid, c, emb in zip(ids, chunks, embeddings)
        ]
        if not self._table_created:
            self._table = self._db.create_table(self._TABLE, data=rows, mode="overwrite")
            self._table_created = True
        else:
            self._table.add(rows)  # type: ignore[union-attr]
        return ids

    def search(self, embedding: list[float], k: int) -> list[Chunk]:
        if self._table is None:
            return []
        try:
            results = self._table.search(embedding).limit(k).to_list()
        except Exception:
            return []
        return [
            Chunk(
                file=str(r["file"]),
                start_line=int(r["start_line"]),  # type: ignore[arg-type]
                end_line=int(r["end_line"]),  # type: ignore[arg-type]
                text=str(r["text"]),
                type=str(r["type"]),
                name=str(r["name"]),
            )
            for r in results
        ]

    def delete(self, chunk_ids: list[str]) -> None:
        if not chunk_ids or self._table is None:
            return
        id_list = ", ".join(f"'{cid}'" for cid in chunk_ids)
        self._table.delete(f"id IN ({id_list})")

    def close(self) -> None:
        pass  # lancedb connections are context-free


class _ChromaDBStore:
    _COLLECTION = "chunks"

    def __init__(self, db_path: Path) -> None:
        try:
            import chromadb  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "chromadb is not installed. Run: uv sync --extra chromadb"
            ) from e
        db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(db_path))
        self._col = self._client.get_or_create_collection(self._COLLECTION)

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
        ids = [str(uuid.uuid4()) for _ in chunks]
        self._col.add(  # type: ignore[arg-type]
            ids=ids,
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "file": c.file,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "type": c.type,
                    "name": c.name,
                }
                for c in chunks
            ],
        )
        return ids

    def search(self, embedding: list[float], k: int) -> list[Chunk]:
        results = self._col.query(query_embeddings=[embedding], n_results=k)
        chunks = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            chunks.append(Chunk(
                file=meta["file"],
                start_line=int(meta["start_line"]),
                end_line=int(meta["end_line"]),
                text=doc,
                type=meta["type"],
                name=meta["name"],
            ))
        return chunks

    def delete(self, chunk_ids: list[str]) -> None:
        if chunk_ids:
            self._col.delete(ids=chunk_ids)

    def close(self) -> None:
        pass
