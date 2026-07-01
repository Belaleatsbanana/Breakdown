# Inline Explanation Strip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the visible sidebar `WebviewPanel` chat surface with an inline, Copilot-style decoration strip that appears at the cursor's line on `Ctrl+Alt+I`, driven by the same LiveKit connection that now runs in a hidden background panel.

**Architecture:** A pure, VS-Code-API-free `InlineStripManager` owns the strip's state machine (visible line, status, transcript text) and delegates actual rendering to an injected `StripDecorator`. The real `DecorationHostAdapter` implements that interface using `vscode.TextEditorDecorationType`. The existing LiveKit webview panel keeps its current internals unchanged but stops being revealed/focused. `commands.ts` and `webview_manager.ts` wire the two together and route `transcript`/`status`/`position` messages from the agent into the manager.

**Tech Stack:** TypeScript (strict), VS Code Extension API, esbuild (existing bundler), Mocha + ts-node (new, dev-only, for pure-logic unit tests).

## Global Constraints

- `strict: true` in TypeScript; no `any` except where forced by the VS Code API (from `AGENTS.md`).
- The Webview and extension host are separate TypeScript compilation targets with separate `tsconfig.json` files — never import browser APIs in extension-host code or VS Code APIs in webview code (from `AGENTS.md`).
- Paths sent over the protocol wire are always relative to workspace root (from `AGENTS.md`).
- Conventional commits only, exactly these prefixes: `feat:`, `fix:`, `docs:`, `perf:`, `chore:`, `test:`. No scope in parentheses unless it aids clarity (from `AGENTS.md`).
- Trigger keybinding is `ctrl+alt+i` / `cmd+alt+i` — deliberately distinct from GitHub Copilot's `ctrl+i`/`cmd+i` (from spec).
- Exactly one inline strip exists at a time; showing it on a new line replaces the old decoration (from spec).
- Dismissal is `Escape`, scoped to a `breakdown.stripVisible` context key so it doesn't shadow normal Escape behavior when the strip isn't open (from spec).
- Push-to-talk and the `explain`/`next`/`prev` data-channel protocol are unchanged; no changes to `core/` (from spec).
- The background LiveKit panel is created once, titled `"Breakdown Engine"`, and is never `.reveal()`-ed or focused (from spec).

---

### Task 1: `InlineStripManager` core state machine + unit tests

**Files:**
- Create: `clients/vscode/extension-host/src/inline_strip_manager.ts`
- Test: `clients/vscode/extension-host/src/inline_strip_manager.test.ts`
- Modify: `clients/vscode/extension-host/package.json` (add test devDependencies and `test` script)

**Interfaces:**
- Produces:
  - `export type StripStatus = "idle" | "explaining" | "listening" | "interrupted";` (mirrors the `status.state` literal union already defined in `message_types.ts:19` — kept as a separate manual copy, matching this file's existing pattern of manually mirroring the webview's types)
  - `export interface StripDecorator { setDecoration(line: number, text: string): void; clearDecoration(): void; }`
  - `export type ContextSetter = (key: string, value: boolean) => void;`
  - `export class InlineStripManager { constructor(decorator: StripDecorator, setContext: ContextSetter); get isVisible(): boolean; get visibleLine(): number | null; show(line: number): void; moveTo(line: number): void; updateStatus(status: StripStatus): void; updateTranscript(text: string): void; dismiss(): void; }`
  - `line` is always 1-based, matching the convention already used by `activeLineInfo()` in `commands.ts:20-32`.

This class has zero runtime dependency on the `vscode` module — it only talks to the injected `StripDecorator` and `ContextSetter`, which is what makes it unit-testable outside the Extension Development Host.

- [ ] **Step 1: Add Mocha + ts-node dev dependencies and a `test` script**

Edit `clients/vscode/extension-host/package.json`. Add to `"devDependencies"` (after `"esbuild": "^0.21.0",`):

