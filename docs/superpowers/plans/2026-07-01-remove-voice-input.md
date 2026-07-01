# Remove Voice Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all microphone/voice-input capture (a VS Code platform limitation with no permission-grant mechanism) and replace it with a typed-question command, while leaving the agent's spoken (TTS) explanations completely unchanged.

**Architecture:** Three independent layers, each removable/addable without touching the others: the Python agent drops its STT provider and gains a new `ask` data-channel handler that calls `AgentSession.generate_reply(user_input=...)`; the webview drops all `getUserMedia()`/mic-track-publishing code; the extension host replaces the never-fully-wired `pushToTalk` stub with a real `askQuestion` command built on `vscode.window.showInputBox()`.

**Tech Stack:** Python (`livekit-agents`, `pydantic-settings`), TypeScript (VS Code Extension API, `livekit-client`).

## Global Constraints

- `agent.py` must stay under 150 lines (from `AGENTS.md`); if it grows beyond that, new logic belongs in a dedicated module. Check the line count after Task 1's edits.
- `strict: true` TypeScript; no `any` except where forced by the VS Code API (from prior plan's Global Constraints, still binding).
- Conventional commits only: `feat:`, `fix:`, `docs:`, `perf:`, `chore:`, `test:`, no scope in parentheses (from `AGENTS.md`).
- All public Python functions require type annotations; no `print()` — use `from loguru import logger` (from `AGENTS.md`).
- Every Python file (including test files) starts with `from __future__ import annotations` (established project convention).
- The background LiveKit webview panel, the `Ctrl+Alt+I` explain flow, `next`/`prev` navigation, and the TTS/transcript pipeline are all unchanged by this plan — do not modify `inline_strip_manager.ts`, `inline_strip_decorator.ts`, or the `position`/`transcript`/`status` message routing in `webview_manager.ts`.

---

### Task 1: Remove STT from the Python agent, add the `ask` data-channel handler

**Files:**
- Delete: `core/src/breakdown/providers/stt.py`
- Modify: `core/src/breakdown/agent.py` (full file, shown below)
- Modify: `core/src/breakdown/config.py:42-44` (remove the STT section)
- Modify: `core/.env`
- Modify: `core/.env.example`
- Test: `core/tests/unit/test_config.py`

**Interfaces:**
- Consumes: `AgentSession.generate_reply(*, user_input: str) -> SpeechHandle` (confirmed present on the installed `livekit-agents` version — same object `agent_session.say(...)` and `agent_session.aclose()` already call elsewhere in this file).
- Produces: no new Python-side interface; the `ask` data-channel message shape (`{type: "ask", text: string}`) is consumed by Task 3's new `askQuestion` command, which sends it via the existing generic `{type: "send_data", payload: {...}}` mechanism (already untyped as `payload: object` on the TypeScript side — no message-type changes needed there).

- [ ] **Step 1: Write the failing regression test**

Open `core/tests/unit/test_config.py` and add this test at the end of the file:

```python
def test_settings_has_no_stt_provider() -> None:
    s = Settings()
    assert not hasattr(s, "stt_provider")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd core && uv run pytest tests/unit/test_config.py::test_settings_has_no_stt_provider -v`
Expected: FAIL with `AssertionError` (because `stt_provider` still exists on `Settings`)

- [ ] **Step 3: Remove the STT section from `config.py`**

In `core/src/breakdown/config.py`, `deepgram_api_key` is currently declared under the `# STT` section (lines 42-44) even though `providers/tts.py` also reads it when `tts_provider == "deepgram"`. Since STT is being removed entirely, move `deepgram_api_key` into the `# TTS` block above it and delete the `# STT` header and `stt_provider` field.

Replace this (the `# TTS` block immediately followed by the `# STT` block):

```python
    # TTS
    tts_provider: Literal["openai", "elevenlabs", "deepgram"] = "openai"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "Rachel"
    deepgram_tts_model: str = "aura-2-andromeda-en"

    # STT
    stt_provider: Literal["openai", "deepgram"] = "openai"
    deepgram_api_key: str = ""
```

with:

```python
    # TTS
    tts_provider: Literal["openai", "elevenlabs", "deepgram"] = "openai"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "Rachel"
    deepgram_tts_model: str = "aura-2-andromeda-en"
    deepgram_api_key: str = ""
```

The blank line and `# Embeddings` section that follow are unaffected.

- [ ] **Step 4: Delete the STT provider module**

```bash
rm core/src/breakdown/providers/stt.py
```

- [ ] **Step 5: Rewrite `agent.py`**

Replace the full contents of `core/src/breakdown/agent.py`:

```python
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from livekit import agents  # type: ignore[import-untyped]
from livekit.agents import Agent, AgentSession, RoomInputOptions  # type: ignore[import-untyped]
from loguru import logger

from breakdown.config import Settings, get_settings
from breakdown.indexer.store import VectorStore, create_store
from breakdown.providers.llm import create_llm
from breakdown.providers.tts import create_tts
from breakdown.session import Session


def _build_system_prompt(session: Session, context_chunks: list[str], window: str) -> str:
    ctx = "\n\n---\n\n".join(context_chunks) if context_chunks else "No additional context."
    return (
        "You are Breakdown, a voice-driven code explainer. "
        "Explain code clearly and concisely as if speaking to the developer who wrote it. "
        "Be direct. Do not say 'certainly' or 'of course'. "
        "When asked about a specific line, explain what it does and why it matters in context.\n\n"
        f"Codebase context:\n{ctx}\n\n"
        f"Current code window:\n{window}"
    )


async def _index_context(
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

    async def _handle_data(packet: object) -> None:
        try:
            msg: dict[str, object] = json.loads(getattr(packet, "data", b"{}"))
        except Exception:
            return

        msg_type: str = str(msg.get("type", ""))

        if msg_type == "explain":
            session.current_file = str(msg.get("file", ""))
            session.current_line = int(msg.get("line", 1))  # type: ignore[arg-type]
            context, window = await _index_context(
                store, session.current_file, session.current_line, workspace_root, settings,
            )
            system = _build_system_prompt(session, context, window)
            session.add_turn("system", system)
            budget = int(settings.llm_context_window * settings.history_budget_pct)
            session.trim_to_budget(budget)
            mid = settings.context_window_lines // 2
            window_lines = window.split("\n")
            target_line = window_lines[mid] if window and mid < len(window_lines) else ""
            await agent_session.say(  # type: ignore[attr-defined]
                f"Line {session.current_line}: {target_line}", allow_interruptions=True,
            )
            session.add_turn("user", f"Explain line {session.current_line}: {target_line}")
            session.save(session_path)

        elif msg_type == "ask":
            text = str(msg.get("text", ""))
            if text:
                session.add_turn("user", text)
                await agent_session.generate_reply(user_input=text)  # type: ignore[attr-defined]
                session.save(session_path)

        elif msg_type == "next":
            session.current_line += 1
            payload = json.dumps(
                {"v": 1, "type": "position", "file": session.current_file, "line": session.current_line}
            ).encode()
            await ctx.room.local_participant.publish_data(payload)  # type: ignore[attr-defined]
            session.save(session_path)

        elif msg_type == "prev":
            session.current_line = max(1, session.current_line - 1)
            payload = json.dumps(
                {"v": 1, "type": "position", "file": session.current_file, "line": session.current_line}
            ).encode()
            await ctx.room.local_participant.publish_data(payload)  # type: ignore[attr-defined]
            session.save(session_path)

        elif msg_type == "stop":
            await agent_session.aclose()  # type: ignore[attr-defined]

    # room.on() requires a sync callback; schedule the async work as a task.
    def on_data(packet: object) -> None:
        asyncio.create_task(_handle_data(packet))

    ctx.room.on("data_received", on_data)  # type: ignore[attr-defined]
    await agent_session.start(  # type: ignore[attr-defined]
        agent=Agent(instructions="You are a helpful code explainer."),
        room=ctx.room,  # keyword-only in livekit-agents v1.6+
        room_input_options=RoomInputOptions(),
    )
```

- [ ] **Step 6: Update `core/.env`**

`core/.env` currently has a `# STT` section containing both `STT_PROVIDER=deepgram` and a `DEEPGRAM_API_KEY=...` line. The API key line must be **kept** (TTS uses the same key when `TTS_PROVIDER=deepgram`, which it currently is) — only the section header and the `STT_PROVIDER` line are removed:

1. Delete the `# STT` comment line.
2. Delete the `STT_PROVIDER=deepgram` line.
3. Change the section comment directly above the `DEEPGRAM_API_KEY=...` line (now the first line of that block) to `# TTS (also used for STT previously; DEEPGRAM_API_KEY is shared)` — or simpler, just move that line to sit directly above the existing `TTS_PROVIDER=deepgram` line under the existing `# TTS` heading, and delete the now-empty former `# STT` section entirely.

Do not paste or retype the actual key value — edit the file in place so the real secret already in `core/.env` is preserved untouched, just relocated/re-headed.

- [ ] **Step 7: Update `core/.env.example`**

Find this block in `core/.env.example`:

```
# ── STT ──────────────────────────────────────────────────────────────────────
STT_PROVIDER=openai          # openai | deepgram
# DEEPGRAM_API_KEY=          # also used for TTS when TTS_PROVIDER=deepgram
```

Replace it with:

```
# ── STT ──────────────────────────────────────────────────────────────────────
# Voice input has been removed (VS Code webviews cannot request microphone
# permission). DEEPGRAM_API_KEY below is only needed when TTS_PROVIDER=deepgram.
```

(If the exact existing line differs slightly, e.g. the `DEEPGRAM_API_KEY` comment line isn't there, just remove the `STT_PROVIDER=openai # openai | deepgram` line and add the explanatory comment in its place.)

- [ ] **Step 8: Run the regression test to verify it passes**

Run: `cd core && uv run pytest tests/unit/test_config.py::test_settings_has_no_stt_provider -v`
Expected: PASS

- [ ] **Step 9: Run the full test suite**

Run: `cd core && uv run pytest`
Expected: same pass/fail counts as before this task started (44 passed, 1 pre-existing unrelated failure: `test_settings_default_tts_provider` — do not attempt to fix that failure, it is out of scope for this task)

- [ ] **Step 10: Lint and typecheck**

Run: `cd core && uv run ruff check src/breakdown/agent.py src/breakdown/config.py tests/unit/test_config.py`
Expected: `All checks passed!`

Run: `cd core && uv run basedpyright src/breakdown/agent.py src/breakdown/config.py`
Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 11: Check `agent.py`'s line count**

Run: `wc -l core/src/breakdown/agent.py`
Expected: fewer than 150 lines (per this project's `AGENTS.md` rule). If it's at or over 150, stop and escalate rather than extracting logic yourself — this task's diff should not cross that threshold.

- [ ] **Step 12: Commit**

```bash
git add core/src/breakdown/agent.py core/src/breakdown/config.py core/.env core/.env.example core/tests/unit/test_config.py
git rm core/src/breakdown/providers/stt.py
git commit -m "feat: replace STT-based voice input with a text ask handler in the agent"
```

---

### Task 2: Remove microphone capture from the webview

**Files:**
- Delete: `clients/vscode/webview/src/mic_capture.ts`
- Modify: `clients/vscode/webview/src/livekit_room.ts` (remove `publishMicTrack`)
- Modify: `clients/vscode/webview/src/index.ts` (remove all mic usage)

**Interfaces:**
- Consumes: none from Task 1 (these are independent layers per the Global Constraints).
- Produces: `LiveKitRoom` loses its `publishMicTrack` method — Task 3 does not call it (it never did; the extension host has no direct reference to `LiveKitRoom`, which lives entirely in the webview).

This task has no automated test — this package has no test infra (same as when it was originally built), and the change is a deletion, not new logic. Verified by confirming the built bundle contains no `getUserMedia` call (Step 5).

- [ ] **Step 1: Delete the mic capture module**

```bash
rm clients/vscode/webview/src/mic_capture.ts
```

- [ ] **Step 2: Remove `publishMicTrack` from `livekit_room.ts`**

In `clients/vscode/webview/src/livekit_room.ts`, delete these lines:

```typescript
  async publishMicTrack(track: MediaStreamTrack): Promise<void> {
    await this._room.localParticipant.publishTrack(track);
  }

```

(Delete the method and the blank line immediately following it, so `disconnect()` follows directly after `sendData()`.)

- [ ] **Step 3: Remove mic usage from `index.ts`**

Replace the full contents of `clients/vscode/webview/src/index.ts`:

```typescript
// clients/vscode/webview/src/index.ts
import { createBridge, type HostToWebview } from "./message_bridge";
import { LiveKitRoom } from "./livekit_room";

const bridge = createBridge();
let room: LiveKitRoom | null = null;

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

  if (msg.type === "send_data") {
    await room?.sendData(msg.payload);
    return;
  }
});
```

- [ ] **Step 4: Typecheck**

Run: `cd clients/vscode/webview && npm run typecheck`
Expected: no errors

- [ ] **Step 5: Build and confirm no `getUserMedia` remains**

Run: `cd clients/vscode/webview && npm run build`
Expected: `⚡ Done in <time>` with no errors

Run: `grep -c getUserMedia ../extension-host/dist/webview.js`
Expected: `0` (the grep should find zero matches; if the command errors with "no matches found" that also confirms zero — either outcome means the mic-capture code is gone from the bundle)

- [ ] **Step 6: Commit**

```bash
git add clients/vscode/webview/src/livekit_room.ts clients/vscode/webview/src/index.ts
git rm clients/vscode/webview/src/mic_capture.ts
git commit -m "feat: remove microphone capture from the webview

VS Code extension webviews have no supported mechanism for granting
getUserMedia() permission (see microsoft/vscode#113916, #303293,
#299521) -- mic capture never actually worked and always failed with
NotAllowedError. Voice input is being replaced with typed questions."
```

---

### Task 3: Replace push-to-talk with a typed "ask a question" command

**Files:**
- Modify: `clients/vscode/extension-host/src/commands.ts:1-113` (full file, shown below)
- Modify: `clients/vscode/extension-host/package.json` (`contributes.commands` and `contributes.keybindings`)

**Interfaces:**
- Consumes: `WebviewManager.isConnected(): boolean` (already exists, used the same way `explainLine` already uses it), `WebviewManager.send(msg: HostToWebview): void` (already exists).
- Produces: a new command `breakdown.askQuestion`, sending `{type: "send_data", payload: {type: "ask", text}}` — this is the exact shape Task 1's `_handle_data` now matches on `msg_type == "ask"`.

This task has no automated test — `commands.ts` has no existing test coverage (it's thin VS Code API glue, same as `explainLine`/`stopSession`/`dismissInlineStrip` before it), verified manually in a running Extension Development Host per Step 4.

- [ ] **Step 1: Replace `breakdown.pushToTalk` with `breakdown.askQuestion` in `commands.ts`**

In `clients/vscode/extension-host/src/commands.ts`, replace this block:

```typescript
    vscode.commands.registerCommand("breakdown.pushToTalk", () => {
      // Push-to-talk is handled entirely in the webview via keyboard events.
      // This command is registered so the keybinding appears in the keybindings UI.
      webviewManager.send({ type: "send_data", payload: { type: "push_to_talk_start" } });
    }),
```

with:

```typescript
    vscode.commands.registerCommand("breakdown.askQuestion", async () => {
      if (!webviewManager.isConnected()) {
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
      webviewManager.send({ type: "send_data", payload: { type: "ask", text } });
    }),
```

- [ ] **Step 2: Update `package.json`'s command and keybinding entries**

In `clients/vscode/extension-host/package.json`, replace this line in `contributes.commands`:

```json
      { "command": "breakdown.pushToTalk", "title": "Breakdown: Push to Talk" },
```

with:

```json
      { "command": "breakdown.askQuestion", "title": "Breakdown: Ask a Question" },
```

Replace this line in `contributes.keybindings`:

```json
      { "command": "breakdown.pushToTalk",   "key": "ctrl+k ctrl+space", "mac": "cmd+k cmd+space" },
```

with:

```json
      { "command": "breakdown.askQuestion",   "key": "ctrl+k ctrl+space", "mac": "cmd+k cmd+space" },
```

- [ ] **Step 3: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 4: Run the existing unit test suite**

Run: `cd clients/vscode/extension-host && npm test`
Expected: `9 passing` (unchanged — this task doesn't touch `inline_strip_manager.ts` or its tests)

- [ ] **Step 5: Build both bundles**

Run: `cd clients/vscode/webview && npm run build && cd ../extension-host && npm run build`
Expected: both `⚡ Done in <time>` with no errors

- [ ] **Step 6: Manual end-to-end verification**

Launch the Extension Development Host (or hot-copy `dist/extension.js`, `dist/webview.js`, and this repo's updated `package.json` into the installed extension per this project's established dev workflow, then **Developer: Reload Window** — note `package.json` changes require a reload, JS-only changes alone are not enough) with the agent running (`cd core && uv run breakdown start ..`). Then:

1. Press `Ctrl+K Ctrl+Space` with no session running. Confirm: an error message "start a session first" appears, no input box opens.
2. Start a session (`Ctrl+K Ctrl+E`), then press `Ctrl+K Ctrl+Space`. Confirm: a VS Code input box appears with the placeholder text.
3. Type a question and press Enter. Confirm: the agent speaks a reply (audio) and the inline strip (if open) shows the reply's transcript.
4. Press `Ctrl+K Ctrl+Space` and press `Escape` without typing anything. Confirm: nothing is sent, no error.
5. Confirm `Ctrl+Alt+I` ("explain this line") still works exactly as before — unaffected by this plan.

- [ ] **Step 7: Commit**

```bash
git add clients/vscode/extension-host/src/commands.ts clients/vscode/extension-host/package.json
git commit -m "feat: replace push-to-talk with a typed ask-a-question command

Push-to-talk was never fully wired end-to-end (no matching handler
existed on the agent side), and depended on microphone capture that
VS Code webviews cannot support. Ctrl+K Ctrl+Space now opens a text
input box instead."
```
