# Zero-Config Startup — Design

**Goal:** Make `Breakdown: Start Session` a self-healing bootstrap so a first-time user only has to (1) install the extension, (2) supply one API key, and (3) run a command from the Command Palette — no manual `docker compose up`, no manual `pip install`, no `.env` file editing.

## Background

Today, using Breakdown requires three manual, undocumented-in-the-UI steps before `Start Session` will succeed: install the Python core (`pip install breakdown-ai`), start LiveKit yourself (`docker compose -f deploy/docker-compose.livekit.yml up`), and hand-edit a `.env` file with API keys. `ProcessManager.start()` only reacts to a missing `breakdown` CLI after attempting to spawn it (`process_manager.ts`'s `ENOENT` handler), and nothing in the extension touches Docker or API keys at all. `README.md` and `docs/getting-started.md` already promise "only `OPENAI_API_KEY` is required," but nothing in the code delivers on that promise, and both docs still describe a `push-to-talk` keybinding and an "audio panel" that were removed from the codebase weeks ago (replaced by the typed `ask` command and the sidebar chat view respectively).

This design closes that gap: `Start Session` becomes a guided bootstrap that checks and repairs each prerequisite in order, prompting the user only when it genuinely needs their input (an API key, permission to install something), and does the rest automatically.

## What Changes

### 1. API key storage — `Breakdown: Set API Key` command

**New file:** `clients/vscode/extension-host/src/secrets_manager.ts`

- `SecretsManager` wraps `vscode.ExtensionContext.secrets` (VS Code's `SecretStorage` API — OS-keychain-backed, never written to disk in plaintext).
- Exposes `promptForKey(context): Promise<void>` — shows a `QuickPick` with these entries, each annotated with its env var name and role:
  - **OpenAI** (`OPENAI_API_KEY`) — marked "Recommended: covers LLM, TTS, and embeddings"
  - Anthropic (`ANTHROPIC_API_KEY`), Mistral (`MISTRAL_API_KEY`), Groq (`GROQ_API_KEY`), OpenRouter (`OPENROUTER_API_KEY`), Together (`TOGETHER_API_KEY`), Perplexity (`PERPLEXITY_API_KEY`) — LLM alternates
  - Deepgram TTS (`DEEPGRAM_API_KEY`), ElevenLabs (`ELEVENLABS_API_KEY`) — TTS alternates
  - Jina (`JINA_API_KEY`), Gemini (`GEMINI_API_KEY`) — embedding alternates
- Selecting an entry opens `vscode.window.showInputBox({ password: true, prompt: "Enter your <Provider> API key" })`; on submit, stores it via `context.secrets.store("breakdown.<ENV_VAR_NAME>", value)`.
- `getStoredEnv(context): Promise<Record<string, string>>` — reads every key in the list above via `context.secrets.get(...)`, returning only the ones actually set, keyed by their real env var name (e.g. `{ OPENAI_API_KEY: "sk-..." }`).
- `hasAnyLlmKey(context): Promise<boolean>` — true if at least one of the LLM-role keys (OpenAI/Anthropic/Mistral/Groq/OpenRouter/Together/Perplexity) is stored. Used as the `Start Session` gate.
- New command `breakdown.setApiKey` registered in `commands.ts`, calling `secretsManager.promptForKey(context)` directly — usable standalone, not just as part of the Start Session flow.
- `package.json` gets a new command contribution: `{ "command": "breakdown.setApiKey", "title": "Breakdown: Set API Key" }`.

### 2. LiveKit auto-start — Docker Compose

**New file:** `clients/vscode/extension-host/src/docker_manager.ts`

- `DockerManager.ensureRunning(extensionPath: string): Promise<void>`:
  1. Runs `docker info` (via `child_process.exec`, 3s timeout). Non-zero exit or timeout throws `Error("Docker isn't running. Install Docker Desktop, start it, and retry — or set LIVEKIT_URL via Breakdown: Set API Key to point at a LiveKit Cloud project instead.")`.
  2. Runs `docker compose -f <composePath> up -d`, where `composePath = path.join(extensionPath, "resources", "docker-compose.livekit.yml")` — the compose file ships as a bundled extension asset, not read from the user's workspace (a Marketplace install has no `deploy/` directory).
  3. Polls `http://127.0.0.1:7880` with a plain HTTP GET every 500ms, up to 15s total (mirrors `token_client.ts`'s `getTokenWithRetry` retry shape). Throws `Error("LiveKit did not become ready within 15s.")` on exhaustion.
- **New file:** `clients/vscode/extension-host/resources/docker-compose.livekit.yml` — a copy of `deploy/docker-compose.livekit.yml` (same dev keys, same ports), placed where it ships with the packaged `.vsix`.
- `package.json`'s `.vscodeignore` must **not** exclude `resources/` (verify during implementation — `.vscodeignore` currently excludes `src/`, `node_modules/@types`, etc.; confirm `resources/` isn't caught by a broad pattern).
- LiveKit is left running once started; `Stop Session` continues to only stop the Python agent process (`ProcessManager.stop()`), unchanged. No new "stop LiveKit" command in this design — tearing down a local dev container on every session end just adds startup latency next time for no real benefit.

### 3. Python core auto-install

**Modify:** `clients/vscode/extension-host/src/process_manager.ts`

- New method `ensureInstalled(): Promise<boolean>`:
  1. Runs `which breakdown` (POSIX) or `where breakdown` (win32) via `child_process.exec`. Resolves `true` if found.
  2. If not found, calls `vscode.window.showErrorMessage("Breakdown core not found.", "Install Now")`. If the user doesn't click it, resolves `false`.
  3. If clicked: checks for `uv` on PATH the same way; opens `vscode.window.createTerminal("Breakdown Install")`, sends `uv tool install breakdown-ai` if `uv` is present else `pip install --user breakdown-ai`, and shows the terminal.
  4. Uses the integrated terminal's `shellIntegration.executeCommand` exit-status event (VS Code API, available on terminals with shell integration) to detect completion; on success, shows `showInformationMessage("Breakdown core installed. Click Retry to start your session.", "Retry")`. Resolves `true` if the user clicks Retry and a fresh `which`/`where` check now finds the CLI, else `false`.
- `start(workspaceRoot)` keeps its existing spawn logic unchanged — `ensureInstalled()` is a new pre-flight check called from `commands.ts`, not folded into `start()` itself, so `ProcessManager`'s existing spawn/stop responsibilities stay focused.

### 4. `startSession` orchestration

**Modify:** `clients/vscode/extension-host/src/commands.ts`

New sequence inside the existing `breakdown.startSession` handler, before the current `alreadyRunning` check:

```
1. If !(await processManager.ensureInstalled()): abort (message already shown).
2. try { await dockerManager.ensureRunning(ctx.extensionPath) } catch (err) { showErrorMessage(err.message); abort }
3. If !(await secretsManager.hasAnyLlmKey(ctx)): await secretsManager.promptForKey(ctx); if still !hasAnyLlmKey, abort with "At least one LLM API key is required."
4. Merge process.env, { LIVEKIT_URL: "ws://localhost:7880", LIVEKIT_API_KEY: "devkey", LIVEKIT_API_SECRET: "devsecret1234567890123456789012345678" }, and await secretsManager.getStoredEnv(ctx) into the env passed to processManager.start() — requires threading an env override through ProcessManager.start(workspaceRoot, extraEnv) (new optional parameter).
5. Existing "already running" check, spawn, getTokenWithRetry, chatView.connect(...) — unchanged.
```

The LiveKit dev credentials (`devkey`/`devsecret...`) are fixed constants matching `resources/docker-compose.livekit.yml`, not user-entered — self-hosted Docker LiveKit doesn't need a per-user secret.

### 5. Documentation & packaging metadata

- **`README.md`** and **`docs/getting-started.md`**: rewritten Quick Start — install extension → run `Breakdown: Start Session` (which prompts for an API key on first run if none is set, per Section 1) → done. Remove: manual `docker compose` instructions, manual `.env` copy step, the `push-to-talk` keybinding row, and "audio panel" language (replaced by "sidebar" throughout, matching the actual current UI).
- **`clients/vscode/extension-host/package.json`**: `publisher` corrected to `belaleatsbanana` (the short publisher name registered/to-be-registered at marketplace.visualstudio.com/manage — distinct from the Marketplace account's internal GUID, which is not what this field takes) and `repository.url` corrected to `https://github.com/Belaleatsbanana/Breakdown`.
- Verifying or fixing the actual `.github/workflows/release.yml` publish pipeline (Marketplace PAT, PyPI token as repo secrets) is **out of scope** for this design — that requires the user's own publisher/PyPI accounts and is a one-time manual credentials setup, not a code change.

## Data Flow (first-time user, zero-config path)

1. User installs the extension from the Marketplace. No prerequisites yet.
2. User runs `Breakdown: Start Session` from the Command Palette.
3. `ensureInstalled()` finds no `breakdown` CLI → prompt → user clicks "Install Now" → terminal runs `uv tool install breakdown-ai` (or `pip install --user breakdown-ai`) → completion detected → user clicks "Retry" → CLI now found.
4. `dockerManager.ensureRunning()` finds Docker running, starts the bundled compose file, polls until LiveKit responds on `:7880`.
5. `secretsManager.hasAnyLlmKey()` is false → `promptForKey()` QuickPick appears → user picks OpenAI → enters their key → stored in `SecretStorage`.
6. Env merged (`LIVEKIT_URL` + dev keys + `OPENAI_API_KEY`), agent spawned, token retrieved, sidebar connects — exactly as today's flow already does from this point on.
7. Every subsequent `Start Session` in the same or a different workspace skips steps 3 and 5 (CLI and key persist), and step 4 is fast (Docker container already running).

## Testing

- `secrets_manager.ts`: unit tests for `hasAnyLlmKey`/`getStoredEnv` against a fake `vscode.SecretStorage` (a simple in-memory `Map`-backed fake implementing `get`/`store`/`delete`, following the existing fake-adapter pattern used for `StripDecorator` in `inline_strip_manager.test.ts`) — no real VS Code API needed for these pure logic paths.
- `docker_manager.ts`: unit test the retry/timeout logic for the `:7880` poll against a fake HTTP check function (inject the check as a constructor parameter, mirroring how `getTokenWithRetry` is already structured for testability) rather than hitting a real Docker daemon in CI.
- `process_manager.ts`'s `ensureInstalled()`: unit test the `which`/`where` branch selection and the "user declines" path; the actual terminal-spawn-and-detect-completion path is inherently interactive and is verified manually (documented in the plan's manual verification task), matching how `ProcessManager.start()`'s real spawn behavior is already untested at the unit level today.
- Manual verification: a clean machine (or `pip uninstall breakdown-ai` + `docker compose down` + VS Code `SecretStorage` cleared) running through the full first-time flow end to end.

## Files Touched

- **Create:** `clients/vscode/extension-host/src/secrets_manager.ts`, `clients/vscode/extension-host/src/docker_manager.ts`, `clients/vscode/extension-host/resources/docker-compose.livekit.yml`, plus test files for the two new managers.
- **Modify:** `clients/vscode/extension-host/src/process_manager.ts` (add `ensureInstalled()`, thread `extraEnv` through `start()`), `clients/vscode/extension-host/src/commands.ts` (new orchestration sequence, new `breakdown.setApiKey` command), `clients/vscode/extension-host/src/extension.ts` (wire up `SecretsManager`/`DockerManager` instances), `clients/vscode/extension-host/package.json` (new command contribution, corrected `publisher`/`repository.url`, verify `resources/` isn't excluded from packaging), `README.md`, `docs/getting-started.md`.
- **Unchanged:** the Python core (`core/`) — this design is entirely about the VS Code extension's bootstrap UX; `config.py`'s existing env-var-driven `Settings` already accepts whatever's merged into the spawned process's environment, no core changes needed.