```json
    "esbuild": "^0.21.0",
    "mocha": "^10.4.0",
    "@types/mocha": "^10.0.6",
    "ts-node": "^10.9.2",
```

Add to `"scripts"` (after `"lint": "eslint src --ext .ts"`):

```json
    "lint": "eslint src --ext .ts",
    "test": "mocha --require ts-node/register --extension ts \"src/**/*.test.ts\""
```

Then install:

```bash
cd clients/vscode/extension-host && npm install
```

- [ ] **Step 2: Write the failing tests**

Create `clients/vscode/extension-host/src/inline_strip_manager.test.ts`:

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
    manager.updateStatus("listening");
    assert.deepEqual(decorator.calls[1], { op: "set", line: 5, text: "listening…" });
  });

  it("updateStatus() is a no-op when the strip is not visible", () => {
    const { manager, decorator } = makeManager();
    manager.updateStatus("listening");
    assert.deepEqual(decorator.calls, []);
  });

  it("updateTranscript() appends transcript text after the status", () => {
    const { manager, decorator } = makeManager();
    manager.show(5);
    manager.updateTranscript("this loop retries on failure");
    assert.deepEqual(decorator.calls[1], {
      op: "set",
      line: 5,
      text: "explaining… this loop retries on failure",
    });
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

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd clients/vscode/extension-host && npm test`
Expected: FAIL with `Cannot find module './inline_strip_manager'`

- [ ] **Step 4: Write the implementation**

Create `clients/vscode/extension-host/src/inline_strip_manager.ts`:

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
  private _transcript = "";

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
    this._transcript = "";
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

  updateTranscript(text: string): void {
    if (this._visibleLine === null) {
      return;
    }
    this._transcript = text;
    this._render();
  }

  dismiss(): void {
    this._visibleLine = null;
    this._status = "explaining";
    this._transcript = "";
    this._setContext(CONTEXT_KEY, false);
    this._decorator.clearDecoration();
  }

  private _render(): void {
    if (this._visibleLine === null) {
      return;
    }
    const text =
      this._transcript.length > 0 ? `${this._status}… ${this._transcript}` : `${this._status}…`;
    this._decorator.setDecoration(this._visibleLine, text);
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd clients/vscode/extension-host && npm test`
Expected: `9 passing`

- [ ] **Step 6: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add clients/vscode/extension-host/package.json clients/vscode/extension-host/package-lock.json clients/vscode/extension-host/src/inline_strip_manager.ts clients/vscode/extension-host/src/inline_strip_manager.test.ts
git commit -m "feat: add InlineStripManager state machine with unit tests"
```

---

### Task 2: `DecorationHostAdapter` — real VS Code rendering

**Files:**
- Create: `clients/vscode/extension-host/src/inline_strip_decorator.ts`

**Interfaces:**
- Consumes: `StripDecorator` interface from Task 1 (`clients/vscode/extension-host/src/inline_strip_manager.ts`)
- Produces: `export class DecorationHostAdapter implements StripDecorator { setDecoration(line: number, text: string): void; clearDecoration(): void; dispose(): void; }`

This talks to the real `vscode` module, so it cannot be unit tested outside the Extension Development Host (there is no existing VS Code integration-test harness in this repo — `clients/vscode/extension-host` has none today). It is verified manually in Task 4's end-to-end check instead.

- [ ] **Step 1: Write the implementation**

Create `clients/vscode/extension-host/src/inline_strip_decorator.ts`:

```typescript
// clients/vscode/extension-host/src/inline_strip_decorator.ts
import * as vscode from "vscode";
import type { StripDecorator } from "./inline_strip_manager";

export class DecorationHostAdapter implements StripDecorator {
  private readonly _decorationType: vscode.TextEditorDecorationType;

  constructor() {
    this._decorationType = vscode.window.createTextEditorDecorationType({
      isWholeLine: true,
      after: {
        margin: "0 0 0 1em",
        color: new vscode.ThemeColor("editorCodeLens.foreground"),
        textDecoration: "none; display: block; opacity: 0.85;",
      },
    });
  }

  setDecoration(line: number, text: string): void {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      return;
    }
    const zeroBasedLine = Math.min(Math.max(line - 1, 0), editor.document.lineCount - 1);
    const lineRange = editor.document.lineAt(zeroBasedLine).range;
    editor.setDecorations(this._decorationType, [
      { range: lineRange, renderOptions: { after: { contentText: `  ${text}` } } },
    ]);
  }

  clearDecoration(): void {
    vscode.window.activeTextEditor?.setDecorations(this._decorationType, []);
  }

  dispose(): void {
    this._decorationType.dispose();
  }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add clients/vscode/extension-host/src/inline_strip_decorator.ts
git commit -m "feat: add DecorationHostAdapter for inline strip rendering"
```

---

### Task 3: Forward `position` messages end-to-end

**Files:**
- Modify: `clients/vscode/webview/src/message_bridge.ts:8-14`
- Modify: `clients/vscode/webview/src/livekit_room.ts:36-47`
- Modify: `clients/vscode/extension-host/src/message_types.ts:13-19`

**Interfaces:**
- Produces: `WebviewToHost` (both the webview's copy in `message_bridge.ts` and the extension host's manually-mirrored copy in `message_types.ts`) gains a new variant: `{ type: "position"; file: string; line: number }`.

The agent already publishes `{v: 1, type: "position", file, line}` on the data channel today (`core/src/breakdown/agent.py:111-114` and `:119-122`), but `livekit_room.ts`'s `DataReceived` handler currently only recognizes `"transcript"` and `"status"` — `"position"` is silently dropped. This task closes that gap so the inline strip can follow `nextLine`/`prevLine` navigation.

- [ ] **Step 1: Add the `position` variant to the webview's message type**

In `clients/vscode/webview/src/message_bridge.ts`, replace lines 7-14:

```typescript
// Messages from webview -> extension host
export type WebviewToHost =
  | { type: "ready" }
  | { type: "connected"; participantId: string }
  | { type: "disconnected"; reason: string }
  | { type: "error"; message: string }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "status"; state: "idle" | "explaining" | "listening" | "interrupted" }
  | { type: "position"; file: string; line: number };
```

- [ ] **Step 2: Forward `position` packets in `livekit_room.ts`**

In `clients/vscode/webview/src/livekit_room.ts`, replace lines 36-47:

```typescript
    this._room.on(RoomEvent.DataReceived, (payload, _participant, _kind) => {
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg.type === "transcript") {
          this._send({ type: "transcript", text: msg.text, final: msg.final });
        } else if (msg.type === "status") {
          this._send({ type: "status", state: msg.state });
        } else if (msg.type === "position") {
          this._send({ type: "position", file: msg.file, line: msg.line });
        }
      } catch {
        // ignore malformed packets
      }
    });
