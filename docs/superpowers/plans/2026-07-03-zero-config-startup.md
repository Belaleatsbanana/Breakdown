# Zero-Config Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Breakdown: Start Session` a self-healing bootstrap so a first-time user only installs the extension, sets one API key, and runs a command — no manual `docker compose up`, no manual `pip install`, no `.env` editing.

**Architecture:** Three new small, independently-testable modules (`secrets_manager.ts`, `docker_manager.ts`, `install_checker.ts`) each hold pure logic behind an injected-dependency interface, following the codebase's existing split between testable logic and untested VS Code API glue (the same pattern `inline_strip_manager.ts`/`inline_strip_decorator.ts` already use). `commands.ts` wires the real VS Code-backed implementations into these modules and sequences them at the top of `breakdown.startSession`.

**Tech Stack:** TypeScript (strict), VS Code `SecretStorage`/`QuickPick`/`Terminal` APIs, Node `child_process`/`http`, Docker Compose.

## Global Constraints

- TypeScript strict mode, no `any` except where forced by the VS Code API.
- Commit prefixes limited to `feat:`/`fix:`/`docs:`/`perf:`/`chore:`/`test:`, no scope in parentheses, **no Co-Authored-By trailer** (this repo's established convention — plain commits only).
- A file that does `import ... from "vscode"` at module scope cannot be loaded by this project's test runner (`mocha --require ts-node/register`) — confirmed empirically: it throws `Cannot find module 'vscode'` (`MODULE_NOT_FOUND`) at `require` time, even if the vscode-touching code path is never executed. Every new module that needs unit tests must have **zero** top-level `vscode` import; VS Code API calls are injected as constructor dependencies, with the real implementations constructed only in `commands.ts` (which already imports `vscode` freely and is never unit tested, matching the codebase's existing convention).
- `docs/superpowers/specs/2026-07-03-zero-config-startup-design.md` is the approved spec — deviations from it must be justified in this plan, not silently made.
- Real API references already verified against the installed `@types/vscode@1.125.0`: `SecretStorage.get(key): Thenable<string|undefined>`, `SecretStorage.store(key, value): Thenable<void>`, `window.showQuickPick<T extends QuickPickItem>(...)`, `window.showInputBox({password, prompt, ignoreFocusOut})`, `Terminal.sendText(text, shouldExecute?)`, `window.createTerminal(name)`.
- Publisher: `belaleatsbanana`. Repository: `https://github.com/Belaleatsbanana/Breakdown`.

---

## Task 1: `secrets_manager.ts` — API key storage (pure, testable)

**Files:**
- Create: `clients/vscode/extension-host/src/secrets_manager.ts`
- Test: `clients/vscode/extension-host/src/secrets_manager.test.ts`

**Interfaces:**
- Produces: `interface ApiKeyEntry { envVar: string; label: string; description: string }`. `const API_KEY_ENTRIES: ApiKeyEntry[]`. `interface SecretStore { get(key: string): PromiseLike<string | undefined>; store(key: string, value: string): PromiseLike<void> }`. `class SecretsManager` with `constructor(secrets: SecretStore)`, `getStoredEnv(): Promise<Record<string, string>>`, `hasAnyLlmKey(): Promise<boolean>`, `store(envVar: string, value: string): Promise<void>`.

- [ ] **Step 1: Write the failing tests**

Create `clients/vscode/extension-host/src/secrets_manager.test.ts`:

```typescript
// clients/vscode/extension-host/src/secrets_manager.test.ts
import assert from "node:assert/strict";
import { SecretsManager, type SecretStore } from "./secrets_manager";

class FakeSecretStore implements SecretStore {
  private _store = new Map<string, string>();

  async get(key: string): Promise<string | undefined> {
    return this._store.get(key);
  }

  async store(key: string, value: string): Promise<void> {
    this._store.set(key, value);
  }
}

describe("SecretsManager", () => {
  it("hasAnyLlmKey() is false when nothing is stored", async () => {
    const manager = new SecretsManager(new FakeSecretStore());
    assert.equal(await manager.hasAnyLlmKey(), false);
  });

  it("hasAnyLlmKey() is true once an LLM key is stored", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.OPENAI_API_KEY", "sk-test");
    const manager = new SecretsManager(store);
    assert.equal(await manager.hasAnyLlmKey(), true);
  });

  it("hasAnyLlmKey() ignores non-LLM keys (TTS/embedding alternates)", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.JINA_API_KEY", "jina-test");
    const manager = new SecretsManager(store);
    assert.equal(await manager.hasAnyLlmKey(), false);
  });

  it("hasAnyLlmKey() ignores a stored LIVEKIT_URL (not an LLM key)", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.LIVEKIT_URL", "wss://my-project.livekit.cloud");
    const manager = new SecretsManager(store);
    assert.equal(await manager.hasAnyLlmKey(), false);
  });

  it("getStoredEnv() includes a stored LIVEKIT_URL alongside API keys", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.OPENAI_API_KEY", "sk-test");
    await store.store("breakdown.LIVEKIT_URL", "wss://my-project.livekit.cloud");
    const manager = new SecretsManager(store);
    assert.deepEqual(await manager.getStoredEnv(), {
      OPENAI_API_KEY: "sk-test",
      LIVEKIT_URL: "wss://my-project.livekit.cloud",
    });
  });

  it("getStoredEnv() returns only the keys that are set, by env var name", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.OPENAI_API_KEY", "sk-test");
    await store.store("breakdown.JINA_API_KEY", "jina-test");
    const manager = new SecretsManager(store);
    assert.deepEqual(await manager.getStoredEnv(), {
      OPENAI_API_KEY: "sk-test",
      JINA_API_KEY: "jina-test",
    });
  });

  it("getStoredEnv() returns an empty object when nothing is stored", async () => {
    const manager = new SecretsManager(new FakeSecretStore());
    assert.deepEqual(await manager.getStoredEnv(), {});
  });

  it("store() prefixes the storage key with breakdown.", async () => {
    const store = new FakeSecretStore();
    const manager = new SecretsManager(store);
    await manager.store("OPENAI_API_KEY", "sk-test");
    assert.equal(await store.get("breakdown.OPENAI_API_KEY"), "sk-test");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd clients/vscode/extension-host && npx mocha --require ts-node/register --extension ts "src/secrets_manager.test.ts"`
Expected: FAIL — `Cannot find module './secrets_manager'`

- [ ] **Step 3: Write the implementation**

Create `clients/vscode/extension-host/src/secrets_manager.ts`:

