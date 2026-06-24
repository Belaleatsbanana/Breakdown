from __future__ import annotations

from pathlib import Path

from breakdown.indexer.ignore import IgnoreFilter


def test_ignores_node_modules(fixtures_dir: Path) -> None:
    root = fixtures_dir / "sample_project"
    f = IgnoreFilter(root)
    assert f.is_ignored(root / "node_modules" / "lodash" / "index.js")


def test_does_not_ignore_src(fixtures_dir: Path) -> None:
    root = fixtures_dir / "sample_project"
    f = IgnoreFilter(root)
    assert not f.is_ignored(root / "src" / "main.py")


def test_ignores_log_file(fixtures_dir: Path) -> None:
    root = fixtures_dir / "sample_project"
    f = IgnoreFilter(root)
    assert f.is_ignored(root / "debug.log")


def test_ignores_pycache_by_default(fixtures_dir: Path) -> None:
    root = fixtures_dir / "sample_project"
    f = IgnoreFilter(root)
    assert f.is_ignored(root / "src" / "__pycache__" / "main.cpython-311.pyc")


def test_ignores_dot_git_by_default(fixtures_dir: Path) -> None:
    root = fixtures_dir / "sample_project"
    f = IgnoreFilter(root)
    assert f.is_ignored(root / ".git" / "config")
