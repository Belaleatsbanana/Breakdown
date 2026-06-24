# AGENTS.md

Guidelines for AI coding assistants working in this repository.

## Architecture Rules

These are intentional. Do not "simplify" them.

- `session.py` is a pure dataclass. It must never import from `agent.py`.
  The dependency is one-directional: agent imports session.
- `agent.py` must stay under 150 lines. If it grows beyond that, the new
  logic belongs in a dedicated module, not inlined.
- The provider factory functions (`create_llm`, `create_tts`, `create_stt`)
  are thin adapters. Do not merge them or move logic into the agent.
- `chunker.py`, `parser.py`, `embedder.py`, `store.py` are four separate
  modules with single responsibilities. Do not merge them.
- The Webview and extension host are separate TypeScript compilation targets
  with separate tsconfig files. Do not import browser APIs in extension host
  code or VS Code APIs in webview code.

## Commit Format

Conventional commits are enforced. Use exactly these prefixes:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation only
- `perf:` for performance improvements
- `chore:` for tooling and maintenance
- `test:` for test-only changes

No other prefixes. No scope in parentheses unless it aids clarity.

## Code Style

- No `print()`. Use `from loguru import logger` and `logger.info()`.
- All public Python functions require type annotations.
- All TypeScript must use `strict: true` and no `any` except where forced by VS Code API.
- Paths sent over the protocol wire are always relative to workspace root.
- Ports are never hardcoded beyond the default starting point (7890).

## Testing

Run a specific test file:
```bash
cd core
uv run pytest tests/unit/indexer/test_chunker.py -v
```

Run all tests:
```bash
cd core
uv run pytest
```

Run type check:
```bash
cd core
uv run basedpyright src/
```

## Dependency Rules

- Never add a dependency without updating `pyproject.toml` and noting the
  rationale in a comment or in `docs/contributing.md`.
- Never add a dependency that requires native compilation unless it ships
  pre-built wheels for Linux x86_64, macOS arm64, and Windows x86_64.

## Protocol

Any change to the DataPacket message schema must bump `PROTOCOL_VERSION`
in `core/src/breakdown/agent.py` and update `docs/protocol.md`.

## The .breakdown/ Directory

Never commit anything from `.breakdown/`. It is runtime state.
It is in `.gitignore`. If you see it in a diff, something is wrong.
