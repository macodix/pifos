"""Tests für pifos.actions.copy_file_action."""

import stat
from pathlib import Path

import pytest
from pifos.actions.copy_file_action import CopyFileAction
from pifos.errors import ActionError


def test_copy_file_action_success(tmp_path: Path) -> None:
    """Datei wird erfolgreich kopiert; Status ist finished."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("hello pifos", encoding="utf-8")

    action = CopyFileAction(str(src), str(dst), safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert dst.read_text(encoding="utf-8") == "hello pifos"


def test_copy_file_action_no_overwrite_raises(tmp_path: Path) -> None:
    """safe_mode ohne overwrite schützt bestehende Zieldatei."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("neu", encoding="utf-8")
    dst.write_text("alt", encoding="utf-8")

    action = CopyFileAction(str(src), str(dst), safe_mode=True, overwrite=False)
    with pytest.raises(ActionError, match="Überschreiben nicht freigegeben"):
        action.run()
    assert action.status == "failed"
    assert dst.read_text(encoding="utf-8") == "alt"


def test_copy_file_action_safe_mode_backup(tmp_path: Path) -> None:
    """safe_mode mit overwrite sichert die Zieldatei vor dem Überschreiben."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    backup_dir = tmp_path / "sicherung"
    backup_dir.mkdir()
    src.write_text("neuer Inhalt", encoding="utf-8")
    dst.write_text("originaler Inhalt", encoding="utf-8")

    action = CopyFileAction(
        str(src),
        str(dst),
        safe_mode=True,
        overwrite=True,
        backup_location=str(backup_dir),
    )
    result = action.run()

    assert result == "finished"
    assert dst.read_text(encoding="utf-8") == "neuer Inhalt"
    backups = list(backup_dir.glob("ziel.txt.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "originaler Inhalt"


def test_copy_file_action_backup_preserves_permissions(tmp_path: Path) -> None:
    """Sicherung übernimmt die Rechte der Originaldatei (SIC-13)."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("neu", encoding="utf-8")
    dst.write_text("alt", encoding="utf-8")
    dst.chmod(0o600)

    action = CopyFileAction(str(src), str(dst), safe_mode=True, overwrite=True)
    action.run()

    backups = list(tmp_path.glob("ziel.txt.bak-*"))
    assert len(backups) == 1
    backup_mode = stat.S_IMODE(backups[0].stat().st_mode)
    assert backup_mode == 0o600


def test_copy_file_action_two_backups_in_a_row_both_succeed(tmp_path: Path) -> None:
    """Zwei Sicherungen derselben Datei nacheinander funktionieren beide.

    Beide Läufe fallen typischerweise in dieselbe Sekunde (gleicher
    Zeitstempel); die zweite Sicherung muss trotzdem gelingen (Kollisions-
    Zusatz statt Fehler).
    """
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("inhalt 1", encoding="utf-8")
    dst.write_text("original", encoding="utf-8")

    action1 = CopyFileAction(str(src), str(dst), safe_mode=True, overwrite=True)
    action1.run()

    src.write_text("inhalt 2", encoding="utf-8")
    action2 = CopyFileAction(str(src), str(dst), safe_mode=True, overwrite=True)
    action2.run()

    backups = sorted(tmp_path.glob("ziel.txt.bak-*"))
    assert len(backups) == 2
    contents = {backup.read_text(encoding="utf-8") for backup in backups}
    assert contents == {"original", "inhalt 1"}


def test_copy_file_action_source_not_found(tmp_path: Path) -> None:
    """Fehlende Quelldatei erzeugt ActionError."""
    src = tmp_path / "existiert_nicht.txt"
    dst = tmp_path / "ziel.txt"

    action = CopyFileAction(str(src), str(dst))
    with pytest.raises(ActionError, match="Quelldatei nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_copy_file_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst.write_text("alt", encoding="utf-8")

    action = CopyFileAction(
        str(src),
        str(dst),
        safe_mode=True,
        overwrite=True,
        backup_location=str(tmp_path / "nicht_vorhanden"),
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"


def test_copy_file_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert CopyFileAction.PARAMS == [
        "src",
        "dst",
        "safe_mode",
        "backup_location",
        "overwrite",
    ]
