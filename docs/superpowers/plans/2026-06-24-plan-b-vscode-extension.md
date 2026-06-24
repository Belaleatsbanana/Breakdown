# Breakdown Plan B: VS Code Extension

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the VS Code extension as a thin client: spawns the Python core, gets a LiveKit JWT from the token server, and connects a browser-context Webview to the LiveKit room for real-time audio playback and mic capture.

**Architecture:** Two separate TypeScript projects inside `clients/vscode/`. The extension host (Node.js) manages process lifecycle, token acquisition, and command registration. The Webview (browser context) runs `livekit-client` for WebRTC audio. They communicate via `postMessage`. The extension activates only on explicit user command, not on VS Code startup.

**Tech Stack:** TypeScript 5+, Node.js 18+, VS Code Extension API, livekit-client (browser SDK, runs in Webview), livekit-server-sdk (Node.js, for token validation only if needed), esbuild, pnpm

**Prerequisite:** Plan A must be complete. The Python core (`breakdown start`) must be runnable.

---

## Global Constraints

- TypeScript strict mode (`"strict": true` in tsconfig)
- No `any` types except where VS Code API forces it
- Extension activates on `onCommand:breakdown.startSession` only -- not on startup
- Extension host never imports `livekit-client` (browser SDK) -- that lives in Webview only
- Webview never calls VS Code API directly -- only via `postMessage` bridge
- All keyboard shortcuts use chord sequences (`Cmd+K Cmd+*`) to avoid conflicts
- Paths sent to the Python core are always relative to workspace root
- `clients/vscode/` uses `pnpm` workspaces; two packages: `extension-host` and `webview`

---

## File Map

```
clients/vscode/
  package.json                      # pnpm workspace root
  pnpm-workspace.yaml

  extension-host/
    src/
      extension.ts                  # activation, command registration, deactivation
      process_manager.ts            # spawn/supervise Python core, SIGTERM on deactivate
      token_client.ts               # read runtime.json, call token server with retry
      commands.ts                   # all command handlers, sends messages to webview
      webview_manager.ts            # creates/manages the Webview panel
    tsconfig.json                   # target: node18, no dom lib
    esbuild.host.config.js
    package.json

  webview/
    src/
      index.ts                      # entry point, initialises bridge + room
      livekit_room.ts               # livekit-client connection, audio track subscription
      audio_player.ts               # Web Audio API, streams TTS audio chunks
      mic_capture.ts                # getUserMedia, push-to-talk capture
      message_bridge.ts             # acquireVsCodeApi(), postMessage to/from host
    tsconfig.json                   # target: es2020, lib: dom,dom.iterable
    esbuild.webview.config.js
    package.json
```

---

### Task 1: Extension Scaffold

**Files:**
- Create: `clients/vscode/package.json`
- Create: `clients/vscode/pnpm-workspace.yaml`
- Create: `clients/vscode/extension-host/package.json`
- Create: `clients/vscode/extension-host/tsconfig.json`
- Create: `clients/vscode/extension-host/esbuild.host.config.js`
- Create: `clients/vscode/webview/package.json`
- Create: `clients/vscode/webview/tsconfig.json`
- Create: `clients/vscode/webview/esbuild.webview.config.js`

**Interfaces:**
- Produces: `pnpm install` succeeds; `pnpm -C extension-host build` produces `dist/extension.js`

- [ ] **Step 1: Create workspace root**

```json
// clients/vscode/package.json
{
  "name": "breakdown-vscode-workspace",
  "private": true,
  "scripts": {
    "build": "pnpm -r build",
    "typecheck": "pnpm -r typecheck",
    "lint": "pnpm -r lint"
  }
}
```

```yaml
# clients/vscode/pnpm-workspace.yaml
packages:
  - "extension-host"
  - "webview"
```

- [ ] **Step 2: Create extension-host package.json**