```typescript
// clients/vscode/extension-host/src/secrets_manager.ts
// No top-level `vscode` import — this file must load under the plain
// mocha/ts-node test runner, which has no `vscode` module available.
// The real vscode.SecretStorage is structurally compatible with
// SecretStore below (Thenable and PromiseLike are the same shape).

export interface ApiKeyEntry {
  envVar: string;
  label: string;
  description: string;
}

export const API_KEY_ENTRIES: ApiKeyEntry[] = [
  { envVar: "OPENAI_API_KEY", label: "OpenAI", description: "Recommended: covers LLM, TTS, and embeddings" },
  { envVar: "ANTHROPIC_API_KEY", label: "Anthropic", description: "LLM alternate" },
  { envVar: "MISTRAL_API_KEY", label: "Mistral", description: "LLM alternate" },
  { envVar: "GROQ_API_KEY", label: "Groq", description: "LLM alternate" },
  { envVar: "OPENROUTER_API_KEY", label: "OpenRouter", description: "LLM alternate" },
  { envVar: "TOGETHER_API_KEY", label: "Together", description: "LLM alternate" },
  { envVar: "PERPLEXITY_API_KEY", label: "Perplexity", description: "LLM alternate" },
  { envVar: "DEEPGRAM_API_KEY", label: "Deepgram", description: "TTS alternate" },
  { envVar: "ELEVENLABS_API_KEY", label: "ElevenLabs", description: "TTS alternate" },
  { envVar: "JINA_API_KEY", label: "Jina", description: "Embedding alternate" },
  { envVar: "GEMINI_API_KEY", label: "Gemini", description: "Embedding alternate" },
  { envVar: "LIVEKIT_URL", label: "LiveKit Cloud URL", description: "Optional: skip self-hosted Docker, use a LiveKit Cloud project instead" },
  { envVar: "LIVEKIT_API_KEY", label: "LiveKit Cloud API Key", description: "Required alongside LiveKit Cloud URL" },
  { envVar: "LIVEKIT_API_SECRET", label: "LiveKit Cloud API Secret", description: "Required alongside LiveKit Cloud URL" },
];

const LLM_ENV_VARS = new Set([
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "MISTRAL_API_KEY",
  "GROQ_API_KEY",
  "OPENROUTER_API_KEY",
  "TOGETHER_API_KEY",
  "PERPLEXITY_API_KEY",
]);

function storageKey(envVar: string): string {
  return `breakdown.${envVar}`;
}

export interface SecretStore {
  get(key: string): PromiseLike<string | undefined>;
  store(key: string, value: string): PromiseLike<void>;
}

export class SecretsManager {
  constructor(private readonly _secrets: SecretStore) {}

  async getStoredEnv(): Promise<Record<string, string>> {
    const env: Record<string, string> = {};
    for (const entry of API_KEY_ENTRIES) {
      const value = await this._secrets.get(storageKey(entry.envVar));
      if (value) {
        env[entry.envVar] = value;
      }
    }
    return env;
  }

  async hasAnyLlmKey(): Promise<boolean> {
    for (const envVar of LLM_ENV_VARS) {
      const value = await this._secrets.get(storageKey(envVar));
      if (value) {
        return true;
      }
    }
    return false;
  }

  async store(envVar: string, value: string): Promise<void> {
    await this._secrets.store(storageKey(envVar), value);
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd clients/vscode/extension-host && npx mocha --require ts-node/register --extension ts "src/secrets_manager.test.ts"`
Expected: PASS (8 tests)

- [ ] **Step 5: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add clients/vscode/extension-host/src/secrets_manager.ts clients/vscode/extension-host/src/secrets_manager.test.ts
git commit -m "feat: add SecretsManager for API key storage"
```

---

## Task 2: `docker_manager.ts` — LiveKit auto-start (pure, testable)

**Files:**
- Create: `clients/vscode/extension-host/src/docker_manager.ts`
- Test: `clients/vscode/extension-host/src/docker_manager.test.ts`

**Interfaces:**
- Produces: `type ExecFn = (command: string, timeoutMs: number) => Promise<void>`. `type PortCheckFn = (url: string) => Promise<boolean>`. `function execCommand: ExecFn` (real `child_process.exec`-backed default). `function checkHttpOk: PortCheckFn` (real `http.get`-backed default). `class DockerManager` with `constructor(exec?: ExecFn, checkPort?: PortCheckFn, maxAttempts?: number, delayMs?: number)`, `ensureRunning(extensionPath: string): Promise<void>`.

- [ ] **Step 1: Write the failing tests**

Create `clients/vscode/extension-host/src/docker_manager.test.ts`:

```typescript
// clients/vscode/extension-host/src/docker_manager.test.ts
import assert from "node:assert/strict";
import { DockerManager } from "./docker_manager";

