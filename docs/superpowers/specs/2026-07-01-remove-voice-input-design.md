# Remove Voice Input, Keep Voice Output — Design

**Goal:** Stop trying to capture the user's microphone inside a VS Code webview — a platform limitation with no supported permission-grant mechanism — and replace voice-driven questions with typed text input, while keeping the agent's spoken (TTS) explanations unchanged.

## Background

`Ctrl+Alt+I` ("explain this line") and the agent's spoken responses have never depended on microphone input — that flow is agent-speaks-to-user only, driven by the LiveKit TTS/transcript pipeline built in the inline-explanation-strip work. Push-to-talk, however, was never actually wired end-to-end: `commands.ts`'s `breakdown.pushToTalk` command only ever sent a `push_to_talk_start` data message that nothing on the agent side handled, and no "stop" event existed anywhere in the codebase.

Attempting to finish that wiring surfaced a platform-level blocker: VS Code's extension webviews (`vscode.window.createWebviewPanel`) have no supported mechanism for granting `getUserMedia()` microphone permission — no permission-prompt UI, no CSP directive, no webview option. This is a known, long-standing gap documented in multiple open `microsoft/vscode` GitHub issues (#113916, #303293, #299521), not a misconfiguration in this project. The `NotAllowedError: Permission denied` error the user hit is that platform restriction surfacing directly (and is exactly what an earlier fix in this project made *visible* instead of silently swallowing — the underlying capability was never there to begin with).

Rather than route around the restriction (e.g. capturing audio in a separate real browser tab, or moving mic capture into the local Python agent process), this design removes voice *input* entirely and replaces it with typed text, since the mic was never functional in the first place and typing is simpler, more reliable, and needs no new architecture.

## What Changes

**Removed:**
- `clients/vscode/webview/src/mic_capture.ts` — the `MicCapture` class and all `getUserMedia()` usage.
- `LiveKitRoom.publishMicTrack()` in `clients/vscode/webview/src/livekit_room.ts` — no local track is ever published anymore.
- The call site in `clients/vscode/webview/src/index.ts` that starts the mic and publishes it on connect (this is what raised the `NotAllowedError`).
- `core/src/breakdown/providers/stt.py` (the `create_stt` factory) — with no audio input, there is nothing to transcribe.
- The `stt_provider` setting and `STT_PROVIDER`/`DEEPGRAM_API_KEY`-for-STT config surface in `core/src/breakdown/config.py` and `.env.example` (Deepgram's key stays if still used for TTS — that's a separate, unrelated setting).
- The `stt=` argument passed to `AgentSession(...)` in `core/src/breakdown/agent.py`.
- `breakdown.pushToTalk`'s stub command and its `push_to_talk_start` message (never had a matching handler on the agent side; replaced outright, not preserved).

**Added:**
- A new command, `breakdown.askQuestion`, bound to the same keybinding push-to-talk used (`Ctrl+K Ctrl+Space` / `Cmd+K Cmd+Space`). It uses VS Code's built-in `vscode.window.showInputBox()` to prompt for text, guarded by the same `webviewManager.isConnected()` check `explainLine` already uses (shows an error message instead of opening the input box if no session is running).
- A new data-channel message type, `{type: "ask", text: string}`, sent from the extension host to the agent on input-box submission, following the exact pattern `explain`/`next`/`prev` already use (`webviewManager.send({type: "send_data", payload: {type: "ask", text}})`).
- A new branch in `core/src/breakdown/agent.py`'s `_handle_data` for `msg_type == "ask"`: records the user's turn via `session.add_turn("user", text)`, calls `await agent_session.generate_reply(user_input=text)` (the `AgentSession` API already used for injecting a text turn and getting a spoken reply — confirmed present on the installed `livekit-agents` version), and saves the session, mirroring how the existing `explain` branch already calls `session.save(session_path)`.

**Unchanged:**
- `Ctrl+Alt+I` ("explain this line") and its whole pipeline: system-prompt construction, context retrieval, `agent_session.say(...)`, the inline strip's live transcript display.
- The background "Breakdown Engine" webview panel — still required for TTS audio playback and the data channel; it simply never publishes an outbound track anymore.
- `next`/`prev` line navigation and the `position` message.
- The `tts_provider` setting and TTS pipeline entirely.

## Data Flow (new "ask" feature)

1. User presses `Ctrl+K Ctrl+Space`.
2. `commands.ts`'s `breakdown.askQuestion` handler checks `webviewManager.isConnected()`; if false, shows `vscode.window.showErrorMessage(...)` and returns (same guard/message style as `explainLine`'s existing session-not-running check).
3. If connected, calls `vscode.window.showInputBox({ prompt: "Ask Breakdown a question" })`. If the user submits non-empty text, sends `{type: "send_data", payload: {type: "ask", text}}` through the existing bridge to the background webview, which forwards it over the LiveKit data channel exactly as `explain`/`next`/`prev` do today.
4. The agent's `_handle_data` receives `{type: "ask", text}`, appends the user's turn to `Session`, and calls `agent_session.generate_reply(user_input=text)`. The reply is spoken via TTS and its live transcript flows to the inline strip through the same `RoomEvent.TranscriptionReceived` → `transcript` message path "explain" replies already use — no new plumbing needed on that side.
5. If the input box is dismissed (Escape) or submitted empty, nothing is sent — same as VS Code's standard `showInputBox` cancel behavior.

## Testing

- `core/tests/unit/test_config.py` and any test referencing `stt_provider`/`STT_PROVIDER` must be updated to remove that setting.
- No test currently exists for `providers/stt.py` beyond what covers `create_stt` generally; confirm none reference it after removal (a quick grep, not a new test suite).
- `clients/vscode/extension-host` has unit tests only for `InlineStripManager`'s pure logic (`inline_strip_manager.test.ts`) — the new `askQuestion` command is thin VS Code API glue like `explainLine`/`stopSession`, verified manually in a running Extension Development Host, consistent with how `explainLine`'s guard and `dismissInlineStrip` were verified in the inline-strip work.
- Manual verification: confirm `Ctrl+Alt+I` still works exactly as before (unaffected), confirm `Ctrl+K Ctrl+Space` opens an input box only when a session is running, confirm submitting text produces a spoken + inline-strip-visible reply, confirm no `getUserMedia()` call remains anywhere in the webview bundle (search the built `webview.js` for `getUserMedia` — should be absent).

## Files Touched

- **Delete:** `clients/vscode/webview/src/mic_capture.ts`, `core/src/breakdown/providers/stt.py`
- **Modify:** `clients/vscode/webview/src/livekit_room.ts` (remove `publishMicTrack`), `clients/vscode/webview/src/index.ts` (remove mic start/publish on connect), `clients/vscode/extension-host/src/commands.ts` (replace `pushToTalk` with `askQuestion`), `clients/vscode/extension-host/package.json` (command title + keybinding rename), `core/src/breakdown/agent.py` (remove `stt=`, add `ask` branch), `core/src/breakdown/config.py` (remove `stt_provider`), `core/.env.example` and `core/.env` (remove `STT_PROVIDER`)
- **No changes:** `core/src/breakdown/providers/tts.py`, `core/src/breakdown/providers/llm.py`, the inline strip manager/decorator (Tasks 1-2 of the prior plan), the `position`/`transcript`/`status` message routing built in the prior plan.
