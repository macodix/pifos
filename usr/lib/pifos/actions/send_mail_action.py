"""Mailversand-Aktion für pifos.

Versendet eine Mail wahlweise über ein lokales Versandprogramm oder per SMTP.
Der Transport (``local`` oder ``smtp``) und beim lokalen Weg das Programm und
sein Aufrufstil kommen aus der Konfiguration des aufrufenden Moduls — die
Aktion setzt kein bestimmtes Paket voraus und installiert nichts. Sie nutzt nur
die Standardbibliothek (``smtplib``/``email``/``subprocess``).

Lokaler Weg, zwei Stile:
- ``sendmail``: volle MIME-Nachricht (mit Anhängen) über die Standardeingabe an
  ein sendmail-kompatibles Programm; Empfänger als Argumente.
- ``mail``: Betreff über ``-s``, cc über ``-c``, bcc über ``-b``, Anhänge über
  ``-a`` (mailx-Konvention), Empfänger als Argumente, Text über die
  Standardeingabe; die Nachricht baut das Programm.

Setzt SIC-03 (kein Shell-Aufruf), SIC-04 (Argumentliste) und SIC-05 (explizite
Zeitgrenze) um; Adress-/Kopfzeilen werden gegen Zeilenumbruch- und
Options-Injektion geprüft.
"""

import mimetypes
import shutil
import smtplib
import subprocess
from email.message import EmailMessage
from pathlib import Path
from typing import ClassVar

from pifos.action import Action
from pifos.errors import ActionError


