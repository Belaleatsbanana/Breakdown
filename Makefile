# Makefile
.PHONY: install dev test lint typecheck build clean

install:
	@bash scripts/check_deps.sh
	cd core && uv sync --all-extras --dev
	cd clients/vscode && pnpm install

dev:
	@echo "Starting LiveKit..."
	docker compose -f deploy/docker-compose.livekit.yml up -d
	@echo "Indexing workspace..."
	cd core && uv run breakdown index ..
	@echo "Starting agent..."
	cd core && uv run breakdown start ..

test:
	cd core && uv run pytest

lint:
	cd core && uv run ruff check src/ tests/
	cd clients/vscode && pnpm lint

typecheck:
	cd core && uv run basedpyright src/
	cd clients/vscode && pnpm typecheck

build:
	cd clients/vscode/webview && pnpm build
	cd clients/vscode/extension-host && pnpm build
	cd core && uv build

clean:
	rm -rf core/dist core/.venv
	rm -rf clients/vscode/extension-host/dist clients/vscode/webview/dist
	rm -rf clients/vscode/node_modules
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
