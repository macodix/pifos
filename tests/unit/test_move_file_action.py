"""Tests für pifos.actions.move_file_action."""

import errno
import os
import stat
from pathlib import Path

import pytest
from pifos.actions.move_file_action import MoveFileAction
from pifos.errors import ActionError


def test_move_file_action_success(tmp_path: Path) -> None:
    """Datei wird verschoben; Quelle verschwindet, Status ist finished."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("hello pifos", encoding="utf-8")

    action = MoveFileAction(str(src), str(dst), safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "hello pifos"


def test_move_file_action_preserves_permissions(tmp_path: Path) -> None:
    """Die Rechte der Quelldatei bleiben nach dem Verschieben erhalten."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("inhalt", encoding="utf-8")
    src.chmod(0o640)

    action = MoveFileAction(str(src), str(dst), safe_mode=False)
    action.run()

    assert stat.S_IMODE(dst.stat().st_mode) == 0o640


def test_move_file_action_no_overwrite_raises(tmp_path: Path) -> None:
    """safe_mode ohne overwrite schützt bestehende Zieldatei."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("neu", encoding="utf-8")
    dst.write_text("alt", encoding="utf-8")

    action = MoveFileAction(str(src), str(dst), safe_mode=True, overwrite=False)
    with pytest.raises(ActionError, match="Überschreiben nicht freigegeben"):
        action.run()
    assert action.status == "failed"
    assert src.exists()
    assert dst.read_text(encoding="utf-8") == "alt"


def test_move_file_action_safe_mode_backup(tmp_path: Path) -> None:
    """safe_mode mit overwrite sichert die Zieldatei vor dem Überschreiben."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    backup_dir = tmp_path / "sicherung"
    backup_dir.mkdir()
    src.write_text("neuer Inhalt", encoding="utf-8")
    dst.write_text("originaler Inhalt", encoding="utf-8")

    action = MoveFileAction(
        str(src),
        str(dst),
        safe_mode=True,
        overwrite=True,
        backup_location=str(backup_dir),
    )
    result = action.run()

    assert result == "finished"
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "neuer Inhalt"
    backups = list(backup_dir.glob("ziel.txt.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "originaler Inhalt"


def test_move_file_action_source_not_found(tmp_path: Path) -> None:
    """Fehlende Quelldatei erzeugt ActionError."""
    src = tmp_path / "existiert_nicht.txt"
    dst = tmp_path / "ziel.txt"

    action = MoveFileAction(str(src), str(dst))
    with pytest.raises(ActionError, match="Quelldatei nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_move_file_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst.write_text("alt", encoding="utf-8")

    action = MoveFileAction(
        str(src),
        str(dst),
        safe_mode=True,
        overwrite=True,
        backup_location=str(tmp_path / "nicht_vorhanden"),
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"


def test_move_file_action_cross_filesystem_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EXDEV bei os.replace löst Kopie über Temp-Datei plus Entfernen aus."""
    src = tmp_path / "quelle.txt"
    dst = tmp_path / "ziel.txt"
    src.write_text("inhalt", encoding="utf-8")
    src.chmod(0o640)

    real_replace = os.replace

    def fake_replace(src_arg: object, dst_arg: object) -> None:
        if str(src_arg) == str(src):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        real_replace(src_arg, dst_arg)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", fake_replace)

    action = MoveFileAction(str(src), str(dst), safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "inhalt"
    assert stat.S_IMODE(dst.stat().st_mode) == 0o640


def test_move_file_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert MoveFileAction.PARAMS == [
        "src",
        "dst",
        "safe_mode",
        "backup_location",
        "overwrite",
    ]
