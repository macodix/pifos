"""Tests für pifos.actions.permissions_action."""

import stat
from pathlib import Path

import pytest
from pifos.actions.permissions_action import PermissionsAction
from pifos.errors import ActionError


def test_permissions_action_sets_mode(tmp_path: Path) -> None:
    """mode wird auf einer bestehenden Datei gesetzt."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")
    path.chmod(0o644)

    action = PermissionsAction(str(path), mode=0o600)
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_permissions_action_sets_mode_on_directory(tmp_path: Path) -> None:
    """mode wird auf einem bestehenden Verzeichnis gesetzt."""
    path = tmp_path / "verzeichnis"
    path.mkdir(mode=0o755)

    action = PermissionsAction(str(path), mode=0o700)
    action.run()

    assert stat.S_IMODE(path.stat().st_mode) == 0o700


def test_permissions_action_owner_by_name_resolved_via_pwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """owner als Name wird über pwd.getpwnam aufgelöst und an fchown übergeben."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    calls: list[tuple[int, int, int]] = []

    class _FakePwEntry:
        pw_uid = 4242

    def fake_getpwnam(name: str) -> _FakePwEntry:
        assert name == "pifosuser"
        return _FakePwEntry()

    def fake_fchown(fd: int, uid: int, gid: int) -> None:
        calls.append((fd, uid, gid))

    monkeypatch.setattr("pifos.actions.permissions_action.pwd.getpwnam", fake_getpwnam)
    monkeypatch.setattr("pifos.actions.permissions_action.os.fchown", fake_fchown)

    action = PermissionsAction(str(path), owner="pifosuser")
    result = action.run()

    assert result == "finished"
    assert len(calls) == 1
    fd, uid, gid = calls[0]
    assert isinstance(fd, int)
    assert (uid, gid) == (4242, -1)


def test_permissions_action_group_by_name_resolved_via_grp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """group als Name wird über grp.getgrnam aufgelöst und an fchown übergeben."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    calls: list[tuple[int, int, int]] = []

    class _FakeGrEntry:
        gr_gid = 4343

    def fake_getgrnam(name: str) -> _FakeGrEntry:
        assert name == "pifosgroup"
        return _FakeGrEntry()

    def fake_fchown(fd: int, uid: int, gid: int) -> None:
        calls.append((fd, uid, gid))

    monkeypatch.setattr("pifos.actions.permissions_action.grp.getgrnam", fake_getgrnam)
    monkeypatch.setattr("pifos.actions.permissions_action.os.fchown", fake_fchown)

    action = PermissionsAction(str(path), group="pifosgroup")
    action.run()

    assert len(calls) == 1
    fd, uid, gid = calls[0]
    assert isinstance(fd, int)
    assert (uid, gid) == (-1, 4343)


def test_permissions_action_owner_as_uid_skips_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """owner als int wird direkt als UID verwendet, keine pwd-Auflösung nötig."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    calls: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        "pifos.actions.permissions_action.os.fchown",
        lambda fd, u, g: calls.append((fd, u, g)),
    )

    action = PermissionsAction(str(path), owner=1000, group=1000)
    action.run()

    assert len(calls) == 1
    fd, uid, gid = calls[0]
    assert isinstance(fd, int)
    assert (uid, gid) == (1000, 1000)


def test_permissions_action_mode_and_owner_use_same_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mode und owner/group laufen über denselben O_NOFOLLOW-Deskriptor."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    fchown_fds: list[int] = []
    fchmod_fds: list[int] = []
    monkeypatch.setattr(
        "pifos.actions.permissions_action.os.fchown",
        lambda fd, u, g: fchown_fds.append(fd),
    )
    monkeypatch.setattr(
        "pifos.actions.permissions_action.os.fchmod",
        lambda fd, m: fchmod_fds.append(fd),
    )

    action = PermissionsAction(str(path), mode=0o600, owner=1000)
    action.run()

    assert len(fchown_fds) == 1
    assert len(fchmod_fds) == 1
    assert fchown_fds[0] == fchmod_fds[0]


def test_permissions_action_unknown_owner_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein unbekannter Benutzername erzeugt ActionError."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    def fake_getpwnam(name: str) -> None:
        raise KeyError(name)

    monkeypatch.setattr("pifos.actions.permissions_action.pwd.getpwnam", fake_getpwnam)

    action = PermissionsAction(str(path), owner="unbekannt")
    with pytest.raises(ActionError, match="Unbekannter Benutzer"):
        action.run()
    assert action.status == "failed"


def test_permissions_action_unknown_group_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine unbekannte Gruppe erzeugt ActionError."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    def fake_getgrnam(name: str) -> None:
        raise KeyError(name)

    monkeypatch.setattr("pifos.actions.permissions_action.grp.getgrnam", fake_getgrnam)

    action = PermissionsAction(str(path), group="unbekannt")
    with pytest.raises(ActionError, match="Unbekannte Gruppe"):
        action.run()
    assert action.status == "failed"


def test_permissions_action_nothing_set_raises(tmp_path: Path) -> None:
    """Ohne mode, owner und group wird ActionError erzeugt."""
    path = tmp_path / "datei.txt"
    path.write_text("inhalt", encoding="utf-8")

    action = PermissionsAction(str(path))
    with pytest.raises(ActionError, match="Mindestens einer von"):
        action.run()
    assert action.status == "failed"


def test_permissions_action_missing_path_raises() -> None:
    """Fehlender Pfad erzeugt ActionError."""
    action = PermissionsAction("/nicht/vorhanden/datei.txt", mode=0o600)
    with pytest.raises(ActionError, match="Pfad nicht gefunden"):
        action.run()
    assert action.status == "failed"


def test_permissions_action_symlink_mode_rejected(tmp_path: Path) -> None:
    """Ein Symlink als path kann nicht ohne Symlink-Folgen geöffnet werden."""
    real_target = tmp_path / "echte_datei.txt"
    real_target.write_text("inhalt", encoding="utf-8")
    real_target.chmod(0o644)
    link = tmp_path / "link.txt"
    link.symlink_to(real_target)

    action = PermissionsAction(str(link), mode=0o600)
    with pytest.raises(ActionError, match="ohne Symlink-Folgen"):
        action.run()

    assert action.status == "failed"
    assert stat.S_IMODE(real_target.stat().st_mode) == 0o644


def test_permissions_action_symlink_owner_rejected(tmp_path: Path) -> None:
    """Ein Symlink als path wird auch bei reiner Eigentümeränderung abgelehnt."""
    real_target = tmp_path / "echte_datei.txt"
    real_target.write_text("inhalt", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real_target)

    action = PermissionsAction(str(link), owner=1000)
    with pytest.raises(ActionError, match="ohne Symlink-Folgen"):
        action.run()

    assert action.status == "failed"


def test_permissions_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert PermissionsAction.PARAMS == ["path", "mode", "owner", "group"]
