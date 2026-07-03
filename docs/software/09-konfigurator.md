# 9. Konfigurator

Der Konfigurator erzeugt Konfigurationsdateien für pifos-Module aus deren
Deklarationen, geht bestehende Dateien Wert für Wert durch und legt beliebige
Dateien frei an. Er ist als Bibliotheks-Schnittstelle (`Configurator` in
`configurator.py`) und über den Einstieg `bin/pifos-config` nutzbar.

## 9.1. Datenmodell

Eine Konfiguration ist ein `dict` aus Abschnitten und Schlüssel/Wert-Paaren. Beim
Erstellen für pifos-Module ist der Abschnittsname der Modul-Klassenname, der
Abschnittswert ein `dict` der Konfigurationswerte des Moduls als Zeichenketten.
Neben Abschnitten kann die oberste Ebene auch einzelne Schlüssel/Wert-Paare ohne
Abschnitt tragen. Verschachtelte Abschnitte gibt es nicht.

Das Abschnittsmodell bilden alle drei Formate `ini`, `json` und `toml` ab.
Abschnittslose Werte auf oberster Ebene unterstützen nur `json` und `toml`; beim
Schreiben im `ini`-Format lehnt der Konfigurator sie mit einer klaren Meldung ab,
da `configparser` keinen Platz außerhalb eines Abschnitts kennt.

Für den Aufbau gilt die Faustregel: ein Thema, ein Abschnitt. Schlüsselnamen sind
sprechend und datei-weit möglichst eindeutig, damit Suchen sowie
Suchen-und-Ersetzen genau greifen.

## 9.2. Bibliotheks-Schnittstelle

`Configurator` wird mit einem `Prompter` und einer `rich.Console` erzeugt; ohne
Argument nutzt er einen questionary-gestützten Prompter. Die Methoden sind
`build_for_module`, `build_for_modules`, `edit` und `build_free`. Die
Modulfunktionen `read_config_data` und `write_config_data` lesen über
`Config.to_dict` und schreiben über die Formatklassen.

## 9.3. Kommando

`bin/pifos-config` bietet drei sich ausschließende Betriebsarten: `--module`
(Erstellen aus Moduldeklarationen, mehrfach für eine Sammeldatei), `--edit`
(Bearbeiten) und `--free` (freies Erstellen). Die Zieldatei (`ZIELDATEI`) ist
ein positionsgebundenes Argument; bei `--edit` ist sie optional — ohne Angabe
wird die `--edit`-Quelle an Ort und Stelle bearbeitet. Bei `--module` und
`--free` ist sie Pflicht.

`--format` ist optional: ohne Angabe wird das Format aus der Endung der
Zieldatei abgeleitet (`.ini`, `.json`, `.toml`, Groß-/Kleinschreibung egal);
ohne `--format` und ohne ableitbare Endung entsteht ein Fehler. `--format`
übersteuert eine abweichende Endung. `--input-format` löst das Format der
`--edit`-Quelle entsprechend auf: zuerst deren Endung, sonst das Zielformat.
`--overwrite` und `--backup-location` steuern das Überschreiben und die
Sicherung.

Kurzbeispiele:

```sh
pifos-config --edit probe.ini
pifos-config --edit alt_bestand.json neuer_bestand.json
pifos-config --module paket.modul:MeinModul einstellungen.toml
```

## 9.4. Sicheres Schreiben

Eine bestehende Zieldatei wird ohne `--overwrite` nicht überschrieben (safe-mode).
Eine Ausnahme gilt für das Bearbeiten an Ort und Stelle (`--edit` ohne
Zieldatei): dort sind Ziel und Quelle dieselbe Datei, und der Konfigurator
ersetzt sie nach der üblichen Sicherung, ohne dass `--overwrite` nötig ist. Bei
abweichendem Ziel gelten die bisherigen Regeln. Vor dem Überschreiben entsteht
eine Sicherung nach dem Muster der dateiverändernden Aktionen (siehe [→
Aktionen](02-aktionen.md), Abschnitt „Gemeinsames Schutzverhalten der
dateiverändernden Aktionen"). Der neue Inhalt wird zuerst vollständig in eine
Hilfsdatei geschrieben und dann in einem Schritt (`os.replace`) an die Stelle
der Zieldatei gesetzt; die Zieldatei erhält die Rechte `0600`. Eingaben werden
als Freitext ohne Maskierung erfasst; Fehler erscheinen als generische Meldung
ohne internen Pfad.
