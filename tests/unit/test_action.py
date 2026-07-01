"""Smoke-Tests für pifos.action."""

import pytest
from pifos.action import Action
from pifos.errors import ActionError


def test_action_is_abstract() -> None:
    """Action kann nicht direkt instanziiert werden."""
    with pytest.raises(TypeError):
        Action()  # type: ignore[abstract]


def test_concrete_action_initial_status() -> None:
    """Eine konkrete Aktion hat den Anfangsstatus not_runned."""

    class NullAction(Action):
        def run(self) -> str:
            self.status = "finished"
            return self.status

    action = NullAction()
    assert action.status == "not_runned"


def test_concrete_action_run_returns_status() -> None:
    """run() gibt den gesetzten Status zurück."""

    class NullAction(Action):
        def run(self) -> str:
            self.status = "finished"
            return self.status

    action = NullAction()
    result = action.run()
    assert result == "finished"
    assert action.status == "finished"


def test_action_failed_status() -> None:
    """Eine fehlerhafte Aktion setzt Status auf failed und wirft ActionError."""

    class FailAction(Action):
        def run(self) -> str:
            self.status = "running"
            self.status = "failed"
            raise ActionError("absichtlicher Fehler")

    action = FailAction()
    with pytest.raises(ActionError):
        action.run()
    assert action.status == "failed"


def test_action_params_default_empty() -> None:
    """PARAMS ist standardmäßig eine leere Liste."""

    class SimpleAction(Action):
        def run(self) -> str:
            self.status = "finished"
            return self.status

    assert SimpleAction.PARAMS == []


def test_action_params_can_be_declared() -> None:
    """Konkrete Aktionen können PARAMS deklarieren."""

    from typing import ClassVar

    class ParamAction(Action):
        PARAMS: ClassVar[list[str]] = ["src", "dst"]

        def run(self) -> str:
            self.status = "finished"
            return self.status

    assert ParamAction.PARAMS == ["src", "dst"]
