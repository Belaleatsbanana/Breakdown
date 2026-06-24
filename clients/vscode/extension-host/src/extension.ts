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
