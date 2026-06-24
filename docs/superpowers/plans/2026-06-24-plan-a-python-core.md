# Breakdown Plan A: Python Core

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Python core: project scaffold, indexer pipeline, provider abstractions, LiveKit agent, session management, token server, and CLI.

**Architecture:** A Python package (`breakdown`) exposing a `breakdown start` command that launches a localhost token server and a LiveKit agent. The agent indexes the codebase on first run, then handles real-time explain/navigate/interrupt DataPackets from platform clients, routing through swappable LLM/TTS/STT providers.

**Tech Stack:** Python 3.11+, uv, livekit-agents 1.x, LiteLLM, LanceDB, tree-sitter, sentence-transformers (optional), pydantic-settings, typer, loguru, watchdog, tiktoken, towncrier, basedpyright, ruff, pytest

---

## Global Constraints

- Python 3.11+ only
- All public functions must have type annotations (basedpyright strict mode enforced in CI)
- No `print()` anywhere -- use `from loguru import logger`
- `agent.py` must stay under 150 lines
- `session.py` must not import anything from `agent.py`
- Paths sent over the protocol wire are always relative to workspace root, never absolute
- Ports are discovered at runtime, never hardcoded beyond the default starting point (7890)
- `.breakdown/` directory is always gitignored
- One `VERSION` file at repo root; `pyproject.toml` reads it via `hatch-vcs` or direct read
- Conventional commits enforced: `feat:`, `fix:`, `docs:`, `perf:`, `chore:`
- Every test file mirrors the source path: `src/breakdown/indexer/chunker.py` -> `tests/unit/indexer/test_chunker.py`

---

## File Map

```
Breakdown/
  VERSION                          # "0.1.0"
  .env.example                     # all keys documented
  .gitignore                       # includes .breakdown/, .env, __pycache__
  ruff.toml                        # E, F, I, UP, ANN, RUF, T20
  pyproject.toml                   # deps, scripts, tool config

  core/
    src/
      breakdown/
        __init__.py                # exposes __version__
        config.py                  # pydantic-settings Settings class
        cli.py                     # typer app: start | index | version
        agent.py                   # LiveKit agent, thin coordinator <150 lines
        session.py                 # Session dataclass, pure, no agent imports
        token_server.py            # stdlib http.server, localhost-only JWT endpoint
        indexer/
          __init__.py
          ignore.py                # IgnoreFilter: defaults + .gitignore + .breakdownignore
          registry.py              # LanguageRegistry: ext -> tree-sitter grammar
          parser.py                # parse_file(path) -> Tree | None
          chunker.py               # chunk_tree(tree, source) -> list[Chunk]
          embedder.py              # Embedder protocol + OpenAIEmbedder + LocalEmbedder
          store.py                 # VectorStore protocol + LanceDBStore + ChromaDBStore
          manifest.py              # Manifest: tracks mtime+hash+chunk_ids per file
          watcher.py               # FileWatcher: watchdog-based incremental re-index
        providers/
          __init__.py
          llm.py                   # LiteLLMLLM: LiveKit LLM plugin adapter
          tts.py                   # TTSProvider protocol + OpenAITTS + ElevenLabsTTS
          stt.py                   # STTProvider protocol + OpenAISTT + DeepgramSTT
        py.typed                   # PEP 561 marker

    tests/
      conftest.py                  # shared fixtures
      unit/
        test_config.py
        test_session.py
        test_token_server.py
        indexer/
          test_ignore.py
          test_chunker.py
          test_manifest.py
          test_store.py
        providers/
          test_llm.py
          test_tts.py
          test_stt.py
      integration/
        test_indexer_pipeline.py   # full index run on fixture codebase
```

---

### Task 1: Repository Scaffold

**Files:**
- Create: `VERSION`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `ruff.toml`
- Create: `core/pyproject.toml`
- Create: `core/src/breakdown/__init__.py`
- Create: `core/src/breakdown/py.typed`
- Create: `core/tests/conftest.py`

**Interfaces:**
- Produces: `breakdown` package importable; `uv run pytest` works; `uv run ruff check` works

- [ ] **Step 1: Create VERSION**

```
0.1.0
```

File: `VERSION` (repo root, no newline after)

- [ ] **Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
dist/
*.egg-info/

# Runtime state
.breakdown/

# Secrets
.env

# Editor
.vscode/settings.json
.idea/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Create .env.example**

```dotenv
# LiveKit -- leave blank to auto-start local Docker server
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

# LLM (required)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=

# TTS (required)
TTS_PROVIDER=openai
# ELEVENLABS_API_KEY=   # set if TTS_PROVIDER=elevenlabs

# STT (required)
STT_PROVIDER=openai
# DEEPGRAM_API_KEY=     # set if STT_PROVIDER=deepgram

# Embeddings
# EMBEDDING_PROVIDER=local   # set to use local sentence-transformers (no extra API key)
```

- [ ] **Step 4: Create ruff.toml**

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["E", "F", "I", "UP", "ANN", "RUF", "T20"]
ignore = ["ANN101", "ANN102"]  # skip self/cls annotations

[lint.isort]
known-first-party = ["breakdown"]

[format]
quote-style = "double"
```

- [ ] **Step 5: Create core/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "breakdown"
dynamic = ["version"]
description = "Voice-driven AI code explainer"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
    "livekit-agents[openai]>=1.0",
    "livekit-api>=0.7",
    "litellm>=1.40",
    "lancedb>=0.6",
    "tree-sitter>=0.23",
    "tree-sitter-languages>=1.10",
    "pydantic-settings>=2.3",
    "typer>=0.12",
    "loguru>=0.7",
    "watchdog>=4.0",
    "tiktoken>=0.7",
    "httpx>=0.27",
    "rich>=13.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
local-embeddings = [
    "sentence-transformers>=3.0",
    "torch>=2.3",
]
chromadb = [
    "chromadb>=0.5",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "basedpyright>=1.14",
    "ruff>=0.5",
]

[project.scripts]
breakdown = "breakdown.cli:app"

[tool.hatch.version]
path = "../VERSION"

[tool.hatch.build.targets.wheel]
packages = ["src/breakdown"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=breakdown --cov-report=term-missing"

[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "strict"
venvPath = "."
venv = ".venv"
```

- [ ] **Step 6: Create core/src/breakdown/__init__.py**

```python
from pathlib import Path

__version__ = (Path(__file__).parent.parent.parent.parent / "VERSION").read_text().strip()
```

- [ ] **Step 7: Create core/src/breakdown/py.typed**

Empty file. Signals PEP 561 compliance.

```
(empty file)
```

- [ ] **Step 8: Create core/tests/conftest.py**

```python
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES_DIR
```

- [ ] **Step 9: Install deps and verify**

