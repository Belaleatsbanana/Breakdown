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

  isConnected(): boolean {
    return this._panel !== null;
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
