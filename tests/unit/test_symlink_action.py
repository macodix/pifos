"""Tests für pifos.actions.symlink_action."""

import os
from pathlib import Path

import pytest
from pifos.actions.symlink_action import SymlinkAction, _create_symlink_atomic
from pifos.errors import ActionError


def test_symlink_action_creates_new_link(tmp_path: Path) -> None:
    """Ein neuer Symlink wird angelegt und zeigt auf target."""
    target = tmp_path / "ziel.txt"
    target.write_text("inhalt", encoding="utf-8")
    link = tmp_path / "link.txt"

    action = SymlinkAction(str(link), str(target))
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert link.is_symlink()
    assert os.readlink(str(link)) == str(target)
    assert link.read_text(encoding="utf-8") == "inhalt"


def test_symlink_action_allows_dead_link(tmp_path: Path) -> None:
    """target muss nicht existieren; ein toter Symlink ist zulässig."""
    target = tmp_path / "existiert_nie.txt"
    link = tmp_path / "link.txt"

    action = SymlinkAction(str(link), str(target))
    result = action.run()

    assert result == "finished"
    assert link.is_symlink()
    assert not link.exists()
    assert os.readlink(str(link)) == str(target)


def test_symlink_action_existing_symlink_without_overwrite_raises(
    tmp_path: Path,
) -> None:
    """Bestehender Symlink ohne overwrite erzeugt ActionError."""
    old_target = tmp_path / "alt.txt"
    old_target.write_text("alt", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(old_target)

    action = SymlinkAction(str(link), str(tmp_path / "neu.txt"), overwrite=False)
    with pytest.raises(ActionError, match="Überschreiben nicht freigegeben"):
        action.run()

    assert action.status == "failed"
    assert os.readlink(str(link)) == str(old_target)


def test_symlink_action_existing_symlink_with_overwrite_replaces_atomically(
    tmp_path: Path,
) -> None:
    """overwrite=True ersetzt einen bestehenden Symlink atomar."""
    old_target = tmp_path / "alt.txt"
    old_target.write_text("alt", encoding="utf-8")
    new_target = tmp_path / "neu.txt"
    new_target.write_text("neu", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(old_target)

    action = SymlinkAction(str(link), str(new_target), overwrite=True)
    result = action.run()

    assert result == "finished"
    assert link.is_symlink()
    assert os.readlink(str(link)) == str(new_target)
    assert link.read_text(encoding="utf-8") == "neu"
    # keine Rückstände temporärer Symlinks im Zielverzeichnis
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "alt.txt",
        "link.txt",
        "neu.txt",
    ]


def test_symlink_action_existing_regular_file_without_overwrite_raises(
    tmp_path: Path,
) -> None:
    """Bestehende reguläre Datei am link_path ohne overwrite erzeugt ActionError."""
    link = tmp_path / "link.txt"
    link.write_text("echte datei", encoding="utf-8")

    action = SymlinkAction(str(link), str(tmp_path / "ziel.txt"), overwrite=False)
    with pytest.raises(ActionError, match="Überschreiben nicht freigegeben"):
        action.run()

    assert action.status == "failed"
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "echte datei"


def test_symlink_action_existing_regular_file_with_overwrite_still_raises(
    tmp_path: Path,
) -> None:
    """Eine reguläre Datei wird auch mit overwrite=True nie ersetzt."""
    link = tmp_path / "link.txt"
    link.write_text("echte datei", encoding="utf-8")

    action = SymlinkAction(str(link), str(tmp_path / "ziel.txt"), overwrite=True)
    with pytest.raises(ActionError, match="wird nie ersetzt"):
        action.run()

    assert action.status == "failed"
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "echte datei"


def test_symlink_action_existing_directory_with_overwrite_raises(
    tmp_path: Path,
) -> None:
    """Ein Verzeichnis am link_path wird auch mit overwrite=True nie ersetzt."""
    link = tmp_path / "link_dir"
    link.mkdir()

    action = SymlinkAction(str(link), str(tmp_path / "ziel.txt"), overwrite=True)
    with pytest.raises(ActionError, match="wird nie ersetzt"):
        action.run()

    assert action.status == "failed"
    assert link.is_dir()
    assert not link.is_symlink()


def test_create_symlink_atomic_recheck_aborts_if_no_longer_symlink(
    tmp_path: Path,
) -> None:
    """Der Recheck bricht ab, wenn link_name zwischenzeitlich kein Symlink mehr ist."""
    (tmp_path / "link.txt").write_text("wurde inzwischen echte datei", encoding="utf-8")

    with pytest.raises(ActionError, match="kein Symlink mehr"):
        _create_symlink_atomic(tmp_path, "link.txt", str(tmp_path / "ziel.txt"))

    assert (tmp_path / "link.txt").read_text(encoding="utf-8") == (
        "wurde inzwischen echte datei"
    )
    # keine liegen gebliebenen Temp-Symlinks
    assert [p.name for p in tmp_path.iterdir()] == ["link.txt"]


def test_create_symlink_atomic_recheck_aborts_if_target_removed(
    tmp_path: Path,
) -> None:
    """Der Recheck bricht ab, wenn link_name zwischenzeitlich ganz fehlt."""
    with pytest.raises(ActionError, match="nicht mehr vorhanden"):
        _create_symlink_atomic(tmp_path, "link.txt", str(tmp_path / "ziel.txt"))

    # keine liegen gebliebenen Temp-Symlinks
    assert list(tmp_path.iterdir()) == []


def test_symlink_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert SymlinkAction.PARAMS == ["link_path", "target", "overwrite"]
