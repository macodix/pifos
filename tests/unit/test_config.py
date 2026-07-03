"""Smoke-Tests für pifos.config."""

import json

import pytest
from pifos.config import Config, IniConfig, JsonConfig, TomlConfig
from pifos.errors import ConfigError

# --- Config ---


def test_config_load_dict() -> None:
    """Config nimmt ein dict per load_dict auf."""
    cfg = Config()
    cfg.load_dict({"key": "value"})
    assert cfg.get_value("key") == "value"


def test_config_get_value_missing_raises() -> None:
    """get_value wirft ConfigError für fehlende Schlüssel."""
    cfg = Config()
    with pytest.raises(ConfigError):
        cfg.get_value("nope")


def test_config_load_raw() -> None:
    """load_raw speichert den Rohinhalt ohne Zerlegung."""
    cfg = Config()
    cfg.load_raw("raw content")
    # _data bleibt leer; Zugriff führt zu ConfigError
    with pytest.raises(ConfigError):
        cfg.get_value("anything")


def test_config_get_section_dict() -> None:
    """get_section gibt ein dict zurück, wenn der Wert ein dict ist."""
    cfg = Config()
    cfg.load_dict({"section": {"k": "v"}})
    sec = cfg.get_section("section")
    assert isinstance(sec, dict)
    assert sec["k"] == "v"


def test_config_get_list() -> None:
    """get_list gibt eine Liste zurück."""
    cfg = Config()
    cfg.load_dict({"items": ["b", "a", "c"]})
    lst = cfg.get_list("items")
    assert lst == ["b", "a", "c"]


def test_config_get_list_sorted() -> None:
    """get_list mit sort=True sortiert die Liste."""
    cfg = Config()
    cfg.load_dict({"items": ["b", "a", "c"]})
    lst = cfg.get_list("items", sort=True)
    assert lst == ["a", "b", "c"]


def test_config_check_pattern_exists() -> None:
    """check_pattern 'exists' erkennt vorhandene und fehlende Werte."""
    cfg = Config()
    assert cfg.check_pattern("exists", "something") is True
    assert cfg.check_pattern("exists", None) is False


def test_config_check_pattern_is_number() -> None:
    """check_pattern 'is_number' erkennt Zahlen."""
    cfg = Config()
    assert cfg.check_pattern("is_number", 42) is True
    assert cfg.check_pattern("is_number", "3.14") is True
    assert cfg.check_pattern("is_number", "no") is False


def test_config_check_pattern_is_email() -> None:
    """check_pattern 'is_email' erkennt syntaktisch gültige Adressen."""
    cfg = Config()
    assert cfg.check_pattern("is_email", "user@example.com") is True
    assert cfg.check_pattern("is_email", "kein-at") is False


def test_config_check_pattern_unknown_raises() -> None:
    """check_pattern wirft ConfigError bei unbekanntem Muster."""
    cfg = Config()
    with pytest.raises(ConfigError):
        cfg.check_pattern("unknown_pattern", "val")


def test_config_to_dict_returns_copy() -> None:
    """to_dict liefert den geladenen Inhalt und eine Kopie."""
    cfg = Config()
    cfg.load_dict({"section": {"key": "value"}})

    result = cfg.to_dict()

    assert result == {"section": {"key": "value"}}
    result["section"] = {"key": "geändert"}
    assert cfg.get_value("section") == {"key": "value"}


# --- IniConfig ---


def test_ini_config_to_dict(tmp_path: pytest.TempPathFactory) -> None:
    """IniConfig liest eine INI-Datei und gibt ein dict zurück."""
    ini_file = tmp_path / "test.ini"  # type: ignore[operator]
    ini_file.write_text("[section]\nkey = value\n", encoding="utf-8")
    cfg = IniConfig(str(ini_file))
    d = cfg.to_dict()
    assert "section" in d
    section = d["section"]
    assert isinstance(section, dict)
    assert section["key"] == "value"


def test_ini_config_raw(tmp_path: pytest.TempPathFactory) -> None:
    """IniConfig.raw() gibt den Rohinhalt der Datei zurück."""
    ini_file = tmp_path / "test.ini"  # type: ignore[operator]
    content = "[s]\nk = v\n"
    ini_file.write_text(content, encoding="utf-8")
    cfg = IniConfig(str(ini_file))
    assert cfg.raw() == content


def test_ini_config_missing_file_raises() -> None:
    """IniConfig wirft ConfigError für nicht vorhandene Datei."""
    with pytest.raises(ConfigError):
        IniConfig("/nonexistent/path/test.ini")


