# Breakdown Design Spec

**Date:** 2026-06-24

## What It Is

Breakdown is a voice-driven AI code explainer. A developer opens a file in VS Code, selects a line, and the AI reads the codebase, understands it, then explains that line and each subsequent line aloud. The developer can navigate with keyboard shortcuts, pause, interrupt with a typed or spoken question, and resume. All AI providers (LLM, TTS, STT) are swappable via config. The core runs as a local server so future platform clients (JetBrains, Neovim) only need to implement a thin client.

---

## Architecture

### Two Runtimes, One Protocol

```
Python Core (breakdown)          VS Code Extension (thin client)
  agent.py          <--DataPacket-->  extension-host/
  session.py                          webview/ (browser, livekit-client)
  token_server.py   <--HTTP JWT-->   token_client.ts
  indexer/
  providers/
  cli.py
```

The Python core exposes:
- A LiveKit agent that joins a room and handles all AI logic
- A localhost-only HTTP token server so clients can get LiveKit JWTs without knowing the secret

The VS Code extension has two separate TypeScript contexts:
- Extension host (Node.js): spawns the Python core, gets a JWT, tells the Webview to connect
- Webview (browser): runs `livekit-client`, plays TTS audio via Web Audio API, captures mic via getUserMedia

Future platform clients implement the same thin client contract: call the token server, connect to the LiveKit room, send DataPackets, receive audio.

---

## Subsystems

### 1. Indexer

Runs once on `breakdown index`, then incrementally via file watcher.

**Pipeline:**
1. `ignore.py` -- builds effective ignore list from defaults + .gitignore + .breakdownignore
2. `registry.py` -- maps file extensions to tree-sitter grammars; falls back to plain text for unknown types
3. `parser.py` -- parses each file to AST; wraps per-file in try/except; plain-text fallback on failure
4. `chunker.py` -- walks AST to produce `Chunk` objects (one per function, class header, import block, constant); unsupported languages get 50-line plain-text chunks
5. `embedder.py` -- embeds chunks using OpenAI `text-embedding-3-small` by default; `sentence-transformers` with `BAAI/bge-code-v1` as optional fallback (no extra API key needed, but requires PyTorch optional dep)
6. `store.py` -- writes chunks to LanceDB atomically (temp dir, rename on success); ChromaDB as optional fallback; maintains `manifest.py` (file path -> mtime + hash + chunk IDs) for incremental re-index
7. `watcher.py` -- uses `watchdog` with 3s debounce; calls incremental re-index on file change; uses manifest to skip unchanged files

### 2. LiveKit Agent

`agent.py` is a thin coordinator under 150 lines. It:
- Joins the LiveKit room
- Receives DataPackets from clients
- Delegates to `session.py` for state
- Calls providers for LLM/TTS/STT
- Publishes TTS audio track

`session.py` is a pure dataclass with no imports from `agent.py`:
- Current file, current line, line iterator
- Conversation history with token budget (tiktoken for OpenAI, character approximation fallback)
- When history exceeds 80% of model context window, oldest N turns are summarised via a cheap LLM call
- Persisted atomically to `.breakdown/session.json` on every state change
- On startup, agent checks for existing session and offers resume via DataPacket

### 3. Token Server

`token_server.py` uses Python stdlib `http.server` (no FastAPI). On start:
- Tries port 7890, increments until a free port is found
- Binds to 127.0.0.1 only
- Writes chosen port to `.breakdown/runtime.json`
- Signs LiveKit JWTs using `livekit-api` (already a dep)
- Single route: `GET /token?room=<name>` -> `{"token": "<jwt>", "url": "<livekit_url>"}`

### 4. Providers

Each provider file defines a base protocol class and concrete implementations as subclasses. Provider selection is driven by config keys, not conditional imports.

- `llm.py` -- LiteLLM adapter conforming to LiveKit Agents LLM plugin interface; model set via `LLM_MODEL` env var
- `tts.py` -- LiveKit TTS plugin interface; implementations: OpenAI (`TTS_PROVIDER=openai`), ElevenLabs (`TTS_PROVIDER=elevenlabs`)
- `stt.py` -- LiveKit STT plugin interface; implementations: OpenAI Whisper (`STT_PROVIDER=openai`), Deepgram (`STT_PROVIDER=deepgram`)

### 5. CLI

`cli.py` exposes three commands via `typer`:
- `breakdown index` -- runs full index with rich progress bar; uses manifest for incremental
- `breakdown start` -- starts token server + LiveKit agent; auto-launches Docker LiveKit if no `LIVEKIT_URL` in env
- `breakdown version` -- prints VERSION file content