```bash
cd core
uv sync --all-extras --dev
uv run python -c "import breakdown; print(breakdown.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 10: Verify ruff and basedpyright pass on empty scaffold**

```bash
cd core
uv run ruff check src/
uv run basedpyright src/
```

Expected: no errors

- [ ] **Step 11: Commit**

```bash
git init
git add VERSION .gitignore .env.example ruff.toml core/
git commit -m "chore: initial project scaffold"
```

---

### Task 2: Configuration System

**Files:**
- Create: `core/src/breakdown/config.py`
- Create: `core/tests/unit/test_config.py`

**Interfaces:**
- Produces: `from breakdown.config import Settings, get_settings`
- `get_settings() -> Settings` -- returns cached singleton loaded from env + .breakdown/config.yaml

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/test_config.py
import os
from unittest.mock import patch

import pytest

from breakdown.config import Settings


def test_settings_loads_from_env() -> None:
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o"}):
        s = Settings()
        assert s.llm_model == "gpt-4o"
        assert s.openai_api_key == "sk-test"


def test_settings_default_tts_provider() -> None:
    s = Settings()
    assert s.tts_provider == "openai"


def test_settings_default_index_backend() -> None:
    s = Settings()
    assert s.index_backend == "lancedb"


def test_settings_context_window_lines_default() -> None:
    s = Settings()
    assert s.context_window_lines == 50


def test_settings_history_budget_pct_default() -> None:
    s = Settings()
    assert s.history_budget_pct == 0.8
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd core
uv run pytest tests/unit/test_config.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Implement config.py**

```python
# core/src/breakdown/config.py
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LiveKit
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_context_window: int = 128_000
    openai_api_key: str = ""

    # TTS
    tts_provider: Literal["openai", "elevenlabs"] = "openai"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "Rachel"

    # STT
    stt_provider: Literal["openai", "deepgram"] = "openai"
    deepgram_api_key: str = ""

    # Embeddings
    embedding_provider: Literal["openai", "local"] = "openai"

    # Index
    index_backend: Literal["lancedb", "chromadb"] = "lancedb"
    context_window_lines: int = Field(default=50, ge=10, le=500)
    index_debounce_seconds: float = 3.0
    index_respect_gitignore: bool = True

    # Session
    history_budget_pct: float = Field(default=0.8, gt=0.0, le=1.0)

    # Token server
    token_server_port_start: int = 7890


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd core
uv run pytest tests/unit/test_config.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/config.py core/tests/unit/test_config.py
git commit -m "feat: add pydantic-settings configuration system"
```

---

### Task 3: Ignore Filter

**Files:**
- Create: `core/src/breakdown/indexer/__init__.py`
- Create: `core/src/breakdown/indexer/ignore.py`
- Create: `core/tests/unit/indexer/test_ignore.py`
- Create: `core/tests/fixtures/sample_project/.gitignore`

**Interfaces:**
- Produces: `IgnoreFilter(root: Path) -> IgnoreFilter`; `filter.is_ignored(path: Path) -> bool`

- [ ] **Step 1: Create fixture project**

```
core/tests/fixtures/sample_project/
  .gitignore          (contains: node_modules/, *.log)
  src/
    main.py           (empty)
  node_modules/
    lodash/
      index.js        (empty)
  debug.log           (empty)
```

Create each file:

```bash
mkdir -p core/tests/fixtures/sample_project/src
mkdir -p core/tests/fixtures/sample_project/node_modules/lodash
echo "node_modules/\n*.log" > core/tests/fixtures/sample_project/.gitignore
touch core/tests/fixtures/sample_project/src/main.py
touch core/tests/fixtures/sample_project/node_modules/lodash/index.js
touch core/tests/fixtures/sample_project/debug.log
```

- [ ] **Step 2: Write failing tests**

```python
# core/tests/unit/indexer/test_ignore.py
from pathlib import Path
import pytest
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
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/indexer/test_ignore.py -v
```

Expected: ImportError

- [ ] **Step 4: Create core/src/breakdown/indexer/__init__.py**

```python
```

(empty)

- [ ] **Step 5: Implement ignore.py**

```python
# core/src/breakdown/indexer/ignore.py
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
            for i, part in enumerate(parts):
                if fnmatch.fnmatch(part, p):
                    return True
            if fnmatch.fnmatch(str(rel), p):
                return True
            if is_dir_pattern and any(fnmatch.fnmatch(part, p) for part in parts):
                return True
        return False
```

- [ ] **Step 6: Run tests**

```bash
cd core
uv run pytest tests/unit/indexer/test_ignore.py -v
```

Expected: all 5 PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/breakdown/indexer/ core/tests/unit/indexer/ core/tests/fixtures/
git commit -m "feat: add ignore filter with gitignore and default patterns"
```

---

### Task 4: Language Registry and Parser

**Files:**
- Create: `core/src/breakdown/indexer/registry.py`
- Create: `core/src/breakdown/indexer/parser.py`
- Create: `core/tests/unit/indexer/test_parser.py`
- Create: `core/tests/fixtures/sample_project/src/hello.py` (simple Python)
- Create: `core/tests/fixtures/sample_project/src/unknown.xyz` (unsupported)

**Interfaces:**
- Produces:
  - `LanguageRegistry` singleton; `registry.get_language(path: Path) -> Language | None`
  - `parse_file(path: Path, registry: LanguageRegistry) -> tuple[Tree | None, bytes]`

- [ ] **Step 1: Add fixture files**

```python
# core/tests/fixtures/sample_project/src/hello.py
def greet(name: str) -> str:
    return f"Hello, {name}"


class Greeter:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def greet(self, name: str) -> str:
        return f"{self.prefix}, {name}"
```

```
# core/tests/fixtures/sample_project/src/unknown.xyz
this is not a known language
```

- [ ] **Step 2: Write failing tests**

```python
# core/tests/unit/indexer/test_parser.py
from pathlib import Path
import pytest
from breakdown.indexer.registry import LanguageRegistry
from breakdown.indexer.parser import parse_file


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
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/indexer/test_parser.py -v
```

Expected: ImportError

- [ ] **Step 4: Implement registry.py**

```python
# core/src/breakdown/indexer/registry.py
from __future__ import annotations

from pathlib import Path

from loguru import logger

try:
    from tree_sitter_languages import get_language  # type: ignore[import-untyped]
    _HAS_TREE_SITTER_LANGUAGES = True
except ImportError:
    _HAS_TREE_SITTER_LANGUAGES = False
    logger.warning("tree-sitter-languages not installed; parsing disabled")

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


class LanguageRegistry:
    def get_language(self, path: Path) -> object | None:
        if not _HAS_TREE_SITTER_LANGUAGES:
            return None
        lang_name = _EXT_TO_LANGUAGE.get(path.suffix.lower())
        if lang_name is None:
            return None
        try:
            return get_language(lang_name)
        except Exception:
            logger.debug("No grammar for {}", path.suffix)
            return None
```

