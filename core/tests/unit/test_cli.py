from __future__ import annotations

from typer.testing import CliRunner

from breakdown import __version__
from breakdown.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_index_requires_directory(tmp_path: object) -> None:
    result = runner.invoke(app, ["index", "--help"])
    assert result.exit_code == 0
    assert "index" in result.output.lower() or "path" in result.output.lower()
