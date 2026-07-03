// clients/vscode/extension-host/src/docker_manager.ts
// No top-level `vscode` import — see Global Constraints.
import * as cp from "child_process";
import * as path from "path";
import * as http from "http";

export type ExecFn = (command: string, timeoutMs: number) => Promise<void>;
export type PortCheckFn = (url: string) => Promise<boolean>;

export function execCommand(command: string, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    cp.exec(command, { timeout: timeoutMs }, (err) => {
      if (err) {
        reject(err);
        return;
      }
      resolve();
    });
  });
}

export function checkHttpOk(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(!!res.statusCode && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

export class DockerManager {
  constructor(
    private readonly _exec: ExecFn = execCommand,
    private readonly _checkPort: PortCheckFn = checkHttpOk,
    private readonly _maxAttempts = 30,
    private readonly _delayMs = 500,
  ) {}

  async ensureRunning(extensionPath: string): Promise<void> {
    try {
      await this._exec("docker info", 3000);
    } catch {
      throw new Error(
        "Docker isn't running. Install Docker Desktop, start it, and retry — " +
          "or set LIVEKIT_URL via Breakdown: Set API Key to point at a LiveKit Cloud project instead.",
      );
    }

    const composePath = path.join(extensionPath, "resources", "docker-compose.livekit.yml");
    await this._exec(`docker compose -f "${composePath}" up -d`, 30000);

    await this._waitForLiveKit();
  }

  private async _waitForLiveKit(): Promise<void> {
    for (let attempt = 1; attempt <= this._maxAttempts; attempt++) {
      if (await this._checkPort("http://127.0.0.1:7880")) {
        return;
      }
      if (attempt < this._maxAttempts) {
        await new Promise((r) => setTimeout(r, this._delayMs));
      }
    }
    throw new Error("LiveKit did not become ready within 15s.");
  }
}
