# Inline Explanation Strip — Design

**Goal:** Replace the visible sidebar `WebviewPanel` chat surface with an inline, Copilot-style strip that appears at the cursor's line when the user presses a shortcut, so explanations render where the user is looking instead of in a separate panel.

## Background

Today, `breakdown.startSession` spawns the agent process and opens a `vscode.WebviewPanel` beside the editor. That panel's webview (`livekit_room.ts`, `mic_capture.ts`, `audio_player.ts`) holds the actual LiveKit WebRTC connection — mic capture, TTS audio playback, and the JSON data channel used for `explain`/`next`/`prev`/`transcript`/`status` messages. The panel itself is also the visible UI: it's what the user reveals and looks at.

This couples "where the LiveKit connection lives" with "what the user sees," and per `CLAUDE.md`, the LiveKit connection *must* live in a webview — `livekit-client` (the browser WebRTC SDK) cannot run in the extension host (Node.js); only `livekit-server-sdk` runs there. That constraint doesn't go away with this redesign; the design below keeps the connection in a webview but stops surfacing that webview as the visible UI.

## Architecture

Two independent pieces, communicating over the existing `postMessage` bridge (`message_bridge.ts` / `message_types.ts`):

### 1. Background audio engine (existing code, new placement)

- The current webview bundle (`webview/src/*`) is unchanged in behavior: it still owns the `Room`, mic capture, audio playback, and `sendData`/`DataReceived` handling.
- It is hosted in a `vscode.WebviewPanel` created once per session start, with `retainContextWhenHidden: true`, titled `"Breakdown Engine"`.
- This panel is **created but never `.reveal()`-ed or given focus**. It exists as one inactive background tab in the user's editor group. The user is not expected to interact with it directly.
- Lifecycle: created on first `Ctrl+Alt+I` (or whenever the agent process is confirmed running, matching today's `startSession` flow in `commands.ts`), and stays alive for the life of the session — same persistent-connection model as today, just not visible.

### 2. Inline strip (new)

- A new module, `inline_strip_manager.ts`, in the extension host.
- Built on `vscode.window.createTextEditorDecorationType`, using an `after: { contentText, ... }` render option attached to the end of the target line, rendered as a block below it (`isWholeLine: true`, `after.textDecoration: "none; display: block;"` — the standard trick extensions use for multi-line inline annotations).
- Decoration content shows:
  - A one-word status indicator sourced from `status` messages (`listening…`, `thinking…`, `speaking…`).
  - The live transcript text sourced from `transcript` messages (both partial and final), replacing its own content as new deltas arrive.
- Exactly one decoration exists at a time, tracked as a single `vscode.Range`. Pressing the shortcut on a different line calls `setDecorations` with a new range, which implicitly clears the old one — no manual cleanup needed.
- A VS Code context key, `breakdown.stripVisible`, is set to `true` when the strip is shown and `false` when hidden, gating the `Escape`-bound dismiss command so it doesn't shadow Escape's normal editor behavior when the strip isn't open.

## Data Flow

Unchanged at the protocol level:

1. `Ctrl+Alt+I` on a line → `commands.ts` resolves `{file, line}` via `activeLineInfo()` (existing helper) → sends `{type: "send_data", payload: {type: "explain", file, line}}` to the background webview, which forwards it over the LiveKit data channel to the Python agent — exactly the flow `breakdown.explainLine` uses today.
2. The agent's existing `_handle_data` in `core/src/breakdown/agent.py` handles `explain`/`next`/`prev` exactly as it does now. No changes to `core/` are required.
3. `transcript` and `status` messages arriving in the background webview are forwarded to the extension host via the bridge (already implemented in `livekit_room.ts` today) — the only change is *where* the host routes them: to `InlineStripManager.update(...)` instead of `WebviewManager`'s panel-refresh logic.

## Interaction Details

- **Trigger:** `Ctrl+Alt+I` (`Cmd+Alt+I` on Mac) — deliberately distinct from GitHub Copilot's default `Ctrl+I`/`Cmd+I` inline chat binding, so the two don't conflict if both extensions are installed.
- **Voice input:** unchanged. Opening the strip triggers the "explain this line" flow (agent responds via transcript + speech); the existing push-to-talk keybinding (`Ctrl+K Ctrl+Space` / `Cmd+K Cmd+Space`) is used for follow-up voice questions about that line. The strip does not auto-start the mic.
- **Navigation:** `breakdown.nextLine` / `breakdown.prevLine` behave as today (advance `session.current_line`, publish a `position` data message) and additionally move the strip's decoration range to follow the new line.
- **Dismissal:** `Escape` clears the current decoration and sets `breakdown.stripVisible` to `false`, without touching the LiveKit connection or the agent session. Moving the cursor to a different line, without pressing the shortcut again, does **not** auto-dismiss — the strip stays until `Escape` or a new `Ctrl+Alt+I` elsewhere.
- **Status bar:** unchanged — continues to reflect connection state (`inactive` / `listening` / etc.) via the same `$(unmute) Breakdown: <state>` text.

## Removed

- `webview_manager.ts`'s role as a *visible* chat surface: the HTML body, CSP, and `onDidReceiveMessage` routing for `transcript`/`status` that used to update panel-visible UI are removed. It's trimmed to: create the background panel once, wire the message bridge, and forward `transcript`/`status`/`error` events to `InlineStripManager` and the status bar.
- No command is removed; `breakdown.explainLine`, `breakdown.nextLine`, `breakdown.prevLine`, `breakdown.pushToTalk`, `breakdown.stopSession` all keep their existing behavior and keybindings. `breakdown.startSession`'s keybinding (`Ctrl+K Ctrl+E`) still starts the agent process, but no longer reveals a panel — it just ensures the background engine is running.

## Files Touched

- **Create:** `clients/vscode/extension-host/src/inline_strip_manager.ts`
- **Modify:** `clients/vscode/extension-host/src/commands.ts` (register `Ctrl+Alt+I` trigger, wire `explainLine` to also show the strip, register `Escape`-gated dismiss command)
- **Modify:** `clients/vscode/extension-host/src/webview_manager.ts` (drop visible-panel HTML/CSP, keep background-panel creation + message routing)
- **Modify:** `clients/vscode/extension-host/package.json` (add `breakdown.dismissInlineStrip` command, `ctrl+alt+i` keybinding with `mac: cmd+alt+i`, `escape` keybinding scoped to `when: breakdown.stripVisible`)
- **No changes** to `clients/vscode/webview/src/*` (audio engine internals untouched) or `core/` (protocol and agent untouched).

## Testing

- Extension host unit tests (existing pattern under `clients/vscode/extension-host/src/*` if present) cover: decoration range replacement on repeated trigger, context-key toggling on show/dismiss, and that `Escape` is a no-op when `breakdown.stripVisible` is false.
- Manual verification (per this repo's convention of testing UI changes in a running VS Code instance): confirm the background panel tab never gains focus on session start, confirm the strip appears/updates/clears as described, confirm push-to-talk and navigation commands still work unchanged.
