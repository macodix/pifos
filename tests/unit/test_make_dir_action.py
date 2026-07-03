"""Tests für pifos.actions.make_dir_action."""

import os
import stat
from pathlib import Path

import pytest
from pifos.actions.make_dir_action import MakeDirAction
from pifos.errors import ActionError


def test_make_dir_action_creates_directory_default_mode(tmp_path: Path) -> None:
    """Neues Verzeichnis erhält die Voreinstellung 0o700."""
    path = tmp_path / "neu"

    action = MakeDirAction(str(path))
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert path.is_dir()
    assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_make_dir_action_explicit_mode(tmp_path: Path) -> None:
    """Ein ausdrücklich übergebenes mode wird gesetzt."""
    path = tmp_path / "neu"

    action = MakeDirAction(str(path), mode=0o750)
    action.run()

    assert stat.S_IMODE(path.stat().st_mode) == 0o750


def test_make_dir_action_parents_creates_missing_ancestors(tmp_path: Path) -> None:
    """parents=True legt fehlende Elternverzeichnisse mit mode an."""
    path = tmp_path / "a" / "b" / "c"

    action = MakeDirAction(str(path), mode=0o750, parents=True)
    result = action.run()

    assert result == "finished"
    assert path.is_dir()
    assert stat.S_IMODE(path.stat().st_mode) == 0o750
    assert stat.S_IMODE((tmp_path / "a").stat().st_mode) == 0o750
    assert stat.S_IMODE((tmp_path / "a" / "b").stat().st_mode) == 0o750


def test_make_dir_action_parents_false_missing_parent_raises(tmp_path: Path) -> None:
    """parents=False ohne bestehendes Elternverzeichnis erzeugt ActionError."""
    path = tmp_path / "fehlt" / "neu"

    action = MakeDirAction(str(path), parents=False)
    with pytest.raises(ActionError, match="Fehler beim Anlegen"):
        action.run()
    assert action.status == "failed"
    assert not path.exists()


def test_make_dir_action_existing_directory_is_idempotent(tmp_path: Path) -> None:
    """Bestehendes Verzeichnis bleibt unverändert; Status ist finished."""
    path = tmp_path / "vorhanden"
    path.mkdir()
    path.chmod(0o700)

    action = MakeDirAction(str(path), mode=0o755)
    result = action.run()

    assert result == "finished"
    assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_make_dir_action_existing_file_raises(tmp_path: Path) -> None:
    """Bestehende Datei am Pfad erzeugt ActionError."""
    path = tmp_path / "datei"
    path.write_text("inhalt", encoding="utf-8")

    action = MakeDirAction(str(path))
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"
    assert path.is_file()


def test_make_dir_action_existing_symlink_raises(tmp_path: Path) -> None:
    """Symlink am Pfad (auch auf ein Verzeichnis) erzeugt ActionError."""
    real_dir = tmp_path / "echtes_verzeichnis"
    real_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_dir)

    action = MakeDirAction(str(link))
    with pytest.raises(ActionError, match="Symlink"):
        action.run()
    assert action.status == "failed"
    assert link.is_symlink()


def test_make_dir_action_exact_mode_despite_restrictive_umask(
    tmp_path: Path,
) -> None:
    """Ein einschränkender umask engt die tatsächlichen Rechte nicht ein.

    os.mkdir mit explizitem mode wäre bei umask 0o077 auf 0o700 statt
    0o750 begrenzt worden; das nachgelagerte os.fchmod korrigiert das.
    """
    path = tmp_path / "neu"
    old_umask = os.umask(0o077)
    try:
        action = MakeDirAction(str(path), mode=0o750)
        action.run()
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(path.stat().st_mode) == 0o750


def test_make_dir_action_parents_exact_mode_despite_restrictive_umask(
    tmp_path: Path,
) -> None:
    """Auch neu angelegte Elternverzeichnisse erhalten trotz umask exakt mode."""
    path = tmp_path / "a" / "b"
    old_umask = os.umask(0o077)
    try:
        action = MakeDirAction(str(path), mode=0o750, parents=True)
        action.run()
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(path.stat().st_mode) == 0o750
    assert stat.S_IMODE((tmp_path / "a").stat().st_mode) == 0o750


def test_make_dir_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert MakeDirAction.PARAMS == ["path", "mode", "parents"]
