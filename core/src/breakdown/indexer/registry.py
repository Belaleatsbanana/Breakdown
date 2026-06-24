from __future__ import annotations

import ctypes
import os
from pathlib import Path

from loguru import logger

try:
    from tree_sitter import Language  # type: ignore[import-untyped]
    _has_tree_sitter: bool = True
except ImportError:
    _has_tree_sitter = False
    Language = None  # type: ignore[assignment]
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


def _load_language_from_so(lang_name: str) -> object | None:
    """Load language directly from tree-sitter-languages .so file."""
    try:
        import tree_sitter_languages  # type: ignore[import-untyped]

        tsl_path = os.path.dirname(tree_sitter_languages.__file__)
        languages_so = os.path.join(tsl_path, "languages.so")

        if not os.path.exists(languages_so):
            return None

        lib = ctypes.CDLL(languages_so)
        func_name = f"tree_sitter_{lang_name}"

        try:
            func = getattr(lib, func_name)
        except AttributeError:
            return None

        # Call the function to get the language pointer
        lang_ptr_raw = func()
        if lang_ptr_raw == 0 or lang_ptr_raw == -1:
            return None

        # Try to create a Language object
        # This may fail due to API incompatibilities, but try anyway
        try:
            # The Language constructor expects a pointer
            lang = Language(lang_ptr_raw)  # type: ignore[call-arg]
            return lang
        except TypeError:
            # If Language() fails, create a wrapper object
            # that tree-sitter might still accept
            class LanguageProxy:
                def __init__(self, ptr: int) -> None:
                    self._ptr = ptr
                    self._ptr_c = ctypes.c_void_p(ptr)

            return LanguageProxy(lang_ptr_raw)
    except Exception:
        return None


class LanguageRegistry:
    def get_language(self, path: Path) -> object | None:
        if not _has_tree_sitter:
            return None
        lang_name = _EXT_TO_LANGUAGE.get(path.suffix.lower())
        if lang_name is None:
            return None

        # Try cache first
        if lang_name in _LANGUAGE_CACHE:
            return _LANGUAGE_CACHE[lang_name]

        # Try the standard get_language first
        try:
            from tree_sitter_languages import (  # type: ignore[import-untyped]
                get_language,  # type: ignore[assignment]
            )

            lang: object | None = get_language(lang_name)  # type: ignore[assignment,call-arg,return-value]
            _LANGUAGE_CACHE[lang_name] = lang
            return lang  # type: ignore[return-value]
        except Exception:
            pass

        # Fallback: load directly from .so
        lang_fallback: object | None = _load_language_from_so(lang_name)
        _LANGUAGE_CACHE[lang_name] = lang_fallback
        if lang_fallback is None:
            logger.debug("No grammar for {}", path.suffix)
        return lang_fallback