### 6. VS Code Extension

Two separate TypeScript projects in `clients/vscode/`:

**extension-host/** (Node.js):
- `extension.ts` -- registers chord keybindings (`Cmd+K Cmd+E` etc), activates on command only
- `process_manager.ts` -- spawns `breakdown start`; SIGTERM on deactivate; Windows taskkill fallback; detects if not in PATH and shows install instructions
- `token_client.ts` -- reads `.breakdown/runtime.json` for port; calls token server; retries with backoff
- `commands.ts` -- all VS Code command handlers; sends DataPackets via postMessage to Webview
- `webview_manager.ts` -- creates and manages the Webview panel

**webview/** (browser context):
- `index.ts` -- entry point
- `livekit_room.ts` -- `livekit-client` connection, subscribes to audio track
- `audio_player.ts` -- Web Audio API playback, streams TTS chunks
- `mic_capture.ts` -- getUserMedia for push-to-talk
- `message_bridge.ts` -- postMessage protocol to extension host

---

## Protocol (v1)

All DataPackets are JSON with envelope `{ "v": 1, "type": "<type>", ...fields }`.

**Client -> Agent:**
| type | fields | meaning |
|---|---|---|
| `explain` | `file` (relative path), `line` (1-indexed) | Explain this line |
| `next` | -- | Move to next line |
| `prev` | -- | Move to previous line |
| `interrupt` | `text` (optional) | Stop TTS, ask follow-up |
| `resume` | -- | Resume after interrupt |
| `stop` | -- | End session |

**Agent -> Client:**
| type | fields | meaning |
|---|---|---|
| `status` | `state`: `idle/indexing/explaining/listening/interrupted` | State change |
| `position` | `file`, `line` | Current position updated |
| `transcript` | `text`, `final`: bool | STT partial/final result |
| `error` | `code`, `message`, `recoverable`: bool, `retry_after_ms` | Error |

Audio is delivered via LiveKit audio track, not DataPackets.

---

## Room Naming

Room name = `breakdown-{sha256(absolute_workspace_root)[:12]}`. Deterministic, collision-resistant, same workspace always reconnects to same room.

---

## Configuration

Two-layer config: `.env` (secrets, never committed) + `.breakdown/config.yaml` (per-project behaviour overrides).

Loaded via `pydantic-settings`. Schema exported as `breakdown.schema.json` for editor autocomplete.

Key config options:
```yaml
llm:
  model: gpt-4o           # any LiteLLM-supported model string
  context_window: 128000  # tokens

tts:
  provider: openai        # openai | elevenlabs

stt:
  provider: openai        # openai | deepgram

index:
  respect_gitignore: true
  debounce_seconds: 3
  backend: lancedb        # lancedb | chromadb
  context_window_lines: 50
  embedding_provider: openai  # openai | local

session:
  history_budget_pct: 0.8   # summarise when history > 80% of context window
```

---

## Key Decisions and Rationale

| Decision | Rationale |
|---|---|
| LiveKit + WebRTC | Sub-100ms audio latency vs WebSocket; VAD and audio track management built in |
| stdlib http.server for token server | One endpoint, zero extra deps; FastAPI is overkill |
| pydantic-settings for config | Auto-validates types, handles .env, single merge step |
| LanceDB as default vector store | Fast Rust-backed, atomic writes, no server required |
| OpenAI text-embedding-3-small as default | No extra API key (already needed for LLM); PyTorch optional dep for local fallback |
| AST-aware chunking | Retrieves whole functions/classes, not arbitrary line windows |
| typer for CLI | Minimal, typed, auto-generates --help |
| Two-context VS Code extension | Browser WebRTC APIs unavailable in Node.js extension host; Webview is the only correct approach |
| MIT license | Maximum contributor reach, no patent clauses |
| towncrier for changelog | Eliminates merge conflicts on CHANGELOG.md |
| basedpyright for type checking | Consistent with VS Code Pylance; contributors see same errors locally and in CI |

---

## Constraints

- Python 3.11+
- Node.js 18+
- livekit-agents 1.x API
- All functions typed (basedpyright strict)
- agent.py must stay under 150 lines
- session.py must not import from agent.py
- No print() -- use loguru
- Paths over the protocol wire are always relative to workspace root
- Ports are never hardcoded beyond the default starting point (7890)
- .breakdown/ is always gitignored
- One VERSION file at repo root, read by both pyproject.toml and package.json
