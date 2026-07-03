"""Tests für pifos.configurator.

Nutzt einen gescripteten Prompter, der vorgegebene Antworten der Reihe nach
liefert, sodass die Dialoge deterministisch ohne questionary laufen. Eine
stumme rich.Console unterdrückt die Ausgabe.
"""

import argparse
import importlib.machinery
import importlib.util
import io
import logging
import stat
import sys
from pathlib import Path
from typing import ClassVar

import pytest
from pifos.configurator import (
    Configurator,
    _format_from_suffix,
    _load_module,
    _resolve_format,
    main,
    read_config_data,
    write_config_data,
)
from pifos.errors import ConfigError
from pifos.module import Module
from rich.console import Console

_BIN_PATH = Path(__file__).resolve().parents[2] / "bin" / "pifos-config"


def _load_bin_module() -> object:
    """Lädt bin/pifos-config als Modul (endungslos, daher mit explizitem Loader).

    Unterdrückt das Schreiben von .pyc-Bytecode: dieser würde als
    bin/__pycache__ entstehen und wildcard bin/* (ruff/mypy in make check)
    stören.
    """
    loader = importlib.machinery.SourceFileLoader("pifos_config_bin", str(_BIN_PATH))
    spec = importlib.util.spec_from_file_location(
        "pifos_config_bin", _BIN_PATH, loader=loader
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    original_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = original_dont_write_bytecode
    return module


class _StubConfigurator:
    """Ersetzt Configurator in main()-Tests; keine echten Dialoge nötig."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def edit(self, data: dict[str, object]) -> dict[str, object]:
        return data

    def build_free(
        self, existing: dict[str, object] | None = None
    ) -> dict[str, object]:
        return existing or {}

    def build_for_modules(
        self,
        modules: object,
        existing: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return existing or {}


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


# --- Formatableitung aus der Dateiendung ---


@pytest.mark.parametrize(
    ("path", "expected"),
    [("datei.ini", "ini"), ("datei.JSON", "json"), ("datei.Toml", "toml")],
)
def test_format_from_suffix_recognizes_all_three_case_insensitive(
    path: str, expected: str
) -> None:
    """Alle drei Endungen werden unabhängig von Groß-/Kleinschreibung erkannt."""
    assert _format_from_suffix(path) == expected


def test_format_from_suffix_unknown_extension_returns_none() -> None:
    """Eine unbekannte Endung liefert None."""
    assert _format_from_suffix("datei.xml") is None


def test_resolve_format_without_explicit_and_unknown_extension_raises() -> None:
    """Kein --format und keine ableitbare Endung erzeugen ConfigError."""
    with pytest.raises(ConfigError, match="Kein Format angegeben"):
        _resolve_format(None, "datei.xml")


def test_resolve_format_explicit_overrides_extension() -> None:
    """--format übersteuert eine abweichende Endung."""
    assert _resolve_format("json", "datei.ini") == "json"


# --- bin/pifos-config: Zieldatei positionsgebunden ---


def test_bin_pifos_config_target_is_positional_argument() -> None:
    """Die Zieldatei wird ohne --output, als positionsgebundenes Argument, gelesen."""
    parser = _load_bin_module().build_parser()  # type: ignore[attr-defined]

    args = parser.parse_args(["--edit", "quelle.ini", "ziel.ini"])

    assert args.target == "ziel.ini"
    assert args.edit == "quelle.ini"
    assert not hasattr(args, "output")


def test_bin_pifos_config_target_optional_with_edit() -> None:
    """Bei --edit bleibt target ohne Angabe None."""
    parser = _load_bin_module().build_parser()  # type: ignore[attr-defined]

    args = parser.parse_args(["--edit", "quelle.ini"])

    assert args.target is None


def test_bin_pifos_config_format_is_optional() -> None:
    """--format ist nicht mehr Pflicht (Ableitung aus der Endung möglich)."""
    parser = _load_bin_module().build_parser()  # type: ignore[attr-defined]

    args = parser.parse_args(["--edit", "quelle.ini"])

    assert args.format is None


# --- main(): Zieldatei-Auflösung ---


def test_main_edit_without_target_edits_in_place_with_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--edit ohne Ziel bearbeitet an Ort und Stelle; Sicherung ohne --overwrite."""
    path = tmp_path / "quelle.ini"
    write_config_data({"section": {"key": "alt"}}, "ini", str(path))
    monkeypatch.setattr("pifos.configurator.Configurator", _StubConfigurator)

    args = argparse.Namespace(
        module=None,
        edit=str(path),
        free=False,
        target=None,
        format=None,
        input_format=None,
        overwrite=False,
        backup_location=None,
    )

    result = main(args)

    assert result == 0
    backups = list(tmp_path.glob("quelle.ini.bak-*"))
    assert len(backups) == 1
    assert read_config_data(str(path), "ini") == {"section": {"key": "alt"}}


def test_main_edit_with_different_target_needs_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein abweichendes Ziel unterliegt weiter der bisherigen overwrite-Regel."""
    source = tmp_path / "quelle.ini"
    write_config_data({"section": {"key": "alt"}}, "ini", str(source))
    target = tmp_path / "ziel.ini"
    write_config_data({"section": {"key": "andere_datei"}}, "ini", str(target))
    monkeypatch.setattr("pifos.configurator.Configurator", _StubConfigurator)

    args = argparse.Namespace(
        module=None,
        edit=str(source),
        free=False,
        target=str(target),
        format=None,
        input_format=None,
        overwrite=False,
        backup_location=None,
    )

    result = main(args)

    assert result == 1


def test_main_module_without_target_reports_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--module ohne Zieldatei erzeugt eine Fehlermeldung und Exit-Code 1."""
    args = argparse.Namespace(
        module=["tests.integration.copy_file_module:CopyFileModule"],
        edit=None,
        free=False,
        target=None,
        format="json",
        input_format=None,
        overwrite=False,
        backup_location=None,
    )

    with caplog.at_level(logging.ERROR, logger="pifos.configurator"):
        result = main(args)

    assert result == 1
    assert "Zieldatei erforderlich" in caplog.text


def test_main_free_without_target_reports_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--free ohne Zieldatei erzeugt eine Fehlermeldung und Exit-Code 1."""
    args = argparse.Namespace(
        module=None,
        edit=None,
        free=True,
        target=None,
        format="json",
        input_format=None,
        overwrite=False,
        backup_location=None,
    )

    with caplog.at_level(logging.ERROR, logger="pifos.configurator"):
        result = main(args)

    assert result == 1
    assert "Zieldatei erforderlich" in caplog.text
