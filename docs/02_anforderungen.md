# pifos — Anforderungen

**Status:** [in Bearbeitung] · **Stand:** 2026-06-27

Dieses Dokument leitet die Anforderungen an den wiederverwendbaren Software-Bausatz pifos (python infrastructure for operational services) aus dem Konzept ab. Es beschreibt das WAS — was pifos leisten muss —, nicht das WIE der Umsetzung. Quelle ist `docs/01_konzept.md`; als Nutzungsszenario dient das Installer-Konzept im Projekt linux-secure-base. Konkrete Klassennamen, Dateinamen und Bibliotheken aus dem Konzept werden nur dort genannt, wo sie selbst Festlegung sind.

## Inhaltsverzeichnis

**1. Geltung und Begriffe**  
**2. Anforderungsformat**  
**3. Übergreifende Anforderungen**  
**4. Aktionen**  
**5. Module**  
**6. Konfiguration**  
**7. Konfigurator**  
**8. Aufruf und Steuerung**  
**9. Logging**  
**10. Ausnahmen**  
**11. Standardaufrufer**  
**12. Bereitstellung**  
**13. Sicherheit**  

## 1. Geltung und Begriffe

pifos ist ein Bausatz aus Python-Komponenten zur Steuerung und Überwachung von Aktivitäten auf einem System. Er wird als allgemein nutzbare Komponente auf dem jeweiligen System bereitgestellt und nicht nur für den Installer. Der LSB-Installer ist der erste Nutzer (Aufrufer) von pifos, aber nur einer von mehreren möglichen.

Die zentralen Begriffe übernimmt dieses Dokument aus dem Konzept.

- **Aktion** — eine Python-Klasse, die genau eine atomare Aufgabe in der Systemumgebung erledigt (z. B. Datei kopieren, Systembefehl ausführen).
- **Modul** — eine Python-Klasse zur Erledigung einer Aufgabe, die dazu Aktionen nutzt und zusätzliche Methoden enthalten kann.
- **Konfiguration** — die Schnittstelle zwischen Anwender und pifos, übergeben als Config-Objekt.
- **Aufrufer** — das Programm (z. B. der Installer), das Module startet und steuert.

## 2. Anforderungsformat

Jede Anforderung trägt eine eindeutige ID, eine Verbindlichkeit und einen Text. Die ID besteht aus einem sprechenden Bereichskürzel und einer laufenden Nummer.

| Bereichskürzel | Bereich |
|----------------|---------|
| ÜBR | Übergreifende Anforderungen |
| AKT | Aktionen |
| MOD | Module |
| KFG | Konfiguration |
| KOR | Konfigurator |
| STR | Aufruf und Steuerung |
| LOG | Logging |
| EXC | Ausnahmen |
| CAL | Standardaufrufer |
| BRS | Bereitstellung |
| SIC | Sicherheit |

Die Verbindlichkeit ist entweder MUSS (Pflicht) oder KANN (optional), entsprechend `konv-anforderungsmanagement.md` Kapitel 1 (Formulierung von Anforderungen).

## 3. Übergreifende Anforderungen

Diese Anforderungen gelten für pifos als Ganzes, unabhängig vom einzelnen Baustein.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| ÜBR-01 | MUSS | pifos stellt die drei Bausteine Aktionen, Module und Konfiguration bereit. |
| ÜBR-02 | MUSS | pifos ist von beliebigen Aufrufern nutzbar, nicht nur vom Installer. |
| ÜBR-03 | MUSS | pifos erfüllt jede Anforderung mit der einfachsten dafür ausreichenden Lösung (KISS). |
| ÜBR-04 | KANN | Öffentliche Attribute (ohne führenden Unterstrich) sind direkt zugänglich; auf flächendeckende getter-/setter-Methoden wird verzichtet. Zugriffslogik über `@property` kann bei Bedarf eingesetzt werden, wo der Zugriff eine Prüfung oder Berechnung erfordert. |
| ÜBR-05 | MUSS | pifos enthält nur Funktionen, die das Konzept fordert; keine darüber hinausgehenden Festlegungen oder Funktionen. |

## 4. Aktionen

