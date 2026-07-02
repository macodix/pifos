# 4. Konfiguration

Die Konfiguration entkoppelt die Dateiformate von ihren Verwendern. Die zentrale Klasse `Config` hält die Konfiguration intern als `dict` und stellt Zugriffs- und Prüfmethoden bereit. Die Formatklassen lesen und schreiben die einzelnen Dateiformate.

## 4.1. Config

`Config` (in `config/config.py`) hält die Daten als `dict[str, object]`. Es werden nur einfache Datentypen verwendet (`str`, `int`, `float`, `bool`, `list`, `dict`); diese sind pickelbar — Voraussetzung für die Übergabe an Modulprozesse (siehe [→ Prozessmodell, Steuerung und IPC](06-prozessmodell-ipc.md)). Eine inhaltliche Prüfung der Werte findet hier nicht statt; `Config` bietet nur formale Musterprüfung.

| Methode | Zweck |
|---|---|
| `load_dict(data) -> None` | übernimmt die Konfiguration als `dict` |
| `load_raw(raw) -> None` | speichert den unzerlegten Inhalt |
| `load_file(path, format) -> None` | liest eine Datei über die passende Formatklasse (`ini`, `json`, `toml`) |
| `get_value(key) -> object` | liefert einen Einzelwert; fehlt der Schlüssel, entsteht `ConfigError` |
| `get_section(name) -> dict \| list` | liefert eine Sektion als `dict` oder `list` |
| `get_list(key, sort=False) -> list` | liefert einen Listenwert, wahlweise sortiert |
| `check_pattern(pattern, value) -> bool` | wendet ein formales Prüfmuster auf einen Wert an |
| `write_config(format, path) -> None` | schreibt die aktuelle Konfiguration in eine Datei |

`check_pattern` kennt die Muster `exists`, `not_empty`, `is_number`, `is_list`, `is_comma_separated` und `is_email`; ein unbekanntes Muster führt zu `ConfigError`.

## 4.2. Formatklassen

Jede Formatklasse liest ihre Datei im Konstruktor und stellt `to_dict()` (Konfiguration als `dict`), `raw()` (Rohinhalt) und die statische Methode `write_data(data, path)` bereit. Keine der Klassen nutzt `eval` oder `pickle`.

- **`IniConfig`** (`config/ini_config.py`) liest und schreibt INI-Dateien über `configparser`. Die oberste Ebene sind Sektionsnamen; Werte sind Zeichenketten. Beim Schreiben werden nur Sektionen mit `dict`-Wert berücksichtigt; andere Einträge werden übersprungen.
- **`JsonConfig`** (`config/json_config.py`) liest und schreibt JSON über das `json`-Modul. Der Inhalt muss ein JSON-Objekt sein, sonst entsteht `ConfigError`.
- **`TomlConfig`** (`config/toml_config.py`) liest TOML über `tomllib` aus der Standardbibliothek. Das Schreiben nutzt die optionale Bibliothek `tomli-w`; ist sie nicht installiert, meldet `write_data` dies als `ConfigError`.

Ein Lese- oder Schreibfehler jeder Formatklasse wird als `ConfigError` gemeldet.
