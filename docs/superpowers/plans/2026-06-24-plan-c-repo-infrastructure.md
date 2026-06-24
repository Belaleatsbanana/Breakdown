# Breakdown Plan C: Repository Infrastructure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up all repository infrastructure: root files, CI workflows, documentation, contributor tooling, and GitHub configuration so the project is ready for open-source collaboration and Marketplace/PyPI release.

**Architecture:** Everything in this plan lives outside `core/` and `clients/`. It is pure configuration, documentation, and automation. No application logic. Can be executed in parallel with Plan A and Plan B.

**Tech Stack:** GitHub Actions, MkDocs Material, towncrier, pre-commit, Husky, ruff, basedpyright

---

## Global Constraints

- No emojis anywhere in any file
- No em dashes in prose -- use regular hyphens or restructure the sentence
- MIT license only
- All CI jobs must pass before any PR can merge (branch protection rule must be documented)
- The README must contain a demo section with a placeholder for the screen recording
- towncrier fragment files live in `changelog/` and are named `<PR_NUMBER>.<type>.md`
- MkDocs deploys to GitHub Pages via the `docs.yml` workflow

---

## File Map

```
Breakdown/
  README.md
  LICENSE
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  MODEL_LICENSE
  CHANGELOG.md
  AGENTS.md
  CLAUDE.md
  STYLE.md
  Makefile
  .editorconfig
  .tool-versions
  mise.toml
  .pre-commit-config.yaml
  .breakdownignore
  breakdown.schema.json        # generated from pydantic Settings model
  mkdocs.yml
  flake.nix
  worktree-config.yaml

  changelog/
    README.md

  scripts/
    check_deps.sh
    smoke_test_providers.py
    setup_worktree.sh

  .github/
    workflows/
      ci.yml
      release.yml
      docs.yml
      issue-check.yml
    dependabot.yml
    ISSUE_TEMPLATE/
      bug_report.md
      feature_request.md
    PULL_REQUEST_TEMPLATE.md
    SECURITY.md               # (symlink or copy of root SECURITY.md)

  docs/
    index.md                  # MkDocs home page
    getting-started.md
    providers.md
    architecture.md
    contributing.md
    supported-languages.md
    protocol.md
```

---

### Task 1: Root Documentation Files

**Files:**
- Create: `LICENSE`
- Create: `CODE_OF_CONDUCT.md`
- Create: `SECURITY.md`
- Create: `MODEL_LICENSE`
- Create: `CHANGELOG.md`

- [ ] **Step 1: Create LICENSE**

```
MIT License

Copyright (c) 2026 Breakdown Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Create SECURITY.md**

```markdown
# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x     | Yes       |

## Reporting a Vulnerability

Do not open a public GitHub issue for security vulnerabilities.

Email: security@breakdown-project.dev (replace with actual address before publishing)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix if known

You will receive a response within 72 hours. We will coordinate a fix and disclosure timeline with you.

## Known Scope

- API keys in .env files: never commit .env; it is in .gitignore by default
- The token server binds to 127.0.0.1 only and is not reachable from the network
- Code sent to LLM/TTS/STT providers is subject to those providers' privacy policies
- The .breakdown/ index directory may contain code snippets; it is gitignored by default
```

- [ ] **Step 3: Create MODEL_LICENSE**

```markdown
# Third-Party Model Licenses

Breakdown uses the following AI models by default. Each has its own license.

## OpenAI Models (LLM, TTS, STT)

Used when OPENAI_API_KEY is set. Subject to OpenAI's usage policies:
https://openai.com/policies/usage-policies

## BAAI/bge-code-v1 (local embeddings, optional)

Used when EMBEDDING_PROVIDER=local. Licensed under MIT License.
https://huggingface.co/BAAI/bge-code-v1

## all-MiniLM-L6-v2 (fallback local embeddings)

Licensed under Apache 2.0.
https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

## ElevenLabs TTS (optional)

Used when TTS_PROVIDER=elevenlabs. Subject to ElevenLabs terms of service.
https://elevenlabs.io/terms

## Deepgram STT (optional)

Used when STT_PROVIDER=deepgram. Subject to Deepgram terms of service.
https://deepgram.com/terms

---

When adding a new model or provider, update this file with its license.
```

- [ ] **Step 4: Create CHANGELOG.md**

```markdown
# Changelog

