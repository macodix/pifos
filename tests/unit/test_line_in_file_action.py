"""Tests für pifos.actions.line_in_file_action."""

import stat
from pathlib import Path

import pytest
from pifos.actions.line_in_file_action import LineInFileAction
from pifos.errors import ActionError


def test_line_in_file_action_present_appends_missing_line(tmp_path: Path) -> None:
    """Fehlende Zeile wird am Dateiende angefügt."""
    path = tmp_path / "config.txt"
    path.write_text("eins\nzwei\n", encoding="utf-8")

    action = LineInFileAction(str(path), "drei", safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "eins\nzwei\ndrei\n"


def test_line_in_file_action_present_appends_to_file_without_trailing_newline(
    tmp_path: Path,
) -> None:
    """Fehlender Zeilenumbruch der letzten Zeile wird vor dem Anfügen ergänzt."""
    path = tmp_path / "config.txt"
    path.write_text("eins\nzwei", encoding="utf-8")

    action = LineInFileAction(str(path), "drei", safe_mode=False)
    action.run()

    assert path.read_text(encoding="utf-8") == "eins\nzwei\ndrei\n"


def test_line_in_file_action_present_exact_match_no_change(tmp_path: Path) -> None:
    """Bereits vorhandene exakte Zeile bewirkt keine Änderung."""
    path = tmp_path / "config.txt"
    path.write_text("eins\nzwei\n", encoding="utf-8")

    action = LineInFileAction(str(path), "zwei", safe_mode=True)
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "eins\nzwei\n"
    assert not (tmp_path / "config.txt.bak").exists()


def test_line_in_file_action_present_with_match_replaces_line(tmp_path: Path) -> None:
    """match erkennt eine abweichende Zeile und ersetzt sie durch line."""
    path = tmp_path / "sshd_config"
    path.write_text("Port 22\n#PermitRootLogin yes\n", encoding="utf-8")

    action = LineInFileAction(
        str(path),
        "PermitRootLogin no",
        match=r"^#?\s*PermitRootLogin\b",
        safe_mode=False,
    )
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "Port 22\nPermitRootLogin no\n"


def test_line_in_file_action_absent_removes_matching_lines(tmp_path: Path) -> None:
    """absent entfernt alle auf match passenden Zeilen."""
    path = tmp_path / "config.txt"
    path.write_text("eins\nfoo=1\nzwei\nfoo=2\n", encoding="utf-8")

    action = LineInFileAction(
        str(path), "", match=r"^foo=", state="absent", safe_mode=False
    )
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "eins\nzwei\n"


def test_line_in_file_action_absent_no_match_no_change(tmp_path: Path) -> None:
    """absent ohne Treffer ändert die Datei nicht; Status ist dennoch finished."""
    path = tmp_path / "config.txt"
    path.write_text("eins\nzwei\n", encoding="utf-8")

    action = LineInFileAction(str(path), "drei", state="absent", safe_mode=True)
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "eins\nzwei\n"
    assert not (tmp_path / "config.txt.bak").exists()


def test_line_in_file_action_missing_file_raises(tmp_path: Path) -> None:
    """Fehlende Zieldatei erzeugt ActionError."""
    path = tmp_path / "existiert_nicht.txt"

    action = LineInFileAction(str(path), "zeile")
    with pytest.raises(ActionError, match="Datei nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_line_in_file_action_safe_mode_backup_on_change(tmp_path: Path) -> None:
    """Bei nötiger Änderung wird die Datei vorher gesichert."""
    path = tmp_path / "config.txt"
    path.write_text("eins\n", encoding="utf-8")

    action = LineInFileAction(str(path), "zwei", safe_mode=True)
    action.run()

    backup_path = tmp_path / "config.txt.bak"
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "eins\n"


def test_line_in_file_action_preserves_permissions(tmp_path: Path) -> None:
    """Die bestehenden Dateirechte bleiben nach dem Schreiben erhalten."""
    path = tmp_path / "config.txt"
    path.write_text("eins\n", encoding="utf-8")
    path.chmod(0o640)

    action = LineInFileAction(str(path), "zwei", safe_mode=False)
    action.run()

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_line_in_file_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    path = tmp_path / "config.txt"
    path.write_text("eins\n", encoding="utf-8")

    action = LineInFileAction(
        str(path),
        "zwei",
        safe_mode=True,
        backup_location=str(tmp_path / "nicht_vorhanden"),
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"


def test_line_in_file_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert LineInFileAction.PARAMS == [
        "path",
        "line",
        "match",
        "state",
        "safe_mode",
        "backup_location",
    ]
