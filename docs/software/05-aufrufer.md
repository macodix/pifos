# 5. Aufrufer-Basisklasse PifosCaller

`PifosCaller` (in `caller.py`) kapselt Prozessstart, IPC-Kommunikation und Logging. Ein konkreter Aufrufer erbt von `PifosCaller` und steuert nur seine Fachlogik und Oberfläche bei. Ein gestarteter Modulprozess wird über die Handle-Klasse `ModuleHandle` geführt, die Prozess, Pipe-Verbindung und Modulklasse zusammenhält.

## 5.1. Methoden der Basisklasse

`PifosCaller` wird mit der Logstufe und den drei Beendigungs-Zeitlimits erzeugt: `__init__(loglevel=LogLevel.INFO, terminate_timeout=None, sigterm_timeout=None, sigkill_timeout=None)`. Ein Zeitlimit von `None` übernimmt die jeweilige Klassenvorgabe (`TERMINATE_TIMEOUT`, `SIGTERM_TIMEOUT`, `SIGKILL_TIMEOUT`; siehe [→ Prozessmodell, Steuerung und IPC](06-prozessmodell-ipc.md)).

| Methode | Zweck |
|---|---|
| `load_config(path, format) -> None` | legt ein `Config`-Objekt an, lädt es über `Config.load_file` und stellt es als Instanzvariable `config` bereit |
| `configure_logging() -> None` | liest `logfile` und `loglevel` aus der Konfiguration, übernimmt die Logstufe und richtet den FileHandler auf die Logdatei (`0600`) ein; nach `load_config` aufzurufen |
| `start_module(module_cls, config=None) -> ModuleHandle` | startet ein Modul als eigenen Prozess (Startmethode `spawn`), übergibt Config und Logstufe |
| `stop_module(handle) -> None` | hält einen Modulprozess kooperativ über IPC an |
| `resume_module(handle) -> None` | setzt einen angehaltenen Modulprozess fort |
| `terminate_module(handle) -> None` | beendet einen Modulprozess gestuft (IPC → SIGTERM → SIGKILL) |
| `send_command(handle, name, payload=None) -> None` | sendet einen Befehl über IPC an das Modul |
| `receive_result(handle) -> IpcMessage` | empfängt eine Meldung oder ein Ergebnis vom Modul (blockierend) |
| `write_log(message, level=LogLevel.INFO) -> None` | schreibt eine Meldung mit ihrer Logstufe ins Logfile (siehe [→ Logging](07-logging.md)) |
| `check_module_exit(handle) -> None` | wertet den Exitcode eines beendeten Moduls aus und ruft den passenden Handler |

## 5.2. Reaktion auf den Modulausgang

`check_module_exit` bildet den Prozess-Exitcode auf drei überschreibbare Methoden ab: `on_module_success` bei Exitcode 0, `on_module_failure` bei einem Exitcode ungleich 0 (mit dem Returncode als Argument) und `on_module_abort`, wenn kein Exitcode vorliegt (erzwungener Abbruch). In der Basisklasse tun diese drei Methoden nichts; ein konkreter Aufrufer überschreibt sie für seine eigene Reaktion.
