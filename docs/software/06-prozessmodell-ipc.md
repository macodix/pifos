# 6. Prozessmodell, Steuerung und IPC

Module laufen als eigene Prozesse; Aufrufer und Modul verständigen sich über eine Pipe mit einem einheitlichen Nachrichtenformat. Dieses Kapitel beschreibt das Prozessmodell, den IPC-Mechanismus, die Hauptschleife des Modulprozesses und die gestufte Beendigung.

## 6.1. Prozessmodell

Jedes Modul startet als eigener Prozess über den `spawn`-Kontext von `multiprocessing`, was deterministisches Verhalten sichert. Der Aufrufer legt dazu eine duplexe Pipe an und startet den Prozess mit der Top-Level-Funktion `_process_target`, die pickelbar ist. Diese ruft die Einsprungfunktion `module_runner` (in `runner.py`) auf und setzt deren Rückgabewert als Exitcode.

## 6.2. IPC-Mechanismus

Die Kommunikation läuft über eine duplexe `multiprocessing.Pipe`. Beide Seiten senden und empfangen `IpcMessage`-Objekte. Die Nachrichtenart `MessageKind` unterscheidet die Richtung und Bedeutung: `COMMAND` und `REQUEST` laufen vom Aufrufer zum Modul, `LOG`, `MESSAGE`, `RESULT` und `EXCEPTION` vom Modul zum Aufrufer.

## 6.3. Nachrichtenformat

`IpcMessage` (in `ipc.py`) hat vier Felder:

| Feld | Inhalt |
|---|---|
| `kind` | Art der Nachricht (`MessageKind`) |
| `level` | Logstufe (`LogLevel`) oder `None` bei nicht-logging-relevanten Nachrichten |
| `name` | Befehlsname oder Meldungskennung |
| `payload` | Nutzdaten als einfacher Datentyp |

## 6.4. Hauptschleife des Modulprozesses

`module_runner` instanziiert die Modulklasse und prüft — sofern eine Config übergeben wurde — die Konfiguration über `check_config`. Ein `ConfigError` wird als `EXCEPTION`-Meldung zugestellt, dann endet der Prozess mit Exitcode 1.

Anschließend läuft die Befehlsschleife. Sie verarbeitet nur `COMMAND`- und `REQUEST`-Nachrichten:

- `terminate` beendet die Schleife.
- `pause` versetzt den Prozess in den angehaltenen Zustand und bestätigt mit einer `paused`-Meldung; er wartet dann auf `resume` oder `terminate`.
- `start` ruft `module.start()` auf und sendet das Ergebnis als `RESULT` mit dem Exitcode; eine dabei auftretende Ausnahme wird als `EXCEPTION` zugestellt.
- Eine `REQUEST` liefert den angeforderten Attributwert des Moduls als `RESULT` zurück.

## 6.5. Anhalten und Fortsetzen

`stop_module` und `resume_module` senden die Befehle `pause` und `resume` über IPC. Das Anhalten ist kooperativ: Der Modulprozess tritt beim Empfang von `pause` in eine innere Warteschleife und verlässt sie erst bei `resume` oder `terminate`. Die Signale SIGSTOP und SIGCONT werden nicht verwendet.

## 6.6. Beenden und Eskalation

Das Beenden erfolgt gestuft in drei Schritten. Zuerst sendet der Aufrufer den IPC-Beenden-Befehl; das Modul schließt geordnet ab und stellt zuvor seine ausstehenden Meldungen zu. Reagiert es nicht innerhalb des Zeitfensters, folgt SIGTERM über `Process.terminate()`, danach als letzte Stufe SIGKILL über `Process.kill()`. Der Regelfall ist der geordnete Abschluss über IPC; SIGTERM und SIGKILL sind die Rückfallebene für nicht reagierende Module.

Jede Stufe hat ein eigenes Zeitfenster. Die drei Wartezeiten sind Konstruktor-Parameter des `PifosCaller` (`terminate_timeout`, `sigterm_timeout`, `sigkill_timeout`) mit den Klassenvorgaben `TERMINATE_TIMEOUT` (5 s), `SIGTERM_TIMEOUT` (5 s) und `SIGKILL_TIMEOUT` (2 s). Ein konkreter Aufrufer kann sie überschreiben, etwa mit Werten aus seiner Konfiguration.
