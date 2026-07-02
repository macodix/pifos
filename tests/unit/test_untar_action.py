"""Tests für pifos.actions.untar_action."""

import io
import tarfile
from pathlib import Path

import pytest
from pifos.actions.untar_action import UntarAction
from pifos.errors import ActionError


def _add_members(tar: tarfile.TarFile, members: dict[str, bytes]) -> None:
    """Fügt die gegebenen Mitglieder (Name -> Inhalt) in tar ein."""
    for name, content in members.items():
        info = tarfile.TarInfo(name=name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))


def _make_archive(
    archive_path: Path, members: dict[str, bytes], gz: bool = True
) -> None:
    """Baut ein tar-Archiv mit den gegebenen Mitgliedern (Name -> Inhalt)."""
    if gz:
        with tarfile.open(str(archive_path), mode="w:gz") as tar:
            _add_members(tar, members)
    else:
        with tarfile.open(str(archive_path), mode="w:") as tar:
            _add_members(tar, members)


def test_untar_action_success_gz(tmp_path: Path) -> None:
    """Ein gzip-Archiv wird korrekt entpackt."""
    archive = tmp_path / "archiv.tar.gz"
    _make_archive(archive, {"a.txt": b"inhalt a", "unter/b.txt": b"inhalt b"}, gz=True)
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()

    action = UntarAction(str(archive), str(dst_dir))
    result = action.run()

    assert result == "finished"
    assert (dst_dir / "a.txt").read_bytes() == b"inhalt a"
    assert (dst_dir / "unter" / "b.txt").read_bytes() == b"inhalt b"


def test_untar_action_success_uncompressed_auto_detected(tmp_path: Path) -> None:
    """Ein unkomprimiertes Archiv wird ohne explizite Angabe erkannt."""
    archive = tmp_path / "archiv.tar"
    _make_archive(archive, {"a.txt": b"inhalt a"}, gz=False)
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()

    action = UntarAction(str(archive), str(dst_dir))
    action.run()

    assert (dst_dir / "a.txt").read_bytes() == b"inhalt a"


def test_untar_action_missing_archive_raises(tmp_path: Path) -> None:
    """Fehlendes Archiv erzeugt ActionError."""
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()

    action = UntarAction(str(tmp_path / "existiert_nicht.tar.gz"), str(dst_dir))
    with pytest.raises(ActionError, match="Archiv nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_untar_action_missing_dst_dir_raises(tmp_path: Path) -> None:
    """Fehlendes Zielverzeichnis erzeugt ActionError."""
    archive = tmp_path / "archiv.tar.gz"
    _make_archive(archive, {"a.txt": b"inhalt a"})

    action = UntarAction(str(archive), str(tmp_path / "existiert_nicht"))
    with pytest.raises(ActionError, match="Zielverzeichnis nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_untar_action_collision_without_overwrite_raises(tmp_path: Path) -> None:
    """Bestehende Zieldatei ohne overwrite erzeugt ActionError, nichts wird entpackt."""
    archive = tmp_path / "archiv.tar.gz"
    _make_archive(archive, {"a.txt": b"neu", "b.txt": b"auch neu"})
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()
    (dst_dir / "a.txt").write_bytes(b"alt")

    action = UntarAction(str(archive), str(dst_dir), overwrite=False)
    with pytest.raises(ActionError, match="Zieldateien bereits vorhanden"):
        action.run()

    assert action.status == "failed"
    assert (dst_dir / "a.txt").read_bytes() == b"alt"
    assert not (dst_dir / "b.txt").exists()


def test_untar_action_collision_with_overwrite_succeeds(tmp_path: Path) -> None:
    """overwrite=True überschreibt bestehende Zieldateien."""
    archive = tmp_path / "archiv.tar.gz"
    _make_archive(archive, {"a.txt": b"neu"})
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()
    (dst_dir / "a.txt").write_bytes(b"alt")

    action = UntarAction(str(archive), str(dst_dir), overwrite=True)
    result = action.run()

    assert result == "finished"
    assert (dst_dir / "a.txt").read_bytes() == b"neu"


def test_untar_action_existing_directory_member_is_not_a_collision(
    tmp_path: Path,
) -> None:
    """Ein bereits vorhandenes Verzeichnis im Archiv gilt nicht als Kollision."""
    archive = tmp_path / "archiv.tar.gz"
    with tarfile.open(str(archive), mode="w:gz") as tar:
        dir_info = tarfile.TarInfo(name="unter")
        dir_info.type = tarfile.DIRTYPE
        tar.addfile(dir_info)
        file_info = tarfile.TarInfo(name="unter/a.txt")
        content = b"inhalt"
        file_info.size = len(content)
        tar.addfile(file_info, io.BytesIO(content))
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()
    (dst_dir / "unter").mkdir()

    action = UntarAction(str(archive), str(dst_dir), overwrite=False)
    result = action.run()

    assert result == "finished"
    assert (dst_dir / "unter" / "a.txt").read_bytes() == b"inhalt"


def test_untar_action_path_traversal_member_rejected(tmp_path: Path) -> None:
    """filter='data' weist Pfadausbruch aus dem Zielverzeichnis zurück."""
    archive = tmp_path / "boese.tar.gz"
    _make_archive(archive, {"../ausserhalb.txt": b"boese"})
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()

    action = UntarAction(str(archive), str(dst_dir))
    with pytest.raises(ActionError, match="Fehler beim Entpacken"):
        action.run()

    assert action.status == "failed"
    assert not (tmp_path / "ausserhalb.txt").exists()


def test_untar_action_absolute_path_member_neutralized(tmp_path: Path) -> None:
    """filter='data' entschärft absolute Pfade statt sie außerhalb zu erstellen.

    tarfile entfernt bei absoluten Mitgliedsnamen den führenden
    Pfadtrenner; die Datei landet dadurch als relativer, verschachtelter
    Pfad innerhalb des Zielverzeichnisses statt außerhalb.
    """
    archive = tmp_path / "boese.tar.gz"
    outside_target = tmp_path / "ausserhalb.txt"
    _make_archive(archive, {str(outside_target): b"boese"})
    dst_dir = tmp_path / "ziel"
    dst_dir.mkdir()

    action = UntarAction(str(archive), str(dst_dir))
    result = action.run()

    assert result == "finished"
    assert not outside_target.exists()
    landed = list(dst_dir.rglob("ausserhalb.txt"))
    assert len(landed) == 1
    assert landed[0].is_relative_to(dst_dir)


def test_untar_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert UntarAction.PARAMS == ["src", "dst_dir", "overwrite"]
