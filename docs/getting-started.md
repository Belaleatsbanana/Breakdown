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
