# Getting Started

## Prerequisites

- VS Code 1.85 or later
- Docker (only if you don't have a LiveKit Cloud account) — Breakdown starts
  it for you automatically, it just needs to already be running
- An OpenAI API key (other providers are optional)

## Install the VS Code Extension

Search for "Breakdown" in the Extensions panel and click Install.

## Start a Session

Open any code file in VS Code. Open the Command Palette and run
`Breakdown: Start Session` (or press `Cmd+K Cmd+E` / `Ctrl+K Ctrl+E`).

The extension will, in order:
1. Check whether the Python core (`breakdown-ai`) is installed. If not, it
   offers to install it for you via `uv` or `pip` in an integrated terminal.
2. Check whether Docker is running and start a local LiveKit server via
   Docker Compose if needed.
3. Check whether you've set an API key. If not, it prompts you — pick OpenAI
   for the simplest setup (one key covers LLM, TTS, and embeddings).
4. Start the Breakdown agent process and connect the sidebar.

You only go through steps 1-3 once; later sessions skip straight to step 4.

## Managing API Keys

Run `Breakdown: Set API Key` from the Command Palette at any time to add or
change a key. Keys are stored via VS Code's `SecretStorage` API (OS
keychain-backed), never written to a plaintext file.

## First Index

The first time you start a session, Breakdown indexes your codebase. This
may take a few seconds to a few minutes depending on the size of your project.
Progress is shown in the VS Code status bar.

Subsequent starts are fast because only changed files are re-indexed.

## Troubleshooting

**"Docker isn't running"**
Install and start Docker Desktop (or Docker Engine), then run
`Breakdown: Start Session` again. Alternatively, run `Breakdown: Set API Key`
and set "LiveKit Cloud URL" (plus its matching API Key and API Secret) to
point at a LiveKit Cloud project instead of self-hosting — once a LiveKit
Cloud URL is set, `Start Session` skips the Docker step entirely.

**"Breakdown: still can't find the `breakdown` command"**
Check the "Breakdown Install" terminal for errors from the `pip`/`uv` install
command. A common cause is the install completing into a directory that isn't
on your shell's `PATH` — restart VS Code after adding it.

**No audio**
Check that your system audio output is working and not muted.

**Remote development (SSH, Codespaces)**
Audio requires a local VS Code window. Remote development is not currently supported.
