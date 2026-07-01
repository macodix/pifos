"""Tests für pifos.actions.sys_cmd_action."""

import sys
from pathlib import Path

import pytest
from pifos.actions.sys_cmd_action import SysCmdAction
from pifos.errors import ActionError


def test_sys_cmd_action_success() -> None:
    """Erfolgreicher Befehl setzt Status finished und füllt stdout."""
    action = SysCmdAction(
        [sys.executable, "-c", "print('hallo')"],
        timeout=10.0,
    )
    result = action.run()
    assert result == "finished"
    assert action.status == "finished"
    assert action.returncode == 0
    assert "hallo" in action.stdout


def test_sys_cmd_action_stderr_captured() -> None:
    """stderr wird erfasst und als Instanzvariable bereitgestellt."""
    action = SysCmdAction(
        [sys.executable, "-c", "import sys; sys.stderr.write('fehler\\n')"],
        timeout=10.0,
    )
    action.run()
    assert "fehler" in action.stderr


def test_sys_cmd_action_nonzero_returncode() -> None:
    """Rückgabewert != 0 erzeugt ActionError und setzt Status failed."""
    action = SysCmdAction(
        [sys.executable, "-c", "import sys; sys.exit(42)"],
        timeout=10.0,
    )
    with pytest.raises(ActionError):
        action.run()
    assert action.status == "failed"
    assert action.returncode == 42


def test_sys_cmd_action_timeout() -> None:
    """Ablauf der Zeitgrenze erzeugt ActionError und setzt Status failed."""
    action = SysCmdAction(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        timeout=0.1,
    )
    with pytest.raises(ActionError, match="Zeitgrenze"):
        action.run()
    assert action.status == "failed"


def test_sys_cmd_action_command_not_found() -> None:
    """Nicht vorhandener Befehl erzeugt ActionError."""
    action = SysCmdAction(
        ["/nonexistent/path/to/command"],
        timeout=5.0,
    )
    with pytest.raises(ActionError):
        action.run()
    assert action.status == "failed"


def test_sys_cmd_action_params() -> None:
    """PARAMS enthält die erwarteten Parameternamen."""
    assert SysCmdAction.PARAMS == ["command", "timeout", "cwd", "env"]


def test_sys_cmd_action_initial_state() -> None:
    """Vor run() sind stdout, stderr und returncode auf Initialwerte gesetzt."""
    action = SysCmdAction(["true"], timeout=5.0)
    assert action.status == "not_runned"
    assert action.stdout == ""
    assert action.stderr == ""
    assert action.returncode == -1


def test_sys_cmd_action_with_cwd(tmp_path: Path) -> None:
    """cwd wird an den Prozess weitergegeben."""
    action = SysCmdAction(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        timeout=10.0,
        cwd=str(tmp_path),
    )
    action.run()
    assert str(tmp_path) in action.stdout