```json
// clients/vscode/extension-host/package.json
{
  "name": "breakdown-vscode",
  "displayName": "Breakdown",
  "description": "Voice-driven AI code explainer",
  "version": "0.1.0",
  "publisher": "breakdown",
  "engines": { "vscode": "^1.85.0" },
  "categories": ["Other"],
  "activationEvents": ["onCommand:breakdown.startSession"],
  "main": "./dist/extension.js",
  "contributes": {
    "commands": [
      { "command": "breakdown.startSession", "title": "Breakdown: Start Session" },
      { "command": "breakdown.stopSession", "title": "Breakdown: Stop Session" },
      { "command": "breakdown.explainLine", "title": "Breakdown: Explain Line" },
      { "command": "breakdown.nextLine", "title": "Breakdown: Next Line" },
      { "command": "breakdown.prevLine", "title": "Breakdown: Previous Line" },
      { "command": "breakdown.pushToTalk", "title": "Breakdown: Push to Talk" }
    ],
    "keybindings": [
      { "command": "breakdown.startSession", "key": "ctrl+k ctrl+e", "mac": "cmd+k cmd+e" },
      { "command": "breakdown.nextLine",     "key": "ctrl+k ctrl+n", "mac": "cmd+k cmd+n" },
      { "command": "breakdown.prevLine",     "key": "ctrl+k ctrl+p", "mac": "cmd+k cmd+p" },
      { "command": "breakdown.pushToTalk",   "key": "ctrl+k ctrl+space", "mac": "cmd+k cmd+space" },
      { "command": "breakdown.stopSession",  "key": "ctrl+k ctrl+q", "mac": "cmd+k cmd+q" }
    ]
  },
  "scripts": {
    "build": "node esbuild.host.config.js",
    "typecheck": "tsc --noEmit",
    "lint": "eslint src --ext .ts"
  },
  "devDependencies": {
    "@types/node": "^18.0.0",
    "@types/vscode": "^1.85.0",
    "esbuild": "^0.21.0",
    "typescript": "^5.4.0"
  },
  "dependencies": {
    "livekit-server-sdk": "^2.4.0"
  }
}
```

- [ ] **Step 3: Create extension-host tsconfig.json**

```json
// clients/vscode/extension-host/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true
  },
  "exclude": ["dist", "node_modules"]
}
```

- [ ] **Step 4: Create extension-host esbuild config**

```js
// clients/vscode/extension-host/esbuild.host.config.js
const esbuild = require("esbuild");

esbuild.build({
  entryPoints: ["src/extension.ts"],
  bundle: true,
  platform: "node",
  target: "node18",
  outfile: "dist/extension.js",
  external: ["vscode"],
  minify: process.env.NODE_ENV === "production",
  sourcemap: process.env.NODE_ENV !== "production",
  logLevel: "info",
}).catch(() => process.exit(1));
```

- [ ] **Step 5: Create webview package.json**

```json
// clients/vscode/webview/package.json
{
  "name": "breakdown-webview",
  "private": true,
  "scripts": {
    "build": "node esbuild.webview.config.js",
    "typecheck": "tsc --noEmit",
    "lint": "eslint src --ext .ts"
  },
  "devDependencies": {
    "esbuild": "^0.21.0",
    "typescript": "^5.4.0"
  },
  "dependencies": {
    "livekit-client": "^2.4.0"
  }
}
```

- [ ] **Step 6: Create webview tsconfig.json**

```json
// clients/vscode/webview/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "moduleResolution": "bundler"
  },
  "exclude": ["dist", "node_modules"]
}
```

- [ ] **Step 7: Create webview esbuild config**

```js
// clients/vscode/webview/esbuild.webview.config.js
const esbuild = require("esbuild");

esbuild.build({
  entryPoints: ["src/index.ts"],
  bundle: true,
  platform: "browser",
  target: "es2020",
  outfile: "../extension-host/dist/webview.js",
  minify: process.env.NODE_ENV === "production",
  sourcemap: process.env.NODE_ENV !== "production",
  logLevel: "info",
}).catch(() => process.exit(1));
```

- [ ] **Step 8: Install and verify**

```bash
cd clients/vscode
pnpm install
```

Expected: no errors, `node_modules` created in both packages

- [ ] **Step 9: Commit**

```bash
git add clients/vscode/
git commit -m "chore: scaffold VS Code extension workspace with two TypeScript contexts"
```

---

### Task 2: Message Bridge Protocol

**Files:**
- Create: `clients/vscode/webview/src/message_bridge.ts`

This module is shared protocol definitions and the postMessage wrapper. Defining it first prevents type drift between host and webview.

**Interfaces:**
- Produces: `HostToWebview` and `WebviewToHost` discriminated union types; `createBridge()` function

- [ ] **Step 1: Implement message_bridge.ts**

