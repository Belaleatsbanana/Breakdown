# CLAUDE.md

Claude Code-specific guidance for this repository.

## Before Starting Any Task

1. Read `AGENTS.md` for architecture rules and commit format.
2. Read `STYLE.md` for code style rules.
3. Run `cd core && uv run pytest` to confirm the baseline is green.

## File Editing Rules

- When editing `agent.py`, check the line count after. If over 150 lines,
  extract the new logic into a new file before committing.
- When editing `session.py`, grep for any import of `agent` after editing.
  If found, remove it.
- When editing any file in `providers/`, verify the corresponding test in
  `tests/unit/providers/` still passes.

## Running the Project

Start the full stack locally:
```bash
# Terminal 1: start LiveKit (Docker required)
docker compose -f deploy/docker-compose.livekit.yml up

# Terminal 2: index the codebase
cd core && uv run breakdown index ..

# Terminal 3: start the agent
cd core && uv run breakdown start ..
```

Then press `Cmd+K Cmd+E` in VS Code (with the extension installed).

## Common Pitfalls

- The extension host (Node.js) cannot use `livekit-client`. That is the
  browser SDK and lives only in the webview. The host uses `livekit-server-sdk`.
- `getTokenWithRetry` retries for 5 seconds. If the Python core has not started
  yet, this is expected. Do not reduce the retry count.
- `manifest.save()` must be called after every batch index run. If omitted,
  the next run re-indexes everything.
