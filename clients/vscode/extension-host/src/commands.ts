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
    return folders[0].uri.fsPath;
  }
  // multi-root: pick first; future enhancement to prompt
  return folders[0].uri.fsPath;
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