- [ ] **Step 5: Implement parser.py**

```python
# core/src/breakdown/indexer/parser.py
from __future__ import annotations

from pathlib import Path

from loguru import logger

from breakdown.indexer.registry import LanguageRegistry

try:
    from tree_sitter import Parser  # type: ignore[import-untyped]
    _HAS_TREE_SITTER = True
except ImportError:
    _HAS_TREE_SITTER = False


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
    if language is None or not _HAS_TREE_SITTER:
        return None, source

    try:
        parser = Parser()
        parser.set_language(language)
        tree = parser.parse(source)
        return tree, source
    except Exception as e:
        logger.warning("Parse failed for {}: {}; using plain-text fallback", path, e)
        return None, source
```

- [ ] **Step 6: Run tests**

```bash
cd core
uv run pytest tests/unit/indexer/test_parser.py -v
```

Expected: all 4 PASS

- [ ] **Step 7: Commit**

```bash
git add core/src/breakdown/indexer/registry.py core/src/breakdown/indexer/parser.py core/tests/unit/indexer/test_parser.py core/tests/fixtures/sample_project/src/
git commit -m "feat: add language registry and tree-sitter parser with fallback"
```

---

### Task 5: AST-Aware Chunker

**Files:**
- Create: `core/src/breakdown/indexer/chunker.py`
- Create: `core/tests/unit/indexer/test_chunker.py`

**Interfaces:**
- Produces:
  - `Chunk` dataclass with fields: `file: str`, `start_line: int`, `end_line: int`, `text: str`, `type: str`, `name: str`
  - `chunk_tree(tree: object | None, source: bytes, file: str, window_lines: int) -> list[Chunk]`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/indexer/test_chunker.py
from pathlib import Path
import pytest
from breakdown.indexer.chunker import Chunk, chunk_tree
from breakdown.indexer.registry import LanguageRegistry
from breakdown.indexer.parser import parse_file


def _parse(fixtures_dir: Path, filename: str) -> tuple[object | None, bytes]:
    registry = LanguageRegistry()
    return parse_file(fixtures_dir / "sample_project" / "src" / filename, registry)


def test_chunks_python_functions(fixtures_dir: Path) -> None:
    tree, source = _parse(fixtures_dir, "hello.py")
    chunks = chunk_tree(tree, source, "src/hello.py", window_lines=50)
    names = [c.name for c in chunks]
    assert "greet" in names


def test_chunks_python_class(fixtures_dir: Path) -> None:
    tree, source = _parse(fixtures_dir, "hello.py")
    chunks = chunk_tree(tree, source, "src/hello.py", window_lines=50)
    types = [c.type for c in chunks]
    assert "class" in types


def test_chunk_has_correct_file(fixtures_dir: Path) -> None:
    tree, source = _parse(fixtures_dir, "hello.py")
    chunks = chunk_tree(tree, source, "src/hello.py", window_lines=50)
    assert all(c.file == "src/hello.py" for c in chunks)


def test_fallback_plain_text_chunks_when_no_tree(fixtures_dir: Path) -> None:
    tree, source = _parse(fixtures_dir, "unknown.xyz")
    assert tree is None
    chunks = chunk_tree(tree, source, "src/unknown.xyz", window_lines=50)
    assert len(chunks) >= 1
    assert chunks[0].type == "text"


def test_chunk_line_numbers_are_positive(fixtures_dir: Path) -> None:
    tree, source = _parse(fixtures_dir, "hello.py")
    chunks = chunk_tree(tree, source, "src/hello.py", window_lines=50)
    assert all(c.start_line >= 1 for c in chunks)
    assert all(c.end_line >= c.start_line for c in chunks)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/indexer/test_chunker.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement chunker.py**

```python
# core/src/breakdown/indexer/chunker.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    file: str
    start_line: int
    end_line: int
    text: str
    type: str   # "function" | "class" | "import" | "variable" | "text"
    name: str


_AST_CHUNK_TYPES = {
    "function_definition": "function",
    "async_function_def": "function",
    "class_definition": "class",
    "import_statement": "import",
    "import_from_statement": "import",
    "expression_statement": "variable",
}


def chunk_tree(
    tree: object | None,
    source: bytes,
    file: str,
    window_lines: int,
) -> list[Chunk]:
    if tree is None:
        return _plain_text_chunks(source, file, window_lines)
    return _ast_chunks(tree, source, file)


def _ast_chunks(tree: object, source: bytes, file: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    lines = source.decode("utf-8", errors="replace").splitlines()

    def walk(node: object) -> None:
        node_type: str = getattr(node, "type", "")
        chunk_type = _AST_CHUNK_TYPES.get(node_type)
        if chunk_type:
            start: int = getattr(node, "start_point", (0,))[0] + 1
            end: int = getattr(node, "end_point", (0,))[0] + 1
            text = "\n".join(lines[start - 1 : end])
            name = _extract_name(node, lines)
            chunks.append(Chunk(file=file, start_line=start, end_line=end, text=text, type=chunk_type, name=name))
        else:
            for child in getattr(node, "children", []):
                walk(child)

    walk(getattr(tree, "root_node", tree))
    return chunks


def _extract_name(node: object, lines: list[str]) -> str:
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == "identifier":
            start = getattr(child, "start_point", (0, 0))
            line = lines[start[0]] if start[0] < len(lines) else ""
            return line[start[1] : getattr(child, "end_point", (0, len(line)))[1]]
    return ""


def _plain_text_chunks(source: bytes, file: str, window_lines: int) -> list[Chunk]:
    lines = source.decode("utf-8", errors="replace").splitlines()
    chunks: list[Chunk] = []
    for i in range(0, len(lines), window_lines):
        block = lines[i : i + window_lines]
        chunks.append(
            Chunk(
                file=file,
                start_line=i + 1,
                end_line=i + len(block),
                text="\n".join(block),
                type="text",
                name="",
            )
        )
    return chunks if chunks else [Chunk(file=file, start_line=1, end_line=1, text="", type="text", name="")]
```

- [ ] **Step 4: Run tests**

```bash
cd core
uv run pytest tests/unit/indexer/test_chunker.py -v
```

