from pathlib import Path

from breakdown.indexer.parser import parse_file
from breakdown.indexer.registry import LanguageRegistry


def test_registry_recognises_python() -> None:
    registry = LanguageRegistry()
    lang = registry.get_language(Path("foo.py"))
    assert lang is not None


def test_registry_returns_none_for_unknown() -> None:
    registry = LanguageRegistry()
    lang = registry.get_language(Path("foo.xyz"))
    assert lang is None


def test_parse_python_file_returns_tree(fixtures_dir: Path) -> None:
    registry = LanguageRegistry()
    path = fixtures_dir / "sample_project" / "src" / "hello.py"
    tree, source = parse_file(path, registry)
    assert tree is not None
    assert b"greet" in source


def test_parse_unknown_file_returns_none_tree(fixtures_dir: Path) -> None:
    registry = LanguageRegistry()
    path = fixtures_dir / "sample_project" / "src" / "unknown.xyz"
    tree, source = parse_file(path, registry)
    assert tree is None
    assert len(source) > 0  # source bytes still returned for fallback chunking