describe("DockerManager", () => {
  it("ensureRunning() throws an actionable error when docker info fails", async () => {
    const exec = async (command: string): Promise<void> => {
      if (command === "docker info") {
        throw new Error("docker: command not found");
      }
    };
    const manager = new DockerManager(exec, async () => true);
    await assert.rejects(
      () => manager.ensureRunning("/fake/ext/path"),
      /Docker isn't running/,
    );
  });

  it("ensureRunning() runs docker compose up with the bundled compose file path", async () => {
    const calls: string[] = [];
    const exec = async (command: string): Promise<void> => {
      calls.push(command);
    };
    const manager = new DockerManager(exec, async () => true);
    await manager.ensureRunning("/fake/ext/path");
    assert.equal(calls[0], "docker info");
    assert.match(calls[1], /docker compose -f "\/fake\/ext\/path\/resources\/docker-compose\.livekit\.yml" up -d/);
  });

  it("ensureRunning() polls until the port check succeeds", async () => {
    let checkCount = 0;
    const exec = async (): Promise<void> => {};
    const checkPort = async (): Promise<boolean> => {
      checkCount += 1;
      return checkCount >= 3;
    };
    const manager = new DockerManager(exec, checkPort, 10, 5);
    await manager.ensureRunning("/fake/ext/path");
    assert.equal(checkCount, 3);
  });

  it("ensureRunning() throws after exhausting retries if LiveKit never becomes ready", async () => {
    const exec = async (): Promise<void> => {};
    const manager = new DockerManager(exec, async () => false, 3, 5);
    await assert.rejects(
      () => manager.ensureRunning("/fake/ext/path"),
      /LiveKit did not become ready/,
    );
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd clients/vscode/extension-host && npx mocha --require ts-node/register --extension ts "src/docker_manager.test.ts"`
Expected: FAIL — `Cannot find module './docker_manager'`

- [ ] **Step 3: Write the implementation**

Create `clients/vscode/extension-host/src/docker_manager.ts`:

```typescript
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd clients/vscode/extension-host && npx mocha --require ts-node/register --extension ts "src/docker_manager.test.ts"`
Expected: PASS (4 tests, completes in well under a second — all delays are 5-10ms in tests)

- [ ] **Step 5: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add clients/vscode/extension-host/src/docker_manager.ts clients/vscode/extension-host/src/docker_manager.test.ts
git commit -m "feat: add DockerManager to auto-start LiveKit via Docker Compose"
```

---

## Task 3: `install_checker.ts` — Python core auto-install (pure, testable)

**Files:**
- Create: `clients/vscode/extension-host/src/install_checker.ts`
- Test: `clients/vscode/extension-host/src/install_checker.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `type CommandExistsFn = (cmd: string) => Promise<boolean>`. `type ShowInstallPromptFn = () => Promise<boolean>`. `type RunInstallFn = (command: string) => void`. `type NotifyFn = (message: string) => void`. `interface InstallCheckerDeps { commandExists: CommandExistsFn; showInstallPrompt: ShowInstallPromptFn; runInstall: RunInstallFn; notify: NotifyFn; waitMaxAttempts?: number; waitDelayMs?: number }`. `class InstallChecker` with `constructor(deps: InstallCheckerDeps)`, `ensureInstalled(): Promise<boolean>`.

Note: the spec (`docs/superpowers/specs/2026-07-03-zero-config-startup-design.md`, Section 3) described this as a new method on `ProcessManager`. During planning, adding it there was found to conflict with the Global Constraint above — `process_manager.ts` already does `import { window } from "vscode"` at module scope for its existing `start()`/error-handling logic, so a test file importing it fails to load entirely, regardless of which method is under test. This plan splits the testable logic into this new vscode-free module instead, matching the existing `inline_strip_manager.ts`/`inline_strip_decorator.ts` split in the same codebase. `ProcessManager` itself is otherwise unchanged except for the `extraEnv` parameter added in Task 4.

- [ ] **Step 1: Write the failing tests**

Create `clients/vscode/extension-host/src/install_checker.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd clients/vscode/extension-host && npx mocha --require ts-node/register --extension ts "src/install_checker.test.ts"`
Expected: FAIL — `Cannot find module './install_checker'`

- [ ] **Step 3: Write the implementation**

Create `clients/vscode/extension-host/src/install_checker.ts`:

```typescript
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd clients/vscode/extension-host && npx mocha --require ts-node/register --extension ts "src/install_checker.test.ts"`
Expected: PASS (6 tests)

- [ ] **Step 5: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add clients/vscode/extension-host/src/install_checker.ts clients/vscode/extension-host/src/install_checker.test.ts
git commit -m "feat: add InstallChecker to auto-detect and prompt-install the Python core"
```

---

## Task 4: `process_manager.ts` — thread `extraEnv` through `start()`

**Files:**
- Modify: `clients/vscode/extension-host/src/process_manager.ts`

**Interfaces:**
- Produces: `ProcessManager.start(workspaceRoot: string, extraEnv?: NodeJS.ProcessEnv): void` (was `start(workspaceRoot: string): void`).

- [ ] **Step 1: Modify `start()`'s signature and env merge**

In `clients/vscode/extension-host/src/process_manager.ts`, replace the `start` method:

```typescript
  start(workspaceRoot: string, extraEnv: NodeJS.ProcessEnv = {}): void {
    if (this._process) {
      return;
    }

    const cmd = "breakdown";
    const args = ["start", workspaceRoot];

    try {
      this._process = cp.spawn(cmd, args, {
        cwd: workspaceRoot,
        env: { ...process.env, ...extraEnv },
        stdio: ["ignore", "pipe", "pipe"],
      });
```

(Only the `env:` line and the method signature change — everything else in `start()`, and all of `stop()`/`isRunning()`, stays exactly as-is.)

- [ ] **Step 2: Typecheck**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors (the call site in `commands.ts` still passes only one argument today, which remains valid since `extraEnv` is optional — it gets updated to pass the merged env in Task 6)

- [ ] **Step 3: Commit**

```bash
git add clients/vscode/extension-host/src/process_manager.ts
git commit -m "feat: allow ProcessManager.start() to merge extra env vars into the spawned agent"
```

---

## Task 5: Bundled LiveKit Docker Compose resource

**Files:**
- Create: `clients/vscode/extension-host/resources/docker-compose.livekit.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: a file at `resources/docker-compose.livekit.yml` relative to the extension root, read by `DockerManager.ensureRunning()` (Task 2) via `path.join(extensionPath, "resources", "docker-compose.livekit.yml")`.

- [ ] **Step 1: Create the resource file**

Create `clients/vscode/extension-host/resources/docker-compose.livekit.yml` with the exact same content as the existing `deploy/docker-compose.livekit.yml` (same dev keys, same ports — a packaged `.vsix` install has no `deploy/` directory, so this needs its own copy that ships with the extension):

```yaml
version: "3.8"
services:
  livekit:
    image: livekit/livekit-server:latest
    ports:
      - "7880:7880"
      - "7881:7881"
      - "7882:7882/udp"
    environment:
      LIVEKIT_KEYS: "devkey: devsecret1234567890123456789012345678"
    command: --dev
    restart: unless-stopped
```

- [ ] **Step 2: Verify the packaging config includes it**

Run: `grep -n "resources" clients/vscode/extension-host/.vscodeignore`
Expected: no output (no match) — confirms `resources/**` is not excluded from the packaged `.vsix`. The current `.vscodeignore` only excludes `.vscode/**`, `node_modules/**`, `src/**`, `tsconfig.json`, `esbuild.host.config.js`, `*.map`.

If this grep DOES find a match excluding `resources/`, add a `!resources/**` negation line to `.vscodeignore` immediately after the matching exclusion line, and re-run this verification step before continuing.

- [ ] **Step 3: Commit**

```bash
git add clients/vscode/extension-host/resources/docker-compose.livekit.yml
git commit -m "chore: bundle the LiveKit Docker Compose config as an extension resource"
```

---

## Task 6: `commands.ts` — orchestrate the bootstrap sequence

**Files:**
- Modify: `clients/vscode/extension-host/src/commands.ts`
- Modify: `clients/vscode/extension-host/package.json`

**Interfaces:**
- Consumes: `SecretsManager` (`getStoredEnv()`, `hasAnyLlmKey()`, `store()`, `API_KEY_ENTRIES`) from Task 1; `DockerManager` (`ensureRunning(extensionPath)`) from Task 2; `InstallChecker`/`InstallCheckerDeps` from Task 3; `ProcessManager.start(workspaceRoot, extraEnv?)` from Task 4.
- Produces: `registerCommands(ctx, chatView, processManager, inlineStripManager, secretsManager, dockerManager)` (two new trailing parameters). New command `breakdown.setApiKey`.

- [ ] **Step 1: Replace the full contents of `clients/vscode/extension-host/src/commands.ts`**

```typescript
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
```

Note: `activeLineInfo() { return null; }` early-return in `explainLine` is now written across two lines (`{ ... }` block instead of the original single-line `{ return; }`) purely to satisfy this codebase's existing formatting elsewhere — this is a cosmetic no-op, not a behavior change.

- [ ] **Step 2: Add the `breakdown.setApiKey` command contribution**

In `clients/vscode/extension-host/package.json`, add this entry to the `"commands"` array (after the existing `breakdown.dismissInlineStrip` entry):

```json
      { "command": "breakdown.setApiKey", "title": "Breakdown: Set API Key" }
```

- [ ] **Step 3: Confirm this doesn't yet typecheck cleanly**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: errors in `extension.ts`, since `registerCommands` now requires two more arguments that `extension.ts` doesn't yet pass — this is expected and fixed in Task 7. Confirm the *only* errors are in `extension.ts`.

- [ ] **Step 4: Commit**

```bash
git add clients/vscode/extension-host/src/commands.ts clients/vscode/extension-host/package.json
git commit -m "feat: orchestrate install/Docker/API-key bootstrap in Start Session"
```

---

## Task 7: `extension.ts` — wire the new managers

**Files:**
- Modify: `clients/vscode/extension-host/src/extension.ts`

**Interfaces:**
- Consumes: `SecretsManager` (Task 1, constructed with `context.secrets`), `DockerManager` (Task 2, constructed with no arguments — uses its real defaults), updated `registerCommands` signature (Task 6).

- [ ] **Step 1: Replace the full contents of `clients/vscode/extension-host/src/extension.ts`**

```typescript
// clients/vscode/extension-host/src/extension.ts
import * as vscode from "vscode";
import { ProcessManager } from "./process_manager";
import { ChatViewProvider, VIEW_ID } from "./chat_view_provider";
import { registerCommands } from "./commands";
import { InlineStripManager } from "./inline_strip_manager";
import { DecorationHostAdapter } from "./inline_strip_decorator";
import { SecretsManager } from "./secrets_manager";
import { DockerManager } from "./docker_manager";

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
  const secretsManager = new SecretsManager(context.secrets);
  const dockerManager = new DockerManager();

  const disposables = [
    vscode.window.registerWebviewViewProvider(VIEW_ID, _chatViewProvider),
    ...registerCommands(
      context,
      _chatViewProvider,
      _processManager,
      inlineStripManager,
      secretsManager,
      dockerManager,
    ),
  ];
  context.subscriptions.push(...disposables, _chatViewProvider);
}

export function deactivate(): void {
  _processManager?.stop();
  _chatViewProvider?.dispose();
  _decorationAdapter?.dispose();
}
```

- [ ] **Step 2: Typecheck the whole package**

Run: `cd clients/vscode/extension-host && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Run tests**

Run: `cd clients/vscode/extension-host && npm test`
Expected: all tests pass (`inline_strip_manager.test.ts` + Tasks 1-3's new test files)

- [ ] **Step 4: Build**

Run: `cd clients/vscode/extension-host && npm run build`
Expected: succeeds, `dist/extension.js` produced

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/extension-host/src/extension.ts
git commit -m "feat: wire SecretsManager and DockerManager into the extension"
```

---

## Task 8: `package.json` metadata — publisher and repository

**Files:**
- Modify: `clients/vscode/extension-host/package.json`

**Interfaces:** none (metadata only).

- [ ] **Step 1: Update `publisher` and `repository.url`**

In `clients/vscode/extension-host/package.json`, change:

```json
  "publisher": "breakdown",
```
to:
```json
  "publisher": "belaleatsbanana",
```

and change:
```json
  "repository": {
    "type": "git",
    "url": "https://github.com/breakdown/breakdown"
  },
```
to:
```json
  "repository": {
    "type": "git",
    "url": "https://github.com/Belaleatsbanana/Breakdown"
  },
```

- [ ] **Step 2: Confirm the JSON is still valid**

Run: `node -e "JSON.parse(require('fs').readFileSync('clients/vscode/extension-host/package.json', 'utf-8')); console.log('valid')"`
Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add clients/vscode/extension-host/package.json
git commit -m "chore: set the real Marketplace publisher and repository URL"
```

---

## Task 9: Documentation — README and getting-started rewrite

**Files:**
- Modify: `README.md`
- Modify: `docs/getting-started.md`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Replace `README.md`'s Quick Start and Keyboard Shortcuts sections**

Replace the full contents of `README.md` from the `## Quick Start` heading through the end of the `## Keyboard Shortcuts` table (leave the `# Breakdown` title, description, and `## Demo` section above it untouched, and everything from `## Providers` onward untouched) with:

```markdown
## Quick Start

**1. Install the VS Code extension**

Search for "Breakdown" in the VS Code Extensions panel, or install from the
[Marketplace](https://marketplace.visualstudio.com/items?itemName=belaleatsbanana.breakdown-vscode).

**2. Run a session**

Open the Command Palette and run `Breakdown: Start Session` (or press
`Cmd+K Cmd+E` on macOS / `Ctrl+K Ctrl+E` on Windows/Linux).

The first time you do this, Breakdown will:
- Prompt to install its Python core if it isn't found (`breakdown-ai`, via `uv` or `pip`)
- Start a local LiveKit server automatically (requires Docker to be running)
- Prompt you for one API key — OpenAI is enough to cover LLM, TTS, and embeddings

Every subsequent `Start Session` skips straight to connecting, since the
Python core, LiveKit, and your API key all persist.

**3. Explain some code**

Open a file, place your cursor on a line, and run `Breakdown: Explain Line`
(`Cmd+Alt+I` / `Ctrl+Alt+I`). The explanation appears in the Breakdown sidebar
and is narrated aloud.

## Keyboard Shortcuts

| Action | macOS | Windows / Linux |
|---|---|---|
| Start session | Cmd+K Cmd+E | Ctrl+K Ctrl+E |
| Explain line | Cmd+Alt+I | Ctrl+Alt+I |
| Next line | Cmd+K Cmd+N | Ctrl+K Ctrl+N |
| Previous line | Cmd+K Cmd+P | Ctrl+K Ctrl+P |
| Ask a question | Cmd+K Cmd+Space | Ctrl+K Ctrl+Space |
| Stop session | Cmd+K Cmd+Q | Ctrl+K Ctrl+Q |

All shortcuts are configurable in VS Code's keyboard settings. API keys are
managed via `Breakdown: Set API Key` in the Command Palette, backed by VS
Code's encrypted secret storage — no `.env` file needed.
```

- [ ] **Step 2: Replace the full contents of `docs/getting-started.md`**

```markdown
# Getting Started

## Prerequisites

- VS Code 1.85 or later
- Docker (only if you don't have a LiveKit Cloud account) — Breakdown starts
  it for you automatically, it just needs to already be running
- An OpenAI API key (other providers are optional)

## Install the VS Code Extension

Search for "Breakdown" in the Extensions panel and click Install.

## Start a Session

Open any code file in VS Code. Open the Command Palette and run
`Breakdown: Start Session` (or press `Cmd+K Cmd+E` / `Ctrl+K Ctrl+E`).

The extension will, in order:
1. Check whether the Python core (`breakdown-ai`) is installed. If not, it
   offers to install it for you via `uv` or `pip` in an integrated terminal.
2. Check whether Docker is running and start a local LiveKit server via
   Docker Compose if needed.
3. Check whether you've set an API key. If not, it prompts you — pick OpenAI
   for the simplest setup (one key covers LLM, TTS, and embeddings).
4. Start the Breakdown agent process and connect the sidebar.

You only go through steps 1-3 once; later sessions skip straight to step 4.

## Managing API Keys

Run `Breakdown: Set API Key` from the Command Palette at any time to add or
change a key. Keys are stored via VS Code's `SecretStorage` API (OS
keychain-backed), never written to a plaintext file.

## First Index

The first time you start a session, Breakdown indexes your codebase. This
may take a few seconds to a few minutes depending on the size of your project.
Progress is shown in the VS Code status bar.

Subsequent starts are fast because only changed files are re-indexed.

## Troubleshooting

**"Docker isn't running"**
Install and start Docker Desktop (or Docker Engine), then run
`Breakdown: Start Session` again. Alternatively, run `Breakdown: Set API Key`
and set "LiveKit Cloud URL" (plus its matching API Key and API Secret) to
point at a LiveKit Cloud project instead of self-hosting — once a LiveKit
Cloud URL is set, `Start Session` skips the Docker step entirely.

**"Breakdown: still can't find the `breakdown` command"**
Check the "Breakdown Install" terminal for errors from the `pip`/`uv` install
command. A common cause is the install completing into a directory that isn't
on your shell's `PATH` — restart VS Code after adding it.

**No audio**
Check that your system audio output is working and not muted.

**Remote development (SSH, Codespaces)**
Audio requires a local VS Code window. Remote development is not currently supported.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/getting-started.md
git commit -m "docs: rewrite Quick Start and getting-started for the zero-config bootstrap"
```

---

## Task 10: Manual verification

**Files:** none (verification only)

- [ ] **Step 1: Full package verification**

Run:
```bash
cd clients/vscode/webview && npm run typecheck && npm run build
cd ../extension-host && npm run typecheck && npm test && npm run build
```
Expected: all green, both `dist/extension.js` and `dist/webview.js` exist.

- [ ] **Step 2: Simulate a first-time user — clear all local state**

```bash
# Uninstall the Python core (if installed via uv; adjust if installed via pip)
uv tool uninstall breakdown-ai 2>/dev/null || pip uninstall -y breakdown-ai 2>/dev/null || true
# Stop and remove the LiveKit container so Docker auto-start is genuinely exercised
docker compose -f deploy/docker-compose.livekit.yml down 2>/dev/null || true
```

Note: VS Code's `SecretStorage` for this extension can't be cleared from the shell — for a true first-run test, use a fresh VS Code profile (`code --profile breakdown-test`) or manually run `Breakdown: Set API Key` won't have prior state in a profile that's never run this extension before.

- [ ] **Step 3: Launch the Extension Development Host and run through the flow**

Open `clients/vscode/extension-host` in VS Code, press F5. In the Extension Development Host:
1. Run `Breakdown: Start Session`.
2. Confirm the "Breakdown core not found" prompt appears; click "Install Now"; confirm a terminal opens and runs the install command; wait for it to finish; confirm a "Retry" follow-up appears.
3. Re-run `Breakdown: Start Session`. Confirm no install prompt this time (CLI now found); confirm Docker Compose starts LiveKit (check `docker ps` shows the `livekit` container) and the flow proceeds without you touching Docker directly.
4. Confirm the API key `QuickPick` appears; select OpenAI; enter a real key; confirm the flow continues and the sidebar shows "connected".
5. Run `Breakdown: Explain Line` on a real line of code; confirm a real explanation appears in the sidebar (not stuck, not an error).
6. Run `Breakdown: Stop Session`, then `Breakdown: Start Session` again; confirm it skips straight to connecting — no install prompt, no API key prompt, Docker already running.

- [ ] **Step 4: Confirm no stale references remain**

Run: `grep -rn "push-to-talk\|audio panel\|copy .env.example" README.md docs/getting-started.md`
Expected: no matches
