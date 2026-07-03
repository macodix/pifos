"""Tests für pifos.configurator.

Nutzt einen gescripteten Prompter, der vorgegebene Antworten der Reihe nach
liefert, sodass die Dialoge deterministisch ohne questionary laufen. Eine
stumme rich.Console unterdrückt die Ausgabe.
"""

import io
import stat
from pathlib import Path
from typing import ClassVar

import pytest
from pifos.configurator import (
    Configurator,
    _load_module,
    read_config_data,
    write_config_data,
)
from pifos.errors import ConfigError
from pifos.module import Module
from rich.console import Console


class ScriptedPrompter:
    """Prompter, der vorgegebene Antworten der Reihe nach liefert."""

    def __init__(self, texts: list[str], confirms: list[bool] | None = None) -> None:
        self._texts = list(texts)
        self._confirms = list(confirms or [])

    def text(self, message: str, default: str = "") -> str:
        return self._texts.pop(0)

    def confirm(self, message: str, default: bool = False) -> bool:
        return self._confirms.pop(0)


class _FirstModule(Module):
    """Erstes Testmodul für Configurator-Tests."""

    CONFIG: ClassVar[list[str]] = ["source_path", "target_path"]

    def start(self) -> int:
        return 0


class _SecondModule(Module):
    """Zweites Testmodul für Configurator-Tests."""

    CONFIG: ClassVar[list[str]] = ["report_path"]

    def start(self) -> int:
        return 0


def _configurator(prompter: ScriptedPrompter) -> Configurator:
    return Configurator(prompter, Console(file=io.StringIO()))


# --- Configurator.build_for_module ---


def test_build_for_module_asks_all_config_names() -> None:
    """Alle CONFIG-Namen werden abgefragt und im Abschnitt abgelegt."""
    configurator = _configurator(ScriptedPrompter(["/pfad/quelle", "/pfad/ziel"]))

    section = configurator.build_for_module(_FirstModule)

    assert section == {
        "source_path": "/pfad/quelle",
        "target_path": "/pfad/ziel",
    }


def test_build_for_module_uses_existing_value_without_asking() -> None:
    """Ein in existing vorhandener Wert wird ohne erneute Frage übernommen."""
    configurator = _configurator(ScriptedPrompter(["/pfad/quelle"]))

    section = configurator.build_for_module(
        _FirstModule, existing={"target_path": "/pfad/ziel"}
    )

    assert section == {
        "source_path": "/pfad/quelle",
        "target_path": "/pfad/ziel",
    }


# --- Configurator.build_for_modules ---


def test_build_for_modules_creates_one_section_per_module() -> None:
    """build_for_modules mit mehreren Modulen ergibt einen Abschnitt je Modul."""
    configurator = _configurator(ScriptedPrompter(["quelle", "ziel", "bericht"]))

    result = configurator.build_for_modules([_FirstModule, _SecondModule])

    assert result == {
        "_FirstModule": {"source_path": "quelle", "target_path": "ziel"},
        "_SecondModule": {"report_path": "bericht"},
    }


# --- Configurator.edit ---


def test_edit_applies_changes_and_adds_key_and_section() -> None:
    """edit übernimmt geänderte Werte und legt neuen Schlüssel/Abschnitt an."""
    configurator = _configurator(
        ScriptedPrompter(
            texts=[
                "neu1",
                "neu2",
                "key3",
                "wert3",
                "section_b",
                "keyX",
                "wertX",
            ],
            confirms=[True, False, True, True, False, False],
        )
    )
    data: dict[str, object] = {
        "section_a": {"key1": "alt1", "key2": "alt2"},
    }

    result = configurator.edit(data)

    assert result == {
        "section_a": {"key1": "neu1", "key2": "neu2", "key3": "wert3"},
        "section_b": {"keyX": "wertX"},
    }


# --- Configurator.build_free ---


