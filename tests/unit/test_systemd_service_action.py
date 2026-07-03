"""Tests für pifos.actions.systemd_service_action.

Kein echter systemctl-Aufruf: subprocess.Popen wird gemockt, um
Kommandoaufbau und Fehlerpfade ohne Systemveränderung zu prüfen.
"""

from types import TracebackType
from typing import ClassVar

import pytest
from pifos.actions.systemd_service_action import SystemdServiceAction
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


def test_systemd_service_action_start_command_and_env() -> None:
    """start baut ein Kommando mit -- vor der Einheit und kontrolliertem env."""
    _FakePopen.stdout_to_report = b"gestartet\n"

    action = SystemdServiceAction("start", unit="nginx.service", timeout=30.0)
    result = action.run()

    assert result == "finished"
    assert action.status == "finished"
    assert _FakePopen.last_command == [
        "/usr/bin/systemctl",
        "--no-pager",
        "start",
        "--",
        "nginx.service",
    ]
    assert _FakePopen.last_env is not None
    assert _FakePopen.last_env["PATH"] == "/usr/sbin:/usr/bin:/sbin:/bin"
    assert _FakePopen.last_env["SYSTEMD_PAGER"] == ""
    assert action.stdout == "gestartet\n"
    assert action.returncode == 0


@pytest.mark.parametrize(
    "operation", ["enable", "disable", "start", "stop", "restart", "reload"]
)
def test_systemd_service_action_builds_command_per_operation(operation: str) -> None:
    """Jede unit-Operation baut das Kommando mit derselben Struktur."""
    action = SystemdServiceAction(operation, unit="nginx.service")
    action.run()

    assert _FakePopen.last_command == [
        "/usr/bin/systemctl",
        "--no-pager",
        operation,
        "--",
        "nginx.service",
    ]


def test_systemd_service_action_daemon_reload_without_unit() -> None:
    """daemon-reload baut ein Kommando ohne Einheit und ohne '--'."""
    action = SystemdServiceAction("daemon-reload")
    result = action.run()

    assert result == "finished"
    assert _FakePopen.last_command == [
        "/usr/bin/systemctl",
        "--no-pager",
        "daemon-reload",
    ]


def test_systemd_service_action_daemon_reload_with_unit_rejected() -> None:
    """unit bei daemon-reload ist unzulässig und erzeugt ActionError."""
    action = SystemdServiceAction("daemon-reload", unit="nginx.service")
    with pytest.raises(ActionError, match="nicht erlaubt"):
        action.run()
    assert action.status == "failed"


def test_systemd_service_action_missing_unit_rejected() -> None:
    """unit ist außer bei daemon-reload Pflicht."""
    action = SystemdServiceAction("start")
    with pytest.raises(ActionError, match="erforderlich"):
        action.run()
    assert action.status == "failed"


def test_systemd_service_action_unknown_operation_rejected() -> None:
    """Eine unbekannte operation erzeugt ActionError."""
    action = SystemdServiceAction("shutdown", unit="nginx.service")
    with pytest.raises(ActionError, match="Unbekannte operation"):
        action.run()
    assert action.status == "failed"


def test_systemd_service_action_unit_with_leading_dash_rejected() -> None:
    """Ein Einheitenname mit führendem '-' wird abgelehnt (Optionsinjektion)."""
    action = SystemdServiceAction("start", unit="--force")
    with pytest.raises(ActionError, match="als Option interpretierbar"):
        action.run()
    assert action.status == "failed"


def test_systemd_service_action_no_shell_used() -> None:
    """Die Einheit wird als Argumentliste übergeben, kein Shell-String."""
    action = SystemdServiceAction("start", unit="foo; rm -rf /")
    action.run()

    assert "foo; rm -rf /" in _FakePopen.last_command
    assert _FakePopen.last_command[0] == "/usr/bin/systemctl"


def test_systemd_service_action_failure_sets_status_and_propagates_output() -> None:
    """Returncode != 0 erzeugt ActionError; stdout/stderr/returncode bleiben gesetzt."""
    _FakePopen.returncode_to_report = 1
    _FakePopen.stdout_to_report = b""
    _FakePopen.stderr_to_report = b"Unit nginx.service not found.\n"

    action = SystemdServiceAction("start", unit="nginx.service")
    with pytest.raises(ActionError):
        action.run()

    assert action.status == "failed"
    assert action.returncode == 1
    assert action.stderr == "Unit nginx.service not found.\n"


def test_systemd_service_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert SystemdServiceAction.PARAMS == ["operation", "unit", "timeout"]
