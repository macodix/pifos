# 2. Aktionen

Eine Aktion erledigt genau eine atomare Aufgabe und stellt Status und Ausgaben dem aufrufenden Modul vollständig bereit. Alle Aktionen erben von der abstrakten Basisklasse `Action`. Die Prüfung der Parameter liegt nicht bei der Aktion, sondern beim aufrufenden Modul. Die konkreten Aktionen liegen im Unterpaket `actions/`; die dateiverändernden Aktionen teilen sich Sicherungs- und Schreiblogik im Hilfsmodul `actions/_file_ops.py`.

## 2.1. Basisklasse Action

`Action` (in `action.py`) hält den Ausführungszustand in `self.status` mit den Werten `not_runned`, `running`, `finished` und `failed`. Das Klassenattribut `PARAMS` listet die Namen der erlaubten Parameter; es ist leer, wenn die Aktion keine Parameter hat.

Konkrete Aktionen implementieren die abstrakte Methode `run() -> str`. Sie setzt `status` vor der Ausführung auf `running`, danach auf `finished` oder `failed`, und gibt den Status zurück. Im Fehlerfall erzeugt `run` eine `ActionError`, die an das aufrufende Modul weitergereicht wird (siehe [→ Fehlerbehandlung und Ausnahmen](08-fehlerbehandlung.md)).

## 2.2. Gemeinsames Schutzverhalten der dateiverändernden Aktionen

Alle Aktionen, die eine einzelne Zieldatei anlegen, ändern oder überschreiben, folgen demselben Muster; die Umsetzung liegt im Hilfsmodul `actions/_file_ops.py`. Einzige Ausnahme ist `UntarAction`, die viele Dateien auf einmal anlegt und eigene Schutzmechanismen hat (siehe Abschnitt 2.11, UntarAction).

**safe-mode** (Voreinstellung `safe_mode=True`): Aktionen, die eine bestehende Zieldatei ersetzen würden (`CopyFileAction`, `WriteFileAction`, `MoveFileAction`, `TarAction`), verweigern das ohne `overwrite=True` mit einer `ActionError`; mit `overwrite=True` sichern sie die Zieldatei vorher. Aktionen, die den Inhalt einer bestehenden Datei ändern (`LineInFileAction`, `BlockInFileAction`, `ReplaceInFileAction`), sichern die Datei vor der ersten tatsächlichen Änderung; ist keine Änderung nötig, entsteht auch keine Sicherung.

**Sicherung:** Die Sicherungsdatei heißt `<name>.bak-<JJJJ-MM-TT-HHMMSS>` (Zeitstempel in lokaler Zeit) und liegt im Verzeichnis der Zieldatei oder unter dem einstellbaren `backup_location`. Sie wird exklusiv angelegt (`O_EXCL`, `O_NOFOLLOW`) und übernimmt die Rechte des Originals, ohne sie auszuweiten. Fällt eine weitere Sicherung derselben Datei in dieselbe Sekunde, erhält der Name einen numerischen Zusatz (`-1`, `-2`, …); erst wenn auch das wiederholt scheitert, entsteht eine `ActionError`.

**Atomares Schreiben:** Geschrieben wird über eine Temp-Datei im Zielverzeichnis mit anschließendem Austausch per `os.replace`. Es gibt zu keinem Zeitpunkt eine halbfertige Zieldatei; schlägt das Schreiben fehl, bleibt die bestehende Datei unverändert und die Temp-Datei wird entfernt.

**Symlink-Schutz:** Wo eine Aktion die bestehende Zieldatei liest — beim Sichern, bei den inhaltsändernden Aktionen (`LineInFileAction`, `BlockInFileAction`, `ReplaceInFileAction`) und bei der Rechteübernahme der `WriteFileAction` —, geschieht das über `O_NOFOLLOW`; ein Symlink an Stelle der Zieldatei führt dort zur `ActionError` statt zum Zugriff durch den Symlink. Der Austausch per `os.replace` ersetzt einen Symlink-Eintrag als Ganzes und schreibt nie durch ihn hindurch.

## 2.3. SysCmdAction

`SysCmdAction` (in `actions/sys_cmd_action.py`) führt einen Systembefehl ohne Shell aus und erfasst Standardausgabe, Fehlerausgabe und Rückgabewert.

Der Befehl wird als Liste einzelner Elemente übergeben (`command`); das erste Element ist der Programmpfad, die weiteren sind Argumente. Eine Zeichenkette wird nicht angenommen. Jede Ausführung trägt eine explizite Zeitgrenze (`timeout` in Sekunden); nach deren Ablauf wird der Prozess mit SIGKILL beendet. Optional sind Arbeitsverzeichnis (`cwd`) und Umgebungsvariablen (`env`); für sicherheitsrelevante Programme empfiehlt sich ein explizites `env` mit kontrolliertem `PATH`.

