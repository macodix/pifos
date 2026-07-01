"""Smoke-Tests für pifos.errors."""

import pytest
from pifos.errors import ActionError, ConfigError, ModuleError, PifosError


def test_pifos_error_is_exception() -> None:
    """PifosError ist eine Unterklasse von Exception."""
    assert issubclass(PifosError, Exception)


def test_action_error_inherits_pifos_error() -> None:
    """ActionError leitet von PifosError ab."""
    assert issubclass(ActionError, PifosError)


def test_module_error_inherits_pifos_error() -> None:
    """ModuleError leitet von PifosError ab."""
    assert issubclass(ModuleError, PifosError)


def test_config_error_inherits_pifos_error() -> None:
    """ConfigError leitet von PifosError ab."""
    assert issubclass(ConfigError, PifosError)


def test_action_error_can_be_raised() -> None:
    """ActionError lässt sich werfen und fangen."""
    with pytest.raises(ActionError, match="test"):
        raise ActionError("test")


def test_module_error_can_be_raised() -> None:
    """ModuleError lässt sich werfen und fangen."""
    with pytest.raises(ModuleError):
        raise ModuleError("modul fehler")


def test_config_error_can_be_raised() -> None:
    """ConfigError lässt sich werfen und fangen."""
    with pytest.raises(ConfigError):
        raise ConfigError("konfig fehler")


def test_pifos_error_caught_as_pifos_error() -> None:
    """ActionError wird als PifosError gefangen."""
    with pytest.raises(PifosError):
        raise ActionError("catch as PifosError")
