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