Eine Aktion erledigt genau eine atomare Aufgabe in der Systemumgebung und liefert vollständige Kontrolle über deren Ausführung und Ausgaben.

### 4.1 Grundverhalten

Die folgenden Anforderungen betreffen jede Aktion.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| AKT-01 | MUSS | Eine Aktion erledigt genau eine Aufgabe (atomar nach der UNIX-Regel: eine Aufgabe gut erledigen). |
| AKT-02 | MUSS | Eine Aktion stellt Status und Ausgaben ihrer Ausführung (insbesondere stdout und stderr) dem aufrufenden Modul vollständig als Variable und/oder Methode bereit. |
| AKT-03 | MUSS | Eine Aktion leitet Fehler und Ausnahmen an das aufrufende Modul weiter. |
| AKT-04 | MUSS | Eine Aktion lässt sich über Optionen an Bedingungen der Ausführung anpassen, ohne ihren atomaren Charakter zu verändern. |
| AKT-05 | MUSS | Alle Aktionen leiten von einer gemeinsamen Elternklasse ab, die ein einheitliches Grundset an Objektvariablen und Methoden sicherstellt. |

### 4.2 Sichere Dateiänderung

Aktionen, die Dateien verändern, müssen den Zustand vor dem Eingriff sichern können.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| AKT-06 | MUSS | Für Aktionen, die Dateien ändern, überschreiben oder löschen, ist ein safe-mode zu implemetieren, der die Datei vor der Änderung sichert oder vor Überschreiben ohne explizite Aufforderung (z. B. --force Schalter) schützt. |
| AKT-07 | MUSS | Wird nach AKT-06 eine Dateisicherung implementiert muss der Ort der Sicherung Parameter einstellbar sein. |

### 4.3 Systembefehle

Für Systembefehle ohne eigene spezifische Aktion existiert eine generische Aktion.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| AKT-08 | MUSS | Es existiert eine Aktion für Systembefehle, die für alle Befehle nutzbar ist, bei denen eine eigene Aktion keinen Sinn ergibt. |

## 5. Module

Ein Modul erledigt eine Aufgabe, indem es Aktionen nutzt, und erhält seine Parameter als Config-Objekt.

### 5.1 Grundverhalten

Die folgenden Anforderungen betreffen jedes Modul.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| MOD-01 | MUSS | Ein Modul erledigt seine Aufgabe unter Nutzung von Aktionen und kann zusätzliche eigene Methoden enthalten. |
| MOD-02 | MUSS | Ein Modul erhält die für die Aufgabe erforderlichen Parameter als Config-Objekt. |
| MOD-03 | MUSS | Module ohne erforderliche Konfiguration sind möglich; bei ihnen entfällt die Übergabe eines Config-Objekts. |
| MOD-04 | MUSS | Ein Modul legt die Konfigurationsdaten aus dem Config-Objekt in seinen Instanzvariablen ab. |
| MOD-05 | MUSS | Alle Module erben von einer gemeinsamen Elternklasse die gemeinsamen Methoden und Variablen zu Systemumgebung, Aufruf von Aktionen, Steuerung von Aktionen und Interaktion mit dem aufrufenden Prozess. |
| MOD-06 | MUSS | Module steuern ihre Aktionen über Parameter oder über das Setzen von Instanzvariablen. |
| MOD-07 | MUSS | Module tragen beschreibende Namen, aus denen ihr Typ erkennbar ist (z. B. Installationsmodul am Namen erkennbar). |

### 5.2 Konfigurationsdeklaration

Ein Modul macht nachvollziehbar sichtbar, welche Konfiguration es benötigt.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| MOD-08 | MUSS | Ein Modul nennt die benötigten Konfigurationswerte als Klassenattribut (Liste der Namen). |
| MOD-09 | MUSS | Ein Modul prüft beim Start das Vorhandensein der benötigten Konfigurationswerte und legt sie in seinen Instanzvariablen ab. |
| MOD-10 | MUSS | Ein Modul behandelt Pflicht- und Kann-Werte: ein fehlender Pflichtwert führt zum Fehler, ein fehlender Kann-Wert erhält einen Vorgabewert. |
| MOD-11 | KANN | Ein Modul enthält sinnfällige Vorgabewerte, wann immer möglich. |

