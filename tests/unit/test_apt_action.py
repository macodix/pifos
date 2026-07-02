"""Tests für pifos.actions.apt_action.

Kein echter apt-Aufruf: subprocess.Popen wird gemockt, um Kommandoaufbau
und Fehlerpfade ohne Systemveränderung zu prüfen.
"""

from types import TracebackType
from typing import ClassVar

import pytest
from pifos.actions.apt_action import AptAction
from pifos.errors import ActionError


class _FakePopen:
    """Ersetzt subprocess.Popen; zeichnet die Aufrufargumente auf."""

    last_command: ClassVar[list[str]] = []
    last_env: ClassVar[dict[str, str] | None] = None
    last_cwd: ClassVar[str | None] = None
    returncode_to_report: ClassVar[int] = 0
    stdout_to_report: ClassVar[bytes] = b""
    stderr_to_report: ClassVar[bytes] = b""

    def __init__(
        self,
        command: list[str],
        *,
        shell: bool,
        stdout: object,
        stderr: object,
        cwd: str | None,
        env: dict[str, str] | None,
    ) -> None:
        _FakePopen.last_command = command
        _FakePopen.last_env = env
        _FakePopen.last_cwd = cwd
        self.returncode = _FakePopen.returncode_to_report

    def __enter__(self) -> "_FakePopen":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
        return _FakePopen.stdout_to_report, _FakePopen.stderr_to_report

    def kill(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _patch_popen(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakePopen.returncode_to_report = 0
    _FakePopen.stdout_to_report = b""
    _FakePopen.stderr_to_report = b""
    monkeypatch.setattr("pifos.actions.sys_cmd_action.subprocess.Popen", _FakePopen)


def test_apt_action_install_command_and_env() -> None:
    """state=present baut ein install-Kommando mit kontrolliertem env."""
    _FakePopen.stdout_to_report = b"installiert\n"

    action = AptAction(["curl", "jq"], state="present", timeout=30.0)
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert _FakePopen.last_command == [
        "/usr/bin/apt-get",
        "install",
        "-y",
        "--",
        "curl",
        "jq",
    ]
    assert _FakePopen.last_env is not None
    assert _FakePopen.last_env["DEBIAN_FRONTEND"] == "noninteractive"
    assert _FakePopen.last_env["PATH"] == "/usr/sbin:/usr/bin:/sbin:/bin"
    assert action.stdout == "installiert\n"
    assert action.returncode == 0


def test_apt_action_absent_builds_remove_command() -> None:
    """state=absent baut ein remove-Kommando."""
    action = AptAction(["curl"], state="absent")
    action.run()

    assert _FakePopen.last_command == [
        "/usr/bin/apt-get",
        "remove",
        "-y",
        "--",
        "curl",
    ]


def test_apt_action_no_shell_used() -> None:
    """Pakete werden als Argumentliste übergeben, kein Shell-String."""
    action = AptAction(["paket; rm -rf /"], state="present")
    action.run()

    assert "paket; rm -rf /" in _FakePopen.last_command
    assert _FakePopen.last_command[0] == "/usr/bin/apt-get"


def test_apt_action_option_terminator_before_packages() -> None:
    """Der Optionsterminator '--' steht immer vor der Paketliste."""
    action = AptAction(["curl", "jq"], state="present")
    action.run()

    assert _FakePopen.last_command.index("--") == 3
    assert _FakePopen.last_command[4:] == ["curl", "jq"]


def test_apt_action_package_with_leading_dash_rejected() -> None:
    """Ein Paketname mit führendem '-' wird abgelehnt (Optionsinjektion)."""
    action = AptAction(["-foo"], state="present")
    with pytest.raises(ActionError, match="als Option interpretierbar"):
        action.run()
    assert action.status == "failed"


def test_apt_action_failure_sets_status_and_propagates_output() -> None:
    """Returncode != 0 erzeugt ActionError; stdout/stderr/returncode bleiben gesetzt."""
    _FakePopen.returncode_to_report = 1
    _FakePopen.stdout_to_report = b""
    _FakePopen.stderr_to_report = b"E: Unable to locate package\n"

    action = AptAction(["nicht-existent"], state="present")
    with pytest.raises(ActionError):
        action.run()

    assert action.status == "failed"
    assert action.returncode == 1
    assert action.stderr == "E: Unable to locate package\n"


def test_apt_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert AptAction.PARAMS == ["packages", "state", "timeout"]
