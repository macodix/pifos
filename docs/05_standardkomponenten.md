# pifos — Standardkomponenten

**Status:** [in Bearbeitung] · **Stand:** 2026-06-29

Dieses Dokument beschreibt die mit *pifos* mitgelieferten konkreten Standardkomponenten. Die abstrakten Basisklassen und die Architektur stehen im Implementierungsplan (`docs/04_implementierungsplan.md`).

## 1. SysCmdAction — generische Systembefehl-Aktion

`SysCmdAction(Action)` in `actions/` ist die generische Aktion für Systembefehle ohne eigene spezifische Aktion (AKT-08). Sie ist die am stärksten exponierte Stelle und setzt die Sicherheitsanforderungen der Befehlsausführung um.

Der Konstruktor nimmt den Befehl als Liste einzelner Elemente und eine Zeitgrenze:

```
SysCmdAction(command: list[str], timeout: float,
             cwd: str | None = None, env: dict[str, str] | None = None)
```

`run` führt den Befehl mit `subprocess.Popen` aus. Die Festlegungen:

Die Ausführung erfolgt ohne Shell (`shell=False`) (SIC-03). Befehl und Argumente werden als Liste übergeben, nicht als zusammengesetzte Befehlszeichenkette (SIC-04). `command` ist daher eine `list[str]`; eine Zeichenkette wird nicht angenommen. Jede Ausführung trägt die explizite Zeitgrenze `timeout`; nach Ablauf wird der Prozess beendet und der Fehler als Ausnahme gemeldet (SIC-05). Bei sicherheitsrelevanten Programmen wird der Programmpfad als absoluter Pfad angegeben oder in einer kontrollierten Umgebung (`env` mit gesetztem `PATH`) aufgelöst (SIC-06).

`Popen` mit getrennten Strömen für stdout und stderr erlaubt das laufende Auslesen während langer Befehle; die Aktion erfasst beide Ströme und den Returncode und stellt sie dem Modul bereit (AKT-02). Bei Bedarf reicht das Modul Ausgaben laufend als Meldungen an den Aufrufer (LOG-02). `subprocess.run` ist nicht gewählt, weil es das Ergebnis erst am Ende liefert und keine laufende Statusmeldung erlaubt.

Werte aus der Konfiguration, die als Argument in `command` oder als Programmpfad einfließen, prüft das aufrufende Modul vor der Übergabe auf Typ, Format und Wertebereich anhand einer Positivliste; die Aktion selbst nimmt keine inhaltliche Prüfung vor (SIC-01, SIC-02). Die Prüfung liegt beim Modul, weil der Konfigurationsbaustein bewusst nicht inhaltlich prüft (Kapitel 3 „Module" und Kapitel 4 „Konfiguration" des Implementierungsplans).

## Versionshistorie

| Version | Datum | Wer | Änderung |
|---------|-------|-----|----------|
| 0.01 | 2026-06-29 | macodix | Erstanlage: SysCmdAction aus dem Implementierungsplan (Abschnitt 2.2) hierher ausgelagert. |