```typescript
// clients/vscode/webview/src/message_bridge.ts

// Messages from extension host -> webview
export type HostToWebview =
  | { type: "connect"; token: string; url: string; room: string }
  | { type: "disconnect" }
  | { type: "send_data"; payload: object };

// Messages from webview -> extension host
export type WebviewToHost =
  | { type: "ready" }
  | { type: "connected"; participantId: string }
  | { type: "disconnected"; reason: string }
  | { type: "error"; message: string }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "status"; state: "idle" | "explaining" | "listening" | "interrupted" };

declare function acquireVsCodeApi(): {
  postMessage(msg: WebviewToHost): void;
  getState(): unknown;
  setState(state: unknown): void;
};

export function createBridge() {
  const vscode = acquireVsCodeApi();

  function send(msg: WebviewToHost): void {
    vscode.postMessage(msg);
  }

  function onMessage(handler: (msg: HostToWebview) => void): void {
    window.addEventListener("message", (event: MessageEvent<HostToWebview>) => {
      handler(event.data);
    });
  }

  return { send, onMessage };
}
```

- [ ] **Step 2: Commit**

```bash
git add clients/vscode/webview/src/message_bridge.ts
git commit -m "feat: add typed postMessage bridge protocol between host and webview"
```

---

### Task 3: Webview -- LiveKit Room and Audio

**Files:**
- Create: `clients/vscode/webview/src/livekit_room.ts`
- Create: `clients/vscode/webview/src/audio_player.ts`
- Create: `clients/vscode/webview/src/mic_capture.ts`
- Create: `clients/vscode/webview/src/index.ts`

**Interfaces:**
- Produces: bundled `webview.js` that connects to a LiveKit room, plays TTS audio, captures mic

- [ ] **Step 1: Implement audio_player.ts**

```typescript
// clients/vscode/webview/src/audio_player.ts

export class AudioPlayer {
  private _context: AudioContext | null = null;

  private _getContext(): AudioContext {
    if (!this._context) {
      this._context = new AudioContext();
    }
    return this._context;
  }

  attachTrack(track: MediaStreamTrack): void {
    const ctx = this._getContext();
    const stream = new MediaStream([track]);
    const source = ctx.createMediaStreamSource(stream);
    source.connect(ctx.destination);
    if (ctx.state === "suspended") {
      ctx.resume();
    }
  }

  stop(): void {
    this._context?.close();
    this._context = null;
  }
}
```

- [ ] **Step 2: Implement mic_capture.ts**

```typescript
// clients/vscode/webview/src/mic_capture.ts

export class MicCapture {
  private _stream: MediaStream | null = null;
  private _track: MediaStreamTrack | null = null;

  async start(): Promise<MediaStreamTrack | null> {
    try {
      this._stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
      this._track = this._stream.getAudioTracks()[0] ?? null;
      return this._track;
    } catch (err) {
      console.error("Mic access denied:", err);
      return null;
    }
  }

  stop(): void {
    this._stream?.getTracks().forEach((t) => t.stop());
    this._stream = null;
    this._track = null;
  }

  get track(): MediaStreamTrack | null {
    return this._track;
  }
}
```

- [ ] **Step 3: Implement livekit_room.ts**

```typescript
// clients/vscode/webview/src/livekit_room.ts
import {
  Room,
  RoomEvent,
  Track,
  RemoteTrackPublication,
  RemoteParticipant,
  DataPacket_Kind,
} from "livekit-client";
import { AudioPlayer } from "./audio_player";
import type { WebviewToHost } from "./message_bridge";

type SendFn = (msg: WebviewToHost) => void;

export class LiveKitRoom {
  private _room: Room;
  private _player: AudioPlayer;

  constructor(private readonly _send: SendFn) {
    this._room = new Room();
    this._player = new AudioPlayer();
  }

  async connect(url: string, token: string): Promise<void> {
    this._room.on(RoomEvent.TrackSubscribed, (track, _pub, _participant) => {
      if (track.kind === Track.Kind.Audio) {
        this._player.attachTrack(track.mediaStreamTrack);
      }
    });

    this._room.on(RoomEvent.Disconnected, (reason) => {
      this._send({ type: "disconnected", reason: String(reason) });
      this._player.stop();
    });

    this._room.on(RoomEvent.DataReceived, (payload, _participant, _kind) => {
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg.type === "transcript") {
          this._send({ type: "transcript", text: msg.text, final: msg.final });
        } else if (msg.type === "status") {
          this._send({ type: "status", state: msg.state });
        }
      } catch {
        // ignore malformed packets
      }
    });

    await this._room.connect(url, token);
    this._send({ type: "connected", participantId: this._room.localParticipant.sid });
  }

  async sendData(payload: object): Promise<void> {
    const data = new TextEncoder().encode(JSON.stringify({ v: 1, ...payload }));
    await this._room.localParticipant.publishData(data, { reliable: true });
  }

  async publishMicTrack(track: MediaStreamTrack): Promise<void> {
    await this._room.localParticipant.publishTrack(track);
  }

  async disconnect(): Promise<void> {
    await this._room.disconnect();
    this._player.stop();
  }
}
```

