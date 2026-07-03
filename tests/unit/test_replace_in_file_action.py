"""Tests für pifos.actions.replace_in_file_action."""

import stat
from pathlib import Path

import pytest
from pifos.actions.replace_in_file_action import ReplaceInFileAction
from pifos.errors import ActionError


def test_replace_in_file_action_replaces_all_occurrences(tmp_path: Path) -> None:
    """count=0 (Voreinstellung) ersetzt alle Fundstellen."""
    path = tmp_path / "config.txt"
    path.write_text("foo=1\nfoo=2\nfoo=3\n", encoding="utf-8")

    action = ReplaceInFileAction(str(path), r"foo=\d+", "foo=0", safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "foo=0\nfoo=0\nfoo=0\n"


def test_replace_in_file_action_respects_count(tmp_path: Path) -> None:
    """Ein gesetztes count begrenzt die Anzahl Ersetzungen."""
    path = tmp_path / "config.txt"
    path.write_text("foo=1\nfoo=2\nfoo=3\n", encoding="utf-8")

    action = ReplaceInFileAction(
        str(path), r"foo=\d+", "foo=0", count=1, safe_mode=False
    )
    action.run()

    assert path.read_text(encoding="utf-8") == "foo=0\nfoo=2\nfoo=3\n"


def test_replace_in_file_action_backreference(tmp_path: Path) -> None:
    """Rückverweise im Ersetzungstext werden aufgelöst."""
    path = tmp_path / "config.txt"
    path.write_text("Name: martin\n", encoding="utf-8")

    action = ReplaceInFileAction(
        str(path), r"Name: (\w+)", r"Name: [\1]", safe_mode=False
    )
    action.run()

    assert path.read_text(encoding="utf-8") == "Name: [martin]\n"


def test_replace_in_file_action_no_match_no_change(tmp_path: Path) -> None:
    """Ohne Fundstelle bleibt die Datei unverändert; Status ist finished."""
    path = tmp_path / "config.txt"
    path.write_text("eins\nzwei\n", encoding="utf-8")

    action = ReplaceInFileAction(str(path), r"drei", "vier", safe_mode=True)
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "eins\nzwei\n"
    assert list(tmp_path.glob("config.txt.bak-*")) == []


def test_replace_in_file_action_missing_file_raises(tmp_path: Path) -> None:
    """Fehlende Zieldatei erzeugt ActionError."""
    path = tmp_path / "existiert_nicht.txt"

    action = ReplaceInFileAction(str(path), r"foo", "bar")
    with pytest.raises(ActionError, match="Datei nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_replace_in_file_action_safe_mode_backup_on_change(tmp_path: Path) -> None:
    """Bei nötiger Änderung wird die Datei vorher gesichert."""
    path = tmp_path / "config.txt"
    path.write_text("alter Inhalt\n", encoding="utf-8")

    action = ReplaceInFileAction(str(path), r"alter", "neuer", safe_mode=True)
    action.run()

    backups = list(tmp_path.glob("config.txt.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "alter Inhalt\n"


def test_replace_in_file_action_preserves_permissions(tmp_path: Path) -> None:
    """Die bestehenden Dateirechte bleiben nach dem Schreiben erhalten."""
    path = tmp_path / "config.txt"
    path.write_text("foo=1\n", encoding="utf-8")
    path.chmod(0o640)

    action = ReplaceInFileAction(str(path), r"foo=\d+", "foo=2", safe_mode=False)
    action.run()

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_replace_in_file_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    path = tmp_path / "config.txt"
    path.write_text("foo=1\n", encoding="utf-8")

    action = ReplaceInFileAction(
        str(path),
        r"foo=\d+",
        "foo=2",
        safe_mode=True,
        backup_location=str(tmp_path / "nicht_vorhanden"),
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"


def test_replace_in_file_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert ReplaceInFileAction.PARAMS == [
        "path",
        "pattern",
        "replacement",
        "count",
        "safe_mode",
        "backup_location",
    ]
