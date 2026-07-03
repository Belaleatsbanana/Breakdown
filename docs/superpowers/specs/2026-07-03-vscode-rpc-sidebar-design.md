# RPC Transport + Chat Sidebar — Design

**Goal:** Replace the hand-rolled DataPacket/JSON protocol with LiveKit's built-in RPC methods, and replace the hidden "audio engine" webview panel with a visible sidebar chat view that renders full markdown explanations while the agent narrates them via TTS. Voice narration is unaffected; this only changes how requests are made and how text is displayed.

## Background

Today, client→agent messages (`explain`, `ask`, `next`, `prev`, `stop`) are hand-encoded JSON published as raw LiveKit DataPackets (`docs/protocol.md`) and parsed on the other side with `json.loads(getattr(packet, "data", b"{}"))` in `agent.py`. Agent→client info (`status`, `position`, `transcript`, `error`) flows the same way, plus a separate live-caption stream sourced from LiveKit's built-in transcription of the agent's own TTS audio (`RoomEvent.TranscriptionReceived` in `livekit_room.ts`).

Two problems with this:

1. **The "text" the user sees today is a speech-derived caption, not the agent's actual output.** `inline_strip_manager.ts`'s `updateTranscript` renders whatever LiveKit's transcription of the TTS audio produces — plain prose, no code blocks, no formatting, and it disappears once the strip is dismissed. There's no persistent, readable record of past explanations.
2. **The `explain` handler doesn't actually explain anything.** `agent.py`'s `explain` branch calls `agent_session.say(f"Line {N}: {target_line}")` — it speaks the raw code line back, not an LLM-generated explanation. Only `ask` calls `generate_reply` for a real answer.
3. **LiveKit already has a purpose-built RPC primitive** (`register_rpc_method` / `perform_rpc` on the Python side, `room.registerRpcMethod` / `room.localParticipant.performRpc` on the JS side) for exactly this request/response pattern, confirmed present in the installed `livekit-agents` and documented for `livekit-client` v2. Using it removes the manual envelope/parsing code and gives us typed request/response semantics with built-in error propagation (`RpcError`) instead of a bespoke `error` packet type.

## What Changes

