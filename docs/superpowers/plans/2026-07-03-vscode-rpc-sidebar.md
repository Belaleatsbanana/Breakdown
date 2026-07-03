# RPC Transport + Chat Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-rolled DataPacket/JSON protocol between the VS Code extension and the Python agent with LiveKit's built-in RPC methods, and replace the hidden "audio engine" webview panel with a visible sidebar chat view that renders the agent's actual generated explanation text as markdown while it narrates via TTS.

**Architecture:** The agent registers five `register_rpc_method` handlers (`explain`, `ask`, `next`, `prev`, `stop`) that call the LLM plugin directly (`llm.chat(chat_ctx=...).collect()`), fire TTS narration via `agent_session.say(text)` without awaiting playback, and return the generated text as the RPC response. The VS Code webview moves from a hidden `WebviewPanel` into a `WebviewViewProvider` sidebar that owns the LiveKit `Room`, issues `performRpc` calls, and renders each response as a markdown turn. The inline strip keeps only a status indicator.

**Tech Stack:** Python 3.12, `livekit-agents`, `livekit.rtc.rpc` (`register_rpc_method`, `perform_rpc`, `RpcError`, `RpcInvocationData`), TypeScript (strict), `livekit-client` v2 (`performRpc`, `RoomEvent.TrackSubscribed`), `marked` (pure-JS markdown renderer), `vscode.WebviewViewProvider`.

## Global Constraints

- `agent.py` must stay under 150 lines; new logic goes in a dedicated module (`AGENTS.md`).
- `session.py` must never import from `agent.py` — dependency stays one-directional (`AGENTS.md`).
- All public Python functions require type annotations (`AGENTS.md`, `STYLE.md`).
- No `print()` in Python — use `from loguru import logger` (`AGENTS.md`).
- All TypeScript must use `strict: true` and no `any` except where forced by the VS Code API (`AGENTS.md`).
- Paths sent over the protocol wire are always relative to workspace root (`AGENTS.md`).
- Never add a dependency requiring native compilation unless it ships pre-built wheels for Linux x86_64, macOS arm64, and Windows x86_64 (`AGENTS.md`) — `marked` is pure JS, no native step, satisfies this trivially.
- Any change to the message schema must bump `PROTOCOL_VERSION` in `core/src/breakdown/agent.py` and update `docs/protocol.md` (`AGENTS.md`).
- Commit messages use exactly one of `feat:`, `fix:`, `docs:`, `perf:`, `chore:`, `test:` — no other prefixes, no scope in parentheses unless it aids clarity (`AGENTS.md`).
- Codes `1001`–`1999` are reserved by LiveKit internally for `RpcError`; Breakdown's own error codes start at `2000` (verified against installed `livekit.rtc.rpc.RpcError`).
- `register_rpc_method`/`perform_rpc`/`RpcError`/`RpcInvocationData`/`LLMStream.collect()`/`AgentSession.say()` are real, verified APIs on the installed `livekit-agents`/`livekit-client` packages — no wrapper functions are to be invented in place of these.

---

## Task 1: `rpc_handlers.py` — dependencies bundle and pure handlers (`next`, `prev`, `stop`)

**Files:**
- Create: `core/src/breakdown/rpc_handlers.py`
- Test: `core/tests/unit/test_rpc_handlers.py`

**Interfaces:**
- Produces: `HandlerDeps` dataclass with fields `session: Session`, `session_path: Path`, `store: VectorStore`, `workspace_root: Path`, `settings: Settings`, `agent_session: AgentSession`, `llm: object`. Produces `async def handle_next(payload: str, deps: HandlerDeps) -> str`, `async def handle_prev(payload: str, deps: HandlerDeps) -> str`, `async def handle_stop(payload: str, deps: HandlerDeps) -> str`. All three take a JSON string payload and return a JSON string.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/unit/test_rpc_handlers.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from breakdown.config import Settings
from breakdown.rpc_handlers import (
    HandlerDeps,
    handle_next,
    handle_prev,
    handle_stop,
)
from breakdown.session import Session


class FakeAgentSession:
    def __init__(self) -> None:
        self.said: list[str] = []
        self.closed = False

    def say(self, text: str, allow_interruptions: bool = True) -> None:
        self.said.append(text)

    async def aclose(self) -> None:
        self.closed = True


def _make_deps(tmp_path: Path) -> HandlerDeps:
    session = Session(workspace_root=tmp_path)
    return HandlerDeps(
        session=session,
        session_path=tmp_path / "session.json",
        store=object(),  # type: ignore[arg-type]
        workspace_root=tmp_path,
        settings=Settings(),
        agent_session=FakeAgentSession(),  # type: ignore[arg-type]
        llm=object(),
    )


