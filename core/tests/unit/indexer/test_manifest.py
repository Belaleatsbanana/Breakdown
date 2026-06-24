from __future__ import annotations

from pathlib import Path

from breakdown.indexer.manifest import Manifest


def test_new_file_is_stale(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    assert manifest.is_stale(f)


def test_unchanged_file_is_not_stale(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    manifest.update(f, ["chunk-1"])
    manifest.save()
    manifest2 = Manifest(tmp_path / "manifest.json")
    assert not manifest2.is_stale(f)


def test_changed_file_is_stale(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    manifest.update(f, ["chunk-1"])
    manifest.save()
    f.write_text("hello world")  # changed
    manifest2 = Manifest(tmp_path / "manifest.json")
    assert manifest2.is_stale(f)


def test_remove_marks_file_unknown(tmp_path: Path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "foo.py"
    f.write_text("hello")
    manifest.update(f, ["chunk-1"])
    manifest.remove(f)
    assert manifest.is_stale(f)