### 5.3 Systemverändernde Module

Module, die das System verändern, müssen ihren Erfolg prüfen und rückgängig machen können.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| MOD-12 | MUSS | Ein Modul, das Veränderungen am System bewirkt, bietet einen Überprüfungsmodus, der den Erfolg seiner Aktionen und Eingriffe gezielt und vollständig prüft. |
| MOD-13 | MUSS | Ein Modul, das Veränderungen am System bewirkt, stellt einen Rollback-Mechanismus bereit. |
| MOD-14 | KANN | Ein systemveränderndes Modul kann bei erneutem Lauf einen bereits erfolgten Eingriff erkennen und nicht wiederholen (Idempotenz). Eine allgemeine Pflicht dazu besteht nicht. |

## 6. Konfiguration

Die Konfiguration ist die Schnittstelle zwischen Anwender und pifos. Sie wird über ein Config-Objekt von den Formaten der Konfigurationsquelle entkoppelt.

### 6.1 Config-Objekt

Das Config-Objekt vermittelt zwischen Konfigurationsquellen und Aufrufern.

Die Nummer KFG-03 ist nicht vergeben; sie forderte eine Klasse zur Deklaration einzelner Konfigurationseinträge, die mit der Vereinfachung der Modul-Deklaration auf reine Namenslisten entfällt.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| KFG-01 | MUSS | Eine Config-Klasse bildet die zentrale Schnittstelle zwischen Konfigurationen und den aufrufenden Programmen. |
| KFG-02 | MUSS | Die Config-Klasse stellt Methoden bereit, um dem Aufrufer Konfiguration in verschiedenen Formen zu liefern: einzelne Werte, Sektionen als dict oder list sowie sortierte und unsortierte Listen. |

### 6.2 Konfigurationsformate

Verschiedene Quellformate werden über je eigene Klassen angebunden.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| KFG-04 | MUSS | Für jede genutzte Konfigurationsart (z. B. ini, toml, json) gibt es eine eigene Klasse, die die Konfiguration standardisiert an die Config-Klasse übergibt. |
| KFG-05 | MUSS | Die Übergabe der Konfiguration an die Config-Klasse erfolgt im Regelfall als dict. |
| KFG-06 | MUSS | Zusätzlich ist die Übergabe der Konfiguration als raw möglich. |
| KFG-07 | KANN | Eine formatspezifische Konfigurationsklasse nutzt zum Einlesen oder Schreiben von Dateien die Aktionsklassen. |

### 6.3 Prüfung von Konfigurationsdaten

pifos prüft die Konfiguration nur formal, nicht inhaltlich.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| KFG-08 | MUSS | Eine inhaltliche Prüfung der Konfigurationsdaten findet nicht statt. |
| KFG-09 | KANN | Die Config-Klasse stellt grundlegende Prüfmuster bereit (z. B. ist leer, Wert existiert, gültige Mailadresse, ist Zahl, ist kommasepariert, ist Liste). |

## 7. Konfigurator

Der Konfigurator ist eine optionale Komponente, die mithilfe der Moduldeklarationen Konfigurationsdateien erstellt. Stellt pifos einen Konfigurator bereit, gelten die folgenden Pflichtanforderungen für ihn; ohne Konfigurator entfallen sie.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| KOR-01 | KANN | pifos stellt einen UI-Konfigurator bereit, der für ein oder mehrere Module Konfiguration erstellt. |
| KOR-02 | MUSS | Der Konfigurator nutzt die Konfigurationsdeklarationen der Module, um die erforderlichen Konfigurationseinträge und -werte zu bestimmen. |
| KOR-03 | MUSS | Der Konfigurator kann ein oder mehrere Module als Parameter erhalten. |
| KOR-04 | MUSS | Über Parameter ist festlegbar, ob bei mehreren Modulen die Reihenfolge in der Parameterliste verbindlich ist. |
| KOR-05 | MUSS | Über Parameter ist das Speicherformat festlegbar. |
| KOR-06 | MUSS | Über Parameter ist festlegbar, ob eine gemeinsame Datei für alle Module oder Einzeldateien je Modul erstellt werden; bei Einzeldateien gehört eine zentrale Steuerdatei für die Reihenfolge dazu. |
| KOR-07 | MUSS | Über Parameter ist der Ablageort der Dateien festlegbar. |
| KOR-08 | MUSS | Nicht gesetzte Parameter fragt der Konfigurator per Dialog ab. |

