"""Tests für pifos.actions.remote_copy_action."""

from pathlib import Path

import pytest
from pifos.actions.remote_copy_action import RemoteCopyAction
from pifos.errors import ActionError


def _fake_tool(
    tmp_path: Path,
    args_out: Path,
    exit_code: int = 0,
    stderr_text: str = "",
) -> str:
    """Legt ein Fake-Kopierprogramm an, das argv festhält und exit_code liefert."""
    lines = ["#!/bin/sh", f'printf "%s\\n" "$@" > "{args_out}"']
    if stderr_text:
        lines.append(f'printf "%s" "{stderr_text}" >&2')
    lines.append(f"exit {exit_code}")
    script = tmp_path / "fake-tool"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


# --- scp ---


def test_scp_upload_command(tmp_path: Path) -> None:
    """scp-Upload: -P/-i/-r, '--', lokale Quelle und user@host:ziel."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction(
        "scp",
        ["/local/file"],
        "/remote/dir",
        "host.example.org",
        user="deploy",
        port=2222,
        identity_file="/k/id",
        recursive=True,
        binary=binp,
        timeout=10.0,
    )
    assert action.run() == "finished"
    assert action.returncode == 0
    argv = args.read_text(encoding="utf-8").splitlines()
    assert "-P" in argv
    assert "2222" in argv
    assert "-i" in argv
    assert "/k/id" in argv
    assert "-r" in argv
    assert "--" in argv
    assert "/local/file" in argv
    assert "deploy@host.example.org:/remote/dir" in argv


def test_scp_download_command(tmp_path: Path) -> None:
    """scp-Download: user@host:quelle vor lokalem Ziel."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction(
        "scp",
        ["/remote/file"],
        "/local/dir",
        "host.example.org",
        user="u",
        direction="download",
        binary=binp,
        timeout=10.0,
    )
    action.run()
    argv = args.read_text(encoding="utf-8").splitlines()
    assert "u@host.example.org:/remote/file" in argv
    assert "/local/dir" in argv
    assert argv.index("u@host.example.org:/remote/file") < argv.index("/local/dir")


# --- rsync ---


def test_rsync_upload_with_ssh_transport(tmp_path: Path) -> None:
    """rsync-Upload: -e 'ssh -p PORT -i KEY' als ein Argument, -r, Pfade."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction(
        "rsync",
        ["/l/f"],
        "/r/d",
        "host.example.org",
        user="u",
        port=2222,
        identity_file="/k",
        recursive=True,
        binary=binp,
        timeout=10.0,
    )
    action.run()
    argv = args.read_text(encoding="utf-8").splitlines()
    assert "-e" in argv
    assert argv[argv.index("-e") + 1] == "ssh -p 2222 -i /k"
    assert "-r" in argv
    assert "/l/f" in argv
    assert "u@host.example.org:/r/d" in argv


def test_rsync_no_port_no_identity_has_no_transport(tmp_path: Path) -> None:
    """Ohne port/identity setzt rsync kein -e; ohne user kein user@-Präfix."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction(
        "rsync", ["/l/f"], "/r/d", "host.example.org", binary=binp, timeout=10.0
    )
    action.run()
    argv = args.read_text(encoding="utf-8").splitlines()
    assert "-e" not in argv
    assert "host.example.org:/r/d" in argv


def test_extra_options_passed(tmp_path: Path) -> None:
    """Zusätzliche Werkzeugoptionen aus der Konfiguration landen im Aufruf."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction(
        "rsync",
        ["/l/f"],
        "/r/d",
        "host.example.org",
        extra_options=["-a", "--delete"],
        binary=binp,
        timeout=10.0,
    )
    action.run()
    argv = args.read_text(encoding="utf-8").splitlines()
    assert "-a" in argv
    assert "--delete" in argv


# --- Fehler / Schutz ---


def test_binary_missing(tmp_path: Path) -> None:
    """Fehlendes Programm erzeugt ActionError (keine Installation)."""
    action = RemoteCopyAction(
        "scp", ["/l/f"], "/r/d", "host", binary=str(tmp_path / "nicht-da")
    )
    with pytest.raises(ActionError, match="nicht vorhanden"):
        action.run()
    assert action.status == "failed"


def test_nonzero_raises(tmp_path: Path) -> None:
    """Rückgabewert != 0 erzeugt ActionError, Status failed, stderr erfasst."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args, exit_code=23, stderr_text="rsync error")
    action = RemoteCopyAction(
        "rsync", ["/l/f"], "/r/d", "host", binary=binp, timeout=10.0
    )
    with pytest.raises(ActionError):
        action.run()
    assert action.status == "failed"
    assert action.returncode == 23
    assert "rsync error" in action.stderr


def test_unknown_tool(tmp_path: Path) -> None:
    """Unbekanntes tool erzeugt ActionError."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction("ftp", ["/l/f"], "/r/d", "host", binary=binp)
    with pytest.raises(ActionError, match="unbekanntes tool"):
        action.run()
    assert action.status == "failed"


def test_unknown_direction(tmp_path: Path) -> None:
    """Unbekannte direction erzeugt ActionError."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction(
        "scp", ["/l/f"], "/r/d", "host", direction="seitwaerts", binary=binp
    )
    with pytest.raises(ActionError, match="direction"):
        action.run()
    assert action.status == "failed"


def test_rejects_option_like_source(tmp_path: Path) -> None:
    """Quelle mit führendem '-' (Options-Injektion) erzeugt ActionError."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction("scp", ["-rf"], "/r/d", "host", binary=binp)
    with pytest.raises(ActionError, match="beginnen"):
        action.run()
    assert action.status == "failed"


def test_rejects_newline_in_host(tmp_path: Path) -> None:
    """Zeilenumbruch im Host erzeugt ActionError."""
    args = tmp_path / "argv.txt"
    binp = _fake_tool(tmp_path, args)
    action = RemoteCopyAction("scp", ["/l/f"], "/r/d", "host\nevil", binary=binp)
    with pytest.raises(ActionError, match="Zeilenumbruch"):
        action.run()
    assert action.status == "failed"
