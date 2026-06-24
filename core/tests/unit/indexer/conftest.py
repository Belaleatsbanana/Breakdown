from __future__ import annotations

from collections.abc import Iterator
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def mock_tree_sitter_languages() -> Iterator[None]:
    """Mock tree-sitter-languages to avoid environment-specific ABI issues."""

    class MockLanguage:
        def __init__(self, name: str) -> None:
            self.name = name

    class MockTree:
        def __init__(self, source: bytes) -> None:
            self.source = source

        @property
        def root_node(self) -> object:
            class MockNode:
                pass

            return MockNode()

    class MockParser:
        def __init__(self) -> None:
            self._language: object | None = None

        def set_language(self, language: object) -> None:
            self._language = language

        def parse(self, source: bytes) -> object | None:
            if self._language is not None:
                return MockTree(source)
            return None

    def mock_get_language(lang_name: str) -> object:
        supported = {
            "python", "javascript", "typescript", "tsx", "go", "rust",
            "java", "c", "cpp", "ruby", "c_sharp", "php", "swift",
            "kotlin", "scala", "lua", "bash",
        }
        if lang_name in supported:
            return MockLanguage(lang_name)
        raise ImportError(f"No grammar for {lang_name}")

    with mock.patch("tree_sitter_languages.get_language", side_effect=mock_get_language):
        with mock.patch("breakdown.indexer.parser.Parser", MockParser):
            yield
