// clients/vscode/extension-host/src/extension.ts
import * as vscode from "vscode";
import { ProcessManager } from "./process_manager";
import { ChatViewProvider, VIEW_ID } from "./chat_view_provider";
import { registerCommands } from "./commands";
import { InlineStripManager } from "./inline_strip_manager";
import { DecorationHostAdapter } from "./inline_strip_decorator";

let _processManager: ProcessManager | null = null;
let _chatViewProvider: ChatViewProvider | null = null;
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
  _chatViewProvider = new ChatViewProvider(context, inlineStripManager);

  const disposables = [
    vscode.window.registerWebviewViewProvider(VIEW_ID, _chatViewProvider),
    ...registerCommands(context, _chatViewProvider, _processManager, inlineStripManager),
  ];
  context.subscriptions.push(...disposables, _chatViewProvider);
}

export function deactivate(): void {
  _processManager?.stop();
  _chatViewProvider?.dispose();
  _decorationAdapter?.dispose();
}