- [ ] **Step 4: Implement index.ts**

```typescript
// clients/vscode/webview/src/index.ts
import { createBridge, type HostToWebview } from "./message_bridge";
import { LiveKitRoom } from "./livekit_room";
import { MicCapture } from "./mic_capture";

const bridge = createBridge();
const mic = new MicCapture();
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
    mic.stop();
    room = null;
    return;
  }

  if (msg.type === "send_data") {
    await room?.sendData(msg.payload);
    return;
  }
});
```

- [ ] **Step 5: Build webview bundle**

```bash
cd clients/vscode/webview
pnpm build
```

Expected: `clients/vscode/extension-host/dist/webview.js` created, no errors

- [ ] **Step 6: Typecheck**

```bash
cd clients/vscode/webview
pnpm typecheck
```

Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add clients/vscode/webview/src/
git commit -m "feat: add webview with LiveKit room, audio player, and mic capture"
```

---

### Task 4: Extension Host -- Token Client and Process Manager

**Files:**
- Create: `clients/vscode/extension-host/src/token_client.ts`
- Create: `clients/vscode/extension-host/src/process_manager.ts`

**Interfaces:**
- Produces:
  - `readRuntimeInfo(breakdownDir: string) -> { port: number; livekit_url: string } | null`
  - `getToken(port: number, room: string) -> Promise<{ token: string; url: string }>`
  - `ProcessManager` class with `start(workspaceRoot: string): void`, `stop(): void`, `isRunning(): boolean`

- [ ] **Step 1: Implement token_client.ts**

```typescript
// clients/vscode/extension-host/src/token_client.ts
import * as fs from "fs";
import * as path from "path";
import * as http from "http";

interface RuntimeInfo {
  port: number;
  livekit_url: string;
}

interface TokenResponse {
  token: string;
  url: string;
}

export function readRuntimeInfo(breakdownDir: string): RuntimeInfo | null {
  const runtimePath = path.join(breakdownDir, "runtime.json");
  try {
    const raw = fs.readFileSync(runtimePath, "utf-8");
    return JSON.parse(raw) as RuntimeInfo;
  } catch {
    return null;
  }
}