## 8. Aufruf und Steuerung

Der Aufrufer startet Module und tauscht mit ihnen über IPC Befehle und Meldungen aus.

### 8.1 Modulstart

Der Aufrufer ist für Beschaffung und Übergabe der Konfiguration zuständig.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| STR-01 | MUSS | Der Aufrufer startet ein Modul über IPC. |
| STR-02 | MUSS | Der Aufrufer beschafft die erforderlichen Konfigurationsdaten durch Instanziierung eines Config-Objekts und übergibt sie beim Start des Moduls. |

### 8.2 Bidirektionale Kommunikation

Aufrufer und Modul tauschen während der Ausführung Nachrichten in beide Richtungen aus.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| STR-03 | MUSS | Ein Modul kann nicht logging-relevante Nachrichten an den aufrufenden Prozess senden, damit dieser über den weiteren Ablauf entscheiden kann. |
| STR-04 | MUSS | Der Aufrufer kann Nachrichten an ein Modul senden, um Daten anzufordern (z. B. Variablenwerte) oder das Modul zu Aktivitäten aufzufordern. |

### 8.3 Abschluss und Nebenläufigkeit

Ein Modul meldet seinen Abschluss; der Aufrufer kann mehrere Module nebenläufig führen.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| STR-05 | MUSS | Ein Modul signalisiert seinen regulären Abschluss über einen Returncode. 0 bedeutet Erfolg, ein Wert ungleich 0 einen Fehler. Der Aufrufer wertet ihn aus. |
| STR-06 | MUSS | Der Aufrufer kann mehrere Module sequenziell oder parallel führen. |

## 9. Logging

Das Logging übernimmt der Aufrufer; Module und Aktionen führen kein eigenes Log.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| LOG-01 | MUSS | Das Logging nimmt ausschließlich der Aufrufer vor; Module und Aktionen erhalten keine eigene Logger-Umgebung. |
| LOG-02 | MUSS | Ein Modul entscheidet, welche Meldungen es per IPC an den Aufrufer weiterreicht; der Aufrufer entscheidet, welche davon er in das Logfile aufnimmt. |
| LOG-03 | MUSS | Das Logging unterscheidet die vier Stufen INFO, WARN, ERROR und CRITICAL; Module qualifizieren ihre Meldungen nach diesen Stufen. |
| LOG-04 | MUSS | Das Loglevel des Aufrufers ist einstellbar. |
| LOG-05 | MUSS | Der Aufrufer gibt das eingestellte Loglevel an die Module weiter. |

## 10. Ausnahmen

Aktionen und Module melden Fehler über Ausnahmen, die der Aufrufer erhält.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| EXC-01 | MUSS | Aktionen und Module erzeugen im Fehlerfall Ausnahmen. |
| EXC-02 | MUSS | Module leiten Ausnahmen entsprechend dem eingestellten Loglevel an den Aufrufer weiter. |
| EXC-03 | MUSS | Beendet sich ein Modul wegen eines als CRITICAL eingestuften Fehlers, stellt es vor dem Beenden sicher, dass die Ausnahme-Meldungen noch an den Aufrufer gelangen. |

## 11. Standardaufrufer

pifos stellt eine Basisklasse für Aufrufer bereit, die die gemeinsame Infrastruktur enthält.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| CAL-01 | MUSS | pifos stellt eine Aufrufer-Basisklasse bereit, von der konkrete Aufrufer (z. B. der Installer) erben. |
| CAL-02 | MUSS | Die Aufrufer-Basisklasse stellt Methoden bereit, um Modulprozesse zu starten, anzuhalten, fortzusetzen und zu beenden. |
| CAL-03 | MUSS | Die Aufrufer-Basisklasse stellt Methoden bereit, um über IPC Befehle an Module zu senden. |
| CAL-04 | MUSS | Die Aufrufer-Basisklasse stellt Methoden bereit, um über IPC Meldungen und Ergebnisse zu erhalten oder anzufordern. |
| CAL-05 | MUSS | Die Aufrufer-Basisklasse stellt Methoden bereit, um Logfiles zu führen. |
| CAL-06 | MUSS | Ein konkreter Aufrufer steuert nur seine Fachlogik und Oberfläche bei. |
| CAL-07 | MUSS | Die Aufrufer-Basisklasse bietet überschreibbare Leer- oder Standardmethoden, mit denen der konkrete Aufrufer auf den Ausgang eines Moduls (Erfolg, Fehler, Abbruch) reagiert. |

