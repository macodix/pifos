"""Smoke-Tests für pifos.module."""

import pytest
from pifos.module import Module


def test_module_is_abstract() -> None:
    """Module kann nicht direkt instanziiert werden."""
    with pytest.raises(TypeError):
        Module()  # type: ignore[abstract, call-arg]


def test_concrete_module_requires_start() -> None:
    """Eine konkrete Module-Unterklasse muss start() implementieren."""
    from multiprocessing.connection import Connection
    from unittest.mock import MagicMock

    from pifos.ipc import LogLevel

    class ConcreteModule(Module):
        def start(self) -> int:
            return 0

    conn = MagicMock(spec=Connection)
    mod = ConcreteModule(conn=conn, loglevel=LogLevel.INFO)
    assert mod.start() == 0


def test_module_check_returns_none_by_default() -> None:
    """check() gibt None zurück, wenn nicht überschrieben."""
    from unittest.mock import MagicMock

    from pifos.ipc import LogLevel
    from pifos.module import Module

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    mod = SimpleModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    assert mod.check() is None


def test_module_rollback_returns_none_by_default() -> None:
    """rollback() gibt None zurück, wenn nicht überschrieben."""
    from unittest.mock import MagicMock

    from pifos.ipc import LogLevel

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    mod = SimpleModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    assert mod.rollback() is None


def test_module_config_class_attribute() -> None:
    """CONFIG ist standardmäßig eine leere Liste."""
    assert Module.CONFIG == []


def test_module_check_config_sets_attributes() -> None:
    """check_config legt Konfigurationswerte als Instanzvariablen ab."""
    from typing import ClassVar
    from unittest.mock import MagicMock

    from pifos.config import Config
    from pifos.ipc import LogLevel

    class ConfModule(Module):
        CONFIG: ClassVar[list[str]] = ["host", "port"]

        def start(self) -> int:
            return 0

    cfg = Config()
    cfg.load_dict({"host": "localhost", "port": 8080})
    mod = ConfModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    mod.check_config(cfg)
    assert mod.host == "localhost"  # type: ignore[attr-defined]
    assert mod.port == 8080  # type: ignore[attr-defined]


def test_module_check_config_missing_raises() -> None:
    """check_config wirft ConfigError, wenn ein Pflichtschlüssel fehlt."""
    from typing import ClassVar
    from unittest.mock import MagicMock

    from pifos.config import Config
    from pifos.errors import ConfigError
    from pifos.ipc import LogLevel

    class StrictModule(Module):
        CONFIG: ClassVar[list[str]] = ["required_key"]

        def start(self) -> int:
            return 0

    cfg = Config()
    cfg.load_dict({})
    mod = StrictModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    with pytest.raises(ConfigError):
        mod.check_config(cfg)


def test_module_run_action_returns_zero_on_success() -> None:
    """run_action gibt 0 zurück, wenn die Aktion finished meldet."""
    from unittest.mock import MagicMock

    from pifos.action import Action
    from pifos.ipc import LogLevel

    class OkAction(Action):
        def run(self) -> str:
            self.status = "finished"
            return self.status

    class SimpleModule(Module):
        def start(self) -> int:
            return self.run_action(OkAction())

    mod = SimpleModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    assert mod.start() == 0


def test_module_run_action_reports_error_detail_on_failure() -> None:
    """run_action meldet bei ActionError Returncode und stderr als ERROR."""
    from unittest.mock import MagicMock

    from pifos.action import Action
    from pifos.errors import ActionError
    from pifos.ipc import LogLevel

    class FailingAction(Action):
        returncode = 3
        stderr = "boom"

        def run(self) -> str:
            self.status = "failed"
            raise ActionError(
                f"Befehl endete mit Code {self.returncode}; stderr: {self.stderr!r}"
            )

    class SimpleModule(Module):
        def start(self) -> int:
            return self.run_action(FailingAction())

    conn = MagicMock()
    mod = SimpleModule(conn=conn, loglevel=LogLevel.INFO)

    assert mod.start() == 1
    errors = [
        c.args[0] for c in conn.send.call_args_list if c.args[0].level == LogLevel.ERROR
    ]
    assert errors, "keine ERROR-Meldung gesendet"
    text = str(errors[-1].payload)
    assert "3" in text
    assert "boom" in text


