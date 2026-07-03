# 3. Module

Ein Modul erledigt eine fachliche Aufgabe unter Nutzung von Aktionen und kommuniziert über IPC mit dem aufrufenden Prozess. Alle Module erben von der abstrakten Basisklasse `Module` (in `module.py`). Ein Modul läuft als eigener Prozess (siehe [→ Prozessmodell, Steuerung und IPC](06-prozessmodell-ipc.md)).

## 3.1. Basisklasse Module

`Module` wird mit der IPC-Verbindung (`conn`) und der Logstufe (`loglevel`) erzeugt. Das Klassenattribut `CONFIG` enthält die Namen der benötigten Konfigurationswerte; es ist standardmäßig leer.

Die konkrete Modulklasse implementiert die abstrakte Methode `start() -> int` mit der Rückgabekonvention 0 bei Erfolg, ungleich 0 bei Fehler.

Die Basisklasse stellt folgende Methoden bereit:

| Methode | Zweck |
|---|---|
| `check_config(config) -> None` | liest die in `CONFIG` genannten Schlüssel aus dem `Config`-Objekt und legt sie als gleichnamige Instanzvariablen ab; fehlt ein Pflichtwert, entsteht `ConfigError` |
| `run_action(action) -> int` | führt eine Aktion aus und übernimmt deren Status: 0 bei `finished`, sonst 1; eine `ActionError` wird zu Rückgabewert 1 |
| `control_action(action, **options) -> None` | setzt die übergebenen Schlüssel-Wert-Paare als Attribute der Aktion |
| `resolve_action(name) -> type[Action]` | importiert das Modul `pifos.actions.<klassenname in snake_case>` (z. B. `SysCmdAction` → `sys_cmd_action`) und liest daraus die Klasse `<name>`; ermöglicht die Auswahl einer Aktion über ihren Namen zur Laufzeit; nicht auffindbar oder keine `Action`-Unterklasse → `ModuleError` |
| `send_message(level, name, payload) -> None` | reicht eine Meldung an den Aufrufer; Meldungen unterhalb der eingestellten Logstufe werden zurückgehalten (siehe [→ Logging](07-logging.md)) |
| `receive_message() -> IpcMessage` | nimmt einen Befehl des Aufrufers an (blockierend) |
| `check() -> bool \| None` | optionale Überprüfung der Modulwirkung; überschreibbar, Standard `None` |
| `rollback() -> bool \| None` | optionaler Rückbau der Modulwirkung; überschreibbar, Standard `None` |

`send_message` bildet die Meldung auf eine `IpcMessage` ab: mit Logstufe als `LOG`, ohne Stufe als `MESSAGE`. Die Filterung unterhalb der Schwelle übernimmt intern `_below_loglevel`. `check` und `rollback` liefern `None`, solange eine Modulklasse sie nicht überschreibt; ein überschriebenes `check` gibt `True` bei bestätigter Wirkung und `False` bei Abweichung zurück, `rollback` entsprechend `True`/`False` für gelungenen oder fehlgeschlagenen Rückbau.

## 3.2. Aktion über ihren Namen auflösen

`resolve_action` ist eine Hilfsmethode: Sie liefert zu einem Aktionsnamen die
zugehörige Klasse aus dem Unterpaket `actions/`. Ein Modul kann damit die
auszuführende Aktion zur Laufzeit im Code bestimmen, statt sie fest zu
importieren. Die Parameter der Aktion setzt das Modul selbst.

