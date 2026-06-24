# Architecture

## System Overview

Breakdown is a client-server architecture with a Python core and platform-specific clients.

### Components

**Python Core**
- Runs as a local HTTP + WebRTC server
- Indexes the codebase using tree-sitter
- Manages agent state and communication with language model, TTS, and STT providers
- Publishes audio to LiveKit

**Platform Clients**
- VS Code Extension (JavaScript/TypeScript, production)
- Template Protocol (documentation for future clients: JetBrains, Neovim, etc.)

**Real-Time Layer**
- LiveKit: WebRTC server for audio transport
- Can be local (Docker) or managed (LiveKit Cloud)

## Data Flow

1. User selects a line in the client
2. Client sends `explain` DataPacket to the agent over LiveKit
3. Agent queries the indexed codebase for context
4. Agent calls the LLM with the code snippet
5. LLM returns explanation text
6. Agent sends the text to TTS provider
7. Agent publishes audio track to LiveKit
8. Client subscribes to the audio track and plays it
9. Agent listens for user speech on the mic track (optional)
10. User speech is sent to STT provider
11. Transcript returned as DataPackets to the client
12. User can navigate with `next`/`prev` or ask follow-up questions

## File Structure

```
Breakdown/
  core/                      # Python package
    src/breakdown/
      agent.py               # Main agent loop
      session.py             # Session state
      config.py              # Configuration (env vars)
      indexer/               # Codebase indexing
        chunker.py           # Code chunking
        embedder.py          # Embeddings
        parser.py            # AST parsing
        store.py             # Vector database
      providers/             # LLM, TTS, STT factories
    tests/                   # Unit tests
  clients/
    vscode/                  # VS Code extension
      extension-host/        # TypeScript, VS Code APIs
      webview/               # TypeScript, browser APIs
    template/                # Protocol specification
  docs/                      # MkDocs site
  scripts/                   # Utilities and checks
  deploy/                    # Docker Compose configs
```

## Key Design Decisions

1. **Thin Client Pattern**: Clients are stateless. All logic lives in the Python core. This makes it easy to add new platform clients.

2. **Live Indexing**: The codebase is indexed incrementally on startup and re-indexed when files change. The index is stored on disk in `.breakdown/`.

3. **Provider Factory**: LLM, TTS, and STT are pluggable factories. All providers are swappable via environment variables.

4. **WebRTC for Audio**: LiveKit provides real-time, low-latency audio transport. Clients do not need to understand audio codecs or buffering.

5. **Stateless HTTP Token Server**: The agent runs a simple HTTP server that issues JWT tokens for LiveKit rooms. No session state on the server.