class SendMailAction(Action):
    """Versendet eine Mail über ein lokales Programm (sendmail/mail) oder SMTP.

    Aufbau der Nachricht: Absender, Empfänger, Betreff, Klartext sowie optionale
    Dateianhänge und cc/bcc. bcc erscheint nicht in den Kopfzeilen, geht aber in
    die Empfänger ein.

    Der Transport wird über ``transport`` gewählt (``local`` oder ``smtp``). Beim
    lokalen Weg benennt die Konfiguration Programm (``mailer``) und Stil
    (``mailer_style``); die Aktion prüft nur, ob das Programm vorhanden ist, und
    installiert nichts.

    Die Aktion prüft ihre Parameter nicht fachlich (Sache des aufrufenden
    Moduls), wehrt aber Zeilenumbrüche in Adress-/Kopfzeilen und führende ``-``
    in Empfängeradressen ab (Kopf- bzw. Options-Injektion).

    Attributes:
        PARAMS: Parameternamen der Aktion.
        sender: Absenderadresse (Envelope-From und From-Kopfzeile).
        recipients: Empfängerliste (To).
        subject: Betreff.
        body: Klartext-Nachrichtentext.
        transport: "local" oder "smtp".
        cc: Kopie-Empfänger oder None.
        bcc: Blindkopie-Empfänger oder None (nicht in Kopfzeilen).
        attachments: Liste von Dateipfaden als Anhänge oder None.
        timeout: Zeitgrenze in Sekunden (lokaler Prozess bzw. SMTP-Verbindung).
        mailer: Pfad/Name des lokalen Versandprogramms (transport="local").
        mailer_style: "sendmail" oder "mail".
        smtp_host: SMTP-Server (transport="smtp") oder None.
        smtp_port: SMTP-Port.
        smtp_security: "none", "starttls" oder "ssl".
        smtp_user: Anmeldename oder None (keine Anmeldung).
        smtp_password: Anmeldekennwort oder None.
        stdout: Standardausgabe des lokalen Programms nach run().
        stderr: Fehlerausgabe des lokalen Programms nach run().
        returncode: Rückgabewert des lokalen Programms nach run(); -1, solange
            nicht lokal ausgeführt.

    Example:
        action = SendMailAction(
            "root@example.org", ["admin@example.org"], "Bericht", "Text\\n",
            transport="local", mailer="/usr/sbin/sendmail", mailer_style="sendmail",
        )
        action.run()
    """

    PARAMS: ClassVar[list[str]] = [
        "sender",
        "recipients",
        "subject",
        "body",
        "transport",
        "cc",
        "bcc",
        "attachments",
        "timeout",
        "mailer",
        "mailer_style",
        "smtp_host",
        "smtp_port",
        "smtp_security",
        "smtp_user",
        "smtp_password",
    ]

    def __init__(
        self,
        sender: str,
        recipients: list[str],
        subject: str,
        body: str,
        transport: str = "local",
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[str] | None = None,
        timeout: float = 30.0,
        mailer: str = "/usr/sbin/sendmail",
        mailer_style: str = "sendmail",
        smtp_host: str | None = None,
        smtp_port: int = 25,
        smtp_security: str = "none",
        smtp_user: str | None = None,
        smtp_password: str | None = None,
    ) -> None:
        """Initialisiert die Mailversand-Aktion (Beschreibung siehe Klasse)."""
        super().__init__()
        self.sender = sender
        self.recipients = recipients
        self.subject = subject
        self.body = body
        self.transport = transport
        self.cc = cc
        self.bcc = bcc
        self.attachments = attachments
        self.timeout = timeout
        self.mailer = mailer
        self.mailer_style = mailer_style
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_security = smtp_security
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.stdout: str = ""
        self.stderr: str = ""
        self.returncode: int = -1

    # --- Hilfen ---------------------------------------------------------

    def _envelope_recipients(self) -> list[str]:
        """Liefert alle Empfänger für den Umschlag (To + cc + bcc)."""
        return [*self.recipients, *(self.cc or []), *(self.bcc or [])]

    def _guard_injection(self) -> None:
        """Wehrt Zeilenumbrüche in Kopf-/Adresswerten ab (Injektionsschutz).

        Raises:
            ActionError: Bei Zeilenumbruch in Absender, Betreff, einer Adresse
                oder einem Anhangspfad.
        """
        werte = [
            ("Absender", self.sender),
            ("Betreff", self.subject),
            *(("Empfänger", r) for r in self.recipients),
            *(("cc", r) for r in self.cc or []),
            *(("bcc", r) for r in self.bcc or []),
            *(("Anhang", a) for a in self.attachments or []),
        ]
        for feld, wert in werte:
            if "\n" in wert or "\r" in wert:
                raise ActionError(f"Zeilenumbruch in {feld} nicht erlaubt: {wert!r}")

    @staticmethod
    def _guard_option_like(adressen: list[str]) -> None:
        """Wehrt Empfängeradressen mit führendem '-' ab (Options-Injektion)."""
        for adr in adressen:
            if adr.startswith("-"):
                raise ActionError(
                    f"Empfängeradresse darf nicht mit '-' beginnen: {adr!r}"
                )

    def _build_message(self) -> EmailMessage:
        """Baut die MIME-Nachricht inkl. Anhänge; bcc bleibt kopfzeilenlos.

        Raises:
            ActionError: Wenn ein Anhang nicht gelesen werden kann.
        """
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        if self.cc:
            msg["Cc"] = ", ".join(self.cc)
        msg["Subject"] = self.subject
        msg.set_content(self.body)

        for pfad in self.attachments or []:
            p = Path(pfad)
            try:
                data = p.read_bytes()
            except OSError as exc:
                raise ActionError(f"Anhang nicht lesbar: {pfad!r} ({exc})") from exc
            ctype, _ = mimetypes.guess_type(p.name)
            if ctype and "/" in ctype:
                maintype, subtype = ctype.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"
            msg.add_attachment(
                data, maintype=maintype, subtype=subtype, filename=p.name
            )
        return msg

    def _store_output(
        self, stdout_b: bytes, stderr_b: bytes, returncode: int | None
    ) -> None:
        """Legt Ausgaben und Rückgabewert des lokalen Prozesses ab."""
        self.stdout = stdout_b.decode("utf-8", errors="replace")
        self.stderr = stderr_b.decode("utf-8", errors="replace")
        self.returncode = returncode if returncode is not None else -1

    def _run_mailer(self, command: list[str], payload: bytes) -> None:
        """Startet das lokale Versandprogramm und übergibt payload an stdin.

        Raises:
            ActionError: Bei Startfehler, Zeitüberschreitung oder Rückgabewert
                ungleich 0.
        """
        try:
            with subprocess.Popen(
                command,
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as proc:
                try:
                    out_b, err_b = proc.communicate(input=payload, timeout=self.timeout)
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
                        f"Versand mit {command[0]!r} endete mit Code"
                        f" {self.returncode}; stderr: {self.stderr.strip()!r}"
                    )
        except OSError as exc:
            raise ActionError(
                f"Versandprogramm konnte nicht gestartet werden: {exc}"
            ) from exc

    # --- Transporte -----------------------------------------------------

    def _send_local(self) -> None:
        """Versendet über das konfigurierte lokale Programm im gewählten Stil.

        Raises:
            ActionError: Wenn das Programm fehlt, der Stil unbekannt ist oder
                die Übergabe scheitert.
        """
        resolved = shutil.which(self.mailer)
        if resolved is None:
            raise ActionError(f"Versandprogramm nicht vorhanden: {self.mailer!r}")

        if self.mailer_style == "sendmail":
            envelope = self._envelope_recipients()
            self._guard_option_like(envelope)
            command = [resolved, "-i", "-f", self.sender, "--", *envelope]
            self._run_mailer(command, self._build_message().as_bytes())
        elif self.mailer_style == "mail":
            self._guard_option_like(self.recipients)
            command = [resolved, "-s", self.subject]
            if self.cc:
                command += ["-c", ",".join(self.cc)]
            if self.bcc:
                command += ["-b", ",".join(self.bcc)]
            for att in self.attachments or []:
                command += ["-a", att]
            command += [*self.recipients]
            self._run_mailer(command, self.body.encode("utf-8"))
        else:
            raise ActionError(f"unbekannter mailer_style: {self.mailer_style!r}")

    def _send_smtp(self) -> None:
        """Stellt die Nachricht über einen SMTP-Server zu.

        Raises:
            ActionError: Wenn smtp_host fehlt, smtp_security unbekannt ist oder
                die Zustellung scheitert.
        """
        if not self.smtp_host:
            raise ActionError("transport='smtp' erfordert smtp_host")
        if self.smtp_security not in ("none", "starttls", "ssl"):
            raise ActionError(f"unbekannte smtp_security: {self.smtp_security!r}")
        envelope = self._envelope_recipients()
        msg = self._build_message()
        try:
            server: smtplib.SMTP
            if self.smtp_security == "ssl":
                server = smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, timeout=self.timeout
                )
            else:
                server = smtplib.SMTP(
                    self.smtp_host, self.smtp_port, timeout=self.timeout
                )
            with server:
                if self.smtp_security == "starttls":
                    server.starttls()
                if self.smtp_user is not None:
                    server.login(self.smtp_user, self.smtp_password or "")
                server.send_message(msg, from_addr=self.sender, to_addrs=envelope)
        except (OSError, smtplib.SMTPException) as exc:
            raise ActionError(f"SMTP-Zustellung fehlgeschlagen: {exc}") from exc

    def run(self) -> str:
        """Baut die Nachricht und stellt sie über den gewählten Transport zu.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Bei unbekanntem Transport, Injektionsversuch oder Fehler
                beim Bauen bzw. Zustellen der Nachricht.
        """
        self.status = "running"
        try:
            self._guard_injection()
            if self.transport == "local":
                self._send_local()
            elif self.transport == "smtp":
                self._send_smtp()
            else:
                raise ActionError(f"unbekannter Transport: {self.transport!r}")
        except ActionError:
            self.status = "failed"
            raise
        self.status = "finished"
        return self.status
