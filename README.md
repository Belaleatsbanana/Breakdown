# Breakdown

A voice-driven AI code explainer. Select a line in VS Code, press a shortcut,
and the AI explains it aloud. Navigate line by line with keyboard shortcuts.
Interrupt at any time with a typed or spoken question.

## Demo

<!-- demo GIF goes here. See scripts/RECORDING.md for how to record it. -->

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
protocol. See [clients/template/README.md](clients/template/README.md).

See [docs/architecture.md](docs/architecture.md) for a full diagram.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome.

## License

MIT. See [LICENSE](LICENSE).