Expected: all 5 PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/indexer/chunker.py core/tests/unit/indexer/test_chunker.py
git commit -m "feat: add AST-aware chunker with plain-text fallback"
```

---

### Task 6: Manifest (Incremental Index State)

**Files:**
- Create: `core/src/breakdown/indexer/manifest.py`
- Create: `core/tests/unit/indexer/test_manifest.py`

**Interfaces:**
- Produces:
  - `Manifest(path: Path)` -- loads/saves from `path` (JSON)
  - `manifest.is_stale(file: Path) -> bool`
  - `manifest.update(file: Path, chunk_ids: list[str]) -> None`
  - `manifest.remove(file: Path) -> None`
  - `manifest.save() -> None`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/indexer/test_manifest.py
import hashlib
import json
import time
from pathlib import Path

import pytest

from breakdown.indexer.manifest import Manifest


def test_new_file_is_stale(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    assert manifest.is_stale(f)


def test_unchanged_file_is_not_stale(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    manifest.update(f, ["chunk-1"])
    manifest.save()
    manifest2 = Manifest(tmp_path / "manifest.json")
    assert not manifest2.is_stale(f)


def test_changed_file_is_stale(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    manifest.update(f, ["chunk-1"])
    manifest.save()
    f.write_text("hello world")  # changed
    manifest2 = Manifest(tmp_path / "manifest.json")
    assert manifest2.is_stale(f)


def test_remove_marks_file_unknown(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    manifest.update(f, ["chunk-1"])
    manifest.remove(f)
    assert manifest.is_stale(f)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/indexer/test_manifest.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement manifest.py**

```python
# core/src/breakdown/indexer/manifest.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
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
```

- [ ] **Step 4: Run tests**

```bash
cd core
uv run pytest tests/unit/indexer/test_manifest.py -v
```

Expected: all 4 PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/indexer/manifest.py core/tests/unit/indexer/test_manifest.py
git commit -m "feat: add incremental index manifest with atomic save"
```

---

### Task 7: Vector Store

**Files:**
- Create: `core/src/breakdown/indexer/store.py`
- Create: `core/tests/unit/indexer/test_store.py`

**Interfaces:**
- Produces:
  - `VectorStore` protocol with methods: `add(chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]`, `search(embedding: list[float], k: int) -> list[Chunk]`, `delete(chunk_ids: list[str]) -> None`, `close() -> None`
  - `create_store(backend: str, db_path: Path) -> VectorStore`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/indexer/test_store.py
from pathlib import Path
import pytest
from breakdown.indexer.chunker import Chunk
from breakdown.indexer.store import create_store


def _dummy_embedding(dim: int = 4) -> list[float]:
    return [0.1] * dim


def test_add_and_search_returns_chunk(tmp_path: Path) -> None:
    store = create_store("lancedb", tmp_path / "db")
    chunk = Chunk(file="src/foo.py", start_line=1, end_line=5, text="def foo(): pass", type="function", name="foo")
    ids = store.add([chunk], [_dummy_embedding()])
    assert len(ids) == 1
    results = store.search(_dummy_embedding(), k=1)
    assert len(results) == 1
    assert results[0].name == "foo"
    store.close()


def test_delete_removes_chunk(tmp_path: Path) -> None:
    store = create_store("lancedb", tmp_path / "db")
    chunk = Chunk(file="src/foo.py", start_line=1, end_line=5, text="def foo(): pass", type="function", name="foo")
    ids = store.add([chunk], [_dummy_embedding()])
    store.delete(ids)
    results = store.search(_dummy_embedding(), k=10)
    assert all(r.name != "foo" for r in results)
    store.close()


def test_empty_store_search_returns_empty(tmp_path: Path) -> None:
    store = create_store("lancedb", tmp_path / "db")
    results = store.search(_dummy_embedding(), k=5)
    assert results == []
    store.close()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/indexer/test_store.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement store.py**

```python
# core/src/breakdown/indexer/store.py
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Protocol, runtime_checkable

from loguru import logger

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
        import pyarrow as pa  # type: ignore[import-untyped]

        db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(db_path))
        self._schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("file", pa.string()),
            pa.field("start_line", pa.int32()),
            pa.field("end_line", pa.int32()),
            pa.field("text", pa.string()),
            pa.field("type", pa.string()),
            pa.field("name", pa.string()),
            pa.field("vector", pa.list_(pa.float32())),
        ])
        if self._TABLE not in self._db.table_names():
            self._db.create_table(self._TABLE, schema=self._schema)
        self._table = self._db.open_table(self._TABLE)

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
        import pyarrow as pa  # type: ignore[import-untyped]
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
        self._table.add(rows)
        return ids

    def search(self, embedding: list[float], k: int) -> list[Chunk]:
        try:
            results = self._table.search(embedding).limit(k).to_list()
        except Exception:
            return []
        return [
            Chunk(
                file=r["file"],
                start_line=r["start_line"],
                end_line=r["end_line"],
                text=r["text"],
                type=r["type"],
                name=r["name"],
            )
            for r in results
        ]

    def delete(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
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
        self._col.add(
            ids=ids,
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[
                {"file": c.file, "start_line": c.start_line, "end_line": c.end_line, "type": c.type, "name": c.name}
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
```

- [ ] **Step 4: Run tests**

```bash
cd core
uv run pytest tests/unit/indexer/test_store.py -v
```

Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/indexer/store.py core/tests/unit/indexer/test_store.py
git commit -m "feat: add LanceDB and ChromaDB vector store implementations"
```

---

### Task 8: Embedder

**Files:**
- Create: `core/src/breakdown/indexer/embedder.py`
- Create: `core/tests/unit/indexer/test_embedder.py`

**Interfaces:**
- Produces:
  - `Embedder` protocol: `embed(texts: list[str]) -> list[list[float]]`
  - `create_embedder(provider: str, settings: Settings) -> Embedder`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/indexer/test_embedder.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from breakdown.config import Settings
from breakdown.indexer.embedder import create_embedder


def test_create_embedder_openai_returns_embedder() -> None:
    settings = Settings(openai_api_key="sk-test", embedding_provider="openai")
    embedder = create_embedder("openai", settings)
    assert hasattr(embedder, "embed")


def test_create_embedder_unknown_raises() -> None:
    settings = Settings()
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        create_embedder("banana", settings)


def test_openai_embedder_calls_api(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    monkeypatch.setattr(
        "openai.OpenAI.embeddings",
        property(lambda self: MagicMock(create=MagicMock(return_value=fake_response))),
    )

    from breakdown.indexer.embedder import _OpenAIEmbedder
    embedder = _OpenAIEmbedder(api_key="sk-test", model="text-embedding-3-small")

    with patch.object(embedder._client.embeddings, "create", return_value=fake_response):
        result = embedder.embed(["hello"])

    assert result == [[0.1, 0.2, 0.3]]
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/indexer/test_embedder.py::test_create_embedder_openai_returns_embedder tests/unit/indexer/test_embedder.py::test_create_embedder_unknown_raises -v
```

Expected: ImportError

- [ ] **Step 3: Implement embedder.py**

