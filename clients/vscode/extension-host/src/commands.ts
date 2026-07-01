// clients/vscode/extension-host/src/commands.ts
import * as vscode from "vscode";
import * as path from "path";
import { getToken, getTokenWithRetry, readRuntimeInfo } from "./token_client";
import { ProcessManager } from "./process_manager";
import { WebviewManager } from "./webview_manager";
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
      if (!webviewManager.isConnected()) {
        vscode.window.showErrorMessage(
          "Breakdown: start a session first (Ctrl+K Ctrl+E / Cmd+K Cmd+E).",
        );
        return;
      }
      inlineStripManager.show(info.line);
      webviewManager.send({ type: "send_data", payload: { type: "explain", ...info } });
    }),

    vscode.commands.registerCommand("breakdown.nextLine", () => {
      webviewManager.send({ type: "send_data", payload: { type: "next" } });
    }),

    vscode.commands.registerCommand("breakdown.prevLine", () => {
      webviewManager.send({ type: "send_data", payload: { type: "prev" } });
    }),

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

    vscode.commands.registerCommand("breakdown.dismissInlineStrip", () => {
      inlineStripManager.dismiss();
    }),
  ];
}
