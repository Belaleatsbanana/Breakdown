# Breakdown

A voice-driven AI code explainer. Select a line in VS Code, press a shortcut,
and the AI explains it aloud. Navigate line by line with keyboard shortcuts.
Interrupt at any time with a typed or spoken question.

## Demo

<!-- demo GIF goes here. See scripts/RECORDING.md for how to record it. -->

## Quick Start

**1. Install the VS Code extension**

Search for "Breakdown" in the VS Code Extensions panel, or install from the
[Marketplace](https://marketplace.visualstudio.com/items?itemName=belaleatsbanana.breakdown-vscode).

**2. Run a session**

Open the Command Palette and run `Breakdown: Start Session` (or press
`Cmd+K Cmd+E` on macOS / `Ctrl+K Ctrl+E` on Windows/Linux).

The first time you do this, Breakdown will:
- Prompt to install its Python core if it isn't found (`breakdown-ai`, via `uv` or `pip`)
- Start a local LiveKit server automatically (requires Docker to be running)
- Prompt you for one API key — OpenAI is enough to cover LLM, TTS, and embeddings

Every subsequent `Start Session` skips straight to connecting, since the
Python core, LiveKit, and your API key all persist.

**3. Explain some code**

Open a file, place your cursor on a line, and run `Breakdown: Explain Line`
(`Cmd+Alt+I` / `Ctrl+Alt+I`). The explanation appears in the Breakdown sidebar
and is narrated aloud.

## Keyboard Shortcuts

| Action | macOS | Windows / Linux |
|---|---|---|
| Start session | Cmd+K Cmd+E | Ctrl+K Ctrl+E |
| Explain line | Cmd+Alt+I | Ctrl+Alt+I |
| Next line | Cmd+K Cmd+N | Ctrl+K Ctrl+N |
| Previous line | Cmd+K Cmd+P | Ctrl+K Ctrl+P |
| Ask a question | Cmd+K Cmd+Space | Ctrl+K Ctrl+Space |
| Stop session | Cmd+K Cmd+Q | Ctrl+K Ctrl+Q |

All shortcuts are configurable in VS Code's keyboard settings. API keys are
managed via `Breakdown: Set API Key` in the Command Palette, backed by VS
Code's encrypted secret storage — no `.env` file needed.

## Providers

Breakdown uses OpenAI by default for LLM, TTS, and STT. All three are
swappable via environment variables. See [docs/providers.md](docs/providers.md)
for the full list of supported providers and configuration options.

## Architecture

The Python core runs as a local server using [LiveKit](https://livekit.io) for
real-time audio over WebRTC. The VS Code extension is a thin client. Future
platform clients (JetBrains, Neovim) only need to implement the thin client
protocol. See [clients/template/README.md](clients/template/README.md).

See [docs/architecture.md](docs/architecture.md) for a full diagram.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome.

## License

MIT. See [LICENSE](LICENSE).