## 12. Bereitstellung

pifos wird mit den nötigen Bibliotheken ausgeliefert, damit auf dem Zielserver nichts nachinstalliert werden muss.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| BRS-01 | MUSS | Für die Bedienoberfläche werden die Bibliotheken Rich und questionary mitgeliefert. |
| BRS-02 | MUSS | Auf dem Zielserver muss für den Betrieb von pifos keine zusätzliche Komponente installiert werden. |

## 13. Sicherheit

pifos läuft auf einem gehärteten Linux-Server, führt Systembefehle aus und startet getrennte Prozesse über IPC. Die folgenden Anforderungen sichern Architektur und Bausteine ab. Grundlage ist `konv-scripting.md` mit der Python-Konkretisierung `konv-scripting-python.md`; der BSI IT-Grundschutz gilt als Mindeststandard.

Die Nummern SIC-10 und SIC-11 sind nicht vergeben; sie bezeichneten Prozessrechte-Anforderungen, die gestrichen wurden, weil pifos als Bausatz keine eigenen Prozessrechte hat. Die übrigen Nummern bleiben unverändert.

### 13.1 Eingabevalidierung an der Verwendungsstelle

Das Config-Objekt prüft Inhalte bewusst nicht (KFG-08). Werte, die sicherheitskritisch verwendet werden — als Argument eines Systembefehls oder als Dateipfad —, werden daher dort geprüft, wo sie so verwendet werden.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-01 | MUSS | Werte aus Konfiguration oder anderen externen Quellen, die als Argument eines Systembefehls oder als Dateipfad verwendet werden, werden vor dieser Verwendung auf Typ, Format und Wertebereich anhand einer Positivliste geprüft. |
| SIC-02 | MUSS | Die Prüfung liegt beim verwendenden Modul oder Aufrufer, da der Konfigurationsbaustein keine inhaltliche Prüfung vornimmt (KFG-08). |

### 13.2 Systembefehl-Aktion

Die generische Aktion für Systembefehle (AKT-08) ist die am stärksten exponierte Stelle.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-03 | MUSS | Die Systembefehl-Aktion führt Befehle ohne Shell aus. |
| SIC-04 | MUSS | Befehl und Argumente werden als Liste einzelner Elemente übergeben, nicht als zusammengesetzte Befehlszeichenkette. |
| SIC-05 | MUSS | Jede Befehlsausführung hat eine explizite Zeitgrenze. |
| SIC-06 | MUSS | Bei sicherheitsrelevanten Programmen wird der Programmpfad kontrolliert (absoluter Pfad oder kontrollierte Umgebung). |

### 13.3 IPC und Serialisierung

Aufrufer und Modul tauschen über IPC Daten zwischen getrennten Prozessen aus. Wird beim Empfang eine Deserialisierung verwendet, die Code ausführen kann, ist sie nur aus vertrauenswürdiger lokaler Quelle zulässig.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-07 | MUSS | Die IPC zwischen Aufrufer und Modulprozess erfolgt ausschließlich lokal, nicht über Netz. |
| SIC-08 | MUSS | Über IPC werden nur Daten innerhalb der Vertrauensdomäne des Aufrufers ausgetauscht; aus nicht vertrauenswürdiger Quelle wird nichts deserialisiert. |
| SIC-09 | KANN | Über IPC und als Config-Objekt übertragene Nutzdaten beschränken sich auf einfache Datentypen; ausführbare oder zustandsbehaftete Objekte werden nicht übertragen. |

### 13.4 Code-Baum des Kerns