Nach `run` stehen `stdout`, `stderr` und `returncode` zur Verfügung. Eine `ActionError` entsteht bei überschrittener Zeitgrenze, bei Rückgabewert ungleich 0 oder bei einem Startfehler. Die Ausführung nutzt `subprocess.Popen` mit `shell=False`.

## 2.4. CopyFileAction

`CopyFileAction` (in `actions/copy_file_action.py`) kopiert eine Datei von `src` nach `dst`. Die Zieldatei übernimmt die Rechte der Quelldatei. Eine fehlende Quelldatei führt zur `ActionError`.

Eine bestehende Zieldatei unterliegt dem safe-mode; gesichert und geschrieben wird nach dem gemeinsamen Schutzverhalten (siehe Abschnitt 2.2, Gemeinsames Schutzverhalten). Ist `safe_mode=False`, entfällt der Schutz.

## 2.5. WriteFileAction

`WriteFileAction` (in `actions/write_file_action.py`) schreibt den übergebenen Inhalt (`content`) in die Zieldatei `dst`.

Die Dateirechte bestimmt der Parameter `mode`: Ein ausdrücklich übergebener Wert gilt immer. Ohne `mode` behält eine bestehende Zieldatei ihre Rechte — ermittelt über einen `O_NOFOLLOW`-Deskriptor, ein Symlink als Ziel führt dabei zur `ActionError` —, eine neue Datei erhält restriktiv `0o600`. safe-mode und atomares Schreiben nach Abschnitt 2.2, Gemeinsames Schutzverhalten.

## 2.6. MoveFileAction

`MoveFileAction` (in `actions/move_file_action.py`) verschiebt eine Datei von `src` nach `dst`. Eine fehlende Quelldatei führt zur `ActionError`.

Innerhalb desselben Dateisystems geschieht das Verschieben atomar per `os.replace`; die Rechte bleiben dabei unverändert erhalten. Über Dateisystemgrenzen hinweg wird die Datei über eine Temp-Datei kopiert (Rechte der Quelle übernommen) und die Quelle anschließend entfernt. Eine bestehende Zieldatei unterliegt dem safe-mode nach Abschnitt 2.2, Gemeinsames Schutzverhalten.

## 2.7. LineInFileAction

`LineInFileAction` (in `actions/line_in_file_action.py`) stellt sicher, dass eine Zeile in einer Textdatei vorhanden ist oder fehlt. Die Datei muss existieren, sonst entsteht eine `ActionError`.

Bei `state="present"` (Voreinstellung) wird die Sollzeile `line` gesetzt: Trifft der optionale reguläre Ausdruck `match` eine Zeile, ersetzt die Aktion die erste Fundstelle durch `line`; ohne `match` zählt der exakte Zeilenvergleich. Gibt es keine Fundstelle, wird `line` am Dateiende angefügt; steht die Zeile bereits so da, ändert sich nichts. Bei `state="absent"` werden alle Fundstellen entfernt.

Gesichert wird nur bei tatsächlicher Änderung; Schreiben atomar, die Dateirechte bleiben erhalten (Abschnitt 2.2, Gemeinsames Schutzverhalten).

## 2.8. BlockInFileAction

`BlockInFileAction` (in `actions/block_in_file_action.py`) pflegt einen markierten, mehrzeiligen Textblock in einer Textdatei. Der Block (`block`, Inhalt ohne Marker) wird von zwei Markerzeilen der Form `<comment_char> BEGIN <marker>` und `<comment_char> END <marker>` eingerahmt; das Kommentarzeichen ist über `comment_char` einstellbar (Voreinstellung `#`).

Bei `state="present"` wird ein vorhandener Block ersetzt, wenn sein Inhalt abweicht; fehlt er, wird er mit einer Leerzeile als Trenner am Dateiende angefügt. Bei `state="absent"` entfernt die Aktion den Block samt Markerzeilen und einer unmittelbar davor stehenden Leerzeile — ein Anlege-Entferne-Zyklus stellt den Ausgangsinhalt exakt wieder her. Ist nur eine der beiden Markerzeilen vorhanden (inkonsistenter Zustand), gilt der Block als nicht vorhanden. Existenzpflicht der Datei, Sicherung und atomares Schreiben wie bei `LineInFileAction`.

## 2.9. ReplaceInFileAction

