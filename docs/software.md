# pifos — Softwaredokumentation

*pifos* ist ein Bausatz zum Bau von Aufrufern, die Aufgaben in gekapselten Modulprozessen ausführen. Diese Dokumentation beschreibt den umgesetzten Stand des Codes unter `usr/lib/pifos/` — sie spiegelt wider, was tatsächlich vorhanden ist, und wird mit dem Code fortgeschrieben. Die frühere Planungsreihe (Konzept, Anforderungen, Machbarkeit, Implementierungsplan) liegt unter `docs/archiv/`.

**Status:** [in Bearbeitung] · **Stand:** 2026-07-02

## Inhaltsverzeichnis

01 [Überblick und Architektur](software/01-ueberblick.md)
02 [Aktionen](software/02-aktionen.md)
03 [Module](software/03-module.md)
04 [Konfiguration](software/04-konfiguration.md)
05 [Aufrufer-Basisklasse PifosCaller](software/05-aufrufer.md)
06 [Prozessmodell, Steuerung und IPC](software/06-prozessmodell-ipc.md)
07 [Logging](software/07-logging.md)
08 [Fehlerbehandlung und Ausnahmen](software/08-fehlerbehandlung.md)

## Versionshistorie

| Version | Datum | Wer | Änderung |
|---------|-------|-----|----------|
| 0.01 | 2026-07-02 | macodix | Erstanlage der Softwaredokumentation als aufgeteiltes Dokument; Kapitel 1 (Überblick und Architektur) ausgearbeitet, Kapitel 2–8 angelegt. |
| 0.02 | 2026-07-02 | macodix | Korrekturen nach Konsistenzprüfung gegen den Code: resolve_action (Modulname aus Kleinschreibung), Logstufe auf dem Logger statt FileHandler, Beenden ohne suggerierten Flush-Schritt, IniConfig-Schreibverhalten ergänzt. |
| 0.03 | 2026-07-02 | macodix | Kap. 3: resolve_action an die Code-Korrektur angepasst — Modulname aus dem Klassennamen in snake_case, Zweck (Aktionswahl über Namen aus der Konfiguration) ergänzt. |
| 0.04 | 2026-07-02 | macodix | Kap. 3: Abschnitt 3.2 „Aktion über die Konfiguration wählen" mit Muster (resolve_action → Instanz mit Config-Parametern → run_action) ergänzt. |
| 0.05 | 2026-07-02 | macodix | Kap. 2: acht neue Aktionen dokumentiert (WriteFile, Move, LineInFile, BlockInFile, ReplaceInFile, Tar, Untar, Apt); gemeinsames Schutzverhalten der dateiverändernden Aktionen als Abschnitt 2.2 herausgezogen und den CopyFileAction-Abschnitt darauf gestrafft; Überblickstabelle (Kap. 1) und Fehlerbehandlung (Kap. 8) angepasst. |