```

- [ ] **Step 3: Mirror the new variant in the extension host's type file**

In `clients/vscode/extension-host/src/message_types.ts`, replace lines 12-19:

```typescript
// Messages from webview -> extension host
export type WebviewToHost =
  | { type: "ready" }
  | { type: "connected"; participantId: string }
  | { type: "disconnected"; reason: string }
  | { type: "error"; message: string }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "status"; state: "idle" | "explaining" | "listening" | "interrupted" }
  | { type: "position"; file: string; line: number };
```

- [ ] **Step 4: Typecheck both packages**

Run: `cd clients/vscode/webview && npm run typecheck`
Expected: no errors

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 5: Build the webview bundle**

Run: `cd clients/vscode/webview && npm run build`
Expected: `⚡ Done in <time>` with no errors, `../extension-host/dist/webview.js` rewritten

- [ ] **Step 6: Manual verification**

This is protocol plumbing with no unit-testable logic on its own (a 3-branch `if/else` mirrored from the existing `transcript`/`status` handling, which has never had dedicated tests either) — verified as part of Task 4's end-to-end check, where `nextLine`/`prevLine` moving the decoration is direct proof `position` messages are arriving.

- [ ] **Step 7: Commit**

```bash
git add clients/vscode/webview/src/message_bridge.ts clients/vscode/webview/src/livekit_room.ts clients/vscode/extension-host/src/message_types.ts clients/vscode/extension-host/dist/webview.js
git commit -m "feat: forward position data-channel messages to the extension host"
```

---

### Task 4: Wire the inline strip into the extension

**Files:**
- Modify: `clients/vscode/extension-host/src/webview_manager.ts` (full file — see below)
- Modify: `clients/vscode/extension-host/src/commands.ts:34-99`
- Modify: `clients/vscode/extension-host/src/extension.ts:10-29`
- Modify: `clients/vscode/extension-host/package.json` (`contributes.commands` and `contributes.keybindings`)

**Interfaces:**
- Consumes:
  - `InlineStripManager` from Task 1 (`show`, `moveTo`, `updateStatus`, `updateTranscript`, `dismiss`)
  - `DecorationHostAdapter` from Task 2
  - `WebviewToHost`'s new `"position"` variant from Task 3
- Produces: `registerCommands(ctx, webviewManager, processManager, inlineStripManager)` — one new parameter, in that position, since `commands.ts` needs `inlineStripManager` to wire `explainLine`, `nextLine`, `prevLine`, and the new dismiss command.

This is the integration task: none of the three pieces built in Tasks 1-3 are reachable from the running extension until this task wires them together, so it is verified end-to-end manually rather than split further.

- [ ] **Step 1: Rewrite `webview_manager.ts`**

Replace the full contents of `clients/vscode/extension-host/src/webview_manager.ts`:

```typescript
// clients/vscode/extension-host/src/webview_manager.ts
import * as vscode from "vscode";
import * as path from "path";
import type { HostToWebview, WebviewToHost } from "./message_types";
import type { InlineStripManager } from "./inline_strip_manager";