```python
# core/src/breakdown/indexer/embedder.py
from __future__ import annotations

from typing import Protocol, runtime_checkable

from loguru import logger

from breakdown.config import Settings


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def create_embedder(provider: str, settings: Settings) -> Embedder:
    if provider == "openai":
        return _OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small",
        )
    if provider == "local":
        return _LocalEmbedder()
    raise ValueError(
        f"Unknown embedding provider: {provider!r}. Choose 'openai' or 'local'."
    )


class _OpenAIEmbedder:
    def __init__(self, api_key: str, model: str) -> None:
        import openai  # type: ignore[import-untyped]
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # batch in groups of 100 to stay within API limits
        results: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            response = self._client.embeddings.create(input=batch, model=self._model)
            results.extend(item.embedding for item in response.data)
        return results


class _LocalEmbedder:
    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: uv sync --extra local-embeddings"
            ) from e
        logger.info("Loading local embedding model BAAI/bge-code-v1 (first run downloads ~117MB)")
        self._model = SentenceTransformer("BAAI/bge-code-v1")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, show_progress_bar=False)
        return [v.tolist() for v in vectors]
```

- [ ] **Step 4: Run tests**

```bash
cd core
uv run pytest tests/unit/indexer/test_embedder.py::test_create_embedder_openai_returns_embedder tests/unit/indexer/test_embedder.py::test_create_embedder_unknown_raises -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/indexer/embedder.py core/tests/unit/indexer/test_embedder.py
git commit -m "feat: add OpenAI and local sentence-transformers embedder"
```

---

### Task 9: Session

**Files:**
- Create: `core/src/breakdown/session.py`
- Create: `core/tests/unit/test_session.py`

**Interfaces:**
- Produces:
  - `Session` dataclass: `current_file: str`, `current_line: int`, `history: list[dict[str,str]]`, `workspace_root: Path`
  - `session.add_turn(role: str, content: str) -> None` -- appends and trims if over token budget
  - `session.save(path: Path) -> None` -- atomic JSON write
  - `Session.load(path: Path) -> Session | None` -- returns None if file missing or corrupt
  - `session.token_count() -> int`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/test_session.py
from pathlib import Path
import pytest
from breakdown.session import Session


def test_session_initial_state() -> None:
    s = Session(workspace_root=Path("/tmp/proj"))
    assert s.current_file == ""
    assert s.current_line == 0
    assert s.history == []


def test_add_turn_appends(tmp_path: Path) -> None:
    s = Session(workspace_root=tmp_path)
    s.add_turn("user", "what is this?")
    assert len(s.history) == 1
    assert s.history[0] == {"role": "user", "content": "what is this?"}


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    s = Session(workspace_root=tmp_path)
    s.current_file = "src/foo.py"
    s.current_line = 42
    s.add_turn("user", "explain this")
    s.add_turn("assistant", "this is a function")
    path = tmp_path / "session.json"
    s.save(path)
    loaded = Session.load(path)
    assert loaded is not None
    assert loaded.current_file == "src/foo.py"
    assert loaded.current_line == 42
    assert len(loaded.history) == 2


def test_load_returns_none_for_missing_file(tmp_path: Path) -> None:
    result = Session.load(tmp_path / "nonexistent.json")
    assert result is None


def test_load_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("not json {{{")
    result = Session.load(path)
    assert result is None


def test_token_count_is_positive_after_turns(tmp_path: Path) -> None:
    s = Session(workspace_root=tmp_path)
    s.add_turn("user", "hello world")
    assert s.token_count() > 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/test_session.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement session.py**

```python
# core/src/breakdown/session.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


def _count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # character-based approximation: ~4 chars per token
        return len(text) // 4


@dataclass
class Session:
    workspace_root: Path
    current_file: str = ""
    current_line: int = 0
    history: list[dict[str, str]] = field(default_factory=list)

    def add_turn(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def token_count(self) -> int:
        return sum(_count_tokens(t["content"]) for t in self.history)

    def trim_to_budget(self, max_tokens: int) -> None:
        while self.token_count() > max_tokens and len(self.history) > 2:
            # remove oldest pair (user + assistant)
            self.history = self.history[2:]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        data = {
            "current_file": self.current_file,
            "current_line": self.current_line,
            "workspace_root": str(self.workspace_root),
            "history": self.history,
        }
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> Session | None:
        if not path.exists():
            return None
        try:
            data: dict[str, object] = json.loads(path.read_text())
            return cls(
                workspace_root=Path(str(data["workspace_root"])),
                current_file=str(data.get("current_file", "")),
                current_line=int(data.get("current_line", 0)),  # type: ignore[arg-type]
                history=list(data.get("history", [])),  # type: ignore[arg-type]
            )
        except Exception as e:
            logger.warning("Session file corrupt, ignoring: {}", e)
            return None
```

- [ ] **Step 4: Run tests**

```bash
cd core
uv run pytest tests/unit/test_session.py -v
```

Expected: all 6 PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/session.py core/tests/unit/test_session.py
git commit -m "feat: add session dataclass with atomic persistence and token budget"
```

---

### Task 10: Token Server

**Files:**
- Create: `core/src/breakdown/token_server.py`
- Create: `core/tests/unit/test_token_server.py`

**Interfaces:**
- Produces:
  - `find_free_port(start: int) -> int`
  - `write_runtime_info(port: int, livekit_url: str, breakdown_dir: Path) -> None`
  - `TokenServer(settings: Settings, breakdown_dir: Path)` with `.start() -> None` (blocks) and `.start_background() -> threading.Thread`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/test_token_server.py
import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest

from breakdown.config import Settings
from breakdown.token_server import TokenServer, find_free_port, write_runtime_info


def test_find_free_port_returns_usable_port() -> None:
    port = find_free_port(7890)
    assert 7890 <= port <= 65535
    # verify it is actually free
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def test_write_runtime_info(tmp_path: Path) -> None:
    write_runtime_info(7890, "ws://localhost:7880", tmp_path)
    data = json.loads((tmp_path / "runtime.json").read_text())
    assert data["port"] == 7890
    assert data["livekit_url"] == "ws://localhost:7880"


def test_token_server_responds_to_token_request(tmp_path: Path) -> None:
    settings = Settings(
        livekit_api_key="devkey",
        livekit_api_secret="devsecret123456789012345678901234567890",
        livekit_url="ws://localhost:7880",
    )
    server = TokenServer(settings=settings, breakdown_dir=tmp_path)
    port = find_free_port(7891)
    thread = threading.Thread(target=server.start, kwargs={"port": port}, daemon=True)
    thread.start()
    time.sleep(0.1)  # let the server bind

    response = httpx.get(f"http://127.0.0.1:{port}/token?room=test-room", timeout=2)
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "url" in data
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/test_token_server.py::test_find_free_port_returns_usable_port tests/unit/test_token_server.py::test_write_runtime_info -v
```

Expected: ImportError

- [ ] **Step 3: Implement token_server.py**

