// clients/vscode/extension-host/src/commands.ts
import * as vscode from "vscode";
import * as path from "path";
import * as os from "os";
import * as cp from "child_process";
import { getToken, getTokenWithRetry, readRuntimeInfo } from "./token_client";
import { ProcessManager } from "./process_manager";
import type { ChatViewProvider } from "./chat_view_provider";
import type { InlineStripManager } from "./inline_strip_manager";
import { SecretsManager, API_KEY_ENTRIES } from "./secrets_manager";
import type { DockerManager } from "./docker_manager";
import { InstallChecker } from "./install_checker";

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

function commandExists(cmd: string): Promise<boolean> {
  const checkCmd = os.platform() === "win32" ? `where ${cmd}` : `which ${cmd}`;
  return new Promise((resolve) => {
    cp.exec(checkCmd, (err) => resolve(!err));
  });
}

function makeInstallChecker(): InstallChecker {
  return new InstallChecker({
    commandExists,
    showInstallPrompt: async () => {
      const choice = await vscode.window.showErrorMessage("Breakdown core not found.", "Install Now");
      return choice === "Install Now";
    },
    runInstall: (command) => {
      const terminal = vscode.window.createTerminal("Breakdown Install");
      terminal.show();
      terminal.sendText(command);
    },
    notify: (message) => {
      vscode.window.showInformationMessage(message);
    },
  });
}

async function promptForApiKey(secretsManager: SecretsManager): Promise<void> {
  const picked = await vscode.window.showQuickPick(
    API_KEY_ENTRIES.map((entry) => ({
      label: entry.label,
      description: entry.description,
      envVar: entry.envVar,
    })),
    { placeHolder: "Select which API key to set" },
  );
  if (!picked) {
    return;
  }
  const value = await vscode.window.showInputBox({
    password: true,
    prompt: `Enter your ${picked.label} API key`,
    ignoreFocusOut: true,
  });
  if (!value) {
    return;
  }
  await secretsManager.store(picked.envVar, value);
}

export function registerCommands(
  ctx: vscode.ExtensionContext,
  chatView: ChatViewProvider,
  processManager: ProcessManager,
  inlineStripManager: InlineStripManager,
  secretsManager: SecretsManager,
  dockerManager: DockerManager,
): vscode.Disposable[] {
  return [
    vscode.commands.registerCommand("breakdown.startSession", async () => {
      const root = workspaceRoot();
      if (!root) {
        vscode.window.showErrorMessage("Breakdown: open a workspace folder first.");
        return;
      }

      if (!(await makeInstallChecker().ensureInstalled())) {
        return;
      }

      // A stored LIVEKIT_URL means the user configured a LiveKit Cloud
      // project via Breakdown: Set API Key — skip the self-hosted Docker
      // path entirely rather than forcing Docker to be running anyway.
      const preDockerEnv = await secretsManager.getStoredEnv();
      if (!preDockerEnv.LIVEKIT_URL) {
        try {
          await dockerManager.ensureRunning(ctx.extensionPath);
        } catch (err) {
          vscode.window.showErrorMessage(`Breakdown: ${String(err)}`);
          return;
        }
      }

      if (!(await secretsManager.hasAnyLlmKey())) {
        await promptForApiKey(secretsManager);
        if (!(await secretsManager.hasAnyLlmKey())) {
          vscode.window.showErrorMessage("Breakdown: at least one LLM API key is required.");
          return;
        }
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
        const storedEnv = await secretsManager.getStoredEnv();
        processManager.start(root, {
          LIVEKIT_URL: "ws://localhost:7880",
          LIVEKIT_API_KEY: "devkey",
          LIVEKIT_API_SECRET: "devsecret1234567890123456789012345678",
          ...storedEnv,
        });
      }

      try {
        // 20 attempts × 500 ms = 10 s, enough for a cold agent start (~8 s)
        const { token, url, room } = await getTokenWithRetry(breakdownDir, 20, 500);
        chatView.connect(token, url, room);
      } catch (err) {
        vscode.window.showErrorMessage(`Breakdown: ${String(err)}`);
      }
    }),

    vscode.commands.registerCommand("breakdown.setApiKey", async () => {
      await promptForApiKey(secretsManager);
    }),

    vscode.commands.registerCommand("breakdown.stopSession", () => {
      chatView.send({ type: "disconnect" });
      inlineStripManager.dismiss();
      processManager.stop();
    }),

    vscode.commands.registerCommand("breakdown.explainLine", () => {
      const info = activeLineInfo();
      if (!info) {
        return;
      }
      if (!chatView.isConnected()) {
        vscode.window.showErrorMessage(
          "Breakdown: start a session first (Ctrl+K Ctrl+E / Cmd+K Cmd+E).",
        );
        return;
      }
      inlineStripManager.show(info.line);
      chatView.send({ type: "rpc", method: "explain", payload: info });
    }),

    vscode.commands.registerCommand("breakdown.nextLine", () => {
      chatView.send({ type: "rpc", method: "next", payload: {} });
    }),

    vscode.commands.registerCommand("breakdown.prevLine", () => {
      chatView.send({ type: "rpc", method: "prev", payload: {} });
    }),

    vscode.commands.registerCommand("breakdown.askQuestion", async () => {
      if (!chatView.isConnected()) {
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
      chatView.send({ type: "rpc", method: "ask", payload: { text } });
    }),

    vscode.commands.registerCommand("breakdown.dismissInlineStrip", () => {
      inlineStripManager.dismiss();
    }),
  ];
}
