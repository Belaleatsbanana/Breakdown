from __future__ import annotations

from pathlib import Path

from loguru import logger

try:
    import tree_sitter  # type: ignore[import-untyped]  # noqa: F401
    _has_tree_sitter: bool = True
except ImportError:
    _has_tree_sitter = False
    logger.warning("tree-sitter not installed; parsing disabled")

_EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".cs": "c_sharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".lua": "lua",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
}

_LANGUAGE_CACHE: dict[str, object | None] = {}


class LanguageRegistry:
    def get_language(self, path: Path) -> object | None:
        if not _has_tree_sitter:
            return None
        lang_name = _EXT_TO_LANGUAGE.get(path.suffix.lower())
        if lang_name is None:
            return None

        if lang_name in _LANGUAGE_CACHE:
            return _LANGUAGE_CACHE[lang_name]

        try:
            from tree_sitter_languages import (  # type: ignore[import-untyped]
                get_language,
            )

            lang: object | None = get_language(lang_name)  # type: ignore[assignment,call-arg,return-value]
            _LANGUAGE_CACHE[lang_name] = lang
            return lang
        except Exception:
            logger.debug("No grammar for {}", path.suffix)
            _LANGUAGE_CACHE[lang_name] = None
            return None