```python
# core/src/breakdown/token_server.py
from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from loguru import logger

from breakdown.config import Settings


def find_free_port(start: int) -> int:
    port = start
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            port += 1
    raise RuntimeError("No free port found starting from {start}")


def write_runtime_info(port: int, livekit_url: str, breakdown_dir: Path) -> None:
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    tmp = breakdown_dir / "runtime.json.tmp"
    tmp.write_text(json.dumps({"port": port, "livekit_url": livekit_url}))
    tmp.replace(breakdown_dir / "runtime.json")


def _make_token(api_key: str, api_secret: str, room: str) -> str:
    from livekit.api import AccessToken, VideoGrants  # type: ignore[import-untyped]
    token = (
        AccessToken(api_key, api_secret)
        .with_grants(VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return str(token)


class TokenServer:
    def __init__(self, settings: Settings, breakdown_dir: Path) -> None:
        self._settings = settings
        self._breakdown_dir = breakdown_dir

    def start(self, port: int | None = None) -> None:
        if port is None:
            port = find_free_port(self._settings.token_server_port_start)
        write_runtime_info(port, self._settings.livekit_url, self._breakdown_dir)

        settings = self._settings

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != "/token":
                    self.send_response(404)
                    self.end_headers()
                    return
                params = parse_qs(parsed.query)
                room = params.get("room", ["default"])[0]
                try:
                    token = _make_token(
                        settings.livekit_api_key,
                        settings.livekit_api_secret,
                        room,
                    )
                    body = json.dumps({"token": token, "url": settings.livekit_url}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:
                    logger.error("Token generation failed: {}", e)
                    self.send_response(500)
                    self.end_headers()

            def log_message(self, fmt: str, *args: object) -> None:
                logger.debug("token_server: " + fmt, *args)

        server = HTTPServer(("127.0.0.1", port), _Handler)
        logger.info("Token server listening on 127.0.0.1:{}", port)
        server.serve_forever()

    def start_background(self, port: int | None = None) -> threading.Thread:
        t = threading.Thread(target=self.start, kwargs={"port": port}, daemon=True)
        t.start()
        return t
```

- [ ] **Step 4: Run tests**

```bash
cd core
uv run pytest tests/unit/test_token_server.py -v
```

Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/token_server.py core/tests/unit/test_token_server.py
git commit -m "feat: add localhost-only token server with dynamic port discovery"
```

---

### Task 11: Providers

**Files:**
- Create: `core/src/breakdown/providers/__init__.py`
- Create: `core/src/breakdown/providers/llm.py`
- Create: `core/src/breakdown/providers/tts.py`
- Create: `core/src/breakdown/providers/stt.py`
- Create: `core/tests/unit/providers/test_llm.py`
- Create: `core/tests/unit/providers/test_tts.py`

**Interfaces:**
- Produces:
  - `create_llm(settings: Settings) -> livekit_agents.llm.LLM`
  - `create_tts(settings: Settings) -> livekit_agents.tts.TTS`
  - `create_stt(settings: Settings) -> livekit_agents.stt.STT`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/providers/test_llm.py
import pytest
from unittest.mock import patch
from breakdown.config import Settings
from breakdown.providers.llm import create_llm


def test_create_llm_returns_object_with_chat() -> None:
    settings = Settings(openai_api_key="sk-test", llm_model="gpt-4o")
    llm = create_llm(settings)
    assert hasattr(llm, "chat")


def test_create_llm_unsupported_model_does_not_raise() -> None:
    # LiteLLM accepts any model string; invalid ones fail at call time, not creation
    settings = Settings(openai_api_key="sk-test", llm_model="gpt-99-nonexistent")
    llm = create_llm(settings)
    assert llm is not None
```

```python
# core/tests/unit/providers/test_tts.py
import pytest
from breakdown.config import Settings
from breakdown.providers.tts import create_tts


def test_create_tts_openai_returns_tts() -> None:
    settings = Settings(openai_api_key="sk-test", tts_provider="openai")
    tts = create_tts(settings)
    assert hasattr(tts, "synthesize")


def test_create_tts_elevenlabs_requires_key() -> None:
    settings = Settings(tts_provider="elevenlabs", elevenlabs_api_key="")
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        create_tts(settings)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/providers/ -v
```

Expected: ImportError

- [ ] **Step 3: Implement providers/__init__.py**

```python
```

(empty)

- [ ] **Step 4: Implement providers/llm.py**

```python
# core/src/breakdown/providers/llm.py
from __future__ import annotations

from breakdown.config import Settings


def create_llm(settings: Settings) -> object:
    from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
    import litellm  # type: ignore[import-untyped]

    # Use LiveKit's OpenAI plugin as the base; route through LiteLLM for
    # non-OpenAI models by setting the base_url and api_key appropriately.
    # LiteLLM proxy is not used -- we call litellm.completion directly in the
    # agent when needed for non-streaming cases.
    return lk_openai.LLM(
        model=settings.llm_model,
        api_key=settings.openai_api_key or "placeholder",
    )
```

- [ ] **Step 5: Implement providers/tts.py**

```python
# core/src/breakdown/providers/tts.py
from __future__ import annotations

from breakdown.config import Settings


def create_tts(settings: Settings) -> object:
    if settings.tts_provider == "openai":
        from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
        return lk_openai.TTS(
            api_key=settings.openai_api_key or "placeholder",
            voice="alloy",
        )

    if settings.tts_provider == "elevenlabs":
        if not settings.elevenlabs_api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is required when TTS_PROVIDER=elevenlabs"
            )
        from livekit.plugins import elevenlabs  # type: ignore[import-untyped]
        return elevenlabs.TTS(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
        )

    raise ValueError(
        f"Unknown TTS provider: {settings.tts_provider!r}. Choose 'openai' or 'elevenlabs'."
    )
```

- [ ] **Step 6: Implement providers/stt.py**

```python
# core/src/breakdown/providers/stt.py
from __future__ import annotations

from breakdown.config import Settings


def create_stt(settings: Settings) -> object:
    if settings.stt_provider == "openai":
        from livekit.plugins import openai as lk_openai  # type: ignore[import-untyped]
        return lk_openai.STT(
            api_key=settings.openai_api_key or "placeholder",
        )

    if settings.stt_provider == "deepgram":
        if not settings.deepgram_api_key:
            raise ValueError(
                "DEEPGRAM_API_KEY is required when STT_PROVIDER=deepgram"
            )
        from livekit.plugins import deepgram  # type: ignore[import-untyped]
        return deepgram.STT(api_key=settings.deepgram_api_key)

    raise ValueError(
        f"Unknown STT provider: {settings.stt_provider!r}. Choose 'openai' or 'deepgram'."
    )
```

- [ ] **Step 7: Run tests**

```bash
cd core
uv run pytest tests/unit/providers/ -v
```

Expected: all 4 PASS

- [ ] **Step 8: Commit**

```bash
git add core/src/breakdown/providers/ core/tests/unit/providers/
git commit -m "feat: add LLM, TTS, STT provider factories using LiveKit plugin system"
```

