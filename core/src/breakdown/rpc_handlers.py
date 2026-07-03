from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from livekit.agents import AgentSession  # type: ignore[import-untyped]

from breakdown.config import Settings
from breakdown.indexer.store import VectorStore
from breakdown.session import Session


@dataclass
class HandlerDeps:
    session: Session
    session_path: Path
    store: VectorStore
    workspace_root: Path
    settings: Settings
    agent_session: AgentSession
    llm: object


async def handle_next(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line += 1
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_prev(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line = max(1, deps.session.current_line - 1)
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_stop(payload: str, deps: HandlerDeps) -> str:
    await deps.agent_session.aclose()  # type: ignore[attr-defined]
    return json.dumps({"ok": True})
