from pathlib import Path
from unittest import mock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(autouse=True)
def mock_tree_sitter_languages() -> None:
    """Mock tree-sitter-languages to work around environment incompatibilities."""

    # Create a mock Language class
    class MockLanguage:
        """Mock Language object for testing."""

        def __init__(self, name: str) -> None:
            self.name = name
            self._ptr = 0xDEADBEEF

    # Create a mock Tree class
    class MockTree:
        """Mock tree-sitter Tree object."""

        def __init__(self, source: bytes) -> None:
            self.source = source

        @property
        def root_node(self) -> object:
            class MockNode:
                pass

            return MockNode()

    # Create a mock Parser class
    class MockParser:
        """Mock tree-sitter Parser object."""

        def __init__(self) -> None:
            self._language = None
            self._source = None

        @property
        def language(self) -> object:  # type: ignore[no-untyped-def]
            return self._language

        @language.setter
        def language(self, value: object) -> None:
            # Accept any object (including mocks)
            self._language = value

        def parse(self, source: bytes) -> object:  # type: ignore[no-untyped-def]
            # If we have a mock language, return a mock tree
            if self._language is not None:
                return MockTree(source)
            # Otherwise, return None (will fallback in parser.py)
            return None

    # Create a mock get_language function
    def mock_get_language(lang_name: str) -> object:
        """Return a mock Language object for testing."""
        supported_langs = {
            "python",
            "javascript",
            "typescript",
            "tsx",
            "go",
            "rust",
            "java",
            "c",
            "cpp",
            "ruby",
            "c_sharp",
            "php",
            "swift",
            "kotlin",
            "scala",
            "lua",
            "bash",
        }
        if lang_name in supported_langs:
            return MockLanguage(lang_name)
        raise ImportError(f"No grammar for {lang_name}")

    # Patch both get_language and Parser
    with mock.patch("tree_sitter_languages.get_language", side_effect=mock_get_language):
        with mock.patch("breakdown.indexer.parser.Parser", MockParser):
            with mock.patch("tree_sitter.Parser", MockParser):
                yield
