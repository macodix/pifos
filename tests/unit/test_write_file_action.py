"""Tests für pifos.actions.write_file_action."""

import stat
from pathlib import Path

import pytest
from pifos.actions.write_file_action import WriteFileAction
from pifos.errors import ActionError


def test_write_file_action_success_default_mode(tmp_path: Path) -> None:
    """Neue Datei wird geschrieben; Voreinstellung ist Rechte 0o600."""
    dst = tmp_path / "ziel.txt"

    action = WriteFileAction(str(dst), "hallo pifos")
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert dst.read_text(encoding="utf-8") == "hallo pifos"
    assert stat.S_IMODE(dst.stat().st_mode) == 0o600


def test_write_file_action_explicit_mode_new_file(tmp_path: Path) -> None:
    """Ausdrücklich übergebenes mode wird bei neuer Datei gesetzt."""
    dst = tmp_path / "ziel.txt"

    action = WriteFileAction(str(dst), "inhalt", mode=0o644)
    action.run()

    assert stat.S_IMODE(dst.stat().st_mode) == 0o644


def test_write_file_action_no_overwrite_raises(tmp_path: Path) -> None:
    """safe_mode ohne overwrite schützt bestehende Zieldatei."""
    dst = tmp_path / "ziel.txt"
    dst.write_text("alt", encoding="utf-8")

    action = WriteFileAction(str(dst), "neu", safe_mode=True, overwrite=False)
    with pytest.raises(ActionError, match="Überschreiben nicht freigegeben"):
        action.run()
    assert action.status == "failed"
    assert dst.read_text(encoding="utf-8") == "alt"


def test_write_file_action_safe_mode_backup(tmp_path: Path) -> None:
    """safe_mode mit overwrite sichert die Zieldatei vor dem Überschreiben."""
    dst = tmp_path / "ziel.txt"
    backup_dir = tmp_path / "sicherung"
    backup_dir.mkdir()
    dst.write_text("originaler Inhalt", encoding="utf-8")

    action = WriteFileAction(
        str(dst),
        "neuer Inhalt",
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


def test_write_file_action_overwrite_preserves_permissions_without_mode(
    tmp_path: Path,
) -> None:
    """Ohne explizites mode bleiben die Rechte der bestehenden Zieldatei erhalten."""
    dst = tmp_path / "ziel.txt"
    dst.write_text("alt", encoding="utf-8")
    dst.chmod(0o640)

    action = WriteFileAction(str(dst), "neu", safe_mode=True, overwrite=True)
    action.run()

    assert stat.S_IMODE(dst.stat().st_mode) == 0o640


def test_write_file_action_explicit_mode_overrides_existing_permissions(
    tmp_path: Path,
) -> None:
    """Ausdrücklich übergebenes mode hat Vorrang vor bestehenden Rechten."""
    dst = tmp_path / "ziel.txt"
    dst.write_text("alt", encoding="utf-8")
    dst.chmod(0o640)

    action = WriteFileAction(
        str(dst), "neu", mode=0o644, safe_mode=True, overwrite=True
    )
    action.run()

    assert stat.S_IMODE(dst.stat().st_mode) == 0o644


def test_write_file_action_safe_mode_false_overwrites_without_backup(
    tmp_path: Path,
) -> None:
    """Ohne safe_mode wird die Zieldatei ohne Sicherung überschrieben."""
    dst = tmp_path / "ziel.txt"
    dst.write_text("alt", encoding="utf-8")

    action = WriteFileAction(str(dst), "neu", safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert dst.read_text(encoding="utf-8") == "neu"
    assert list(tmp_path.glob("ziel.txt.bak-*")) == []


def test_write_file_action_symlink_dst_without_explicit_mode_raises(
    tmp_path: Path,
) -> None:
    """Symlink als Ziel ohne explizites mode erzeugt ActionError.

    Ohne O_NOFOLLOW würden die Rechte des Symlinks (typischerweise
    0o777) übernommen und beim atomaren Austausch auf eine reguläre
    Datei angewendet — eine Rechteausweitung (SIC-13).
    """
    real_target = tmp_path / "echte_datei.txt"
    real_target.write_text("alt", encoding="utf-8")
    real_target.chmod(0o600)
    dst = tmp_path / "symlink.txt"
    dst.symlink_to(real_target)

    action = WriteFileAction(str(dst), "neu", safe_mode=False)
    with pytest.raises(ActionError):
        action.run()

    assert action.status == "failed"
    assert dst.is_symlink()
    assert real_target.read_text(encoding="utf-8") == "alt"
    assert stat.S_IMODE(real_target.stat().st_mode) == 0o600


def test_write_file_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    dst = tmp_path / "ziel.txt"
    dst.write_text("alt", encoding="utf-8")

    action = WriteFileAction(
        str(dst),
        "neu",
        safe_mode=True,
        overwrite=True,
        backup_location=str(tmp_path / "nicht_vorhanden"),
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"


def test_write_file_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert WriteFileAction.PARAMS == [
        "dst",
        "content",
        "mode",
        "safe_mode",
        "backup_location",
        "overwrite",
    ]