Der Code-Baum des pifos-Kerns wird vor Veränderung geschützt. pifos ist ein Bausatz ohne eigene Prozessrechte; er läuft mit den Rechten des einbindenden Programms.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-12 | MUSS | Der pifos-Kern liegt als nur lesbarer Code-Baum vor (Eigentümer root, für Dienstkonten nicht schreibbar). |

### 13.5 safe-mode und Sicherungsort

Der safe-mode legt vor dateiverändernden Aktionen eine Sicherung an (AKT-06/07); deren Pfad und Rechte sind sicherheitsrelevant.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-13 | MUSS | Wird nach AKT-06/AKT-96 eine Sicherung angelegt, weitet diese die Zugriffsrechte gegenüber der Originaldatei nicht aus. |
| SIC-14 | MUSS | Wird nach AKT-06/AKT-96 eine Sicherung angelegt, wird der Sicherungspfad vorder Nutzung als Pfad geprüft. |
| SIC-15 | KANN | Prüfung und Schreiben der Sicherung erfolgen so, dass Manipulation über symbolische Verweise oder zeitliche Wettläufe zwischen Prüfung und Nutzung vermieden wird. |

### 13.6 Laden von Konfigurationsquellen

Beim Einlesen von Konfigurationsdateien sind Format und Größe zu kontrollieren.

Die Nummer SIC-16 ist nicht vergeben; sie forderte eine Pfadprüfung der Konfigurationsquelle. Da pifos mit den Rechten des Aufrufers lädt, regeln die Dateirechte den Zugriff; eine gesonderte Pfadbegrenzung wäre nur bei einer Rechtegrenze zwischen Pfad-Quelle und ladendem Prozess wirksam und ist für den Bausatz nicht gefordert.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-17 | MUSS | Konfigurationsdateien werden mit einem Parser eingelesen, der nur Daten verarbeitet; eine Deserialisierung, die Code ausführen kann, wird nicht verwendet. |
| SIC-18 | KANN | Beim Einlesen von Konfigurationsquellen gelten Größengrenzen. |

### 13.7 Sicheres Protokollieren

Der Aufrufer führt das Logfile (LOG-01) und protokolliert dabei Fremddaten, insbesondere stdout und stderr aufgerufener Befehle (AKT-02).

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-19 | MUSS | Fremddaten, die der Aufrufer protokolliert, werden vor dem Schreiben ins Logfile von Steuerzeichen, insbesondere Zeilenumbrüchen, befreit. |
| SIC-20 | MUSS | In Logmeldungen, Ausnahme-Texten und IPC-Meldungen erscheinen keine Geheimnisse im Klartext. |
| SIC-27 | MUSS | Das Logfile wird mit engen Rechten (`0600`) angelegt, da es sensible Daten (stdout/stderr aufgerufener Befehle, interne Pfade) enthält. |

### 13.8 Sicherer Zustand bei Fehlern und Abbruch

Bei Abbruch darf kein unsicherer Zustand verbleiben. Die erzwungene Beendigung bis SIGKILL kann einen Eingriff unvollständig hinterlassen.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-21 | MUSS | Bricht eine Aktion oder ein Modul ab, verbleibt kein undefinierter unsicherer Zustand; belegte Ressourcen werden freigegeben. |
| SIC-22 | MUSS | Nach einer erzwungenen Beendigung (SIGKILL) eines systemverändernden Moduls ist über den Überprüfungsmodus (MOD-12) erkennbar, ob der Eingriff vollständig, teilweise oder nicht erfolgte. |
| SIC-23 | MUSS | Fehlermeldungen nach außen sind allgemein gehalten; interne Pfade und Details gehen nur ins Log. |

### 13.9 Mitgelieferte Bibliotheken und Importpfad

pifos liefert Rich, questionary und deren Abhängigkeiten mit (BRS-01). Herkunft und Ladeweg sind abzusichern.

| ID | Verb. | Anforderung |
|----|-------|-------------|
| SIC-24 | MUSS | Die mitgelieferten Fremdbibliotheken stammen aus vertrauenswürdiger Quelle und sind über Prüfsummen (Hash-Pinning der `requirements.txt`) gegen Manipulation gesichert. |
| SIC-25 | MUSS | Die mitgelieferten Bibliotheken werden auf bekannte Schwachstellen geprüft und aktuell gehalten. |
| SIC-26 | MUSS | Der Importpfad wird so gesetzt, dass die mitgelieferten Bibliotheken eindeutig geladen werden und kein gleichnamiger Fremdcode untergeschoben werden kann. |

