from __future__ import annotations

from pathlib import Path
import pytest
from breakdown.session import Session


def test_session_initial_state() -> None:
    s = Session(workspace_root=Path("/tmp/proj"))
    assert s.current_file == ""
    assert s.current_line == 0
    assert s.history == []


def test_add_turn_appends(tmp_path: Path) -> None:
    s = Session(workspace_root=tmp_path)
    s.add_turn("user", "what is this?")
    assert len(s.history) == 1
    assert s.history[0] == {"role": "user", "content": "what is this?"}


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    s = Session(workspace_root=tmp_path)
    s.current_file = "src/foo.py"
    s.current_line = 42
    s.add_turn("user", "explain this")
    s.add_turn("assistant", "this is a function")
    path = tmp_path / "session.json"
    s.save(path)
    loaded = Session.load(path)
    assert loaded is not None
    assert loaded.current_file == "src/foo.py"
    assert loaded.current_line == 42
    assert len(loaded.history) == 2


def test_load_returns_none_for_missing_file(tmp_path: Path) -> None:
    result = Session.load(tmp_path / "nonexistent.json")
    assert result is None


def test_load_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text("not json {{{")
    result = Session.load(path)
    assert result is None


def test_token_count_is_positive_after_turns(tmp_path: Path) -> None:
    s = Session(workspace_root=tmp_path)
    s.add_turn("user", "hello world")
    assert s.token_count() > 0
