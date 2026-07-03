from __future__ import annotations

import json
from pathlib import Path

from breakdown.config import Settings
from breakdown.rpc_handlers import (
    HandlerDeps,
    handle_next,
    handle_prev,
    handle_stop,
)
from breakdown.session import Session


class FakeAgentSession:
    def __init__(self) -> None:
        self.said: list[str] = []
        self.closed = False

    def say(self, text: str, allow_interruptions: bool = True) -> None:
        self.said.append(text)

    async def aclose(self) -> None:
        self.closed = True


def _make_deps(tmp_path: Path) -> HandlerDeps:
    session = Session(workspace_root=tmp_path)
    return HandlerDeps(
        session=session,
        session_path=tmp_path / "session.json",
        store=object(),  # type: ignore[arg-type]
        workspace_root=tmp_path,
        settings=Settings(),
        agent_session=FakeAgentSession(),  # type: ignore[arg-type]
        llm=object(),
    )


async def test_handle_next_increments_line_and_persists(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.session.current_file = "src/foo.py"
    deps.session.current_line = 5

    result = await handle_next("{}", deps)

    assert json.loads(result) == {"file": "src/foo.py", "line": 6}
    assert deps.session_path.exists()


async def test_handle_prev_decrements_line(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.session.current_file = "src/foo.py"
    deps.session.current_line = 5

    result = await handle_prev("{}", deps)

    assert json.loads(result) == {"file": "src/foo.py", "line": 4}


async def test_handle_prev_does_not_go_below_line_one(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.session.current_file = "src/foo.py"
    deps.session.current_line = 1

    result = await handle_prev("{}", deps)

    assert json.loads(result) == {"file": "src/foo.py", "line": 1}


async def test_handle_stop_closes_the_agent_session(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)

    result = await handle_stop("{}", deps)

    assert json.loads(result) == {"ok": True}
    assert deps.agent_session.closed is True  # type: ignore[attr-defined]
