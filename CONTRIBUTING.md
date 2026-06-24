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