export class WebviewManager {
  private _panel: vscode.WebviewPanel | null = null;
  private _statusBar: vscode.StatusBarItem;

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

  show(token: string, url: string, room: string): void {
    if (this._panel) {
      // Reconnect with new credentials rather than reusing stale ones.
      // Deliberately does not call .reveal() — this panel is a background
      // audio engine, never the visible UI.
      this.send({ type: "disconnect" });
      this.send({ type: "connect", token, url, room });
      return;
    }

    this._panel = vscode.window.createWebviewPanel(
      "breakdown",
      "Breakdown Engine",
      { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(this._context.extensionPath, "dist")),
        ],
      },
    );

    const webviewScriptUri = this._panel.webview.asWebviewUri(
      vscode.Uri.file(path.join(this._context.extensionPath, "dist", "webview.js")),
    );

    const nonce = getNonce();
    const csp = [
      `default-src 'none'`,
      `script-src 'nonce-${nonce}'`,
      `connect-src wss: https: ws://localhost:* http://localhost:*`,
      `media-src *`,
    ].join("; ");

    this._panel.webview.html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <title>Breakdown Engine</title>
</head>
<body>
<script nonce="${nonce}" src="${webviewScriptUri}"></script>
</body>
</html>`;

    this._panel.webview.onDidReceiveMessage((msg: WebviewToHost) => {
      if (msg.type === "ready") {
        this.send({ type: "connect", token, url, room });
      } else if (msg.type === "status") {
        this._statusBar.text = `$(unmute) Breakdown: ${msg.state}`;
        this._inlineStrip.updateStatus(msg.state);
      } else if (msg.type === "transcript") {
        this._inlineStrip.updateTranscript(msg.text);
      } else if (msg.type === "position") {
        this._inlineStrip.moveTo(msg.line);
      } else if (msg.type === "error") {
        vscode.window.showErrorMessage(`Breakdown: ${msg.message}`);
      }
    });

    this._panel.onDidDispose(() => {
      this._panel = null;
      this._statusBar.text = "$(unmute) Breakdown: inactive";
    });
  }

  send(msg: HostToWebview): void {
    this._panel?.webview.postMessage(msg);
  }

  dispose(): void {
    this._panel?.dispose();
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

- [ ] **Step 2: Rewrite `commands.ts`'s `registerCommands` function**

Replace lines 34-99 of `clients/vscode/extension-host/src/commands.ts` (everything from `export function registerCommands` to the closing `}` of the file):

```typescript
export function registerCommands(
  ctx: vscode.ExtensionContext,
  webviewManager: WebviewManager,
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
        webviewManager.show(token, url, room);
      } catch (err) {
        vscode.window.showErrorMessage(`Breakdown: ${String(err)}`);
      }
    }),

    vscode.commands.registerCommand("breakdown.stopSession", () => {
      webviewManager.send({ type: "disconnect" });
      inlineStripManager.dismiss();
      processManager.stop();
    }),

    vscode.commands.registerCommand("breakdown.explainLine", () => {
      const info = activeLineInfo();
      if (!info) { return; }
      inlineStripManager.show(info.line);
      webviewManager.send({ type: "send_data", payload: { type: "explain", ...info } });
    }),

    vscode.commands.registerCommand("breakdown.nextLine", () => {
      webviewManager.send({ type: "send_data", payload: { type: "next" } });
    }),

    vscode.commands.registerCommand("breakdown.prevLine", () => {
      webviewManager.send({ type: "send_data", payload: { type: "prev" } });
    }),

    vscode.commands.registerCommand("breakdown.pushToTalk", () => {
      // Push-to-talk is handled entirely in the webview via keyboard events.
      // This command is registered so the keybinding appears in the keybindings UI.
      webviewManager.send({ type: "send_data", payload: { type: "push_to_talk_start" } });
    }),

    vscode.commands.registerCommand("breakdown.dismissInlineStrip", () => {
      inlineStripManager.dismiss();
    }),
  ];
}
```

Also add the new import at the top of `clients/vscode/extension-host/src/commands.ts` (after the existing `WebviewManager` import on line 6):

```typescript
import { WebviewManager } from "./webview_manager";
import type { InlineStripManager } from "./inline_strip_manager";
```

Note: `nextLine`/`prevLine` don't call `inlineStripManager.moveTo()` directly — the agent is the source of truth for the new line number, and it echoes it back as a `position` data-channel message (Task 3), which `webview_manager.ts`'s `onDidReceiveMessage` routes to `moveTo()`. This matches the existing protocol: the extension host has never tracked `current_line` itself.

- [ ] **Step 3: Wire everything in `extension.ts`**

Replace the full contents of `clients/vscode/extension-host/src/extension.ts`:

```typescript
// clients/vscode/extension-host/src/extension.ts
import * as vscode from "vscode";
import { ProcessManager } from "./process_manager";
import { WebviewManager } from "./webview_manager";
import { registerCommands } from "./commands";
import { InlineStripManager } from "./inline_strip_manager";
import { DecorationHostAdapter } from "./inline_strip_decorator";

