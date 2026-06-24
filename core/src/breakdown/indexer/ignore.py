from __future__ import annotations

import fnmatch
from pathlib import Path

_DEFAULT_IGNORE: list[str] = [
    ".git/",
    ".breakdown/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "node_modules/",
    "dist/",
    "build/",
    ".next/",
    "*.pyc",
    "*.pyo",
    "*.min.js",
    "*.min.css",
    "*.lock",
    "*.log",
    "*.egg-info/",
    ".DS_Store",
    "Thumbs.db",
]


class IgnoreFilter:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._patterns: list[str] = list(_DEFAULT_IGNORE)
        self._load_gitignore(root / ".gitignore")
        self._load_gitignore(root / ".breakdownignore")

    def _load_gitignore(self, path: Path) -> None:
        if not path.exists():
            return
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self._patterns.append(line)

    def is_ignored(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self._root)
        except ValueError:
            return False
        parts = rel.parts
        for pattern in self._patterns:
            is_dir_pattern = pattern.endswith("/")
            p = pattern.rstrip("/")
            # match against any path component or full relative path
            for part in parts:
                if fnmatch.fnmatch(part, p):
                    return True
            if fnmatch.fnmatch(str(rel), p):
                return True
            if is_dir_pattern and any(fnmatch.fnmatch(part, p) for part in parts):
                return True
        return False
