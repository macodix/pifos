# 2. Aktionen

Eine Aktion erledigt genau eine atomare Aufgabe und stellt Status und Ausgaben dem aufrufenden Modul vollständig bereit. Alle Aktionen erben von der abstrakten Basisklasse `Action`. Die Prüfung der Parameter liegt nicht bei der Aktion, sondern beim aufrufenden Modul.

## 2.1. Basisklasse Action

`Action` (in `action.py`) hält den Ausführungszustand in `self.status` mit den Werten `not_runned`, `running`, `finished` und `failed`. Das Klassenattribut `PARAMS` listet die Namen der erlaubten Parameter; es ist leer, wenn die Aktion keine Parameter hat.

Konkrete Aktionen implementieren die abstrakte Methode `run() -> str`. Sie setzt `status` vor der Ausführung auf `running`, danach auf `finished` oder `failed`, und gibt den Status zurück. Im Fehlerfall erzeugt `run` eine `ActionError`, die an das aufrufende Modul weitergereicht wird (siehe [→ Fehlerbehandlung und Ausnahmen](08-fehlerbehandlung.md)).

## 2.2. SysCmdAction

`SysCmdAction` (in `actions/sys_cmd_action.py`) führt einen Systembefehl ohne Shell aus und erfasst Standardausgabe, Fehlerausgabe und Rückgabewert.

Der Befehl wird als Liste einzelner Elemente übergeben (`command`); das erste Element ist der Programmpfad, die weiteren sind Argumente. Eine Zeichenkette wird nicht angenommen. Jede Ausführung trägt eine explizite Zeitgrenze (`timeout` in Sekunden); nach deren Ablauf wird der Prozess mit SIGKILL beendet. Optional sind Arbeitsverzeichnis (`cwd`) und Umgebungsvariablen (`env`); für sicherheitsrelevante Programme empfiehlt sich ein explizites `env` mit kontrolliertem `PATH`.

Nach `run` stehen `stdout`, `stderr` und `returncode` zur Verfügung. Eine `ActionError` entsteht bei überschrittener Zeitgrenze, bei Rückgabewert ungleich 0 oder bei einem Startfehler. Die Ausführung nutzt `subprocess.Popen` mit `shell=False`.

## 2.3. CopyFileAction

`CopyFileAction` (in `actions/copy_file_action.py`) kopiert eine Datei von `src` nach `dst`.

Im safe-mode (Voreinstellung `safe_mode=True`) wird eine bestehende Zieldatei ohne ausdrückliche Freigabe nicht überschrieben; der Versuch führt zu einer `ActionError`. Erst mit `overwrite=True` wird überschrieben — dabei sichert die Aktion die bestehende Zieldatei zuvor. Der Sicherungsort ist über `backup_location` einstellbar; ohne Angabe liegt die Sicherung im Verzeichnis der Zieldatei. Ist `safe_mode=False`, entfällt der Schutz.

Das Kopieren erfolgt über eine Temp-Datei im Zielverzeichnis mit anschließendem atomarem Austausch (`os.replace`); die Rechte der Quelldatei werden übernommen. Sicherung und Schreiben sind gegen Symlink-Manipulation und TOCTOU abgesichert (`O_NOFOLLOW`, exklusives Anlegen der Sicherung mit `O_EXCL`, Kopie über Dateideskriptoren). Die Sicherung weitet die Zugriffsrechte des Originals nicht aus. Fehlt die Quelldatei oder tritt ein Dateifehler auf, entsteht eine `ActionError`; eine angefangene Temp-Datei wird dabei entfernt.