let _processManager: ProcessManager | null = null;
let _webviewManager: WebviewManager | null = null;
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
  _webviewManager = new WebviewManager(context, inlineStripManager);

  const disposables = registerCommands(context, _webviewManager, _processManager, inlineStripManager);
  context.subscriptions.push(...disposables, _webviewManager);
}

export function deactivate(): void {
  _processManager?.stop();
  _webviewManager?.dispose();
  _decorationAdapter?.dispose();
}
```

- [ ] **Step 4: Update `package.json` commands and keybindings**

In `clients/vscode/extension-host/package.json`, replace the `"commands"` array:

```json
    "commands": [
      { "command": "breakdown.startSession", "title": "Breakdown: Start Session" },
      { "command": "breakdown.stopSession", "title": "Breakdown: Stop Session" },
      { "command": "breakdown.explainLine", "title": "Breakdown: Explain Line" },
      { "command": "breakdown.nextLine", "title": "Breakdown: Next Line" },
      { "command": "breakdown.prevLine", "title": "Breakdown: Previous Line" },
      { "command": "breakdown.pushToTalk", "title": "Breakdown: Push to Talk" },
      { "command": "breakdown.dismissInlineStrip", "title": "Breakdown: Dismiss Inline Strip" }
    ],
```

Replace the `"keybindings"` array:

```json
    "keybindings": [
      { "command": "breakdown.startSession", "key": "ctrl+k ctrl+e", "mac": "cmd+k cmd+e" },
      { "command": "breakdown.explainLine",   "key": "ctrl+alt+i", "mac": "cmd+alt+i" },
      { "command": "breakdown.nextLine",     "key": "ctrl+k ctrl+n", "mac": "cmd+k cmd+n" },
      { "command": "breakdown.prevLine",     "key": "ctrl+k ctrl+p", "mac": "cmd+k cmd+p" },
      { "command": "breakdown.pushToTalk",   "key": "ctrl+k ctrl+space", "mac": "cmd+k cmd+space" },
      { "command": "breakdown.stopSession",  "key": "ctrl+k ctrl+q", "mac": "cmd+k cmd+q" },
      { "command": "breakdown.dismissInlineStrip", "key": "escape", "mac": "escape", "when": "breakdown.stripVisible" }
    ]