`ReplaceInFileAction` (in `actions/replace_in_file_action.py`) sucht und ersetzt im Inhalt einer Textdatei per regulärem Ausdruck (`pattern`, `replacement`; Rückverweise sind möglich). `count` begrenzt die Zahl der Ersetzungen; `0` (Voreinstellung) ersetzt alle Fundstellen.

Die Datei muss existieren. Ohne Fundstelle bleibt die Datei unverändert und es entsteht keine Sicherung; der Status ist dennoch `finished`. Sicherung und atomares Schreiben wie bei `LineInFileAction`. Die Datei wird vollständig in den Speicher gelesen; ein Größenlimit gibt es nicht — die Aktion ist für Konfigurationsdateien gedacht, nicht für beliebig große Dateien.

## 2.10. TarAction

`TarAction` (in `actions/tar_action.py`) packt die Pfade der Liste `sources` (Dateien oder Verzeichnisse, rekursiv) in das tar-Archiv `dst`. `compression` wählt gzip (`"gz"`, Voreinstellung) oder unkomprimiert (`None`). Fehlende Quellen führen zur `ActionError`.

Das Archiv erhält restriktive Rechte (`mode`, Voreinstellung `0o600`) und wird atomar über eine Temp-Datei erstellt; bei einem Packfehler bleibt kein Temp-Rest zurück. Symlinks in den Quellen werden als Symlink-Einträge archiviert, nicht dereferenziert. Ein bestehendes Archiv unterliegt dem safe-mode nach Abschnitt 2.2, Gemeinsames Schutzverhalten.

## 2.11. UntarAction

`UntarAction` (in `actions/untar_action.py`) entpackt das tar-Archiv `src` (gzip oder unkomprimiert, automatisch erkannt) in das bestehende Zielverzeichnis `dst_dir`.

Entpackt wird ausschließlich mit dem tarfile-Extraktionsfilter `data`: Pfadausbruch (`../`), absolute Pfade, Symlink-Angriffe, Gerätedateien und Rechteausweitung aus dem Archiv werden abgewehrt. Vor der Extraktion prüft die Aktion Kollisionen: Trifft ein Archiv-Eintrag auf eine bestehende Datei oder einen Symlink im Ziel, entsteht ohne `overwrite=True` eine `ActionError` und nichts wird entpackt; bestehende Verzeichnisse zählen nicht als Kollision. Ebenfalls vor der Extraktion greifen zwei Grenzen gegen Dekompressionsangriffe: `max_members` (Voreinstellung 10 000 Einträge) und `max_total_size` (Voreinstellung 1 GiB, Summe der entpackten Größen). Ein safe-mode mit Sicherung einzelner Dateien besteht hier nicht.

## 2.12. AptAction

`AptAction` (in `actions/apt_action.py`) installiert (`state="present"`, Voreinstellung) oder entfernt (`state="absent"`) die Debian-/Ubuntu-Pakete der Liste `packages` über `apt-get`.

Der Aufruf läuft nicht-interaktiv (`DEBIAN_FRONTEND=noninteractive`), ohne Shell, mit absolutem Programmpfad, festem `PATH` und Zeitgrenze (`timeout`, Voreinstellung 300 s); intern nutzt die Aktion `SysCmdAction`, deren `stdout`, `stderr` und `returncode` auch im Fehlerfall bereitstehen. Der Kommandoaufbau trennt Optionen und Paketliste durch `--`; Paketnamen mit führendem `-` weist die Aktion mit `ActionError` ab. Das schützt den Kommandoaufbau vor Optionsinjektion und ersetzt nicht die inhaltliche Parameterprüfung durch das aufrufende Modul.

## 2.13. SystemdServiceAction

`SystemdServiceAction` (in `actions/systemd_service_action.py`) steuert systemd-Einheiten über `systemctl`. Je Ausführung gilt genau eine `operation` aus der Positivliste `enable`, `disable`, `start`, `stop`, `restart`, `reload`, `daemon-reload`; eine unbekannte Operation führt zur `ActionError`. Der Einheitenname `unit` ist Pflicht — außer bei `daemon-reload`, wo er nicht erlaubt ist.

Der Kommandoaufbau folgt dem Muster der `AptAction`: `systemctl --no-pager <operation> -- <unit>`, ohne Shell, mit absolutem Programmpfad, festem `PATH`, abgeschaltetem Pager (zusätzlich `SYSTEMD_PAGER` leer) und Zeitgrenze (`timeout`, Voreinstellung 60 s); intern `SysCmdAction` mit verfügbarem `stdout`, `stderr` und `returncode` auch im Fehlerfall. Einheitennamen mit führendem `-` weist die Aktion mit `ActionError` ab — Schutz vor Optionsinjektion, keine inhaltliche Parameterprüfung (die liegt beim aufrufenden Modul).
