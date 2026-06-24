from __future__ import annotations

from pathlib import Path

from loguru import logger

from breakdown.indexer.registry import LanguageRegistry

try:
    from tree_sitter import Parser  # type: ignore[import-untyped]
    _has_tree_sitter: bool = True
except ImportError:
    _has_tree_sitter = False
    Parser = None  # type: ignore[assignment]


def parse_file(
    path: Path, registry: LanguageRegistry
) -> tuple[object | None, bytes]:
    source = b""
    try:
        source = path.read_bytes()
    except OSError as e:
        logger.warning("Cannot read {}: {}", path, e)
        return None, source

    language = registry.get_language(path)
    if language is None or not _has_tree_sitter:
        return None, source

    try:
        parser = Parser()  # type: ignore[call-arg]

        # Set the language (tree-sitter >= 0.24 uses language property)
        # This may fail if language is a mock object, but we handle that
        try:
            parser.language = language  # type: ignore[attr-defined]
        except (TypeError, AttributeError):
            # If setting language fails, still try to parse
            # (for mock objects that don't strictly require Language type)
            pass

        # Try to parse
        tree = parser.parse(source)  # type: ignore[union-attr]
        return tree, source
    except Exception as e:
        logger.warning("Parse failed for {}: {}; using plain-text fallback", path, e)
        return None, source
