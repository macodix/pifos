"""Tests für pifos.actions.block_in_file_action."""

import stat
from pathlib import Path

import pytest
from pifos.actions.block_in_file_action import BlockInFileAction
from pifos.errors import ActionError


def test_block_in_file_action_present_appends_missing_block(tmp_path: Path) -> None:
    """Fehlender Block wird mit Leerzeile davor am Dateiende angefügt."""
    path = tmp_path / "hosts"
    path.write_text("127.0.0.1 localhost\n", encoding="utf-8")

    action = BlockInFileAction(
        str(path), "10.0.0.1 intern", marker="pifos-hosts", safe_mode=False
    )
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == (
        "127.0.0.1 localhost\n"
        "\n"
        "# BEGIN pifos-hosts\n"
        "10.0.0.1 intern\n"
        "# END pifos-hosts\n"
    )


def test_block_in_file_action_present_multiline_block(tmp_path: Path) -> None:
    """Mehrzeiliger Blockinhalt wird zeilenweise eingefügt."""
    path = tmp_path / "config.txt"
    path.write_text("", encoding="utf-8")

    action = BlockInFileAction(str(path), "eins\nzwei", marker="block", safe_mode=False)
    action.run()

    assert path.read_text(encoding="utf-8") == (
        "# BEGIN block\neins\nzwei\n# END block\n"
    )


def test_block_in_file_action_present_existing_block_no_change(
    tmp_path: Path,
) -> None:
    """Bereits vorhandener, identischer Block bewirkt keine Änderung."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n# BEGIN block\ninhalt\n# END block\nnach\n", encoding="utf-8")

    action = BlockInFileAction(str(path), "inhalt", marker="block", safe_mode=True)
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == (
        "vor\n# BEGIN block\ninhalt\n# END block\nnach\n"
    )
    assert not (tmp_path / "config.txt.bak").exists()


def test_block_in_file_action_present_replaces_differing_block(
    tmp_path: Path,
) -> None:
    """Abweichender Blockinhalt wird zwischen den Markerzeilen ersetzt."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n# BEGIN block\nalt\n# END block\nnach\n", encoding="utf-8")

    action = BlockInFileAction(str(path), "neu", marker="block", safe_mode=False)
    action.run()

    assert path.read_text(encoding="utf-8") == (
        "vor\n# BEGIN block\nneu\n# END block\nnach\n"
    )


def test_block_in_file_action_absent_removes_block(tmp_path: Path) -> None:
    """absent entfernt Block samt Markerzeilen."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n# BEGIN block\ninhalt\n# END block\nnach\n", encoding="utf-8")

    action = BlockInFileAction(
        str(path), "inhalt", marker="block", state="absent", safe_mode=False
    )
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "vor\nnach\n"


def test_block_in_file_action_absent_removes_separator_blank_line(
    tmp_path: Path,
) -> None:
    """absent entfernt auch die Trenner-Leerzeile vor der Begin-Markerzeile."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n\n# BEGIN block\ninhalt\n# END block\n", encoding="utf-8")

    action = BlockInFileAction(
        str(path), "inhalt", marker="block", state="absent", safe_mode=False
    )
    action.run()

    assert path.read_text(encoding="utf-8") == "vor\n"


