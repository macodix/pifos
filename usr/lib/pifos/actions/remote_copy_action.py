"""Fernkopier-Aktion für pifos.

Kopiert Dateien/Verzeichnisse zwischen dem lokalen System und einem entfernten
Host — wahlweise mit ``scp`` oder ``rsync`` (per Konfiguration umschaltbar).
Programm und Zusatzoptionen kommen aus der Konfiguration des aufrufenden
Moduls; die Aktion setzt kein bestimmtes Paket voraus und installiert nichts.
Sie nutzt nur die Standardbibliothek (``subprocess``/``shutil``).

Setzt SIC-03 (kein Shell-Aufruf), SIC-04 (Argumentliste) und SIC-05 (explizite
Zeitgrenze) um; Pfade/Adressen werden gegen Zeilenumbruch- und Options-Injektion
geprüft, ein ``--`` trennt Optionen von Pfaden.
"""

import shutil
import subprocess
from typing import ClassVar

from pifos.action import Action
from pifos.errors import ActionError


class RemoteCopyAction(Action):
    """Kopiert per scp oder rsync zwischen lokal und einem entfernten Host.

    ``direction`` legt die Richtung fest: ``upload`` kopiert lokale ``sources``
    nach ``destination`` auf dem Host, ``download`` kopiert entfernte ``sources``
    vom Host nach lokal ``destination``. Das Werkzeug (``tool``: ``scp`` oder
    ``rsync``) und optional dessen Pfad (``binary``) sowie Zusatzoptionen
    (``extra_options``) kommen aus der Konfiguration; die Aktion prüft nur, ob
    das Programm vorhanden ist, und installiert nichts.

    Der SSH-Zugang (``port``, ``identity_file``) wird werkzeuggerecht gesetzt:
    bei scp über ``-P``/``-i``, bei rsync über ``-e "ssh …"``.

    Die Aktion prüft ihre Parameter nicht fachlich (Sache des aufrufenden
    Moduls), wehrt aber Zeilenumbrüche in Adress-/Pfadwerten und führende ``-``
    in Pfaden ab (Options-Injektion).

    Attributes:
        PARAMS: Parameternamen der Aktion.
        tool: "scp" oder "rsync".
        sources: Quellpfade (lokal bei upload, entfernt bei download).
        destination: Zielpfad (entfernt bei upload, lokal bei download).
        host: Entfernter Host.
        direction: "upload" oder "download".
        user: Anmeldename auf dem Host oder None.
        port: SSH-Port oder None.
        identity_file: SSH-Schlüsseldatei oder None.
        recursive: Verzeichnisse rekursiv kopieren (-r).
        extra_options: Zusätzliche Werkzeugoptionen oder None.
        timeout: Zeitgrenze in Sekunden.
        binary: Pfad/Name des Programms oder None (dann tool-Name).
        stdout: Standardausgabe des Programms nach run().
        stderr: Fehlerausgabe des Programms nach run().
        returncode: Rückgabewert des Programms nach run(); -1 vor Ausführung.

    Example:
        action = RemoteCopyAction(
            "rsync", ["/etc/hosts"], "/tmp/", "server.example.org",
            user="deploy", port=22, recursive=True,
        )
        action.run()
    """

    PARAMS: ClassVar[list[str]] = [
        "tool",
        "sources",
        "destination",
        "host",
        "direction",
        "user",
        "port",
        "identity_file",
        "recursive",
        "extra_options",
        "timeout",
        "binary",
    ]

    def __init__(
        self,
        tool: str,
        sources: list[str],
        destination: str,
        host: str,
        direction: str = "upload",
        user: str | None = None,
        port: int | None = None,
        identity_file: str | None = None,
        recursive: bool = False,
        extra_options: list[str] | None = None,
        timeout: float = 300.0,
        binary: str | None = None,
    ) -> None:
        """Initialisiert die Fernkopier-Aktion (Beschreibung siehe Klasse)."""
        super().__init__()
        self.tool = tool
        self.sources = sources
        self.destination = destination
        self.host = host
        self.direction = direction
        self.user = user
        self.port = port
        self.identity_file = identity_file
        self.recursive = recursive
        self.extra_options = extra_options
        self.timeout = timeout
        self.binary = binary
        self.stdout: str = ""
        self.stderr: str = ""
        self.returncode: int = -1

    # --- Hilfen ---------------------------------------------------------

    def _userhost(self) -> str:
        """Liefert ``[user@]host`` für die entfernte Seite."""
        return f"{self.user}@{self.host}" if self.user else self.host

    def _remote(self, path: str) -> str:
        """Liefert die entfernte Ortsangabe ``[user@]host:path``."""
        return f"{self._userhost()}:{path}"

    def _guard_injection(self) -> None:
        """Wehrt Zeilenumbrüche in Adress-/Pfadwerten ab (Injektionsschutz).

        Raises:
            ActionError: Bei Zeilenumbruch in Host, Benutzer, Pfad oder
                Schlüsseldatei.
        """
        werte = [
            ("Host", self.host),
            ("Benutzer", self.user or ""),
            ("Zielpfad", self.destination),
            ("Schlüsseldatei", self.identity_file or ""),
            *(("Quellpfad", s) for s in self.sources),
        ]
        for feld, wert in werte:
            if "\n" in wert or "\r" in wert:
                raise ActionError(f"Zeilenumbruch in {feld} nicht erlaubt: {wert!r}")

    @staticmethod
    def _guard_option_like(pfade: list[str]) -> None:
        """Wehrt Pfade mit führendem '-' ab (Options-Injektion)."""
        for pfad in pfade:
            if pfad.startswith("-"):
                raise ActionError(f"Pfad darf nicht mit '-' beginnen: {pfad!r}")

    def _ssh_transport(self) -> str | None:
        """Baut den rsync-SSH-Transport ``ssh …`` aus port/identity oder None."""
        if self.port is None and self.identity_file is None:
            return None
        parts = ["ssh"]
        if self.port is not None:
            parts += ["-p", str(self.port)]
        if self.identity_file is not None:
            parts += ["-i", self.identity_file]
        return " ".join(parts)

    def _local_and_remote(self, binary: str) -> list[str]:
        """Baut die Pfad-Argumente je nach Richtung.

        upload: lokale Quellen → entferntes Ziel.
        download: entfernte Quellen → lokales Ziel.
        """
        if self.direction == "upload":
            self._guard_option_like(self.sources)
            return [*self.sources, self._remote(self.destination)]
        remote_sources = [self._remote(s) for s in self.sources]
        self._guard_option_like([self.destination])
        return [*remote_sources, self.destination]

    def _build_command(self, binary: str) -> list[str]:
        """Baut die vollständige Befehlsliste für das gewählte Werkzeug.

        Raises:
            ActionError: Bei unbekanntem tool oder unbekannter direction.
        """
        if self.direction not in ("upload", "download"):
            raise ActionError(f"unbekannte direction: {self.direction!r}")
        options: list[str] = []
        if self.tool == "scp":
            if self.port is not None:
                options += ["-P", str(self.port)]
            if self.identity_file is not None:
                options += ["-i", self.identity_file]
            if self.recursive:
                options += ["-r"]
        elif self.tool == "rsync":
            if self.recursive:
                options += ["-r"]
            transport = self._ssh_transport()
            if transport is not None:
                options += ["-e", transport]
        else:
            raise ActionError(f"unbekanntes tool: {self.tool!r}")
        options += self.extra_options or []
        return [binary, *options, "--", *self._local_and_remote(binary)]

    def _store_output(
        self, stdout_b: bytes, stderr_b: bytes, returncode: int | None
    ) -> None:
        """Legt Ausgaben und Rückgabewert des Prozesses ab."""
        self.stdout = stdout_b.decode("utf-8", errors="replace")
        self.stderr = stderr_b.decode("utf-8", errors="replace")
        self.returncode = returncode if returncode is not None else -1

    def _run(self, command: list[str]) -> None:
        """Startet das Kopierprogramm und wertet das Ergebnis aus.

        Raises:
            ActionError: Bei Startfehler, Zeitüberschreitung oder Rückgabewert
                ungleich 0.
        """
        try:
            with subprocess.Popen(
                command,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as proc:
                try:
                    out_b, err_b = proc.communicate(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    out_b, err_b = proc.communicate()
                    self._store_output(out_b, err_b, proc.returncode)
                    raise ActionError(
                        f"Zeitgrenze ({self.timeout}s) überschritten: {command[0]!r}"
                    ) from None
                self._store_output(out_b, err_b, proc.returncode)
                if self.returncode != 0:
                    raise ActionError(
                        f"{self.tool} {command[0]!r} endete mit Code"
                        f" {self.returncode}; stderr: {self.stderr.strip()!r}"
                    )
        except OSError as exc:
            raise ActionError(
                f"Kopierprogramm konnte nicht gestartet werden: {exc}"
            ) from exc

    def run(self) -> str:
        """Baut den Befehl und führt die Fernkopie aus.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Bei unbekanntem tool/direction, Injektionsversuch,
                fehlendem Programm oder Fehler beim Kopieren.
        """
        self.status = "running"
        try:
            self._guard_injection()
            resolved = shutil.which(self.binary or self.tool)
            if resolved is None:
                raise ActionError(
                    f"Kopierprogramm nicht vorhanden: {self.binary or self.tool!r}"
                )
            self._run(self._build_command(resolved))
        except ActionError:
            self.status = "failed"
            raise
        self.status = "finished"
        return self.status
