// clients/vscode/extension-host/src/install_checker.ts
// No top-level `vscode` import — see Global Constraints.

export type CommandExistsFn = (cmd: string) => Promise<boolean>;
export type ShowInstallPromptFn = () => Promise<boolean>;
export type RunInstallFn = (command: string) => void;
export type NotifyFn = (message: string) => void;

export interface InstallCheckerDeps {
  commandExists: CommandExistsFn;
  showInstallPrompt: ShowInstallPromptFn;
  runInstall: RunInstallFn;
  notify: NotifyFn;
  waitMaxAttempts?: number;
  waitDelayMs?: number;
}

export class InstallChecker {
  private readonly _waitMaxAttempts: number;
  private readonly _waitDelayMs: number;

  constructor(private readonly _deps: InstallCheckerDeps) {
    this._waitMaxAttempts = _deps.waitMaxAttempts ?? 60;
    this._waitDelayMs = _deps.waitDelayMs ?? 2000;
  }

  async ensureInstalled(): Promise<boolean> {
    if (await this._deps.commandExists("breakdown")) {
      return true;
    }
    if (!(await this._deps.showInstallPrompt())) {
      return false;
    }
    const hasUv = await this._deps.commandExists("uv");
    const installCmd = hasUv ? "uv tool install breakdown-ai" : "pip install --user breakdown-ai";
    this._deps.runInstall(installCmd);
    this._deps.notify("Installing Breakdown core in the terminal. This may take a minute.");
    return await this._waitForInstall();
  }

  private async _waitForInstall(): Promise<boolean> {
    for (let attempt = 1; attempt <= this._waitMaxAttempts; attempt++) {
      await new Promise((r) => setTimeout(r, this._waitDelayMs));
      if (await this._deps.commandExists("breakdown")) {
        return true;
      }
    }
    this._deps.notify(
      "Breakdown: still can't find the `breakdown` command. Check the install terminal for errors, then try Start Session again.",
    );
    return false;
  }
}