def test_ini_config_invalid_syntax_raises_configerror(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Fehlerhafte INI-Syntax löst ConfigError statt configparser.Error aus."""
    ini_file = tmp_path / "ungueltig.ini"  # type: ignore[operator]
    ini_file.write_text("kein_abschnitt_davor = wert\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="INI-Datei ungültig"):
        IniConfig(str(ini_file))


def test_ini_config_write_and_read(tmp_path: pytest.TempPathFactory) -> None:
    """write_data schreibt eine INI-Datei, die IniConfig danach lesen kann."""
    out = tmp_path / "out.ini"  # type: ignore[operator]
    data: dict[str, object] = {"sec": {"a": "1", "b": "2"}}
    IniConfig.write_data(data, str(out))
    cfg = IniConfig(str(out))
    d = cfg.to_dict()
    assert "sec" in d


# --- JsonConfig ---


def test_json_config_to_dict(tmp_path: pytest.TempPathFactory) -> None:
    """JsonConfig liest eine JSON-Datei und gibt ein dict zurück."""
    json_file = tmp_path / "test.json"  # type: ignore[operator]
    json_file.write_text('{"key": "value", "num": 42}', encoding="utf-8")
    cfg = JsonConfig(str(json_file))
    d = cfg.to_dict()
    assert d["key"] == "value"
    assert d["num"] == 42


def test_json_config_raw(tmp_path: pytest.TempPathFactory) -> None:
    """JsonConfig.raw() gibt den Rohinhalt der Datei zurück."""
    content = '{"k": "v"}'
    json_file = tmp_path / "test.json"  # type: ignore[operator]
    json_file.write_text(content, encoding="utf-8")
    cfg = JsonConfig(str(json_file))
    assert cfg.raw() == content


def test_json_config_missing_file_raises() -> None:
    """JsonConfig wirft ConfigError für nicht vorhandene Datei."""
    with pytest.raises(ConfigError):
        JsonConfig("/nonexistent/test.json")


def test_json_config_non_object_raises(tmp_path: pytest.TempPathFactory) -> None:
    """JsonConfig wirft ConfigError, wenn der Inhalt kein Objekt ist."""
    json_file = tmp_path / "arr.json"  # type: ignore[operator]
    json_file.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ConfigError):
        JsonConfig(str(json_file))


def test_json_config_write_and_read(tmp_path: pytest.TempPathFactory) -> None:
    """write_data schreibt eine JSON-Datei, die JsonConfig danach lesen kann."""
    out = tmp_path / "out.json"  # type: ignore[operator]
    data: dict[str, object] = {"x": 1, "y": "two"}
    JsonConfig.write_data(data, str(out))
    content = out.read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert parsed["x"] == 1
    assert parsed["y"] == "two"


# --- TomlConfig ---


def test_toml_config_to_dict(tmp_path: pytest.TempPathFactory) -> None:
    """TomlConfig liest eine TOML-Datei und gibt ein dict zurück."""
    toml_file = tmp_path / "test.toml"  # type: ignore[operator]
    toml_file.write_text('[section]\nkey = "value"\n', encoding="utf-8")
    cfg = TomlConfig(str(toml_file))
    d = cfg.to_dict()
    assert "section" in d
    section = d["section"]
    assert isinstance(section, dict)
    assert section["key"] == "value"


def test_toml_config_raw(tmp_path: pytest.TempPathFactory) -> None:
    """TomlConfig.raw() gibt den Rohinhalt der Datei zurück."""
    content = '[s]\nk = "v"\n'
    toml_file = tmp_path / "test.toml"  # type: ignore[operator]
    toml_file.write_text(content, encoding="utf-8")
    cfg = TomlConfig(str(toml_file))
    assert cfg.raw() == content


def test_toml_config_missing_file_raises() -> None:
    """TomlConfig wirft ConfigError für nicht vorhandene Datei."""
    with pytest.raises(ConfigError):
        TomlConfig("/nonexistent/test.toml")


def test_config_load_file_ini(tmp_path: pytest.TempPathFactory) -> None:
    """Config.load_file liest INI-Dateien korrekt."""
    ini_file = tmp_path / "cfg.ini"  # type: ignore[operator]
    ini_file.write_text("[s]\nk = v\n", encoding="utf-8")
    cfg = Config()
    cfg.load_file(str(ini_file), "ini")
    assert cfg.get_value("s") is not None


def test_config_load_file_json(tmp_path: pytest.TempPathFactory) -> None:
    """Config.load_file liest JSON-Dateien korrekt."""
    json_file = tmp_path / "cfg.json"  # type: ignore[operator]
    json_file.write_text('{"key": "val"}', encoding="utf-8")
    cfg = Config()
    cfg.load_file(str(json_file), "json")
    assert cfg.get_value("key") == "val"


def test_config_load_file_unknown_format_raises() -> None:
    """Config.load_file wirft ConfigError für unbekannte Formate."""
    cfg = Config()
    with pytest.raises(ConfigError):
        cfg.load_file("/some/path", "xml")
