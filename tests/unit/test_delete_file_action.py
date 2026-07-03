"""Tests für pifos.actions.delete_file_action."""

from pathlib import Path

import pytest
from pifos.actions.delete_file_action import DeleteFileAction
from pifos.errors import ActionError


def test_delete_file_action_success_without_safe_mode(tmp_path: Path) -> None:
    """safe_mode=False löscht die Datei ohne Sicherung."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    action = DeleteFileAction(str(path), safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert not path.exists()
    assert list(tmp_path.glob("datei.txt.bak-*")) == []


def test_delete_file_action_safe_mode_creates_backup(tmp_path: Path) -> None:
    """safe_mode=True (Voreinstellung) sichert die Datei vor dem Löschen."""
    path = tmp_path / "datei.txt"
    path.write_text("wichtiger inhalt", encoding="utf-8")

    action = DeleteFileAction(str(path))
    result = action.run()

    assert result == "finished"
    assert not path.exists()
    backups = list(tmp_path.glob("datei.txt.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "wichtiger inhalt"


def test_delete_file_action_safe_mode_backup_location(tmp_path: Path) -> None:
    """backup_location bestimmt das Sicherungsverzeichnis."""
    path = tmp_path / "datei.txt"
    backup_dir = tmp_path / "sicherung"
    backup_dir.mkdir()
    path.write_text("inhalt", encoding="utf-8")

    action = DeleteFileAction(str(path), backup_location=str(backup_dir))
    action.run()

    assert not path.exists()
    backups = list(backup_dir.glob("datei.txt.bak-*"))
    assert len(backups) == 1


def test_delete_file_action_missing_file_raises(tmp_path: Path) -> None:
    """Fehlende Datei erzeugt ActionError."""
    path = tmp_path / "existiert_nicht.txt"

    action = DeleteFileAction(str(path))
    with pytest.raises(ActionError, match="Datei nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_delete_file_action_symlink_safe_mode_rejected(tmp_path: Path) -> None:
    """Symlink als path kann im safe-mode nicht gesichert werden."""
    real_target = tmp_path / "echte_datei.txt"
    real_target.write_text("inhalt", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real_target)

    action = DeleteFileAction(str(link), safe_mode=True)
    with pytest.raises(ActionError):
        action.run()

    assert action.status == "failed"
    assert link.is_symlink()
    assert real_target.read_text(encoding="utf-8") == "inhalt"


def test_delete_file_action_symlink_without_safe_mode_removes_link_only(
    tmp_path: Path,
) -> None:
    """Ohne safe_mode wird nur der Symlink entfernt, nicht sein Ziel."""
    real_target = tmp_path / "echte_datei.txt"
    real_target.write_text("inhalt", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real_target)

    action = DeleteFileAction(str(link), safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert not link.is_symlink()
    assert not link.exists()
    assert real_target.exists()
    assert real_target.read_text(encoding="utf-8") == "inhalt"


def test_delete_file_action_broken_symlink_without_safe_mode(tmp_path: Path) -> None:
    """Ein defekter Symlink (Ziel fehlt) gilt als vorhanden und ist löschbar."""
    link = tmp_path / "kaputter_link.txt"
    link.symlink_to(tmp_path / "existiert_nie.txt")

    action = DeleteFileAction(str(link), safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert not link.is_symlink()


def test_delete_file_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    action = DeleteFileAction(
        str(path), backup_location=str(tmp_path / "nicht_vorhanden")
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"
    assert path.exists()


def test_delete_file_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert DeleteFileAction.PARAMS == ["path", "safe_mode", "backup_location"]
