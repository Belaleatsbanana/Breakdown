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
    const proc = this._process;
    this._process = null;

    if (os.platform() === "win32") {
      cp.exec(`taskkill /F /T /PID ${proc.pid}`);
      return;
    }

    proc.kill("SIGTERM");
    // Escalate to SIGKILL if the process doesn't exit within 5 seconds
    const escalation = setTimeout(() => {
      if (!proc.killed) {
        proc.kill("SIGKILL");
      }
    }, 5000);
    proc.once("exit", () => clearTimeout(escalation));
  }

  isRunning(): boolean {
    return this._process !== null;
  }
}