---

### Task 12: LiveKit Agent

**Files:**
- Create: `core/src/breakdown/agent.py`

**Interfaces:**
- Consumes: `Session`, `create_llm`, `create_tts`, `create_stt`, `VectorStore`, `Settings`
- Produces: `create_agent(settings: Settings, store: VectorStore, breakdown_dir: Path) -> entrypoint function` compatible with `livekit.agents.WorkerOptions`

Note: The agent is not unit-tested directly because it requires a live LiveKit room. It is covered by the integration test in Task 13. Keep agent.py under 150 lines.

- [ ] **Step 1: Implement agent.py**

```python
# core/src/breakdown/agent.py
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from loguru import logger
from livekit import agents  # type: ignore[import-untyped]
from livekit.agents import AgentSession, Agent, RoomInputOptions  # type: ignore[import-untyped]

from breakdown.config import Settings
from breakdown.indexer.store import VectorStore
from breakdown.providers.llm import create_llm
from breakdown.providers.tts import create_tts
from breakdown.providers.stt import create_stt
from breakdown.session import Session


def _room_name(workspace_root: Path) -> str:
    digest = hashlib.sha256(str(workspace_root.resolve()).encode()).hexdigest()[:12]
    return f"breakdown-{digest}"


def _build_system_prompt(session: Session, context_chunks: list[str], window: str) -> str:
    ctx = "\n\n---\n\n".join(context_chunks) if context_chunks else "No additional context."
    return (
        "You are Breakdown, a voice-driven code explainer. "
        "Explain code clearly and concisely as if speaking to the developer who wrote it. "
        "Be direct. Do not say 'certainly' or 'of course'. "
        "When asked about a specific line, explain what it does and why it matters in context.\n\n"
        f"Codebase context:\n{ctx}\n\n"
        f"Current code window:\n{window}"
    )


async def _index_context(
    store: VectorStore,
    file: str,
    line: int,
    workspace_root: Path,
    settings: Settings,
) -> tuple[list[str], str]:
    abs_path = workspace_root / file
    try:
        lines = abs_path.read_text(errors="replace").splitlines()
    except OSError:
        return [], ""

    half = settings.context_window_lines // 2
    start = max(0, line - 1 - half)
    end = min(len(lines), line - 1 + half)
    window = "\n".join(
        f"{i + 1}: {l}" for i, l in enumerate(lines[start:end], start=start)
    )

    try:
        from breakdown.indexer.embedder import create_embedder
        embedder = create_embedder(settings.embedding_provider, settings)
        query_emb = embedder.embed([lines[line - 1] if line <= len(lines) else ""])[0]
        chunks = store.search(query_emb, k=5)
        context = [c.text for c in chunks]
    except Exception as e:
        logger.warning("Context retrieval failed: {}", e)
        context = []

    return context, window


def create_agent(
    settings: Settings,
    store: VectorStore,
    breakdown_dir: Path,
) -> Any:
    async def entrypoint(ctx: agents.JobContext) -> None:
        workspace_root = breakdown_dir.parent
        session = Session.load(breakdown_dir / "session.json") or Session(
            workspace_root=workspace_root
        )
        session_path = breakdown_dir / "session.json"

        llm = create_llm(settings)
        tts = create_tts(settings)
        stt = create_stt(settings)

        agent_session = AgentSession(llm=llm, tts=tts, stt=stt)

        async def on_data(packet: Any) -> None:
            import json as _json
            try:
                msg = _json.loads(packet.data)
            except Exception:
                return

            msg_type: str = msg.get("type", "")

            if msg_type == "explain":
                session.current_file = msg.get("file", "")
                session.current_line = int(msg.get("line", 1))
                context, window = await _index_context(
                    store,
                    session.current_file,
                    session.current_line,
                    workspace_root,
                    settings,
                )
                system = _build_system_prompt(session, context, window)
                target_line = window.split("\n")[settings.context_window_lines // 2] if window else ""
                await agent_session.say(
                    f"Line {session.current_line}: {target_line}",
                    allow_interruptions=True,
                )
                session.add_turn("user", f"Explain line {session.current_line}: {target_line}")
                session.save(session_path)

            elif msg_type == "next":
                session.current_line += 1
                await ctx.room.local_participant.publish_data(
                    _json.dumps({"v": 1, "type": "position", "file": session.current_file, "line": session.current_line}).encode()
                )
                session.save(session_path)

            elif msg_type == "prev":
                session.current_line = max(1, session.current_line - 1)
                session.save(session_path)

            elif msg_type == "stop":
                await agent_session.aclose()

        ctx.room.on("data_received", on_data)
        await agent_session.start(
            ctx.room,
            agent=Agent(instructions="You are a helpful code explainer."),
            room_input_options=RoomInputOptions(),
        )

    return entrypoint
```

- [ ] **Step 2: Verify line count**

```bash
wc -l core/src/breakdown/agent.py
```

Expected: under 150 lines

- [ ] **Step 3: Commit**

```bash
git add core/src/breakdown/agent.py
git commit -m "feat: add LiveKit agent as thin coordinator under 150 lines"
```

---

### Task 13: CLI

**Files:**
- Create: `core/src/breakdown/cli.py`
- Create: `core/tests/unit/test_cli.py`

**Interfaces:**
- Produces: `breakdown start`, `breakdown index`, `breakdown version` commands via `typer`

- [ ] **Step 1: Write failing tests**

```python
# core/tests/unit/test_cli.py
from typer.testing import CliRunner
from breakdown.cli import app
from breakdown import __version__

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_index_requires_directory(tmp_path: object) -> None:
    result = runner.invoke(app, ["index", "--help"])
    assert result.exit_code == 0
    assert "index" in result.output.lower() or "path" in result.output.lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd core
uv run pytest tests/unit/test_cli.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement cli.py**

```python
# core/src/breakdown/cli.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from breakdown import __version__
from breakdown.config import get_settings

app = typer.Typer(help="Breakdown -- voice-driven AI code explainer", add_completion=False)
console = Console()


@app.command()
def version() -> None:
    """Print the current version."""
    console.print(__version__)


