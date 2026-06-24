#!/usr/bin/env bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

ok() { echo -e "${GREEN}[ok]${NC} $1"; }
fail() { echo -e "${RED}[missing]${NC} $1: install from $2"; FAILED=1; }

FAILED=0

command -v python3 >/dev/null 2>&1 && ok "python3" || fail "python3" "https://python.org"
command -v uv >/dev/null 2>&1 && ok "uv" || fail "uv" "https://docs.astral.sh/uv/getting-started/installation/"
command -v node >/dev/null 2>&1 && ok "node" || fail "node" "https://nodejs.org"
command -v pnpm >/dev/null 2>&1 && ok "pnpm" || fail "pnpm" "https://pnpm.io/installation"
command -v docker >/dev/null 2>&1 && ok "docker" || fail "docker" "https://docs.docker.com/get-docker/"

if [ "$FAILED" -eq 1 ]; then
  echo ""
  echo "Fix the missing dependencies above, then re-run: make install"
  exit 1
fi

echo ""
echo "All dependencies found."
