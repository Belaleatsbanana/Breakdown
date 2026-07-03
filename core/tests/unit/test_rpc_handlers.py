from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from livekit.rtc.rpc import RpcError  # type: ignore[import-untyped]

from breakdown.config import Settings
from breakdown.rpc_handlers import (
    HandlerDeps,
    handle_ask,
    handle_explain,
    handle_next,
    handle_prev,
    handle_stop,
)
from breakdown.session import Session


class FakeSpeechHandle:
    def __init__(self) -> None:
        self.id = "fake-speech-handle"
        self.scheduled = True
        self.interrupted = False

    def add_done_callback(self, callback: object) -> None:
        callback(self)  # type: ignore[operator]


class FakeAgentSession:
    def __init__(self) -> None:
        self.said: list[str] = []
        self.closed = False

    def say(self, text: str, allow_interruptions: bool = True) -> FakeSpeechHandle:
        self.said.append(text)
        return FakeSpeechHandle()

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


class FakeLLMStream:
    def __init__(self, text: str) -> None:
        self._text = text

    async def collect(self) -> SimpleNamespace:
        return SimpleNamespace(text=self._text)


class FailingLLMStream:
    async def collect(self) -> SimpleNamespace:
        raise RuntimeError("boom")


class FakeLLM:
    def __init__(self, text: str = "", fail: bool = False) -> None:
        self._text = text
        self._fail = fail
        self.chat_calls: list[object] = []

    def chat(self, *, chat_ctx: object) -> object:
        self.chat_calls.append(chat_ctx)
        if self._fail:
            return FailingLLMStream()
        return FakeLLMStream(self._text)


@patch("breakdown.rpc_handlers.index_context")
async def test_handle_explain_returns_generated_text(
    mock_index_context: MagicMock, tmp_path: Path
) -> None:
    mock_index_context.return_value = ([], "42: def foo(): pass")
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM(text="This defines a no-op function.")

    result = await handle_explain(json.dumps({"file": "src/foo.py", "line": 42}), deps)

    data = json.loads(result)
    assert data == {"text": "This defines a no-op function.", "file": "src/foo.py", "line": 42}
    assert deps.session.current_file == "src/foo.py"
    assert deps.session.current_line == 42
    assert deps.agent_session.said == ["This defines a no-op function."]  # type: ignore[attr-defined]
    assert any(turn["role"] == "assistant" for turn in deps.session.history)


@patch("breakdown.rpc_handlers.index_context")
async def test_handle_explain_raises_rpc_error_on_llm_failure(
    mock_index_context: MagicMock, tmp_path: Path
) -> None:
    mock_index_context.return_value = ([], "")
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM(fail=True)

    with pytest.raises(RpcError):
        await handle_explain(json.dumps({"file": "src/foo.py", "line": 1}), deps)


async def test_handle_ask_returns_answer_text(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM(text="It retries because the network can flake.")

    result = await handle_ask(json.dumps({"text": "why does this retry?"}), deps)

    data = json.loads(result)
    assert data == {"text": "It retries because the network can flake."}
    assert deps.agent_session.said == ["It retries because the network can flake."]  # type: ignore[attr-defined]


async def test_handle_ask_rejects_empty_text(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)
    deps.llm = FakeLLM()

    with pytest.raises(RpcError):
        await handle_ask(json.dumps({"text": ""}), deps)


@patch("breakdown.rpc_handlers.index_context")
async def test_handle_explain_raises_rpc_error_on_malformed_payload(
    mock_index_context: MagicMock, tmp_path: Path
) -> None:
    mock_index_context.return_value = ([], "")
    deps = _make_deps(tmp_path)

    with pytest.raises(RpcError):
        await handle_explain(json.dumps({"file": "src/foo.py", "line": "not-a-number"}), deps)


async def test_handle_ask_raises_rpc_error_on_malformed_json(tmp_path: Path) -> None:
    deps = _make_deps(tmp_path)

    with pytest.raises(RpcError):
        await handle_ask("not valid json", deps)