export async function getToken(port: number, room: string): Promise<TokenResponse> {
  return new Promise((resolve, reject) => {
    const req = http.get(
      `http://127.0.0.1:${port}/token?room=${encodeURIComponent(room)}`,
      (res) => {
        let body = "";
        res.on("data", (chunk: Buffer) => { body += chunk.toString(); });
        res.on("end", () => {
          try {
            resolve(JSON.parse(body) as TokenResponse);
          } catch {
            reject(new Error(`Invalid token response: ${body}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.setTimeout(3000, () => {
      req.destroy();
      reject(new Error("Token server request timed out"));
    });
  });
}

export async function getTokenWithRetry(
  breakdownDir: string,
  room: string,
  maxAttempts = 10,
  delayMs = 500,
): Promise<TokenResponse> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const info = readRuntimeInfo(breakdownDir);
    if (info) {
      try {
        return await getToken(info.port, room);
      } catch {
        // server not ready yet
      }
    }
    if (attempt < maxAttempts) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  throw new Error(
    "Could not reach Breakdown token server. Is `breakdown start` running?"
  );
}
```

- [ ] **Step 2: Implement process_manager.ts**

```typescript
// clients/vscode/extension-host/src/process_manager.ts
import * as cp from "child_process";
import * as os from "os";
import { window } from "vscode";

export class ProcessManager {
  private _process: cp.ChildProcess | null = null;

  start(workspaceRoot: string): void {
    if (this._process) {
      return;
    }

    const cmd = "breakdown";
    const args = ["start", workspaceRoot];

    try {
      this._process = cp.spawn(cmd, args, {
        cwd: workspaceRoot,
        env: { ...process.env },
        stdio: ["ignore", "pipe", "pipe"],
      });

      this._process.stdout?.on("data", (data: Buffer) => {
        console.log("[breakdown]", data.toString().trim());
      });

      this._process.stderr?.on("data", (data: Buffer) => {
        console.error("[breakdown]", data.toString().trim());
      });

      this._process.on("exit", (code) => {
        console.log(`[breakdown] process exited with code ${code}`);
        this._process = null;
      });

      this._process.on("error", (err) => {
        if ((err as NodeJS.ErrnoException).code === "ENOENT") {
          window.showErrorMessage(
            "Breakdown: `breakdown` command not found. Install it with: pip install breakdown",
          );
        } else {
          window.showErrorMessage(`Breakdown: failed to start process: ${err.message}`);
        }
        this._process = null;
      });
    } catch (err) {
      window.showErrorMessage(`Breakdown: could not spawn process: ${String(err)}`);
    }
  }

  stop(): void {
    if (!this._process) {
      return;
    }
    if (os.platform() === "win32") {
      cp.exec(`taskkill /F /T /PID ${this._process.pid}`);
    } else {
      this._process.kill("SIGTERM");
    }
    this._process = null;
  }

  isRunning(): boolean {
    return this._process !== null;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add clients/vscode/extension-host/src/token_client.ts clients/vscode/extension-host/src/process_manager.ts
git commit -m "feat: add token client with retry and process manager with SIGTERM"
```

---

### Task 5: Extension Host -- Webview Manager and Commands

**Files:**
- Create: `clients/vscode/extension-host/src/webview_manager.ts`
- Create: `clients/vscode/extension-host/src/commands.ts`

**Interfaces:**
- Consumes: `ProcessManager`, `getTokenWithRetry`
- Produces: `WebviewManager` class; `registerCommands(ctx, manager, processManager) -> Disposable[]`

- [ ] **Step 1: Implement webview_manager.ts**

```typescript
// clients/vscode/extension-host/src/webview_manager.ts
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import type { HostToWebview, WebviewToHost } from "../../webview/src/message_bridge";

export class WebviewManager {
  private _panel: vscode.WebviewPanel | null = null;
  private _statusBar: vscode.StatusBarItem;

  constructor(private readonly _context: vscode.ExtensionContext) {
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
      this._panel.reveal();
      return;
    }

    this._panel = vscode.window.createWebviewPanel(
      "breakdown",
      "Breakdown",
      { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
      {
        enableScripts: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(this._context.extensionPath, "dist")),
        ],
      },
    );

    const webviewScriptUri = this._panel.webview.asWebviewUri(
      vscode.Uri.file(path.join(this._context.extensionPath, "dist", "webview.js")),
    );

    this._panel.webview.html = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Breakdown</title></head>
<body>
<script src="${webviewScriptUri}"></script>
</body>
</html>`;

    this._panel.webview.onDidReceiveMessage((msg: WebviewToHost) => {
      if (msg.type === "ready") {
        this.send({ type: "connect", token, url, room });
      } else if (msg.type === "status") {
        this._statusBar.text = `$(unmute) Breakdown: ${msg.state}`;
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
```

- [ ] **Step 2: Implement commands.ts**

```typescript
// clients/vscode/extension-host/src/commands.ts
import * as vscode from "vscode";
import * as crypto from "crypto";
import * as path from "path";
import { getTokenWithRetry } from "./token_client";
import { ProcessManager } from "./process_manager";
import { WebviewManager } from "./webview_manager";

function workspaceRoot(): string | null {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    return null;
  }
  if (folders.length === 1) {
    return folders[0].fsPath;
  }
  // multi-root: pick first; future enhancement to prompt
  return folders[0].fsPath;
}

function roomName(wsRoot: string): string {
  const hash = crypto.createHash("sha256").update(wsRoot).digest("hex").slice(0, 12);
  return `breakdown-${hash}`;
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
  webviewManager: WebviewManager,
  processManager: ProcessManager,
): vscode.Disposable[] {
  return [
    vscode.commands.registerCommand("breakdown.startSession", async () => {
      const root = workspaceRoot();
      if (!root) {
        vscode.window.showErrorMessage("Breakdown: open a workspace folder first.");
        return;
      }
      processManager.start(root);
      const breakdownDir = path.join(root, ".breakdown");
      const room = roomName(root);
      try {
        const { token, url } = await getTokenWithRetry(breakdownDir, room);
        webviewManager.show(token, url, room);
      } catch (err) {
        vscode.window.showErrorMessage(`Breakdown: ${String(err)}`);
      }
    }),

    vscode.commands.registerCommand("breakdown.stopSession", () => {
      webviewManager.send({ type: "disconnect" });
      processManager.stop();
    }),

    vscode.commands.registerCommand("breakdown.explainLine", () => {
      const info = activeLineInfo();
      if (!info) { return; }
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
  ];
}
```

- [ ] **Step 3: Commit**

```bash
git add clients/vscode/extension-host/src/webview_manager.ts clients/vscode/extension-host/src/commands.ts
git commit -m "feat: add webview manager and command handlers"
```

---

### Task 6: Extension Entry Point and Build

**Files:**
- Create: `clients/vscode/extension-host/src/extension.ts`

**Interfaces:**
- Produces: working VS Code extension that activates, starts the Python core, and opens the Webview

- [ ] **Step 1: Implement extension.ts**

```typescript
// clients/vscode/extension-host/src/extension.ts
import * as vscode from "vscode";
import { ProcessManager } from "./process_manager";
import { WebviewManager } from "./webview_manager";
import { registerCommands } from "./commands";

let _processManager: ProcessManager | null = null;
let _webviewManager: WebviewManager | null = null;

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

  _processManager = new ProcessManager();
  _webviewManager = new WebviewManager(context);

  const disposables = registerCommands(context, _webviewManager, _processManager);
  context.subscriptions.push(...disposables, _webviewManager);
}

export function deactivate(): void {
  _processManager?.stop();
  _webviewManager?.dispose();
}
```

- [ ] **Step 2: Build both bundles**

```bash
cd clients/vscode/webview
pnpm build

cd ../extension-host
pnpm build
```

Expected: `dist/webview.js` and `dist/extension.js` both created without errors

- [ ] **Step 3: Typecheck both projects**

```bash
cd clients/vscode
pnpm typecheck
```

Expected: no TypeScript errors

- [ ] **Step 4: Verify bundle sizes**

```bash
ls -lh clients/vscode/extension-host/dist/
```

Expected: `extension.js` under 500KB, `webview.js` under 2MB (livekit-client is large; acceptable)

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/extension-host/src/extension.ts
git commit -m "feat: add extension entry point with remote detection and clean deactivation"
```

---

### Task 7: Deploy Configuration and Final Verification

**Files:**
- Create: `deploy/docker-compose.livekit.yml`
- Create: `clients/vscode/.vscodeignore`

**Interfaces:**
- Produces: `docker compose -f deploy/docker-compose.livekit.yml up -d` starts a local LiveKit server; VSIX can be packaged

- [ ] **Step 1: Create docker-compose.livekit.yml**

```yaml
# deploy/docker-compose.livekit.yml
version: "3.8"
services:
  livekit:
    image: livekit/livekit-server:latest
    ports:
      - "7880:7880"
      - "7881:7881"
      - "7882:7882/udp"
    environment:
      LIVEKIT_KEYS: "devkey: devsecret1234567890123456789012345678"
    command: --dev
    restart: unless-stopped
```

- [ ] **Step 2: Create .vscodeignore**

```
# clients/vscode/extension-host/.vscodeignore
.vscode/**
node_modules/**
src/**
tsconfig.json
esbuild.host.config.js
*.map
```

- [ ] **Step 3: Verify extension can be packaged**

```bash
cd clients/vscode/extension-host
npx @vscode/vsce package --no-dependencies
```

Expected: a `.vsix` file is created without errors

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.livekit.yml clients/vscode/extension-host/.vscodeignore
git commit -m "chore: add local LiveKit Docker config and VSIX packaging setup"
```

---

## Plan B Complete

After Task 7, the VS Code extension is fully built:

- `Cmd+K Cmd+E` starts a session: spawns Python core, gets JWT, opens Webview
- `Cmd+K Cmd+N` / `Cmd+K Cmd+P` navigates lines
- `Cmd+K Cmd+Space` initiates push-to-talk
- `Cmd+K Cmd+Q` stops the session and kills the Python process
- Status bar shows current state (inactive / explaining / listening)
- Remote environment warning shown if running in Codespaces or Remote SSH
- VSIX can be packaged for Marketplace submission

**Next:** Plan C (Repository Infrastructure).