def test_module_run_action_reports_detail_when_status_not_finished() -> None:
    """run_action meldet auch ohne Ausnahme bei nicht-fertigem Status die Werte."""
    from unittest.mock import MagicMock

    from pifos.action import Action
    from pifos.ipc import LogLevel

    class NotFinishedAction(Action):
        returncode = 7
        stderr = "kaputt"

        def run(self) -> str:
            self.status = "failed"
            return self.status

    class SimpleModule(Module):
        def start(self) -> int:
            return self.run_action(NotFinishedAction())

    conn = MagicMock()
    mod = SimpleModule(conn=conn, loglevel=LogLevel.INFO)

    assert mod.start() == 1
    errors = [
        c.args[0] for c in conn.send.call_args_list if c.args[0].level == LogLevel.ERROR
    ]
    assert errors, "keine ERROR-Meldung gesendet"
    text = str(errors[-1].payload)
    assert "7" in text
    assert "kaputt" in text


def test_module_control_action_sets_attribute() -> None:
    """control_action setzt Attribute auf der Aktion."""
    from unittest.mock import MagicMock

    from pifos.action import Action
    from pifos.ipc import LogLevel

    class TweakableAction(Action):
        def run(self) -> str:
            self.status = "finished"
            return self.status

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    mod = SimpleModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    action = TweakableAction()
    mod.control_action(action, custom_param="hello")
    assert action.custom_param == "hello"  # type: ignore[attr-defined]


def test_module_name_for_maps_camel_to_snake() -> None:
    """Der Modulname wird korrekt aus dem CamelCase-Klassennamen gebildet."""
    from pifos.module import _module_name_for

    assert _module_name_for("SysCmdAction") == "sys_cmd_action"
    assert _module_name_for("CopyFileAction") == "copy_file_action"
    assert _module_name_for("HTTPServerAction") == "http_server_action"


def test_module_resolve_action_finds_existing_actions() -> None:
    """resolve_action liefert die vorhandenen Aktionsklassen anhand des Namens."""
    from unittest.mock import MagicMock

    from pifos.actions.copy_file_action import CopyFileAction
    from pifos.actions.sys_cmd_action import SysCmdAction
    from pifos.ipc import LogLevel

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    mod = SimpleModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    assert mod.resolve_action("SysCmdAction") is SysCmdAction
    assert mod.resolve_action("CopyFileAction") is CopyFileAction


def test_module_resolve_action_unknown_raises() -> None:
    """Eine unbekannte Aktion führt zu ModuleError."""
    from unittest.mock import MagicMock

    from pifos.errors import ModuleError
    from pifos.ipc import LogLevel

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    mod = SimpleModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    with pytest.raises(ModuleError):
        mod.resolve_action("NichtVorhandenAction")


def test_module_resolve_action_non_action_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Name, der auf keine Action-Unterklasse zeigt, führt zu ModuleError."""
    import sys
    import types
    from unittest.mock import MagicMock

    from pifos.errors import ModuleError
    from pifos.ipc import LogLevel

    fake = types.ModuleType("pifos.actions.fake_thing")

    class FakeThing:  # keine Action-Unterklasse
        pass

    fake.FakeThing = FakeThing  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pifos.actions.fake_thing", fake)

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    mod = SimpleModule(conn=MagicMock(), loglevel=LogLevel.INFO)
    with pytest.raises(ModuleError):
        mod.resolve_action("FakeThing")


def test_module_send_message_filters_below_loglevel() -> None:
    """send_message unterdrückt Meldungen unterhalb der eingestellten Stufe (LOG-02)."""
    from unittest.mock import MagicMock

    from pifos.ipc import LogLevel

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    conn = MagicMock()
    mod = SimpleModule(conn=conn, loglevel=LogLevel.WARN)
    mod.send_message(LogLevel.INFO, "unter_schwelle", None)
    conn.send.assert_not_called()


def test_module_send_message_sends_at_or_above_loglevel() -> None:
    """send_message sendet Meldungen auf oder über der Schwelle (LOG-02, LOG-03)."""
    from unittest.mock import MagicMock

    from pifos.ipc import LogLevel, MessageKind

    class SimpleModule(Module):
        def start(self) -> int:
            return 0

    conn = MagicMock()
    mod = SimpleModule(conn=conn, loglevel=LogLevel.WARN)
    mod.send_message(LogLevel.WARN, "auf_schwelle", "details")
    conn.send.assert_called_once()
    msg = conn.send.call_args.args[0]
    assert msg.kind == MessageKind.LOG
    assert msg.level == LogLevel.WARN
    assert msg.name == "auf_schwelle"