## Versionshistorie

| Version | Datum | Wer | Änderung |
|---------|-------|-----|----------|
| 0.01 | 2026-06-26 | macodix | Erstanlage: Anforderungen aus `docs/01_konzept.md` abgeleitet, gegliedert nach den pifos-Bausteinen, mit IDs und Verbindlichkeit (MUSS/KANN). |
| 0.02 | 2026-06-26 | macodix | Klärungen eingearbeitet: CAL-02 um Fortsetzen ergänzt; neu STR-05 (Abschluss über Returncode), STR-06 (sequenziell/parallel), CAL-07 (Reaktion auf Modulausgang), MOD-14 (Idempotenz modulabhängig). |
| 0.03 | 2026-06-27 | macodix | Kapitel 13 Sicherheit ergänzt (SIC-01 bis SIC-26, 23 MUSS / 3 KANN), Bereichskürzel SIC: Eingabevalidierung an der Verwendungsstelle, Systembefehl-Aktion, IPC/Serialisierung, Rechtekontext, safe-mode, Konfig-Laden, Protokollierung, Fehlerzustand, mitgelieferte Bibliotheken. |
| 0.04 | 2026-06-27 | macodix | Konsistenz: Inhaltsverzeichnis ohne Listen-Markup; Konfigurator-Pflichtanforderungen als bedingt gekennzeichnet (nur falls Konfigurator vorhanden); Implementierungsdetail (multiprocessing/pickle) aus Kapitel 13.3 entfernt. |
| 0.05 | 2026-06-27 | macodix | ÜBR-04 neu gefasst (Entscheidung Martin): direkter Zugriff auf öffentliche Attribute, `@property` nur bei Zugriffslogik, keine flächendeckenden getter/setter. |
| 0.06 | 2026-06-27 | macodix | Begriff korrigiert: MOD-04, MOD-06, MOD-09 von Klassenvariablen auf Instanzvariablen; SIC-01 „gegen … geprüft" zu „auf … anhand einer Positivliste geprüft". |
| 0.07 | 2026-06-29 | macodix | Rechte-Anforderungen korrigiert: SIC-10 und SIC-11 (Prozessrechte) gestrichen, da pifos als Bausatz keine eigenen Prozessrechte hat; Kapitel 13.4 auf den Code-Baum (SIC-12) fokussiert; neue SIC-27 (Logfile mit engen Rechten 0600) ergänzt. SIC-10/11 bleiben als Lücke unbesetzt. |
| 0.08 | 2026-06-29 | macodix | Hinweis in der Einleitung von Kapitel 13 ergänzt: SIC-10 und SIC-11 sind nicht vergeben (gestrichene Prozessrechte-Anforderungen). |
| 0.09 | 2026-06-29 | macodix | ÜBR-04 (Attributzugriff) von MUSS auf KANN herabgestuft und als Empfehlung gefasst — direkter Zugriff, `@property` optional bei Prüfung/Berechnung; Attributzugriff ist Stilfrage, keine Pflicht. |
| 0.10 | 2026-06-30 | macodix | Konfigurations-Deklaration vereinfacht (Entscheidung Martin): MOD-08 auf reine Namensliste, MOD-09 auf Vorhandensein, MOD-10 von Deklaration auf Modul-Verhalten umgestellt; KFG-03 (Klasse für einzelne Konfigurationseinträge) gestrichen, Nummer bleibt unbesetzt, Hinweis in Kapitel 6 ergänzt. |
| 0.11 | 2026-07-01 | macodix | SIC-16 (Pfadprüfung der Konfigurationsquelle) gestrichen (Entscheidung Martin) — ohne Rechtegrenze zwischen Pfad-Quelle und ladendem Prozess wirkungslos; Nummer bleibt unbesetzt, Hinweis in Kapitel 13.6 ergänzt, Einleitung angepasst. |
</content>
</invoke>