```

- [ ] **Step 5: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 6: Run the unit test suite**

Run: `cd clients/vscode/extension-host && npm test`
Expected: `9 passing` (unchanged from Task 1 — this task doesn't add new pure-logic units)

- [ ] **Step 7: Build both bundles**

Run: `cd clients/vscode/webview && npm run build && cd ../extension-host && npm run build`
Expected: both `⚡ Done in <time>` with no errors

- [ ] **Step 8: Manual end-to-end verification**

Launch the Extension Development Host (`F5` in VS Code, or package/hot-copy `dist/extension.js` and `dist/webview.js` into the installed extension per this repo's existing hot-reload workflow) with the agent running (`cd core && uv run breakdown start ..`). Then, in a workspace file:

1. Place the cursor on a line and press `Ctrl+Alt+I` (`Cmd+Alt+I` on Mac). Confirm: no visible panel/tab is focused, and an inline decoration appears below that line reading `explaining…`.
2. Confirm the decoration's text updates to `listening…`/`speaking…`/the live transcript as the agent responds (driven by `status`/`transcript` messages).
3. Move the cursor to a different line and press `Ctrl+Alt+I` again. Confirm the old decoration is gone and a new one appears at the new line — never two at once.
4. Press the existing next/prev-line keybindings (`Ctrl+K Ctrl+N` / `Ctrl+K Ctrl+P`) and confirm the decoration follows the agent's reported line via the new `position` message.
5. Press `Escape`. Confirm the decoration disappears and that pressing `Escape` again (with the strip already closed) does nothing unexpected to normal editor behavior (i.e. it doesn't swallow Escape elsewhere).
6. Check the "Breakdown Engine" background tab exists in the editor group but was never focused/activated during any of the above.

- [ ] **Step 9: Commit**

```bash
git add clients/vscode/extension-host/src/webview_manager.ts clients/vscode/extension-host/src/commands.ts clients/vscode/extension-host/src/extension.ts clients/vscode/extension-host/package.json clients/vscode/extension-host/dist clients/vscode/webview/dist 2>/dev/null
git add -A clients/vscode/extension-host/dist clients/vscode/webview
git commit -m "feat: wire inline explanation strip into extension host, replacing visible panel"
```
