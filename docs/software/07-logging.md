# 7. Logging

Das Logging übernimmt allein der Aufrufer. Module und Aktionen führen kein eigenes Log, sondern reichen qualifizierte Meldungen über IPC nach oben. Dieses Kapitel beschreibt die Logstufen und ihre Filterung sowie den Schutz protokollierter Fremddaten.

## 7.1. Stufen und Filterung

Das Logging unterscheidet die vier Stufen INFO, WARN, ERROR und CRITICAL, abgebildet als Enum `LogLevel`. Der Aufrufer bildet sie auf die Stufen des `logging`-Moduls der Standardbibliothek ab. Die Logstufe des Aufrufers steht in der Instanzvariable `loglevel`.

Logdatei und Logstufe bezieht der Aufrufer aus der Konfiguration: `configure_logging` liest die Schlüssel `logfile` und `loglevel`, übernimmt die Stufe und richtet den FileHandler auf die Logdatei ein. Die Meldungen schreibt `write_log` mit der Stufe der jeweiligen Meldung, sodass ERROR und CRITICAL auch als solche im Logfile erscheinen.

Die Filterung greift an zwei Stellen. Das Modul kennzeichnet jede `IpcMessage` mit ihrer Stufe und hält Meldungen unterhalb der eingestellten Schwelle bereits selbst zurück (`send_message` über `_below_loglevel`); es sendet also gar nicht erst, was der Aufrufer ohnehin verwerfen würde. Der Aufrufer setzt die Schwelle zusätzlich auf dem Logger, sodass nur Meldungen ab der eingestellten Stufe ins Logfile gelangen.

## 7.2. Schutz protokollierter Fremddaten

Der Aufrufer protokolliert auch Fremddaten, insbesondere Standard- und Fehlerausgabe aufgerufener Befehle. Vor dem Schreiben ins Logfile ersetzt `write_log` Steuerzeichen — insbesondere Zeilenumbrüche — durch Leerzeichen. Die Logdatei wird mit engen Rechten (`0600`) angelegt, da sie sensible Daten und interne Pfade enthalten kann.