def test_block_in_file_action_absent_keeps_content_line_without_separator(
    tmp_path: Path,
) -> None:
    """Ohne Trenner-Leerzeile bleibt eine inhaltlich gefüllte Zeile davor erhalten."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n# BEGIN block\ninhalt\n# END block\nnach\n", encoding="utf-8")

    action = BlockInFileAction(
        str(path), "inhalt", marker="block", state="absent", safe_mode=False
    )
    action.run()

    assert path.read_text(encoding="utf-8") == "vor\nnach\n"


def test_block_in_file_action_present_absent_round_trip_restores_original(
    tmp_path: Path,
) -> None:
    """present (Neuanlage) gefolgt von absent stellt den Ausgangsinhalt wieder her."""
    path = tmp_path / "hosts"
    original = "127.0.0.1 localhost\n"
    path.write_text(original, encoding="utf-8")

    present_action = BlockInFileAction(
        str(path), "10.0.0.1 intern", marker="pifos-hosts", safe_mode=False
    )
    present_action.run()
    assert path.read_text(encoding="utf-8") != original

    absent_action = BlockInFileAction(
        str(path),
        "10.0.0.1 intern",
        marker="pifos-hosts",
        state="absent",
        safe_mode=False,
    )
    absent_action.run()

    assert path.read_text(encoding="utf-8") == original


def test_block_in_file_action_present_absent_double_cycle_is_idempotent(
    tmp_path: Path,
) -> None:
    """Zwei present/absent-Zyklen hintereinander summieren keine Leerzeilen auf."""
    path = tmp_path / "hosts"
    original = "127.0.0.1 localhost\n"
    path.write_text(original, encoding="utf-8")

    for _ in range(2):
        present_action = BlockInFileAction(
            str(path), "10.0.0.1 intern", marker="pifos-hosts", safe_mode=False
        )
        present_action.run()

        absent_action = BlockInFileAction(
            str(path),
            "10.0.0.1 intern",
            marker="pifos-hosts",
            state="absent",
            safe_mode=False,
        )
        absent_action.run()

        assert path.read_text(encoding="utf-8") == original


def test_block_in_file_action_absent_missing_block_no_change(tmp_path: Path) -> None:
    """absent ohne vorhandenen Block ändert die Datei nicht."""
    path = tmp_path / "config.txt"
    path.write_text("vor\nnach\n", encoding="utf-8")

    action = BlockInFileAction(
        str(path), "inhalt", marker="block", state="absent", safe_mode=True
    )
    result = action.run()

    assert result == "finished"
    assert path.read_text(encoding="utf-8") == "vor\nnach\n"
    assert not (tmp_path / "config.txt.bak").exists()


def test_block_in_file_action_custom_comment_char(tmp_path: Path) -> None:
    """comment_char bestimmt das Kommentarzeichen der Markerzeilen."""
    path = tmp_path / "config.ini"
    path.write_text("", encoding="utf-8")

    action = BlockInFileAction(
        str(path),
        "inhalt",
        marker="block",
        comment_char=";",
        safe_mode=False,
    )
    action.run()

    assert path.read_text(encoding="utf-8") == "; BEGIN block\ninhalt\n; END block\n"


def test_block_in_file_action_missing_file_raises(tmp_path: Path) -> None:
    """Fehlende Zieldatei erzeugt ActionError."""
    path = tmp_path / "existiert_nicht.txt"

    action = BlockInFileAction(str(path), "inhalt", marker="block")
    with pytest.raises(ActionError, match="Datei nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_block_in_file_action_safe_mode_backup_on_change(tmp_path: Path) -> None:
    """Bei nötiger Änderung wird die Datei vorher gesichert."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n", encoding="utf-8")

    action = BlockInFileAction(str(path), "inhalt", marker="block", safe_mode=True)
    action.run()

    backup_path = tmp_path / "config.txt.bak"
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "vor\n"


def test_block_in_file_action_preserves_permissions(tmp_path: Path) -> None:
    """Die bestehenden Dateirechte bleiben nach dem Schreiben erhalten."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n", encoding="utf-8")
    path.chmod(0o640)

    action = BlockInFileAction(str(path), "inhalt", marker="block", safe_mode=False)
    action.run()

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_block_in_file_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    path = tmp_path / "config.txt"
    path.write_text("vor\n", encoding="utf-8")

    action = BlockInFileAction(
        str(path),
        "inhalt",
        marker="block",
        safe_mode=True,
        backup_location=str(tmp_path / "nicht_vorhanden"),
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"


def test_block_in_file_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert BlockInFileAction.PARAMS == [
        "path",
        "block",
        "marker",
        "comment_char",
        "state",
        "safe_mode",
        "backup_location",
    ]