This file is generated automatically by [towncrier](https://towncrier.readthedocs.io).
Do not edit it manually.

To add a changelog entry for your pull request, create a file in the
`changelog/` directory named `<PR_NUMBER>.<type>.md` where type is one of:
`feature`, `bugfix`, `doc`, `removal`, `misc`.

Example: `changelog/42.feature.md` containing one sentence describing the change.

<!-- towncrier release notes start -->
```

- [ ] **Step 5: Create CODE_OF_CONDUCT.md**

```markdown
# Contributor Covenant Code of Conduct

## Our Pledge

We pledge to make participation in our community a harassment-free experience for everyone.

## Our Standards

Examples of behavior that contributes to a positive environment:
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

Examples of unacceptable behavior:
- Harassment, trolling, or personal attacks
- Publishing others' private information without permission
- Other conduct that could reasonably be considered inappropriate

## Enforcement

Instances of abusive behavior may be reported to the project maintainers.
All complaints will be reviewed and investigated.

## Attribution

This Code of Conduct is adapted from the Contributor Covenant, version 2.1.
```

- [ ] **Step 6: Commit**

```bash
git add LICENSE SECURITY.md MODEL_LICENSE CHANGELOG.md CODE_OF_CONDUCT.md
git commit -m "docs: add license, security policy, model license, and code of conduct"
```

---

### Task 2: AGENTS.md, CLAUDE.md, and STYLE.md

**Files:**
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `STYLE.md`

- [ ] **Step 1: Create AGENTS.md**

```markdown
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
```

- [ ] **Step 2: Create CLAUDE.md**

```markdown
# CLAUDE.md

Claude Code-specific guidance for this repository.

## Before Starting Any Task

1. Read `AGENTS.md` for architecture rules and commit format.
2. Read `STYLE.md` for code style rules.
3. Run `cd core && uv run pytest` to confirm the baseline is green.

## File Editing Rules

- When editing `agent.py`, check the line count after. If over 150 lines,
  extract the new logic into a new file before committing.
- When editing `session.py`, grep for any import of `agent` after editing.
  If found, remove it.
- When editing any file in `providers/`, verify the corresponding test in
  `tests/unit/providers/` still passes.

## Running the Project

Start the full stack locally:
```bash
# Terminal 1: start LiveKit (Docker required)
docker compose -f deploy/docker-compose.livekit.yml up

# Terminal 2: index the codebase
cd core && uv run breakdown index ..

# Terminal 3: start the agent
cd core && uv run breakdown start ..
```

Then press `Cmd+K Cmd+E` in VS Code (with the extension installed).

## Common Pitfalls

- The extension host (Node.js) cannot use `livekit-client`. That is the
  browser SDK and lives only in the webview. The host uses `livekit-server-sdk`.
- `getTokenWithRetry` retries for 5 seconds. If the Python core has not started
  yet, this is expected. Do not reduce the retry count.
- `manifest.save()` must be called after every batch index run. If omitted,
  the next run re-indexes everything.
```

- [ ] **Step 3: Create STYLE.md**

```markdown
# Style Guide

## Python

**Types**
- Use `str | None` not `Optional[str]`.
- Use `list[str]` not `List[str]`.
- All public functions require return type annotations.
- Use `from __future__ import annotations` at the top of every Python file.

**Imports**
- No star imports (`from foo import *`).
- No aliased imports (`import numpy as np`) except for well-known conventions.
- Order: stdlib, third-party, local (enforced by ruff).

**Functions**
- Flag any function over 40 lines for review. It probably does too much.
- Prefer early returns over deeply nested if/else.
- No abbreviations in names except: `i`, `k`, `v` in loops; `ctx` for context.

**Logging**
- No `print()`. Always `from loguru import logger`.
- Use `logger.info()` for normal operation, `logger.warning()` for recoverable
  issues, `logger.error()` for failures, `logger.debug()` for verbose output.

**Error Handling**
- Catch specific exception types, not bare `except:`.
- Log the exception before re-raising or swallowing it.
- Functions that can fail gracefully return `X | None` and log a warning.
  Functions that represent unrecoverable states raise with a clear message.

## TypeScript

**Types**
- `strict: true` in every tsconfig. No `any` except where VS Code API forces it.
- Prefer discriminated unions over optional fields.
- Use `readonly` for properties that should not be mutated after construction.

**Naming**
- Classes: `PascalCase`
- Functions and variables: `camelCase`
- Constants: `SCREAMING_SNAKE_CASE` for true module-level constants
- Private class members: prefix with `_`

**Async**
- Always `await` promises. Never `.then()` chains unless chaining is genuinely clearer.
- Handle rejections. Every `async` function that can fail should catch and either
  re-throw with context or handle the error explicitly.

## General

- Commit messages follow conventional commits. See `AGENTS.md`.
- One concept per file. If a file is doing two things, split it.
- No TODO comments in committed code. Open a GitHub issue instead.
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md STYLE.md
git commit -m "docs: add AGENTS.md, CLAUDE.md, and STYLE.md contributor guides"
```

---

### Task 3: CONTRIBUTING.md and README.md

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `README.md`

- [ ] **Step 1: Create CONTRIBUTING.md**

```markdown
# Contributing to Breakdown

## Issue First Policy

Before writing any code for a new feature or significant change, open a GitHub
issue first. Describe what you want to build and why. PRs without a linked
issue will be closed with a request to open one first.

Bug fixes and documentation improvements do not need a prior issue.

## Getting Started

### Prerequisites

Install these before anything else:

- Python 3.11 or later
- uv: https://docs.astral.sh/uv/getting-started/installation/
- Node.js 18 or later
- pnpm: https://pnpm.io/installation
- Docker (for local LiveKit server): https://docs.docker.com/get-docker/

Check everything is present:

```bash
bash scripts/check_deps.sh
```

### Install

```bash
make install
```

This installs both the Python core and the VS Code extension dependencies.

### Running Tests

```bash
make test
```

### Running the Full Stack Locally

```bash
make dev
```

This starts LiveKit via Docker, indexes the current directory, and starts the agent.

## Adding a New LLM Provider

1. Open `core/src/breakdown/providers/llm.py`.
2. The `create_llm` function returns a LiveKit LLM plugin. Add a new branch
   for your provider following the same pattern as the existing OpenAI branch.
3. Add the provider name to the `Literal` type in `core/src/breakdown/config.py`.
4. Add a test in `core/tests/unit/providers/test_llm.py`.
5. Document the new provider in `docs/providers.md` with required environment
   variables and a link to sign up.

## Adding a New TTS or STT Provider

Same process as LLM. Edit `providers/tts.py` or `providers/stt.py` respectively.

## Adding a New Platform Client (JetBrains, Neovim, etc.)

Read `clients/template/README.md`. It contains the full protocol specification
and a step-by-step checklist for building a thin client. You do not need to
understand the Python core to build a client -- only the protocol matters.

## Changelog

Add a changelog fragment for your PR:

```bash
echo "Brief description of the change." > changelog/<PR_NUMBER>.feature.md
```

Replace `feature` with `bugfix`, `doc`, `removal`, or `misc` as appropriate.

## Commit Format

Follow conventional commits. See `AGENTS.md` for the full list of valid prefixes.

## Pull Request Checklist

- [ ] Linked issue in the PR description
- [ ] Tests added or updated
- [ ] `make test` passes locally
- [ ] `make lint` passes locally
- [ ] Changelog fragment added in `changelog/`
- [ ] `docs/` updated if the change affects user-facing behaviour
```

- [ ] **Step 2: Create README.md**

```markdown
# Breakdown

A voice-driven AI code explainer. Select a line in VS Code, press a shortcut,
and the AI explains it aloud. Navigate line by line with keyboard shortcuts.
Interrupt at any time with a typed or spoken question.

<!-- demo GIF goes here -- see scripts/RECORDING.md for how to record it -->

## Quick Start

**1. Install the Python core**

```bash
pip install breakdown
```

**2. Install the VS Code extension**

Search for "Breakdown" in the VS Code Extensions panel, or install from the
Marketplace page (link when published).

**3. Set your API keys**

Copy `.env.example` to `.env` in your project root and fill in your keys.
Only `OPENAI_API_KEY` is required to get started.

**4. Start a session**

Press `Cmd+K Cmd+E` (macOS) or `Ctrl+K Ctrl+E` (Windows/Linux) in any open file.

## Keyboard Shortcuts

| Action | macOS | Windows / Linux |
|---|---|---|
| Start session / explain line | Cmd+K Cmd+E | Ctrl+K Ctrl+E |
| Next line | Cmd+K Cmd+N | Ctrl+K Ctrl+N |
| Previous line | Cmd+K Cmd+P | Ctrl+K Ctrl+P |
| Push to talk | Cmd+K Cmd+Space | Ctrl+K Ctrl+Space |
| Stop session | Cmd+K Cmd+Q | Ctrl+K Ctrl+Q |

All shortcuts are configurable in VS Code's keyboard settings.

## Providers

Breakdown uses OpenAI by default for LLM, TTS, and STT. All three are
swappable via environment variables. See [docs/providers.md](docs/providers.md)
for the full list of supported providers and configuration options.

## Architecture

The Python core runs as a local server using [LiveKit](https://livekit.io) for
real-time audio over WebRTC. The VS Code extension is a thin client. Future
platform clients (JetBrains, Neovim) only need to implement the thin client
protocol -- see [clients/template/README.md](clients/template/README.md).

See [docs/architecture.md](docs/architecture.md) for a full diagram.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome.

## License

MIT. See [LICENSE](LICENSE).
```

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md README.md
git commit -m "docs: add CONTRIBUTING.md and README.md"
```

---

### Task 4: Makefile and Developer Tooling

**Files:**
- Create: `Makefile`
- Create: `.editorconfig`
- Create: `.tool-versions`
- Create: `mise.toml`
- Create: `scripts/check_deps.sh`
- Create: `scripts/smoke_test_providers.py`
- Create: `changelog/README.md`
- Create: `.breakdownignore`
- Create: `clients/template/README.md`

- [ ] **Step 1: Create Makefile**

```makefile
# Makefile
.PHONY: install dev test lint typecheck build clean

install:
	@bash scripts/check_deps.sh
	cd core && uv sync --all-extras --dev
	cd clients/vscode && pnpm install

dev:
	@echo "Starting LiveKit..."
	docker compose -f deploy/docker-compose.livekit.yml up -d
	@echo "Indexing workspace..."
	cd core && uv run breakdown index ..
	@echo "Starting agent..."
	cd core && uv run breakdown start ..

test:
	cd core && uv run pytest

lint:
	cd core && uv run ruff check src/ tests/
	cd clients/vscode && pnpm lint

typecheck:
	cd core && uv run basedpyright src/
	cd clients/vscode && pnpm typecheck

build:
	cd clients/vscode/webview && pnpm build
	cd clients/vscode/extension-host && pnpm build
	cd core && uv build

clean:
	rm -rf core/dist core/.venv
	rm -rf clients/vscode/extension-host/dist clients/vscode/webview/dist
	rm -rf clients/vscode/node_modules
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
```

- [ ] **Step 2: Create .editorconfig**

```ini
root = true

[*]
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
charset = utf-8

[*.py]
indent_style = space
indent_size = 4

[*.ts]
indent_style = space
indent_size = 2

[*.json]
indent_style = space
indent_size = 2

[*.yml]
indent_style = space
indent_size = 2

[Makefile]
indent_style = tab
```

- [ ] **Step 3: Create .tool-versions**

```
python 3.11.9
nodejs 18.20.3
```

- [ ] **Step 4: Create mise.toml**

```toml
[tools]
python = "3.11.9"
node = "18.20.3"
```

- [ ] **Step 5: Create scripts/check_deps.sh**

```bash
#!/usr/bin/env bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

ok() { echo -e "${GREEN}[ok]${NC} $1"; }
fail() { echo -e "${RED}[missing]${NC} $1 -- $2"; FAILED=1; }

FAILED=0

command -v python3 >/dev/null 2>&1 && ok "python3" || fail "python3" "https://python.org"
command -v uv >/dev/null 2>&1 && ok "uv" || fail "uv" "https://docs.astral.sh/uv/getting-started/installation/"
command -v node >/dev/null 2>&1 && ok "node" || fail "node" "https://nodejs.org"
command -v pnpm >/dev/null 2>&1 && ok "pnpm" || fail "pnpm" "https://pnpm.io/installation"
command -v docker >/dev/null 2>&1 && ok "docker" || fail "docker" "https://docs.docker.com/get-docker/"

if [ "$FAILED" -eq 1 ]; then
  echo ""
  echo "Fix the missing dependencies above, then re-run: make install"
  exit 1
fi

echo ""
echo "All dependencies found."
```

```bash
chmod +x scripts/check_deps.sh
```

- [ ] **Step 6: Create scripts/smoke_test_providers.py**

```python
#!/usr/bin/env python3
"""Smoke test all configured providers. Run before opening a PR that touches providers."""
from __future__ import annotations

import sys
from breakdown.config import get_settings
from loguru import logger


def test_openai_llm() -> bool:
    try:
        import openai
        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        client.models.list()
        logger.info("OpenAI LLM: ok")
        return True
    except Exception as e:
        logger.error("OpenAI LLM: {}", e)
        return False


def test_openai_tts() -> bool:
    try:
        import openai
        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        client.audio.speech.create(model="tts-1", voice="alloy", input="test")
        logger.info("OpenAI TTS: ok")
        return True
    except Exception as e:
        logger.error("OpenAI TTS: {}", e)
        return False


def test_openai_stt() -> bool:
    try:
        import openai, io
        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        # minimal silent WAV for smoke test
        silent_wav = bytes([
            0x52, 0x49, 0x46, 0x46, 0x24, 0x00, 0x00, 0x00, 0x57, 0x41, 0x56,
            0x45, 0x66, 0x6D, 0x74, 0x20, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00,
            0x01, 0x00, 0x44, 0xAC, 0x00, 0x00, 0x88, 0x58, 0x01, 0x00, 0x02,
            0x00, 0x10, 0x00, 0x64, 0x61, 0x74, 0x61, 0x00, 0x00, 0x00, 0x00,
        ])
        client.audio.transcriptions.create(
            model="whisper-1", file=("test.wav", io.BytesIO(silent_wav), "audio/wav")
        )
        logger.info("OpenAI STT: ok")
        return True
    except Exception as e:
        logger.error("OpenAI STT: {}", e)
        return False


if __name__ == "__main__":
    results = [test_openai_llm(), test_openai_tts(), test_openai_stt()]
    if not all(results):
        logger.error("Some providers failed. Check your API keys in .env.")
        sys.exit(1)
    logger.info("All providers healthy.")
```

- [ ] **Step 7: Create changelog/README.md**

```markdown
# Changelog Fragments

Add one file per pull request in this directory. Do not edit `CHANGELOG.md` directly.

## Naming

`<PR_NUMBER>.<type>.md`

Types:
- `feature` -- new feature
- `bugfix` -- bug fix
- `doc` -- documentation change
- `removal` -- deprecated feature removed
- `misc` -- maintenance, dependency update, refactor

## Content

One sentence describing the change from the user's perspective.

## Example

File: `changelog/42.feature.md`
Content: `Add ElevenLabs TTS provider support via TTS_PROVIDER=elevenlabs.`

## How Releases Work

The release workflow runs `towncrier build` which compiles all fragments into
`CHANGELOG.md` and deletes the individual files.
```

- [ ] **Step 8: Create .breakdownignore**

```
# .breakdownignore
# Files and directories excluded from Breakdown's codebase index.
# Syntax is the same as .gitignore.

# Add project-specific exclusions below:
# vendor/
# data/
```

- [ ] **Step 9: Create clients/template/README.md**

```markdown
# Building a Breakdown Platform Client

This document specifies what a thin client must implement to work with the
Breakdown Python core. You do not need to understand the core internals.

## What a Client Does

1. Read `.breakdown/runtime.json` to find the token server port.
2. Call `GET http://127.0.0.1:<port>/token?room=breakdown-<hash>` to get a JWT.
3. Connect to the LiveKit room using the JWT and the `livekit_url` from the response.
4. Send DataPackets to the agent (commands).
5. Receive DataPackets from the agent (status, position, transcript, error).
6. Play the TTS audio track published by the agent (via the platform's audio API).
7. Optionally capture mic audio and publish it as a track for STT.

## Room Name

The room name is deterministic based on the workspace root:

```
sha256(absolute_workspace_root_path)[:12]
room_name = "breakdown-" + hash
```

## DataPacket Schema (Protocol v1)

All packets are JSON with envelope: `{ "v": 1, "type": "<type>", ...fields }`

### Client -> Agent

| type | required fields | meaning |
|---|---|---|
| `explain` | `file` (string, relative path), `line` (integer, 1-indexed) | Explain this line |
| `next` | none | Move to next line |
| `prev` | none | Move to previous line |
| `stop` | none | End the session |

### Agent -> Client

| type | fields | meaning |
|---|---|---|
| `status` | `state`: `"idle"/"explaining"/"listening"/"interrupted"` | State changed |
| `position` | `file` (string), `line` (integer) | Current position updated |
| `transcript` | `text` (string), `final` (boolean) | STT result (partial or final) |
| `error` | `code` (string), `message` (string), `recoverable` (boolean), `retry_after_ms` (integer) | Error occurred |

### Error Codes

| code | meaning | recoverable |
|---|---|---|
| `PROVIDER_RATE_LIMITED` | API rate limit hit | true |
| `INDEX_EMPTY` | No index found; run `breakdown index` | false |
| `STT_FAILED` | Speech transcription failed | true |
| `ROOM_DISCONNECTED` | LiveKit room connection lost | true |

## Important Rules

- Paths in `explain` packets must be relative to the workspace root. Never send absolute paths.
- The client is responsible for audio playback. The agent publishes a LiveKit audio track.
- Protocol version is in the `v` field. If `v` does not equal `1`, show an error asking
  the user to update both the core and the client.

## Implementation Checklist

- [ ] Read runtime.json and get token
- [ ] Connect to LiveKit room
- [ ] Send `explain` packet on line selection
- [ ] Send `next` / `prev` on navigation
- [ ] Receive and display `status` updates
- [ ] Play the agent's audio track
- [ ] Handle `error` packets (show notification for `recoverable: true`, block UI for `false`)
- [ ] Send `stop` on session end / plugin deactivation
- [ ] Kill the Python core process on deactivation (if the client started it)
```

- [ ] **Step 10: Commit**

```bash
git add Makefile .editorconfig .tool-versions mise.toml scripts/ changelog/ .breakdownignore clients/template/
git commit -m "chore: add Makefile, editor config, dev tooling, and client template"
```

---

### Task 5: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/issue-check.yml`
- Create: `.github/dependabot.yml`
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1: Create ci.yml**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python:
    name: Python ${{ matrix.python-version }} on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        working-directory: core
        run: uv sync --all-extras --dev

      - name: Lint
        working-directory: core
        run: uv run ruff check src/ tests/

      - name: Type check
        working-directory: core
        run: uv run basedpyright src/

      - name: Test
        working-directory: core
        run: uv run pytest --cov=breakdown --cov-report=xml -x

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.11'
        with:
          files: core/coverage.xml

  typescript:
    name: TypeScript on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v3
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: "18"
          cache: "pnpm"
          cache-dependency-path: clients/vscode/pnpm-lock.yaml

      - name: Install dependencies
        working-directory: clients/vscode
        run: pnpm install

      - name: Typecheck
        working-directory: clients/vscode
        run: pnpm typecheck

      - name: Build
        working-directory: clients/vscode
        run: pnpm build

      - name: Check bundle size
        working-directory: clients/vscode/extension-host
        shell: bash
        run: |
          SIZE=$(wc -c < dist/extension.js)
          if [ "$SIZE" -gt 524288 ]; then
            echo "extension.js is too large: ${SIZE} bytes (limit: 512KB)"
            exit 1
          fi
          echo "extension.js size: ${SIZE} bytes (ok)"
```

- [ ] **Step 2: Create issue-check.yml**

```yaml
# .github/workflows/issue-check.yml
name: Issue Check

on:
  pull_request:
    types: [opened, edited]

jobs:
  check-linked-issue:
    runs-on: ubuntu-latest
    steps:
      - name: Check for linked issue
        uses: actions/github-script@v7
        with:
          script: |
            const body = context.payload.pull_request.body || "";
            const hasIssue = /closes?\s+#\d+|fixes?\s+#\d+|resolves?\s+#\d+|related\s+to\s+#\d+/i.test(body);
            const isDependabot = context.payload.pull_request.user.login === "dependabot[bot]";
            const isBugFix = context.payload.pull_request.labels?.some(l => l.name === "bug");

            if (!hasIssue && !isDependabot && !isBugFix) {
              core.setFailed(
                "This PR does not reference a GitHub issue. " +
                "Please link an issue using 'Closes #N' in the PR description. " +
                "Bug fixes are exempt -- add the 'bug' label to bypass this check."
              );
            }
```

- [ ] **Step 3: Create dependabot.yml**

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/core"
    schedule:
      interval: "weekly"
    groups:
      all-dependencies:
        patterns: ["*"]

  - package-ecosystem: "npm"
    directory: "/clients/vscode/extension-host"
    schedule:
      interval: "weekly"

  - package-ecosystem: "npm"
    directory: "/clients/vscode/webview"
    schedule:
      interval: "weekly"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

- [ ] **Step 4: Create issue templates**

```markdown
<!-- .github/ISSUE_TEMPLATE/bug_report.md -->
---
name: Bug report
about: Something is not working
labels: bug
---

**Describe the bug**
A clear description of what is wrong.

**To reproduce**
Steps to reproduce:
1.
2.
3.

**Expected behavior**
What you expected to happen.

**Environment**
- OS:
- Python version:
- VS Code version:
- Breakdown version:
- Provider (LLM/TTS/STT):

**Logs**
Paste relevant output from `breakdown start` here.
```

```markdown
<!-- .github/ISSUE_TEMPLATE/feature_request.md -->
---
name: Feature request
about: Propose a new feature or change
labels: enhancement
---

**What problem does this solve?**
Describe the problem you are trying to solve.

**Proposed solution**
Describe what you want to build.

**Alternatives considered**
What other approaches did you consider?

**Are you willing to implement this?**
Yes / No / Maybe
```

- [ ] **Step 5: Create PULL_REQUEST_TEMPLATE.md**

```markdown
<!-- .github/PULL_REQUEST_TEMPLATE.md -->
## What does this PR do?

<!-- One paragraph describing the change. -->

## Linked issue

Closes #

## Testing

<!-- Describe how you tested this change. -->

## Checklist

- [ ] Tests added or updated
- [ ] `make test` passes locally
- [ ] `make lint` passes locally
- [ ] Changelog fragment added in `changelog/`
- [ ] Documentation updated if needed
```

- [ ] **Step 6: Commit**

```bash
git add .github/
git commit -m "chore: add CI workflows, dependabot, and GitHub templates"
```

---

### Task 6: MkDocs Documentation Site

**Files:**
- Create: `mkdocs.yml`
- Create: `docs/index.md`
- Create: `docs/getting-started.md`
- Create: `docs/providers.md`
- Create: `docs/architecture.md`
- Create: `docs/protocol.md`
- Create: `docs/supported-languages.md`
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: Create mkdocs.yml**

```yaml
site_name: Breakdown
site_description: Voice-driven AI code explainer
site_url: https://breakdown-project.dev
repo_url: https://github.com/breakdown-project/breakdown
repo_name: breakdown-project/breakdown
edit_uri: edit/main/docs/

theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - content.code.copy
    - content.action.edit

nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Providers: providers.md
  - Architecture: architecture.md
  - Protocol: protocol.md
  - Supported Languages: supported-languages.md
  - Contributing: contributing.md

plugins:
  - search

markdown_extensions:
  - admonition
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - tables
```

- [ ] **Step 2: Create docs/index.md**

```markdown
# Breakdown

A voice-driven AI code explainer for VS Code.

Select a line, press a shortcut, and the AI explains it aloud. Navigate
line by line. Interrupt to ask follow-up questions. All providers are
swappable.

## Quick links

- [Getting Started](getting-started.md)
- [Supported Providers](providers.md)
- [Architecture](architecture.md)
- [Building a Platform Client](protocol.md)
```

- [ ] **Step 3: Create docs/getting-started.md**

```markdown
# Getting Started

## Prerequisites

- Python 3.11 or later
- VS Code 1.85 or later
- An OpenAI API key (other providers are optional)
- Docker (only if you do not have a LiveKit Cloud account)

## Install the Python Core

```bash
pip install breakdown
```

Or with uv:

```bash
uv tool install breakdown
```

## Install the VS Code Extension

Search for "Breakdown" in the Extensions panel and click Install.

## Configure API Keys

Create a `.env` file in your project root:

```bash
cp .env.example .env
```

Open `.env` and add your `OPENAI_API_KEY`. All other keys are optional.

## Start a Session

Open any code file in VS Code. Press `Cmd+K Cmd+E` (macOS) or
`Ctrl+K Ctrl+E` (Windows/Linux).

The extension will:
1. Start the Breakdown Python process
2. Start a local LiveKit server (if no `LIVEKIT_URL` is set)
3. Index your codebase (first run only; subsequent runs are incremental)
4. Open the audio panel and begin explaining the selected line

## First Index

The first time you start a session, Breakdown indexes your codebase. This
may take a few seconds to a few minutes depending on the size of your project.
Progress is shown in the VS Code status bar.

Subsequent starts are fast because only changed files are re-indexed.

## Troubleshooting

**"breakdown command not found"**
Make sure the Python package is installed and on your PATH. With uv:
```bash
uv tool install breakdown
```

**No audio**
Check that your system audio output is working and not muted.

**Remote development (SSH, Codespaces)**
Audio requires a local VS Code window. Remote development is not currently supported.
```

- [ ] **Step 4: Create docs/providers.md**

```markdown
# Providers

Breakdown uses three provider types: LLM (language model), TTS (text to speech),
and STT (speech to text). All are configured via environment variables in `.env`.

## LLM Providers

| Provider | Env var | Model example |
|---|---|---|
| OpenAI (default) | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-opus-4-8` |
| Groq | `GROQ_API_KEY` | `llama3-70b-8192` |
| Ollama (local) | none | `ollama/llama3` |

Set the model with `LLM_MODEL=<model>`. Breakdown uses LiteLLM for provider
routing, so any model string LiteLLM supports will work.

## TTS Providers

| Provider | Env var | Config key |
|---|---|---|
| OpenAI (default) | `OPENAI_API_KEY` | `TTS_PROVIDER=openai` |
| ElevenLabs | `ELEVENLABS_API_KEY` | `TTS_PROVIDER=elevenlabs` |

## STT Providers

| Provider | Env var | Config key |
|---|---|---|
| OpenAI Whisper (default) | `OPENAI_API_KEY` | `STT_PROVIDER=openai` |
| Deepgram | `DEEPGRAM_API_KEY` | `STT_PROVIDER=deepgram` |

## Embedding Providers

Embeddings are used for codebase indexing.

| Provider | Env var | Config key | Notes |
|---|---|---|---|
| OpenAI (default) | `OPENAI_API_KEY` | `EMBEDDING_PROVIDER=openai` | No extra key if already set |
| Local | none | `EMBEDDING_PROVIDER=local` | Downloads ~117MB model on first run |

## LiveKit

| Setup | Config |
|---|---|
| Local Docker (default if no key) | No config needed; Docker must be installed |
| LiveKit Cloud | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |

## Adding a Provider

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the step-by-step guide.
```

- [ ] **Step 5: Create docs/protocol.md**

```markdown
# Protocol Specification v1

This document is the authoritative reference for the message protocol between
a Breakdown platform client and the Python core agent.

## Connection Flow

1. Read `.breakdown/runtime.json` -- contains `port` and `livekit_url`.
2. `GET http://127.0.0.1:<port>/token?room=<room_name>` -- returns `{"token": "...", "url": "..."}`.
3. Connect to the LiveKit room using the token.
4. Begin sending and receiving DataPackets.

## Room Name

```
room_name = "breakdown-" + sha256(absolute_workspace_root)[:12]
```

The room name is deterministic. The same workspace root always produces the same room name.

## Packet Envelope

All DataPackets are UTF-8 encoded JSON with this envelope:

```json
{ "v": 1, "type": "<type>", ...additional fields }
```

If `v` is not `1`, show an error and ask the user to update Breakdown.

## Client to Agent

### explain

```json
{ "v": 1, "type": "explain", "file": "src/foo.py", "line": 42 }
```

`file` must be relative to the workspace root. `line` is 1-indexed.

### next / prev

```json
{ "v": 1, "type": "next" }
{ "v": 1, "type": "prev" }
```

### stop

```json
{ "v": 1, "type": "stop" }
```

## Agent to Client

### status

```json
{ "v": 1, "type": "status", "state": "explaining" }
```

States: `idle`, `explaining`, `listening`, `interrupted`

### position

```json
{ "v": 1, "type": "position", "file": "src/foo.py", "line": 43 }
```

### transcript

```json
{ "v": 1, "type": "transcript", "text": "what does this do", "final": true }
```

`final: false` for partial STT results; `final: true` for the committed transcription.

### error

```json
{
  "v": 1,
  "type": "error",
  "code": "PROVIDER_RATE_LIMITED",
  "message": "OpenAI rate limit reached. Retrying in 5 seconds.",
  "recoverable": true,
  "retry_after_ms": 5000
}
```

Error codes: `PROVIDER_RATE_LIMITED`, `INDEX_EMPTY`, `STT_FAILED`, `ROOM_DISCONNECTED`

When `recoverable` is `true`, show a non-blocking notification and wait.
When `recoverable` is `false`, show a blocking error and offer to restart the session.

## Audio

The agent publishes a LiveKit audio track. Clients subscribe to it and play it
using whatever audio API is available on their platform. Audio is not sent as
DataPackets.
```

- [ ] **Step 6: Create docs/supported-languages.md**

```markdown
# Supported Languages

Breakdown uses tree-sitter for AST-aware code parsing. Languages with a
tree-sitter grammar get accurate, function-level chunking. Other languages
fall back to 50-line plain-text chunks, which still produce useful explanations.

## AST-Aware (tree-sitter)

Python, JavaScript, TypeScript, TSX, Go, Rust, Java, C, C++, Ruby, C#,
PHP, Swift, Kotlin, Scala, Lua, Bash

## Plain-Text Fallback

All other file types are chunked as plain text. This includes most config
files, markup languages, and languages not yet in tree-sitter-languages.

## Adding a Language

1. Check if the language is in `tree-sitter-languages`:
   https://github.com/grantjenks/py-tree-sitter-languages
2. If yes, add the file extension mapping to `_EXT_TO_LANGUAGE` in
   `core/src/breakdown/indexer/registry.py`.
3. If no, open a PR to `tree-sitter-languages` first, or open an issue
   here requesting it.
4. Update this file with the new language.
```

- [ ] **Step 7: Create docs.yml workflow**

```yaml
# .github/workflows/docs.yml
name: Docs

on:
  push:
    branches: [main]
    paths:
      - "docs/**"
      - "mkdocs.yml"

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install MkDocs
        run: uv tool install mkdocs-material

      - name: Deploy
        run: mkdocs gh-deploy --force
```

- [ ] **Step 8: Commit**

```bash
git add mkdocs.yml docs/ .github/workflows/docs.yml
git commit -m "docs: add MkDocs documentation site with all core pages"
```

---

### Task 7: Release Workflow

**Files:**
- Create: `.github/workflows/release.yml`
- Create: `scripts/RECORDING.md`

- [ ] **Step 1: Create release.yml**

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - uses: pnpm/action-setup@v3
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: "18"

      - name: Run CI
        working-directory: core
        run: |
          uv sync --all-extras --dev
          uv run pytest

      - name: Build Python wheel
        working-directory: core
        run: uv build

      - name: Publish to PyPI
        working-directory: core
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}
        run: uv publish

      - name: Build VS Code extension
        working-directory: clients/vscode
        run: |
          pnpm install
          pnpm build
          cd extension-host && npx @vscode/vsce package --no-dependencies

      - name: Publish to VS Code Marketplace
        working-directory: clients/vscode/extension-host
        env:
          VSCE_PAT: ${{ secrets.VSCE_PAT }}
          # Note: VSCE_PAT expires annually. Rotate before expiry.
          # Current expiry: update this comment when rotating the token.
        run: npx @vscode/vsce publish --no-dependencies --pat "$VSCE_PAT"

      - name: Build changelog
        run: |
          uv tool install towncrier
          towncrier build --yes --version "${{ github.ref_name }}"

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          body_path: CHANGELOG.md
          files: |
            clients/vscode/extension-host/*.vsix
            core/dist/*.whl
            core/dist/*.tar.gz
```

- [ ] **Step 2: Create scripts/RECORDING.md**

```markdown
# How to Record the README Demo

This document ensures the demo can be reproduced when the UI changes.

## Setup

- VS Code theme: Default Light+ (most legible in small GIFs)
- Font: Cascadia Code, size 14
- Terminal: VS Code integrated terminal
- Demo file: `examples/minimal_agent.py` (visible in the recording)
- Window size: 1280x720

## VS Code Settings for Recording

```json
{
  "editor.fontSize": 14,
  "editor.fontFamily": "Cascadia Code",
  "workbench.colorTheme": "Default Light+",
  "editor.minimap.enabled": false,
  "breadcrumbs.enabled": false
}
```

## Script

1. Open `examples/minimal_agent.py` in VS Code.
2. Click line 8 (the `async def entrypoint` line).
3. Press `Cmd+K Cmd+E` to start the session.
4. Wait for the audio to start (status bar changes to "explaining").
5. Press `Cmd+K Cmd+N` three times to advance through lines.
6. Hold `Cmd+K Cmd+Space` and say "what does this parameter do?".
7. Wait for the AI to answer.
8. Press `Cmd+K Cmd+Q` to stop.

## Export

- Record at 1280x720 using Kap (macOS) or OBS (all platforms).
- Export as GIF, max 5MB, using Gifski for quality compression.
- Export as MP4 at 1080p for the linked full-quality version.
- Place GIF at `docs/demo.gif` and link it from README.md.

## Duration

Target: 25-35 seconds total. Cut anything over 40 seconds.
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml scripts/RECORDING.md
git commit -m "chore: add release workflow and demo recording guide"
```

---

## Plan C Complete

After Task 7, the repository is fully set up for open-source collaboration:

- MIT licensed, model licenses documented
- AGENTS.md, CLAUDE.md, STYLE.md guide contributors and AI assistants
- Makefile: `make install`, `make dev`, `make test`, `make lint`, `make build`
- CI: 3 OS x 3 Python versions, TypeScript build + bundle size check
- Issue First Policy enforced via GitHub Action
- Dependabot configured for Python, npm, and GitHub Actions
- MkDocs site deploys to GitHub Pages on every push to main
- Release workflow publishes to PyPI and VS Code Marketplace on tag
- Towncrier changelog with per-PR fragment files
- Client template documents the full protocol for future platform contributors
- Demo recording instructions documented
