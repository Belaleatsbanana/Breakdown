// clients/vscode/extension-host/src/install_checker.test.ts
import assert from "node:assert/strict";
import { InstallChecker } from "./install_checker";

describe("InstallChecker", () => {
  it("ensureInstalled() returns true immediately when breakdown is already on PATH", async () => {
    const runInstallCalls: string[] = [];
    const checker = new InstallChecker({
      commandExists: async (cmd) => cmd === "breakdown",
      showInstallPrompt: async () => {
        throw new Error("should not be called");
      },
      runInstall: (cmd) => runInstallCalls.push(cmd),
      notify: () => {},
    });
    assert.equal(await checker.ensureInstalled(), true);
    assert.deepEqual(runInstallCalls, []);
  });

  it("ensureInstalled() returns false without installing when the user declines the prompt", async () => {
    const runInstallCalls: string[] = [];
    const checker = new InstallChecker({
      commandExists: async () => false,
      showInstallPrompt: async () => false,
      runInstall: (cmd) => runInstallCalls.push(cmd),
      notify: () => {},
    });
    assert.equal(await checker.ensureInstalled(), false);
    assert.deepEqual(runInstallCalls, []);
  });

  it("ensureInstalled() runs the uv install command when uv is on PATH", async () => {
    const runInstallCalls: string[] = [];
    const checker = new InstallChecker({
      commandExists: async (cmd) => cmd === "uv",
      showInstallPrompt: async () => true,
      runInstall: (cmd) => runInstallCalls.push(cmd),
      notify: () => {},
      waitMaxAttempts: 1,
      waitDelayMs: 1,
    });
    await checker.ensureInstalled();
    assert.deepEqual(runInstallCalls, ["uv tool install breakdown-ai"]);
  });

  it("ensureInstalled() falls back to pip when uv is not on PATH", async () => {
    const runInstallCalls: string[] = [];
    const checker = new InstallChecker({
      commandExists: async () => false,
      showInstallPrompt: async () => true,
      runInstall: (cmd) => runInstallCalls.push(cmd),
      notify: () => {},
      waitMaxAttempts: 1,
      waitDelayMs: 1,
    });
    await checker.ensureInstalled();
    assert.deepEqual(runInstallCalls, ["pip install --user breakdown-ai"]);
  });

  it("ensureInstalled() returns true once the post-install poll finds breakdown on PATH", async () => {
    let pollCount = 0;
    const checker = new InstallChecker({
      commandExists: async (cmd) => {
        if (cmd === "uv") {
          return false;
        }
        // breakdown check: not found on the pre-install check (pollCount 0),
        // found starting from the 2nd post-install poll attempt.
        pollCount += 1;
        return pollCount >= 3;
      },
      showInstallPrompt: async () => true,
      runInstall: () => {},
      notify: () => {},
      waitMaxAttempts: 5,
      waitDelayMs: 1,
    });
    assert.equal(await checker.ensureInstalled(), true);
  });

  it("ensureInstalled() returns false and notifies once the post-install poll is exhausted", async () => {
    const notifications: string[] = [];
    const checker = new InstallChecker({
      commandExists: async () => false,
      showInstallPrompt: async () => true,
      runInstall: () => {},
      notify: (msg) => notifications.push(msg),
      waitMaxAttempts: 2,
      waitDelayMs: 1,
    });
    assert.equal(await checker.ensureInstalled(), false);
    assert.ok(notifications.some((m) => m.includes("still can't find")));
  });
});