async def test_handle_next_increments_line_and_persists(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.session.current_file = "src/foo.py"
    deps.session.current_line = 5

    result = await handle_next("{}", deps)

    assert json.loads(result) == {"file": "src/foo.py", "line": 6}
    assert deps.session_path.exists()


async def test_handle_prev_decrements_line(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.session.current_file = "src/foo.py"
    deps.session.current_line = 5

    result = await handle_prev("{}", deps)

    assert json.loads(result) == {"file": "src/foo.py", "line": 4}


async def test_handle_prev_does_not_go_below_line_one(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.session.current_file = "src/foo.py"
    deps.session.current_line = 1

    result = await handle_prev("{}", deps)

    assert json.loads(result) == {"file": "src/foo.py", "line": 1}


async def test_handle_stop_closes_the_agent_session(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)

    result = await handle_stop("{}", deps)

    assert json.loads(result) == {"ok": True}
    assert deps.agent_session.closed is True  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && uv run pytest tests/unit/test_rpc_handlers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'breakdown.rpc_handlers'`

- [ ] **Step 3: Write the implementation**

Create `core/src/breakdown/rpc_handlers.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from livekit.agents import AgentSession  # type: ignore[import-untyped]

from breakdown.config import Settings
from breakdown.indexer.store import VectorStore
from breakdown.session import Session


@dataclass
class HandlerDeps:
    session: Session
    session_path: Path
    store: VectorStore
    workspace_root: Path
    settings: Settings
    agent_session: AgentSession
    llm: object


async def handle_next(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line += 1
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_prev(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line = max(1, deps.session.current_line - 1)
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_stop(payload: str, deps: HandlerDeps) -> str:
    await deps.agent_session.aclose()  # type: ignore[attr-defined]
    return json.dumps({"ok": True})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd core && uv run pytest tests/unit/test_rpc_handlers.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/rpc_handlers.py core/tests/unit/test_rpc_handlers.py
git commit -m "feat: add RPC handler dependencies bundle and next/prev/stop handlers"
```

---

## Task 2: `rpc_handlers.py` — `explain`/`ask` with real LLM-generated text

**Files:**
- Modify: `core/src/breakdown/rpc_handlers.py`
- Test: `core/tests/unit/test_rpc_handlers.py`

**Interfaces:**
- Consumes: `HandlerDeps` from Task 1.
- Produces: `RPC_ERROR_PROVIDER_FAILURE = 2001`, `RPC_ERROR_EMPTY_QUESTION = 2002` (module-level ints). `build_system_prompt(session: Session, context_chunks: list[str], window: str) -> str`. `async def index_context(store: VectorStore, file: str, line: int, workspace_root: Path, settings: Settings) -> tuple[list[str], str]`. `async def handle_explain(payload: str, deps: HandlerDeps) -> str`. `async def handle_ask(payload: str, deps: HandlerDeps) -> str`. Both raise `livekit.rtc.rpc.RpcError` on LLM failure or invalid input.

- [ ] **Step 1: Write the failing tests**

Append to `core/tests/unit/test_rpc_handlers.py` (add these imports to the top of the file, next to the existing ones):

```python
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from livekit.rtc.rpc import RpcError  # type: ignore[import-untyped]

from breakdown.rpc_handlers import handle_ask, handle_explain
```

Append these test doubles and tests at the bottom of the file:

```python
class FakeLLMStream:
    def __init__(self, text: str) -> None:
        self._text = text

    async def collect(self) -> SimpleNamespace:
        return SimpleNamespace(text=self._text)


class FailingLLMStream:
    async def collect(self) -> SimpleNamespace:
        raise RuntimeError("boom")


class FakeLLM:
    def __init__(self, text: str = "", fail: bool = False) -> None:
        self._text = text
        self._fail = fail
        self.chat_calls: list[object] = []

    def chat(self, *, chat_ctx: object) -> object:
        self.chat_calls.append(chat_ctx)
        if self._fail:
            return FailingLLMStream()
        return FakeLLMStream(self._text)


@patch("breakdown.rpc_handlers.index_context")
async def test_handle_explain_returns_generated_text(mock_index_context, tmp_path: Path) -> None:
    mock_index_context.return_value = ([], "42: def foo(): pass")
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM(text="This defines a no-op function.")

    result = await handle_explain(json.dumps({"file": "src/foo.py", "line": 42}), deps)

    data = json.loads(result)
    assert data == {"text": "This defines a no-op function.", "file": "src/foo.py", "line": 42}
    assert deps.session.current_file == "src/foo.py"
    assert deps.session.current_line == 42
    assert deps.agent_session.said == ["This defines a no-op function."]  # type: ignore[attr-defined]
    assert any(turn["role"] == "assistant" for turn in deps.session.history)


@patch("breakdown.rpc_handlers.index_context")
async def test_handle_explain_raises_rpc_error_on_llm_failure(mock_index_context, tmp_path: Path) -> None:
    mock_index_context.return_value = ([], "")
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM(fail=True)

    with pytest.raises(RpcError):
        await handle_explain(json.dumps({"file": "src/foo.py", "line": 1}), deps)


async def test_handle_ask_returns_answer_text(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM(text="It retries because the network can flake.")

    result = await handle_ask(json.dumps({"text": "why does this retry?"}), deps)

    data = json.loads(result)
    assert data == {"text": "It retries because the network can flake."}
    assert deps.agent_session.said == ["It retries because the network can flake."]  # type: ignore[attr-defined]


async def test_handle_ask_rejects_empty_text(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM()

    with pytest.raises(RpcError):
        await handle_ask(json.dumps({"text": ""}), deps)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd core && uv run pytest tests/unit/test_rpc_handlers.py -v`
Expected: FAIL with `ImportError: cannot import name 'handle_explain' from 'breakdown.rpc_handlers'`

- [ ] **Step 3: Write the implementation**

Replace the full contents of `core/src/breakdown/rpc_handlers.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from livekit.agents import AgentSession  # type: ignore[import-untyped]
from livekit.agents import llm as lk_llm  # type: ignore[import-untyped]
from livekit.rtc.rpc import RpcError  # type: ignore[import-untyped]
from loguru import logger

from breakdown.config import Settings
from breakdown.indexer.store import VectorStore
from breakdown.session import Session

RPC_ERROR_PROVIDER_FAILURE = 2001
RPC_ERROR_EMPTY_QUESTION = 2002


@dataclass
class HandlerDeps:
    session: Session
    session_path: Path
    store: VectorStore
    workspace_root: Path
    settings: Settings
    agent_session: AgentSession
    llm: object


def build_system_prompt(session: Session, context_chunks: list[str], window: str) -> str:
    ctx = "\n\n---\n\n".join(context_chunks) if context_chunks else "No additional context."
    return (
        "You are Breakdown, a voice-driven code explainer. "
        "Explain code clearly and concisely as if speaking to the developer who wrote it. "
        "Be direct. Do not say 'certainly' or 'of course'. "
        "When asked about a specific line, explain what it does and why it matters in context.\n\n"
        f"Codebase context:\n{ctx}\n\n"
        f"Current code window:\n{window}"
    )


async def index_context(
    store: VectorStore,
    file: str,
    line: int,
    workspace_root: Path,
    settings: Settings,
) -> tuple[list[str], str]:
    abs_path = workspace_root / file
    try:
        source_lines = abs_path.read_text(errors="replace").splitlines()
    except OSError:
        return [], ""

    half = settings.context_window_lines // 2
    start = max(0, line - 1 - half)
    end = min(len(source_lines), line - 1 + half)
    window = "\n".join(
        f"{i + 1}: {src}" for i, src in enumerate(source_lines[start:end], start=start)
    )

    try:
        from breakdown.indexer.embedder import create_embedder
        embedder = create_embedder(settings.embedding_provider, settings)
        query_emb = embedder.embed([source_lines[line - 1] if line <= len(source_lines) else ""])[0]
        chunks = store.search(query_emb, k=5)
        context = [c.text for c in chunks]
    except Exception as exc:
        logger.warning("Context retrieval failed: {}", exc)
        context = []

    return context, window


async def _generate_text(llm_plugin: object, system: str, question: str) -> str:
    chat_ctx = lk_llm.ChatContext()
    chat_ctx.add_message(role="system", content=system)
    chat_ctx.add_message(role="user", content=question)
    try:
        response = await llm_plugin.chat(chat_ctx=chat_ctx).collect()  # type: ignore[attr-defined]
    except Exception as exc:
        raise RpcError(RPC_ERROR_PROVIDER_FAILURE, f"LLM call failed: {exc}") from None
    return str(response.text)


def _last_system_prompt(session: Session) -> str:
    for turn in reversed(session.history):
        if turn["role"] == "system":
            return turn["content"]
    return (
        "You are Breakdown, a voice-driven code explainer. "
        "Answer clearly and concisely."
    )


async def handle_explain(payload: str, deps: HandlerDeps) -> str:
    data: dict[str, object] = json.loads(payload)
    file = str(data.get("file", ""))
    line = int(data.get("line", 1))  # type: ignore[arg-type]
    deps.session.current_file = file
    deps.session.current_line = line

    context, window = await index_context(
        deps.store, file, line, deps.workspace_root, deps.settings,
    )
    system = build_system_prompt(deps.session, context, window)
    deps.session.add_turn("system", system)
    budget = int(deps.settings.llm_context_window * deps.settings.history_budget_pct)
    deps.session.trim_to_budget(budget)

    question = f"Explain line {line} in {file}."
    deps.session.add_turn("user", question)

    text = await _generate_text(deps.llm, system, question)

    deps.session.add_turn("assistant", text)
    deps.session.save(deps.session_path)
    deps.agent_session.say(text, allow_interruptions=True)  # type: ignore[attr-defined]

    return json.dumps({"text": text, "file": file, "line": line})


async def handle_ask(payload: str, deps: HandlerDeps) -> str:
    data: dict[str, object] = json.loads(payload)
    text = str(data.get("text", ""))
    if not text:
        raise RpcError(RPC_ERROR_EMPTY_QUESTION, "Question text must not be empty")

    deps.session.add_turn("user", text)
    system = _last_system_prompt(deps.session)
    answer = await _generate_text(deps.llm, system, text)
    deps.session.add_turn("assistant", answer)
    deps.session.save(deps.session_path)
    deps.agent_session.say(answer, allow_interruptions=True)  # type: ignore[attr-defined]

    return json.dumps({"text": answer})


async def handle_next(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line += 1
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_prev(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line = max(1, deps.session.current_line - 1)
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_stop(payload: str, deps: HandlerDeps) -> str:
    await deps.agent_session.aclose()  # type: ignore[attr-defined]
    return json.dumps({"ok": True})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd core && uv run pytest tests/unit/test_rpc_handlers.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Type-check**

Run: `cd core && uv run basedpyright src/breakdown/rpc_handlers.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add core/src/breakdown/rpc_handlers.py core/tests/unit/test_rpc_handlers.py
git commit -m "feat: generate real explanation text for explain and ask RPC handlers"
```

---

## Task 3: `agent.py` — register RPC methods, remove DataPacket handling

**Files:**
- Modify: `core/src/breakdown/agent.py`

**Interfaces:**
- Consumes: `HandlerDeps`, `handle_explain`, `handle_ask`, `handle_next`, `handle_prev`, `handle_stop` from Tasks 1–2.
- Produces: `PROTOCOL_VERSION = 2` (module-level int, referenced by `docs/protocol.md`).

- [ ] **Step 1: Replace the full contents of `core/src/breakdown/agent.py`**

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Awaitable, Callable

from livekit import agents  # type: ignore[import-untyped]
from livekit.agents import Agent, AgentSession, RoomInputOptions  # type: ignore[import-untyped]
from livekit.rtc.rpc import RpcInvocationData  # type: ignore[import-untyped]

from breakdown.config import get_settings
from breakdown.indexer.store import create_store
from breakdown.providers.llm import create_llm
from breakdown.providers.tts import create_tts
from breakdown.rpc_handlers import (
    HandlerDeps,
    handle_ask,
    handle_explain,
    handle_next,
    handle_prev,
    handle_stop,
)
from breakdown.session import Session

# Bumped whenever the RPC method set or payload shapes change; see
# docs/protocol.md for the full history.
PROTOCOL_VERSION = 2


# Module-level function so livekit-agents can pickle it for worker subprocesses.
async def entrypoint(ctx: agents.JobContext) -> None:
    settings = get_settings()
    breakdown_dir = Path(os.environ.get("BREAKDOWN_DIR", ".breakdown"))
    workspace_root = breakdown_dir.parent
    store = create_store(settings.index_backend, breakdown_dir / "index")

    session = Session.load(breakdown_dir / "session.json") or Session(
        workspace_root=workspace_root
    )
    session_path = breakdown_dir / "session.json"

    llm = create_llm(settings)
    tts = create_tts(settings)
    agent_session = AgentSession(llm=llm, tts=tts)  # type: ignore[arg-type]

    deps = HandlerDeps(
        session=session,
        session_path=session_path,
        store=store,
        workspace_root=workspace_root,
        settings=settings,
        agent_session=agent_session,
        llm=llm,
    )

    def _register(
        method_name: str,
        handler: Callable[[str, HandlerDeps], Awaitable[str]],
    ) -> None:
        async def _wrapped(data: RpcInvocationData) -> str:
            return await handler(data.payload, deps)

        ctx.room.local_participant.register_rpc_method(method_name, _wrapped)  # type: ignore[attr-defined]

    _register("explain", handle_explain)
    _register("ask", handle_ask)
    _register("next", handle_next)
    _register("prev", handle_prev)
    _register("stop", handle_stop)

    await agent_session.start(  # type: ignore[attr-defined]
        agent=Agent(instructions="You are a helpful code explainer."),
        room=ctx.room,  # keyword-only in livekit-agents v1.6+
        room_input_options=RoomInputOptions(),
    )
```

- [ ] **Step 2: Confirm the line count is under the 150-line cap**

Run: `wc -l core/src/breakdown/agent.py`
Expected: fewer than 150 lines (the file above is ~68 lines)

- [ ] **Step 3: Run the full test suite**

Run: `cd core && uv run pytest`
Expected: all tests pass, including `test_rpc_handlers.py` from Tasks 1–2

- [ ] **Step 4: Type-check**

Run: `cd core && uv run basedpyright src/breakdown/agent.py`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add core/src/breakdown/agent.py
git commit -m "feat: register LiveKit RPC methods on the agent instead of parsing DataPackets"
```

---

## Task 4: `docs/protocol.md` — document protocol v2

**Files:**
- Modify: `docs/protocol.md`

**Interfaces:**
- Consumes: `PROTOCOL_VERSION = 2` from Task 3, the RPC method payload shapes defined in Tasks 1–2.

- [ ] **Step 1: Replace the full contents of `docs/protocol.md`**

```markdown
# Protocol Specification v2

This document is the authoritative reference for how a Breakdown platform
client talks to the Python core agent, over a LiveKit room using LiveKit's
built-in RPC methods for requests and a published audio track for narration.

## Connection Flow

1. Read `.breakdown/runtime.json` -- contains `port` and `livekit_url`.
2. `GET http://127.0.0.1:<port>/token?room=<room_name>` -- returns `{"token": "...", "url": "..."}`.
3. Connect to the LiveKit room using the token.
4. Wait for the agent's participant to publish its track (e.g. `RoomEvent.TrackSubscribed`)
   to learn its identity -- every RPC call needs it as `destinationIdentity`.
5. Call RPC methods against that identity as needed.

## Room Name

```
room_name = "breakdown-" + sha256(absolute_workspace_root)[:12]
```

The room name is deterministic. The same workspace root always produces the same room name.

## RPC Methods

All client-to-agent requests are LiveKit RPC calls: the client calls
`localParticipant.performRpc({ destinationIdentity, method, payload,
responseTimeout })` where `payload` is a JSON string and the return value is
a JSON string. The agent registers each method with
`local_participant.register_rpc_method(method_name, handler)`.

### explain

Request payload:
```json
{ "file": "src/foo.py", "line": 42 }
```
`file` must be relative to the workspace root. `line` is 1-indexed.

Response payload:
```json
{ "text": "This function retries the request...", "file": "src/foo.py", "line": 42 }
```
`text` is the full markdown explanation generated by the LLM. The agent also
narrates `text` over its published audio track via TTS -- narration starts
before the RPC response is returned and continues independently of it.

### ask

Request payload:
```json
{ "text": "why does this retry on failure?" }
```

Response payload:
```json
{ "text": "It retries because..." }
```
Same narration behavior as `explain`. There is no client-to-agent audio in
this protocol -- clients never publish a microphone track; all questions are
typed text.

### next / prev

Request payload: `{}` (empty object).

Response payload:
```json
{ "file": "src/foo.py", "line": 43 }
```

### stop

Request payload: `{}` (empty object).

Response payload:
```json
{ "ok": true }
```

## Errors

RPC handlers raise `livekit.rtc.rpc.RpcError(code, message)` on failure,
which surfaces as a rejected `performRpc()` promise on the client carrying
that `code`/`message`. Codes `1001`-`1999` are reserved by LiveKit
internally; Breakdown's own codes start at `2000`:

| Code | Meaning |
|------|---------|
| 2001 | The configured LLM provider call failed (rate limit, network error, etc.) |
| 2002 | `ask` was called with empty question text |

Clients should catch the rejected promise and show a non-blocking error
message with `message`.

## Audio

The agent publishes a LiveKit audio track carrying its TTS narration.
Clients subscribe to it and play it using whatever audio API is available on
their platform. Audio is never sent as an RPC payload.

## Changelog

- **v2** (current): replaced the DataPacket JSON envelope and the
  `status`/`position`/`transcript`/`error` push-message types with LiveKit
  RPC methods (`explain`, `ask`, `next`, `prev`, `stop`) and typed
  request/response payloads. The agent now generates and returns real
  explanation text instead of narrating the raw code line; the live-caption
  transcript stream (sourced from LiveKit's transcription of the agent's own
  TTS audio) is removed in favor of returning the agent's actual generated
  text directly.
- **v1**: initial DataPacket-based protocol.
```

- [ ] **Step 2: Commit**

```bash
git add docs/protocol.md
git commit -m "docs: rewrite protocol spec for RPC-based transport (v2)"
```

---

## Task 5: Message type shapes for RPC (extension-host + webview)

**Files:**
- Modify: `clients/vscode/extension-host/src/message_types.ts`
- Modify: `clients/vscode/webview/src/message_bridge.ts`

**Interfaces:**
- Produces: `HostToWebview` union with `{type: "connect", token, url, room}`, `{type: "disconnect"}`, `{type: "rpc", method: "explain"|"ask"|"next"|"prev"|"stop", payload: object}`. Produces `WebviewToHost` union with `{type: "ready"}`, `{type: "connected", participantId}`, `{type: "disconnected", reason}`, `{type: "error", message}`, `{type: "rpc_start", method}`, `{type: "rpc_end", method}`, `{type: "position", file, line}`.

- [ ] **Step 1: Replace `clients/vscode/extension-host/src/message_types.ts`**

```typescript
// clients/vscode/extension-host/src/message_types.ts
// Mirror of ../../webview/src/message_bridge types, kept in sync manually.
// The webview package uses DOM APIs so cannot be imported directly by the
// Node.js extension host (different rootDir and lib targets).

// Messages from extension host -> webview
export type HostToWebview =
  | { type: "connect"; token: string; url: string; room: string }
  | { type: "disconnect" }
  | {
      type: "rpc";
      method: "explain" | "ask" | "next" | "prev" | "stop";
      payload: object;
    };

// Messages from webview -> extension host
export type WebviewToHost =
  | { type: "ready" }
  | { type: "connected"; participantId: string }
  | { type: "disconnected"; reason: string }
  | { type: "error"; message: string }
  | { type: "rpc_start"; method: string }
  | { type: "rpc_end"; method: string }
  | { type: "position"; file: string; line: number };
```

- [ ] **Step 2: Replace the type exports at the top of `clients/vscode/webview/src/message_bridge.ts`**

Replace lines 1–15 of the file (the `HostToWebview`/`WebviewToHost` type declarations) with:

```typescript
// Messages from extension host -> webview
export type HostToWebview =
  | { type: "connect"; token: string; url: string; room: string }
  | { type: "disconnect" }
  | {
      type: "rpc";
      method: "explain" | "ask" | "next" | "prev" | "stop";
      payload: object;
    };

// Messages from webview -> extension host
export type WebviewToHost =
  | { type: "ready" }
  | { type: "connected"; participantId: string }
  | { type: "disconnected"; reason: string }
  | { type: "error"; message: string }
  | { type: "rpc_start"; method: string }
  | { type: "rpc_end"; method: string }
  | { type: "position"; file: string; line: number };
```

Leave the rest of the file (`declare function acquireVsCodeApi`, `createBridge`) unchanged.

- [ ] **Step 3: Type-check both packages**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: fails here because `commands.ts` and `webview_manager.ts` still reference the old `send_data`/`status`/`transcript` message shapes — this is expected until Tasks 9–10 update those files. Confirm the *only* errors reported are in `commands.ts` and `webview_manager.ts`.

Run: `cd clients/vscode/webview && npm run typecheck`
Expected: fails here because `index.ts` and `livekit_room.ts` still reference the old shapes — expected until Tasks 6–7. Confirm the *only* errors are in those two files.

- [ ] **Step 4: Commit**

```bash
git add clients/vscode/extension-host/src/message_types.ts clients/vscode/webview/src/message_bridge.ts
git commit -m "feat: replace DataPacket message shapes with RPC message types"
```

---

## Task 6: `livekit_room.ts` — `performRpc` replaces `sendData`

**Files:**
- Modify: `clients/vscode/webview/src/livekit_room.ts`

**Interfaces:**
- Consumes: `WebviewToHost` from Task 5.
- Produces: `class LiveKitRoom` with `connect(url, token): Promise<void>`, `performRpc(method: string, payload: object): Promise<string>`, `disconnect(): Promise<void>`.

- [ ] **Step 1: Replace the full contents of `clients/vscode/webview/src/livekit_room.ts`**

```typescript
// clients/vscode/webview/src/livekit_room.ts
import { Room, RoomEvent, Track, RemoteParticipant } from "livekit-client";
import { AudioPlayer } from "./audio_player";
import type { WebviewToHost } from "./message_bridge";

type SendFn = (msg: WebviewToHost) => void;

export class LiveKitRoom {
  private _room: Room;
  private _player: AudioPlayer;
  private _agentIdentity: string | null = null;

  constructor(private readonly _send: SendFn) {
    this._room = new Room();
    this._player = new AudioPlayer();
  }

  async connect(url: string, token: string): Promise<void> {
    this._room.on(
      RoomEvent.TrackSubscribed,
      (track, _pub, participant: RemoteParticipant) => {
        this._agentIdentity = participant.identity;
        if (track.kind === Track.Kind.Audio) {
          this._player.attachTrack(track.mediaStreamTrack);
        }
      },
    );

    this._room.on(RoomEvent.Disconnected, (reason) => {
      this._send({ type: "disconnected", reason: String(reason) });
      this._player.stop();
    });

    await this._room.connect(url, token);
    this._send({ type: "connected", participantId: this._room.localParticipant.sid });
  }

  async performRpc(method: string, payload: object): Promise<string> {
    if (!this._agentIdentity) {
      throw new Error("Breakdown agent is not connected yet.");
    }
    return this._room.localParticipant.performRpc({
      destinationIdentity: this._agentIdentity,
      method,
      payload: JSON.stringify(payload),
      responseTimeout: 15000,
    });
  }

  async disconnect(): Promise<void> {
    await this._room.disconnect();
    this._player.stop();
    this._agentIdentity = null;
  }
}
```

- [ ] **Step 2: Type-check**

Run: `cd clients/vscode/webview && npm run typecheck`
Expected: no errors from `livekit_room.ts`; `index.ts` still errors until Task 7

- [ ] **Step 3: Commit**

```bash
git add clients/vscode/webview/src/livekit_room.ts
git commit -m "feat: replace DataPacket sendData with LiveKit performRpc"
```

---

## Task 7: `chat_view.ts` markdown rendering + `index.ts` RPC routing

**Files:**
- Modify: `clients/vscode/webview/package.json`
- Create: `clients/vscode/webview/src/chat_view.ts`
- Modify: `clients/vscode/webview/src/index.ts`

**Interfaces:**
- Consumes: `LiveKitRoom.performRpc` from Task 6, `HostToWebview`/`WebviewToHost` from Task 5.
- Produces: `class ChatView` with `addExplainTurn(file: string, line: number, text: string): void` and `addAskTurn(question: string, text: string): void`, constructed with an `HTMLElement` container. Assumes the webview HTML shell (built in Task 9) contains `<div id="turns"></div>`.

- [ ] **Step 1: Add the `marked` dependency**

Modify `clients/vscode/webview/package.json`'s `dependencies` block:

```json
  "dependencies": {
    "livekit-client": "^2.4.0",
    "marked": "^12.0.0"
  }
```

Run: `cd clients/vscode/webview && npm install`
Expected: `marked` added to `node_modules` and `package-lock.json` (or `pnpm-lock.yaml`, matching whatever lockfile the workspace already uses — confirm with `ls clients/vscode/*.lock* clients/vscode/webview/*.lock*` first and use the matching install command, e.g. `pnpm install` if `pnpm-lock.yaml` is present at the workspace root).

- [ ] **Step 2: Create `clients/vscode/webview/src/chat_view.ts`**

```typescript
// clients/vscode/webview/src/chat_view.ts
import { marked } from "marked";

export class ChatView {
  constructor(private readonly _container: HTMLElement) {}

  addExplainTurn(file: string, line: number, text: string): void {
    this._append(`**${file}:${line}**\n\n${text}`);
  }

  addAskTurn(question: string, text: string): void {
    this._append(`**Q: ${question}**\n\n${text}`);
  }

  private _append(markdownSource: string): void {
    const el = document.createElement("div");
    el.className = "turn";
    el.innerHTML = marked.parse(markdownSource) as string;
    this._container.appendChild(el);
    el.scrollIntoView({ block: "end" });
  }
}
```

- [ ] **Step 3: Replace the full contents of `clients/vscode/webview/src/index.ts`**

```typescript
// clients/vscode/webview/src/index.ts
import { createBridge, type HostToWebview } from "./message_bridge";
import { LiveKitRoom } from "./livekit_room";
import { ChatView } from "./chat_view";

const bridge = createBridge();
let room: LiveKitRoom | null = null;

const container = document.getElementById("turns");
if (!container) {
  throw new Error("Breakdown webview: #turns container missing from HTML shell.");
}
const chatView = new ChatView(container);

bridge.send({ type: "ready" });

bridge.onMessage(async (msg: HostToWebview) => {
  if (msg.type === "connect") {
    room = new LiveKitRoom(bridge.send);
    try {
      await room.connect(msg.url, msg.token);
    } catch (err) {
      bridge.send({ type: "error", message: String(err) });
    }
    return;
  }

  if (msg.type === "disconnect") {
    await room?.disconnect();
    room = null;
    return;
  }

  if (msg.type === "rpc") {
    if (!room) {
      bridge.send({ type: "error", message: "Breakdown: not connected." });
      return;
    }
    bridge.send({ type: "rpc_start", method: msg.method });
    try {
      const raw = await room.performRpc(msg.method, msg.payload);
      const data = JSON.parse(raw) as { text?: string; file?: string; line?: number };
      if (msg.method === "explain" && data.text !== undefined) {
        chatView.addExplainTurn(data.file ?? "", data.line ?? 0, data.text);
      } else if (msg.method === "ask" && data.text !== undefined) {
        const question =
          "text" in msg.payload ? String((msg.payload as { text: string }).text) : "";
        chatView.addAskTurn(question, data.text);
      } else if ((msg.method === "next" || msg.method === "prev") && data.file !== undefined) {
        bridge.send({ type: "position", file: data.file, line: data.line ?? 0 });
      }
    } catch (err) {
      bridge.send({ type: "error", message: String(err) });
    } finally {
      bridge.send({ type: "rpc_end", method: msg.method });
    }
    return;
  }
});
```

- [ ] **Step 4: Type-check**

Run: `cd clients/vscode/webview && npm run typecheck`
Expected: no errors

- [ ] **Step 5: Build the webview bundle**

Run: `cd clients/vscode/webview && npm run build`
Expected: `../extension-host/dist/webview.js` produced without errors

- [ ] **Step 6: Commit**

```bash
git add clients/vscode/webview/package.json clients/vscode/webview/package-lock.json clients/vscode/webview/src/chat_view.ts clients/vscode/webview/src/index.ts
git commit -m "feat: render RPC explain/ask responses as markdown turns in the webview"
```

---

## Task 8: Inline strip — status only, drop live transcript

**Files:**
- Modify: `clients/vscode/extension-host/src/inline_strip_manager.ts`
- Modify: `clients/vscode/extension-host/src/inline_strip_manager.test.ts`

**Interfaces:**
- Produces: `class InlineStripManager` unchanged public surface except `updateTranscript` is removed. `show(line)`, `moveTo(line)`, `updateStatus(status)`, `dismiss()`, `isVisible`, `visibleLine` all keep their existing signatures.

- [ ] **Step 1: Update the failing test — remove the transcript test, update rendered text expectations**

Replace the full contents of `clients/vscode/extension-host/src/inline_strip_manager.test.ts`:

```typescript
// clients/vscode/extension-host/src/inline_strip_manager.test.ts
import assert from "node:assert/strict";
import { InlineStripManager, type StripDecorator } from "./inline_strip_manager";

class FakeDecorator implements StripDecorator {
  calls: Array<{ op: "set"; line: number; text: string } | { op: "clear" }> = [];

  setDecoration(line: number, text: string): void {
    this.calls.push({ op: "set", line, text });
  }

  clearDecoration(): void {
    this.calls.push({ op: "clear" });
  }
}

function makeManager() {
  const decorator = new FakeDecorator();
  const contextCalls: Array<{ key: string; value: boolean }> = [];
  const manager = new InlineStripManager(decorator, (key, value) => {
    contextCalls.push({ key, value });
  });
  return { manager, decorator, contextCalls };
}

describe("InlineStripManager", () => {
  it("is not visible before show() is called", () => {
    const { manager } = makeManager();
    assert.equal(manager.isVisible, false);
    assert.equal(manager.visibleLine, null);
  });

  it("show() sets the context key, marks visible, and renders the initial status", () => {
    const { manager, decorator, contextCalls } = makeManager();
    manager.show(5);
    assert.equal(manager.isVisible, true);
    assert.equal(manager.visibleLine, 5);
    assert.deepEqual(contextCalls, [{ key: "breakdown.stripVisible", value: true }]);
    assert.deepEqual(decorator.calls, [{ op: "set", line: 5, text: "explaining…" }]);
  });

  it("moveTo() replaces the decoration at the new line instead of stacking", () => {
    const { manager, decorator } = makeManager();
    manager.show(5);
    manager.moveTo(10);
    assert.equal(manager.visibleLine, 10);
    assert.deepEqual(decorator.calls, [
      { op: "set", line: 5, text: "explaining…" },
      { op: "set", line: 10, text: "explaining…" },
    ]);
  });

  it("moveTo() is a no-op when the strip is not visible", () => {
    const { manager, decorator } = makeManager();
    manager.moveTo(10);
    assert.equal(manager.isVisible, false);
    assert.deepEqual(decorator.calls, []);
  });

  it("updateStatus() re-renders with the new status while visible", () => {
    const { manager, decorator } = makeManager();
    manager.show(5);
    manager.updateStatus("idle");
    assert.deepEqual(decorator.calls[1], { op: "set", line: 5, text: "idle…" });
  });

  it("updateStatus() is a no-op when the strip is not visible", () => {
    const { manager, decorator } = makeManager();
    manager.updateStatus("idle");
    assert.deepEqual(decorator.calls, []);
  });

  it("dismiss() clears the decoration, resets the context key, and hides the strip", () => {
    const { manager, decorator, contextCalls } = makeManager();
    manager.show(5);
    manager.dismiss();
    assert.equal(manager.isVisible, false);
    assert.equal(manager.visibleLine, null);
    assert.deepEqual(contextCalls, [
      { key: "breakdown.stripVisible", value: true },
      { key: "breakdown.stripVisible", value: false },
    ]);
    assert.deepEqual(decorator.calls[1], { op: "clear" });
  });

  it("show() on a second line after dismiss() starts a fresh render", () => {
    const { manager, decorator } = makeManager();
    manager.show(5);
    manager.dismiss();
    manager.show(7);
    assert.deepEqual(decorator.calls[2], { op: "set", line: 7, text: "explaining…" });
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd clients/vscode/extension-host && npm test`
Expected: FAIL — `updateStatus("idle")` currently renders `"explaining… "` prefix logic incorrectly / `updateTranscript` still exists and old text-concatenation logic doesn't match `"idle…"`

- [ ] **Step 3: Replace the full contents of `clients/vscode/extension-host/src/inline_strip_manager.ts`**

```typescript
// clients/vscode/extension-host/src/inline_strip_manager.ts
// Mirrors the status.state literal union in ./message_types.ts, kept as a
// manual copy in the same style that file already uses for the webview types.
export type StripStatus = "idle" | "explaining" | "listening" | "interrupted";

export interface StripDecorator {
  setDecoration(line: number, text: string): void;
  clearDecoration(): void;
}

export type ContextSetter = (key: string, value: boolean) => void;

const CONTEXT_KEY = "breakdown.stripVisible";

export class InlineStripManager {
  private _visibleLine: number | null = null;
  private _status: StripStatus = "explaining";

  constructor(
    private readonly _decorator: StripDecorator,
    private readonly _setContext: ContextSetter,
  ) {}

  get isVisible(): boolean {
    return this._visibleLine !== null;
  }

  get visibleLine(): number | null {
    return this._visibleLine;
  }

  show(line: number): void {
    this._visibleLine = line;
    this._status = "explaining";
    this._setContext(CONTEXT_KEY, true);
    this._render();
  }

  moveTo(line: number): void {
    if (this._visibleLine === null) {
      return;
    }
    this._visibleLine = line;
    this._render();
  }

  updateStatus(status: StripStatus): void {
    if (this._visibleLine === null) {
      return;
    }
    this._status = status;
    this._render();
  }

  dismiss(): void {
    this._visibleLine = null;
    this._status = "explaining";
    this._setContext(CONTEXT_KEY, false);
    this._decorator.clearDecoration();
  }

  private _render(): void {
    if (this._visibleLine === null) {
      return;
    }
    this._decorator.setDecoration(this._visibleLine, `${this._status}…`);
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd clients/vscode/extension-host && npm test`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/extension-host/src/inline_strip_manager.ts clients/vscode/extension-host/src/inline_strip_manager.test.ts
git commit -m "feat: simplify inline strip to a status indicator, drop live transcript"
```

---

## Task 9: `ChatViewProvider` sidebar replaces the hidden webview panel

**Files:**
- Create: `clients/vscode/extension-host/src/chat_view_provider.ts`
- Create: `clients/vscode/extension-host/media/icon.svg`
- Delete: `clients/vscode/extension-host/src/webview_manager.ts`
- Modify: `clients/vscode/extension-host/package.json`
- Modify: `clients/vscode/extension-host/src/extension.ts`

**Interfaces:**
- Consumes: `HostToWebview`/`WebviewToHost` from Task 5, `InlineStripManager` from Task 8.
- Produces: `VIEW_ID = "breakdown.chatView"` (exported const). `class ChatViewProvider implements vscode.WebviewViewProvider` with `connect(token: string, url: string, room: string): void`, `send(msg: HostToWebview): void`, `isConnected(): boolean`, `dispose(): void`.

- [ ] **Step 1: Create the activity bar icon**

Create `clients/vscode/extension-host/media/icon.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
  <path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H6.5L3 14v-3H3a1 1 0 0 1-1-1V3z"/>
</svg>
```

- [ ] **Step 2: Create `clients/vscode/extension-host/src/chat_view_provider.ts`**

```typescript
// clients/vscode/extension-host/src/chat_view_provider.ts
import * as vscode from "vscode";
import * as path from "path";
import type { HostToWebview, WebviewToHost } from "./message_types";
import type { InlineStripManager } from "./inline_strip_manager";

export const VIEW_ID = "breakdown.chatView";

export class ChatViewProvider implements vscode.WebviewViewProvider {
  private _view: vscode.WebviewView | null = null;
  private _pendingConnect: { token: string; url: string; room: string } | null = null;
  private _connected = false;
  private readonly _statusBar: vscode.StatusBarItem;

  constructor(
    private readonly _context: vscode.ExtensionContext,
    private readonly _inlineStrip: InlineStripManager,
  ) {
    this._statusBar = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100,
    );
    this._statusBar.text = "$(unmute) Breakdown: inactive";
    this._statusBar.command = "breakdown.startSession";
    this._statusBar.show();
  }

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.file(path.join(this._context.extensionPath, "dist")),
      ],
    };

    const webviewScriptUri = webviewView.webview.asWebviewUri(
      vscode.Uri.file(path.join(this._context.extensionPath, "dist", "webview.js")),
    );

    const nonce = getNonce();
    const csp = [
      `default-src 'none'`,
      `style-src 'unsafe-inline'`,
      `script-src 'nonce-${nonce}'`,
      `connect-src wss: https: ws://localhost:* http://localhost:*`,
      `media-src *`,
    ].join("; ");

    webviewView.webview.html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <title>Breakdown</title>
  <style>
    body { font-family: var(--vscode-font-family); padding: 0 8px; }
    .turn { margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--vscode-panel-border); }
    .turn pre { background: var(--vscode-textCodeBlock-background); padding: 6px; overflow-x: auto; }
  </style>
</head>
<body>
<div id="turns"></div>
<script nonce="${nonce}" src="${webviewScriptUri}"></script>
</body>
</html>`;

    webviewView.webview.onDidReceiveMessage((msg: WebviewToHost) => {
      if (msg.type === "ready") {
        if (this._pendingConnect) {
          this.send({ type: "connect", ...this._pendingConnect });
          this._pendingConnect = null;
        }
      } else if (msg.type === "connected") {
        this._connected = true;
        this._statusBar.text = "$(unmute) Breakdown: connected";
      } else if (msg.type === "disconnected") {
        this._connected = false;
        this._statusBar.text = "$(unmute) Breakdown: inactive";
      } else if (msg.type === "rpc_start") {
        this._statusBar.text = "$(loading~spin) Breakdown: explaining";
        this._inlineStrip.updateStatus("explaining");
      } else if (msg.type === "rpc_end") {
        this._statusBar.text = this._connected
          ? "$(unmute) Breakdown: connected"
          : "$(unmute) Breakdown: inactive";
        this._inlineStrip.updateStatus("idle");
      } else if (msg.type === "position") {
        this._inlineStrip.moveTo(msg.line);
      } else if (msg.type === "error") {
        vscode.window.showErrorMessage(`Breakdown: ${msg.message}`);
      }
    });
  }

  connect(token: string, url: string, room: string): void {
    if (this._view) {
      this.send({ type: "disconnect" });
      this.send({ type: "connect", token, url, room });
    } else {
      this._pendingConnect = { token, url, room };
    }
    void vscode.commands.executeCommand(`${VIEW_ID}.focus`);
  }

  send(msg: HostToWebview): void {
    this._view?.webview.postMessage(msg);
  }

  isConnected(): boolean {
    return this._connected;
  }

  dispose(): void {
    this._statusBar.dispose();
  }
}

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}
```

- [ ] **Step 3: Delete `clients/vscode/extension-host/src/webview_manager.ts`**

```bash
git rm clients/vscode/extension-host/src/webview_manager.ts
```

- [ ] **Step 4: Add the view container and view contribution to `clients/vscode/extension-host/package.json`**

Add this new top-level key inside `"contributes"`, alongside the existing `"commands"` and `"keybindings"` arrays:

```json
    "viewsContainers": {
      "activitybar": [
        { "id": "breakdown", "title": "Breakdown", "icon": "media/icon.svg" }
      ]
    },
    "views": {
      "breakdown": [
        { "id": "breakdown.chatView", "name": "Breakdown", "type": "webview" }
      ]
    },
```

- [ ] **Step 5: Rewrite `clients/vscode/extension-host/src/extension.ts`**

```typescript
// clients/vscode/extension-host/src/extension.ts
import * as vscode from "vscode";
import { ProcessManager } from "./process_manager";
import { ChatViewProvider, VIEW_ID } from "./chat_view_provider";
import { registerCommands } from "./commands";
import { InlineStripManager } from "./inline_strip_manager";
import { DecorationHostAdapter } from "./inline_strip_decorator";

let _processManager: ProcessManager | null = null;
let _chatViewProvider: ChatViewProvider | null = null;
let _decorationAdapter: DecorationHostAdapter | null = null;

export function activate(context: vscode.ExtensionContext): void {
  // Warn if running in a remote environment where audio won't work
  const isRemote =
    process.env["REMOTE_CONTAINERS"] ||
    process.env["CODESPACES"] ||
    vscode.env.remoteName;

  if (isRemote) {
    vscode.window.showWarningMessage(
      "Breakdown: audio playback requires a local VS Code window. " +
        "Remote development is not currently supported.",
    );
  }

  _decorationAdapter = new DecorationHostAdapter();
  const inlineStripManager = new InlineStripManager(_decorationAdapter, (key, value) =>
    vscode.commands.executeCommand("setContext", key, value),
  );

  _processManager = new ProcessManager();
  _chatViewProvider = new ChatViewProvider(context, inlineStripManager);

  const disposables = [
    vscode.window.registerWebviewViewProvider(VIEW_ID, _chatViewProvider),
    ...registerCommands(context, _chatViewProvider, _processManager, inlineStripManager),
  ];
  context.subscriptions.push(...disposables, _chatViewProvider);
}

export function deactivate(): void {
  _processManager?.stop();
  _chatViewProvider?.dispose();
  _decorationAdapter?.dispose();
}
```

- [ ] **Step 6: Note this will not compile until Task 10 updates `commands.ts`**

`registerCommands` in `commands.ts` still expects a `WebviewManager` parameter type; this is resolved in Task 10. Do not run `npm run typecheck` as a pass/fail gate yet.

- [ ] **Step 7: Commit**

```bash
git add clients/vscode/extension-host/src/chat_view_provider.ts clients/vscode/extension-host/media/icon.svg clients/vscode/extension-host/package.json clients/vscode/extension-host/src/extension.ts
git commit -m "feat: add Breakdown sidebar chat view, replacing the hidden webview panel"
```

---

## Task 10: `commands.ts` — route through `ChatViewProvider`

**Files:**
- Modify: `clients/vscode/extension-host/src/commands.ts`

**Interfaces:**
- Consumes: `ChatViewProvider` from Task 9 (`connect`, `send`, `isConnected`).

- [ ] **Step 1: Replace the full contents of `clients/vscode/extension-host/src/commands.ts`**

```typescript
// clients/vscode/extension-host/src/commands.ts
import * as vscode from "vscode";
import * as path from "path";
import { getToken, getTokenWithRetry, readRuntimeInfo } from "./token_client";
import { ProcessManager } from "./process_manager";
import type { ChatViewProvider } from "./chat_view_provider";
import type { InlineStripManager } from "./inline_strip_manager";

function workspaceRoot(): string | null {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    return null;
  }
  if (folders.length === 1) {
    return folders[0].uri.fsPath;
  }
  // multi-root: pick first; future enhancement to prompt
  return folders[0].uri.fsPath;
}

function activeLineInfo(): { file: string; line: number } | null {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return null;
  }
  const wsRoot = workspaceRoot();
  if (!wsRoot) {
    return null;
  }
  const rel = path.relative(wsRoot, editor.document.uri.fsPath);
  const line = editor.selection.active.line + 1;
  return { file: rel, line };
}

export function registerCommands(
  ctx: vscode.ExtensionContext,
  chatView: ChatViewProvider,
  processManager: ProcessManager,
  inlineStripManager: InlineStripManager,
): vscode.Disposable[] {
  return [
    vscode.commands.registerCommand("breakdown.startSession", async () => {
      const root = workspaceRoot();
      if (!root) {
        vscode.window.showErrorMessage("Breakdown: open a workspace folder first.");
        return;
      }
      const breakdownDir = path.join(root, ".breakdown");

      // Only spawn a new agent if one isn't already responding.
      // Spawning when a server exists overwrites runtime.json with a new port
      // and the extension times out waiting for the replacement to start.
      const existing = readRuntimeInfo(breakdownDir);
      let alreadyRunning = false;
      if (existing) {
        try {
          await getToken(existing.port);
          alreadyRunning = true;
        } catch {
          // not running — fall through to spawn
        }
      }
      if (!alreadyRunning) {
        processManager.start(root);
      }

      try {
        // 20 attempts × 500 ms = 10 s, enough for a cold agent start (~8 s)
        const { token, url, room } = await getTokenWithRetry(breakdownDir, 20, 500);
        chatView.connect(token, url, room);
      } catch (err) {
        vscode.window.showErrorMessage(`Breakdown: ${String(err)}`);
      }
    }),

    vscode.commands.registerCommand("breakdown.stopSession", () => {
      chatView.send({ type: "disconnect" });
      inlineStripManager.dismiss();
      processManager.stop();
    }),

    vscode.commands.registerCommand("breakdown.explainLine", () => {
      const info = activeLineInfo();
      if (!info) { return; }
      if (!chatView.isConnected()) {
        vscode.window.showErrorMessage(
          "Breakdown: start a session first (Ctrl+K Ctrl+E / Cmd+K Cmd+E).",
        );
        return;
      }
      inlineStripManager.show(info.line);
      chatView.send({ type: "rpc", method: "explain", payload: info });
    }),

    vscode.commands.registerCommand("breakdown.nextLine", () => {
      chatView.send({ type: "rpc", method: "next", payload: {} });
    }),

    vscode.commands.registerCommand("breakdown.prevLine", () => {
      chatView.send({ type: "rpc", method: "prev", payload: {} });
    }),

    vscode.commands.registerCommand("breakdown.askQuestion", async () => {
      if (!chatView.isConnected()) {
        vscode.window.showErrorMessage(
          "Breakdown: start a session first (Ctrl+K Ctrl+E / Cmd+K Cmd+E).",
        );
        return;
      }
      const text = await vscode.window.showInputBox({
        prompt: "Ask Breakdown a question",
        placeHolder: "e.g. Why does this function retry on failure?",
      });
      if (!text) {
        return;
      }
      chatView.send({ type: "rpc", method: "ask", payload: { text } });
    }),

    vscode.commands.registerCommand("breakdown.dismissInlineStrip", () => {
      inlineStripManager.dismiss();
    }),
  ];
}
```

Note: `chatView.isConnected()` now reflects the real LiveKit connection state (`true` only after the webview reports a `connected` message), rather than the previous `WebviewManager.isConnected()` which just checked whether the hidden panel object existed. This is a correctness improvement — RPC calls cannot succeed until the agent's identity has been captured on `TrackSubscribed` (Task 6), so gating on a merely-existing-but-not-yet-connected view would let users fire RPCs before the transport is ready.

- [ ] **Step 2: Type-check the full extension-host package**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Run the extension-host test suite**

Run: `cd clients/vscode/extension-host && npm test`
Expected: PASS (all `inline_strip_manager.test.ts` tests from Task 8)

- [ ] **Step 4: Build both packages**

Run: `cd clients/vscode/webview && npm run build`
Run: `cd clients/vscode/extension-host && npm run build`
Expected: both succeed; `clients/vscode/extension-host/dist/extension.js` and `dist/webview.js` exist

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/extension-host/src/commands.ts
git commit -m "feat: route explain/ask/next/prev commands through ChatViewProvider RPC calls"
```

---

## Task 11: Manual verification in the Extension Development Host

**Files:** none (verification only)

- [ ] **Step 1: Launch the local stack**

```bash
# Terminal 1
docker compose -f deploy/docker-compose.livekit.yml up
# Terminal 2
cd core && uv run breakdown index ..
# Terminal 3
cd core && uv run breakdown start ..
```

- [ ] **Step 2: Launch the Extension Development Host**

Open `clients/vscode/extension-host` in VS Code and press F5 (or run `code --extensionDevelopmentPath=clients/vscode/extension-host <test-workspace>` if driving from the CLI).

- [ ] **Step 3: Verify the sidebar appears**

Click the Breakdown icon in the Activity Bar. Confirm the "Breakdown" view opens showing an empty turn list (the `#turns` div).

- [ ] **Step 4: Verify `explain` produces a real markdown turn plus narration**

Run `Breakdown: Start Session` (`Ctrl+K Ctrl+E`). Open a file with a multi-line function, place the cursor on a line inside it, run `Breakdown: Explain Line` (`Ctrl+Alt+I`). Confirm:
- The inline strip shows `explaining…` then returns to no visible caption text (status-only).
- The sidebar shows a new turn with the file:line heading and a real explanation of the code (not just the raw line echoed back) — if the explained line is inside a function, the explanation should reference the function's behavior.
- Narration audio plays.

- [ ] **Step 5: Verify `ask` renders a Q/A turn**

Run `Breakdown: Ask a Question` (`Ctrl+K Ctrl+Space`), type a question, confirm a new turn appears in the sidebar with the question and a generated answer, and audio narrates it.

- [ ] **Step 6: Verify `next`/`prev` move the inline strip without a separate position packet**

With the strip visible, run `Breakdown: Next Line` / `Breakdown: Previous Line`, confirm the strip moves to the adjacent line.

- [ ] **Step 7: Verify error surfacing**

Stop the Python agent process (Ctrl+C in Terminal 3) while the extension still thinks it's connected, then run `Breakdown: Explain Line` again. Confirm a VS Code error notification appears (from the rejected `performRpc` promise / `LiveKitRoom.performRpc` timeout), not a silent failure.

- [ ] **Step 8: Confirm no stale references remain**

Run: `grep -rn "TranscriptionReceived\|send_data\|DataPacket_Kind" clients/vscode/webview/src clients/vscode/extension-host/src`
Expected: no matches

Run: `grep -n "getUserMedia" clients/vscode/extension-host/dist/webview.js`
Expected: no matches (confirms the earlier voice-input removal is still intact and nothing reintroduced it)

- [ ] **Step 9: Final commit (if any cleanup was needed during verification)**

```bash
git status
# only commit here if Step 8 or manual testing surfaced a fix; otherwise this task produces no commit
```
