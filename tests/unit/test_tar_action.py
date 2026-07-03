"""Tests für pifos.actions.tar_action."""

import stat
import tarfile
from pathlib import Path

import pytest
from pifos.actions.tar_action import TarAction
from pifos.errors import ActionError


def test_tar_action_success_gz(tmp_path: Path) -> None:
    """Quellen werden gzip-komprimiert ins Archiv gepackt."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst = tmp_path / "archiv.tar.gz"

    action = TarAction([str(src)], str(dst), safe_mode=False)
    result = action.run()

    assert result == "finished"
    assert dst.exists()
    with tarfile.open(str(dst), mode="r:gz") as tar:
        assert tar.getnames() == ["quelle.txt"]
        extracted = tar.extractfile("quelle.txt")
        assert extracted is not None
        assert extracted.read() == b"inhalt"


def test_tar_action_success_uncompressed(tmp_path: Path) -> None:
    """compression=None erstellt ein unkomprimiertes Archiv."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst = tmp_path / "archiv.tar"

    action = TarAction([str(src)], str(dst), compression=None, safe_mode=False)
    action.run()

    with tarfile.open(str(dst), mode="r:") as tar:
        assert tar.getnames() == ["quelle.txt"]


def test_tar_action_directory_source_recursive(tmp_path: Path) -> None:
    """Ein Verzeichnis wird rekursiv mit Basisname ins Archiv aufgenommen."""
    src_dir = tmp_path / "daten"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("a", encoding="utf-8")
    (src_dir / "unterordner").mkdir()
    (src_dir / "unterordner" / "b.txt").write_text("b", encoding="utf-8")
    dst = tmp_path / "archiv.tar.gz"

    action = TarAction([str(src_dir)], str(dst), safe_mode=False)
    action.run()

    with tarfile.open(str(dst), mode="r:gz") as tar:
        names = set(tar.getnames())
    assert "daten" in names
    assert "daten/a.txt" in names
    assert "daten/unterordner/b.txt" in names


def test_tar_action_default_mode(tmp_path: Path) -> None:
    """Voreinstellung für die Archivrechte ist 0o600."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst = tmp_path / "archiv.tar.gz"

    action = TarAction([str(src)], str(dst), safe_mode=False)
    action.run()

    assert stat.S_IMODE(dst.stat().st_mode) == 0o600


def test_tar_action_explicit_mode(tmp_path: Path) -> None:
    """Ein ausdrücklich übergebenes mode wird gesetzt."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst = tmp_path / "archiv.tar.gz"

    action = TarAction([str(src)], str(dst), mode=0o644, safe_mode=False)
    action.run()

    assert stat.S_IMODE(dst.stat().st_mode) == 0o644


def test_tar_action_source_not_found(tmp_path: Path) -> None:
    """Fehlende Quelle erzeugt ActionError; kein Archiv wird angelegt."""
    dst = tmp_path / "archiv.tar.gz"

    action = TarAction([str(tmp_path / "existiert_nicht")], str(dst))
    with pytest.raises(ActionError, match="Quelle nicht gefunden"):
        action.run()
    assert action.status == "failed"
    assert not dst.exists()


def test_tar_action_no_overwrite_raises(tmp_path: Path) -> None:
    """safe_mode ohne overwrite schützt ein bestehendes Zielarchiv."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst = tmp_path / "archiv.tar.gz"
    dst.write_bytes(b"altes archiv")

    action = TarAction([str(src)], str(dst), safe_mode=True, overwrite=False)
    with pytest.raises(ActionError, match="Überschreiben nicht freigegeben"):
        action.run()
    assert action.status == "failed"
    assert dst.read_bytes() == b"altes archiv"


def test_tar_action_safe_mode_backup(tmp_path: Path) -> None:
    """safe_mode mit overwrite sichert das bestehende Zielarchiv."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst = tmp_path / "archiv.tar.gz"
    dst.write_bytes(b"altes archiv")

    action = TarAction([str(src)], str(dst), safe_mode=True, overwrite=True)
    result = action.run()

    assert result == "finished"
    backups = list(tmp_path.glob("archiv.tar.gz.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"altes archiv"


def test_tar_action_invalid_backup_location(tmp_path: Path) -> None:
    """Ungültiger Sicherungsort erzeugt ActionError."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst = tmp_path / "archiv.tar.gz"
    dst.write_bytes(b"altes archiv")

    action = TarAction(
        [str(src)],
        str(dst),
        safe_mode=True,
        overwrite=True,
        backup_location=str(tmp_path / "nicht_vorhanden"),
    )
    with pytest.raises(ActionError, match="kein Verzeichnis"):
        action.run()
    assert action.status == "failed"


def test_tar_action_no_temp_file_left_after_pack_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Packungsfehler (TarError) hinterlässt keine Temp-Datei im Zielverzeichnis."""
    src = tmp_path / "quelle.txt"
    src.write_text("inhalt", encoding="utf-8")
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()
    dst = dst_dir / "archiv.tar.gz"

    def raise_tar_error(*_args: object, **_kwargs: object) -> None:
        raise tarfile.TarError("simulierter Packungsfehler")

    monkeypatch.setattr(tarfile.TarFile, "add", raise_tar_error)

    action = TarAction([str(src)], str(dst), safe_mode=False)
    with pytest.raises(ActionError, match="Fehler beim Packen"):
        action.run()
    assert action.status == "failed"
    assert list(dst_dir.iterdir()) == []


def test_tar_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert TarAction.PARAMS == [
        "sources",
        "dst",
        "compression",
        "mode",
        "safe_mode",
        "backup_location",
        "overwrite",
    ]