**Transport (`explain`/`ask`/`next`/`prev`/`stop`):**
- Client calls become `room.localParticipant.performRpc({ destinationIdentity, method, payload, responseTimeout })` (JS) which awaits a JSON string response.
- Agent registers matching handlers via `ctx.room.local_participant.register_rpc_method(method_name, handler)`, where `handler(data: rtc.rpc.RpcInvocationData) -> str` reads `data.payload` and returns a JSON string.
- `destinationIdentity` (the agent's participant identity) is captured client-side from the `participant` argument LiveKit already passes to the `TrackSubscribed` handler in `livekit_room.ts` (currently received as `_participant` and discarded) — no new lookup invented.
- Errors: agent handlers raise `livekit.rtc.rpc.RpcError(code, message)` for known failure cases (rate limits, empty index, etc.). Custom codes start at `2000` — codes `1001`–`1999` are reserved by LiveKit internally. The client catches the rejected `performRpc` promise and shows `vscode.window.showErrorMessage`, replacing the old `error` DataPacket type.
- The `status` and `transcript` DataPacket types and the `RoomEvent.TranscriptionReceived` listener are removed entirely. Status is now inferred client-side from RPC call lifecycle: sending → `"explaining"`, resolved/rejected → `"idle"`.
- `next`/`prev` return `{file, line}` directly in the RPC response instead of publishing a separate `position` packet.
- Protocol version bumps to v2 (`PROTOCOL_VERSION` in `agent.py`, `docs/protocol.md` rewritten to document RPC methods instead of the DataPacket envelope for client↔agent traffic; the Audio section is unchanged).

**Agent (`core/src/breakdown/agent.py` + new `core/src/breakdown/rpc_handlers.py`):**
- `explain` handler now builds context/prompt as today, but calls the LLM for a real explanation (reusing the same `generate_reply`-based pattern `ask` already uses) instead of echoing the code line. It fires `agent_session.say(text)` without awaiting completion (so the RPC response returns promptly while narration continues in the background) and returns `{"text": markdown, "file": ..., "line": ...}`.
- `ask` handler: same pattern, returns `{"text": markdown}`.
- `next`/`prev`: compute the new line, return it directly.
- `stop`: closes the agent session, returns an ack.
- Per `AGENTS.md`'s 150-line cap on `agent.py`, the five handler bodies move into `rpc_handlers.py`; `agent.py` keeps only settings/session/LLM/TTS wiring and the `register_rpc_method` calls.

**UI — sidebar replaces the hidden panel:**
- New `WebviewViewProvider` registered under a "Breakdown" Activity Bar view container (replacing `webview_manager.ts`'s hidden `ViewColumn.Beside` panel created in `show()`). This webview owns the `LiveKitRoom` connection — both the subscribed audio track (existing `AudioPlayer`, unchanged) and the `performRpc` calls.
- Renders conversation history as a list of turns — `{ kind: "explain", file, line, text }` or `{ kind: "ask", question, text }` — as markdown via `marked` (pure JS, no native build step, consistent with `AGENTS.md`'s dependency rule about pre-built wheels not applying since this is a JS-only addition). Auto-scrolls to the newest turn. History lives in webview memory for the session; cleared on `stopSession`.
- `commands.ts`: `explainLine`/`askQuestion`/`nextLine`/`prevLine` now send `{type: "rpc", method, payload}` to the webview; the webview performs the actual `performRpc` call and posts `rpc_start`/`rpc_end` events back to the extension host so the inline strip can reflect status.

**Inline strip — status only:**
- `inline_strip_manager.ts` drops `_transcript` and `updateTranscript`; keeps `_status`, now driven by the webview's `rpc_start`/`rpc_end` events instead of `transcript`/`status` DataPackets.
- `_render()` shows only `${status}…`, no caption text.
- `inline_strip_decorator.ts` is unchanged structurally.

## Data Flow (explain, new)

1. User triggers `Ctrl+Alt+I`. `commands.ts` sends `{type: "rpc", method: "explain", payload: {file, line}}` to the sidebar webview.
2. Sidebar webview posts `rpc_start` to the extension host (strip shows "explaining…"), then calls `room.localParticipant.performRpc({ destinationIdentity: agentIdentity, method: "explain", payload: JSON.stringify({file, line}), responseTimeout: 15000 })`.
3. Agent's registered `explain` RPC handler retrieves context, builds the prompt, calls the LLM for explanation text, starts `agent_session.say(text)` (audio, not awaited), and returns the text as the RPC response.
4. Webview receives the response, appends an `explain` turn to its history list, renders it as markdown, posts `rpc_end` to the extension host (strip returns to "idle" once narration-triggering call resolves).
5. Audio plays via the already-subscribed LiveKit track, independent of the RPC round-trip.
6. On `RpcError` (e.g. rate limit), the webview's `performRpc` promise rejects; the extension host shows `vscode.window.showErrorMessage` with the error's message.

## Testing

- `core/tests/unit`: add/adjust tests for the new `rpc_handlers.py` functions (pure logic, given the existing `_index_context` and prompt-building already have coverage patterns to follow) — verify `explain` now returns LLM-generated text rather than echoing the code line.
- `clients/vscode/extension-host`: extend `inline_strip_manager.test.ts` for the simplified status-only behavior (removal of transcript-related assertions).
- Manual verification in the Extension Development Host: confirm the sidebar view appears, `Ctrl+Alt+I` populates it with markdown (including a code block from a multi-line function) while narration plays, `next`/`prev` update position without a separate packet, and disconnecting the agent mid-call surfaces an error message via the rejected RPC promise rather than a silent timeout.
- Search the built `webview.js` bundle to confirm no references to the removed `TranscriptionReceived` listener or `transcript`/`status` DataPacket types remain.

## Files Touched

- **Delete:** none outright; `RoomEvent.TranscriptionReceived` listener and its handling in `livekit_room.ts`.
- **Add:** `core/src/breakdown/rpc_handlers.py`, a new `WebviewViewProvider` implementation (likely `clients/vscode/extension-host/src/chat_view_provider.ts`) and its webview entry point (`clients/vscode/webview/src/chat_view.ts` or similar), Activity Bar view container contribution in `clients/vscode/extension-host/package.json`.
- **Modify:** `core/src/breakdown/agent.py` (register RPC methods, drop `_handle_data`/DataPacket parsing), `clients/vscode/webview/src/livekit_room.ts` (RPC calls replace `sendData`, drop transcription listener), `clients/vscode/extension-host/src/commands.ts`, `clients/vscode/extension-host/src/webview_manager.ts` (replaced by/merged into the new view provider), `clients/vscode/extension-host/src/message_types.ts` (new message shapes for `rpc`/`rpc_start`/`rpc_end`), `clients/vscode/extension-host/src/inline_strip_manager.ts`, `docs/protocol.md`, `PROTOCOL_VERSION` in `agent.py`.
- **Unchanged:** `AudioPlayer`, TTS/LLM provider factories, indexing pipeline, `Session` dataclass.