def test_build_free_follows_script() -> None:
    """build_free legt Abschnitte und Schlüssel/Werte nach Skript an."""
    configurator = _configurator(
        ScriptedPrompter(
            texts=["section_a", "key1", "wert1", "key2", "wert2"],
            confirms=[True, True, True, False, False],
        )
    )

    result = configurator.build_free()

    assert result == {"section_a": {"key1": "wert1", "key2": "wert2"}}


# --- write_config_data ---


def test_write_config_data_creates_file_with_mode_0600(tmp_path: Path) -> None:
    """Die Zieldatei entsteht mit den Rechten 0600."""
    target = tmp_path / "out.json"

    write_config_data({"section": {"key": "value"}}, "json", str(target))

    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_write_config_data_existing_without_overwrite_raises(
    tmp_path: Path,
) -> None:
    """Ohne overwrite löst eine bestehende Zieldatei ConfigError aus."""
    target = tmp_path / "out.json"
    target.write_text("{}", encoding="utf-8")

    with pytest.raises(ConfigError, match="existiert bereits"):
        write_config_data({"section": {"key": "value"}}, "json", str(target))


def test_write_config_data_overwrite_creates_backup(tmp_path: Path) -> None:
    """Mit overwrite entsteht eine Sicherung der bestehenden Zieldatei."""
    target = tmp_path / "out.json"
    target.write_text('{"alt": true}', encoding="utf-8")

    write_config_data(
        {"section": {"key": "value"}}, "json", str(target), overwrite=True
    )

    backups = list(tmp_path.glob("out.json.bak-*"))
    assert len(backups) == 1


def test_write_config_data_unknown_format_raises(tmp_path: Path) -> None:
    """Ein unbekanntes Format löst ConfigError aus."""
    with pytest.raises(ConfigError, match="Unbekanntes Konfigurationsformat"):
        write_config_data({}, "xml", str(tmp_path / "out.xml"))


def test_write_config_data_sectionless_value_in_ini_raises(
    tmp_path: Path,
) -> None:
    """Ein abschnittsloser Wert im ini-Format löst ConfigError aus."""
    with pytest.raises(ConfigError, match="abschnittslosen Wert"):
        write_config_data({"lonely": "value"}, "ini", str(tmp_path / "out.ini"))


# --- read_config_data ---


@pytest.mark.parametrize("fmt", ["ini", "json", "toml"])
def test_read_config_data_round_trip(tmp_path: Path, fmt: str) -> None:
    """Das gelesene dict entspricht dem geschriebenen, je Format."""
    data: dict[str, object] = {"section": {"key": "value"}}
    path = tmp_path / f"out.{fmt}"
    write_config_data(data, fmt, str(path))

    result = read_config_data(str(path), fmt)

    assert result == data


# --- _load_module ---


def test_load_module_valid_path_returns_class() -> None:
    """Ein gültiger Pfad liefert Klassenname und Klasse."""
    name, cls = _load_module("tests.integration.copy_file_module:CopyFileModule")

    assert name == "CopyFileModule"
    assert cls.__name__ == "CopyFileModule"
    assert issubclass(cls, Module)


def test_load_module_non_module_class_raises() -> None:
    """Eine Klasse, die nicht von Module erbt, löst ConfigError aus."""
    with pytest.raises(ConfigError, match="keine Module-Unterklasse"):
        _load_module("pathlib:Path")


def test_load_module_invalid_spec_raises() -> None:
    """Ein Pfad ohne Modul- und Klassenanteil löst ConfigError aus."""
    with pytest.raises(ConfigError, match="Ungültiger Modulpfad"):
        _load_module("keinpunktkeindoppelpunkt")


def test_load_module_import_error_raises() -> None:
    """Ein Modul, dessen Import scheitert, löst ConfigError aus."""
    with pytest.raises(ConfigError, match="nicht ladbar"):
        _load_module("pifos.nonexistent_module_xyz:Something")
