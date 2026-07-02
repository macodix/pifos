# 8. Fehlerbehandlung und Ausnahmen

pifos hat eine eigene Ausnahmehierarchie. Fehler entstehen in Aktionen, Modulen oder der Konfiguration und werden über die Prozessgrenze an den Aufrufer weitergereicht. Dieses Kapitel beschreibt die Hierarchie, die Weiterleitung und den sicheren Zustand bei Abbruch.

## 8.1. Ausnahmehierarchie

Alle pifos-Ausnahmen leiten von `PifosError` ab (in `errors.py`):

| Ausnahme | Herkunft |
|---|---|
| `PifosError` | gemeinsame Basisklasse |
| `ActionError` | Fehler in einer Aktion; von `Action.run()` erzeugt |
| `ModuleError` | Fehler in einem Modul |
| `ConfigError` | fehlende oder formal ungültige Konfigurationswerte |

## 8.2. Weiterleitung über die Prozessgrenze

Der Modulprozess läuft getrennt vom Aufrufer; Ausnahmen können nicht direkt geworfen werden. `module_runner` fängt sie und stellt sie als `EXCEPTION`-`IpcMessage` zu: `name` trägt den Ausnahmetyp, `payload` die Meldung samt Traceback, `level` die Stufe ERROR oder CRITICAL. Ein `ConfigError` bei der Konfigurationsprüfung wird als `EXCEPTION` gemeldet, danach endet der Prozess mit Exitcode 1.

## 8.3. Sicherer Zustand bei Abbruch

Beendet sich ein Modul wegen eines als CRITICAL eingestuften Fehlers, stellt es über die synchrone Pipe zuerst sicher, dass die Ausnahme-Meldung den Aufrufer noch erreicht, bevor der Prozess endet. Bei einer unerwarteten Ausnahme in der Hauptschleife wird die `EXCEPTION`-Meldung zunächst zugestellt und die Verbindung anschließend geschlossen.

Auf Aktionsebene sichert `CopyFileAction` den Zustand: Das Kopieren läuft über eine Temp-Datei mit atomarem Austausch; schlägt es fehl, bleibt die bestehende Zieldatei unverändert und die Temp-Datei wird entfernt.
