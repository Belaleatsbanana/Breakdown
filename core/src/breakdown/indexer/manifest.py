from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class _Entry:
    mtime: float
    content_hash: str
    chunk_ids: list[str]


class Manifest:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, _Entry] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data: dict[str, dict[str, object]] = json.loads(self._path.read_text())
            for k, v in data.items():
                self._entries[k] = _Entry(
                    mtime=float(v["mtime"]),  # type: ignore[arg-type]
                    content_hash=str(v["content_hash"]),
                    chunk_ids=list(v["chunk_ids"]),  # type: ignore[arg-type]
                )
        except Exception as e:
            logger.warning("Manifest corrupt, starting fresh: {}", e)
            self._entries = {}

    def is_stale(self, file: Path) -> bool:
        key = str(file)
        entry = self._entries.get(key)
        if entry is None:
            return True
        try:
            stat = file.stat()
            if stat.st_mtime != entry.mtime:
                current_hash = hashlib.sha256(file.read_bytes()).hexdigest()
                return current_hash != entry.content_hash
            return False
        except OSError:
            return True

    def update(self, file: Path, chunk_ids: list[str]) -> None:
        try:
            stat = file.stat()
            content_hash = hashlib.sha256(file.read_bytes()).hexdigest()
            self._entries[str(file)] = _Entry(
                mtime=stat.st_mtime,
                content_hash=content_hash,
                chunk_ids=chunk_ids,
            )
        except OSError as e:
            logger.warning("Cannot update manifest for {}: {}", file, e)

    def remove(self, file: Path) -> None:
        self._entries.pop(str(file), None)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        data = {
            k: {"mtime": e.mtime, "content_hash": e.content_hash, "chunk_ids": e.chunk_ids}
            for k, e in self._entries.items()
        }
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._path)  # atomic rename