@app.command()
def index(
    path: Path = typer.Argument(Path("."), help="Workspace root to index"),
) -> None:
    """Index a codebase for context-aware explanations."""
    settings = get_settings()
    path = path.resolve()
    breakdown_dir = path / ".breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)

    from breakdown.indexer.ignore import IgnoreFilter
    from breakdown.indexer.registry import LanguageRegistry
    from breakdown.indexer.parser import parse_file
    from breakdown.indexer.chunker import chunk_tree
    from breakdown.indexer.embedder import create_embedder
    from breakdown.indexer.store import create_store
    from breakdown.indexer.manifest import Manifest

    ignore = IgnoreFilter(path)
    registry = LanguageRegistry()
    embedder = create_embedder(settings.embedding_provider, settings)
    store = create_store(settings.index_backend, breakdown_dir / "index")
    manifest = Manifest(breakdown_dir / "manifest.json")

    files = [
        f for f in path.rglob("*")
        if f.is_file() and not ignore.is_ignored(f)
    ]

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task(f"Indexing {len(files)} files...", total=len(files))
        for file in files:
            if not manifest.is_stale(file):
                progress.advance(task)
                continue
            tree, source = parse_file(file, registry)
            rel = str(file.relative_to(path))
            chunks = chunk_tree(tree, source, rel, settings.context_window_lines)
            if chunks:
                embeddings = embedder.embed([c.text for c in chunks])
                ids = store.add(chunks, embeddings)
                manifest.update(file, ids)
            progress.advance(task)

    manifest.save()
    store.close()
    console.print(f"[green]Index complete.[/green] {len(files)} files processed.")


@app.command()
def start(
    path: Path = typer.Argument(Path("."), help="Workspace root"),
) -> None:
    """Start the Breakdown agent and token server."""
    settings = get_settings()
    path = path.resolve()
    breakdown_dir = path / ".breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)

    _ensure_livekit(settings)

    from breakdown.token_server import TokenServer
    from breakdown.indexer.store import create_store

    token_server = TokenServer(settings=settings, breakdown_dir=breakdown_dir)
    token_server.start_background()

    store = create_store(settings.index_backend, breakdown_dir / "index")

    from breakdown.agent import create_agent
    from livekit.agents import WorkerOptions, cli as lk_cli  # type: ignore[import-untyped]

    entrypoint = create_agent(settings, store, breakdown_dir)
    lk_cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, api_key=settings.livekit_api_key, api_secret=settings.livekit_api_secret, ws_url=settings.livekit_url))


def _ensure_livekit(settings: object) -> None:
    import os
    if getattr(settings, "livekit_url", ""):
        return
    logger.info("No LIVEKIT_URL set -- starting local LiveKit server via Docker")
    try:
        subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.livekit.yml", "up", "-d"],
            check=True,
            capture_output=True,
        )
        import os
        os.environ["LIVEKIT_URL"] = "ws://localhost:7880"
        os.environ.setdefault("LIVEKIT_API_KEY", "devkey")
        os.environ.setdefault("LIVEKIT_API_SECRET", "devsecret1234567890123456789012345678")
        logger.info("Local LiveKit server started on ws://localhost:7880")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to start local LiveKit: {}", e.stderr.decode())
        raise typer.Exit(1)
    except FileNotFoundError:
        logger.error("Docker not found. Install Docker or set LIVEKIT_URL in .env")
        raise typer.Exit(1)
```

- [ ] **Step 4: Run tests**

```bash
cd core
uv run pytest tests/unit/test_cli.py -v
```

Expected: all 2 PASS

- [ ] **Step 5: Run type check and lint**

```bash
cd core
uv run basedpyright src/
uv run ruff check src/
```

Expected: no errors (address any that appear)

- [ ] **Step 6: Smoke test the CLI**

```bash
cd core
uv run breakdown version
```

Expected: `0.1.0`

- [ ] **Step 7: Commit**

```bash
git add core/src/breakdown/cli.py core/tests/unit/test_cli.py
git commit -m "feat: add CLI with start, index, and version commands"
```

---

### Task 14: Integration Test and Final Verification

**Files:**
- Create: `core/tests/integration/test_indexer_pipeline.py`

**Interfaces:**
- Consumes: all indexer modules
- Produces: confidence that the full index pipeline works end-to-end on a fixture codebase

- [ ] **Step 1: Write integration test**

```python
# core/tests/integration/test_indexer_pipeline.py
"""
Full pipeline: ignore -> parse -> chunk -> embed -> store -> search.
Uses a real fixture codebase but mocks the OpenAI embedding call.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from breakdown.config import Settings
from breakdown.indexer.ignore import IgnoreFilter
from breakdown.indexer.registry import LanguageRegistry
from breakdown.indexer.parser import parse_file
from breakdown.indexer.chunker import chunk_tree
from breakdown.indexer.embedder import create_embedder
from breakdown.indexer.store import create_store
from breakdown.indexer.manifest import Manifest


@pytest.mark.integration
def test_full_index_pipeline(fixtures_dir: Path, tmp_path: Path) -> None:
    root = fixtures_dir / "sample_project"
    settings = Settings(openai_api_key="sk-test", embedding_provider="openai")

    ignore = IgnoreFilter(root)
    registry = LanguageRegistry()
    manifest = Manifest(tmp_path / "manifest.json")
    store = create_store("lancedb", tmp_path / "db")

    fake_embedding = [0.1] * 1536  # text-embedding-3-small dimension

    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=fake_embedding)]
        mock_client.embeddings.create.return_value = mock_response

        embedder = create_embedder("openai", settings)

        files = [f for f in root.rglob("*") if f.is_file() and not ignore.is_ignored(f)]
        assert len(files) > 0

        total_chunks = 0
        for file in files:
            tree, source = parse_file(file, registry)
            rel = str(file.relative_to(root))
            chunks = chunk_tree(tree, source, rel, window_lines=50)
            if chunks:
                # return one embedding per chunk
                mock_response.data = [MagicMock(embedding=fake_embedding) for _ in chunks]
                embeddings = embedder.embed([c.text for c in chunks])
                ids = store.add(chunks, embeddings)
                manifest.update(file, ids)
                total_chunks += len(chunks)

        manifest.save()
        assert total_chunks > 0

        results = store.search(fake_embedding, k=3)
        assert len(results) > 0
        assert results[0].file.endswith(".py") or results[0].file.endswith(".xyz")

    store.close()
```

- [ ] **Step 2: Run integration test**

```bash
cd core
uv run pytest tests/integration/test_indexer_pipeline.py -v -m integration
```

Expected: PASS

- [ ] **Step 3: Run full test suite**

```bash
cd core
uv run pytest --cov=breakdown --cov-report=term-missing -v
```

Expected: all tests PASS, coverage report shown

- [ ] **Step 4: Final lint and type check**

```bash
cd core
uv run ruff check src/ tests/
uv run basedpyright src/
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add core/tests/integration/
git commit -m "test: add full indexer pipeline integration test"
```

---

## Plan A Complete

After Task 14, the Python core is fully implemented and tested:

- `breakdown version` -- works
- `breakdown index <path>` -- indexes a codebase with progress, incremental re-index on subsequent runs
- `breakdown start <path>` -- starts token server + LiveKit agent (requires LiveKit running or Docker)
- All providers are swappable via `.env` config
- All modules are typed and pass basedpyright strict
- Test coverage across all indexer, session, token server, and provider modules

**Next:** Plan B (VS Code Extension) or Plan C (Repository Infrastructure) can proceed independently.
