"""Datei-Kopier-Aktion mit safe-mode für pifos.

Setzt AKT-06, AKT-07 (safe-mode und einstellbarer Sicherungsort)
sowie SIC-13, SIC-14, SIC-15 (Rechte, Pfadprüfung, TOCTOU) um.
"""

import contextlib
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import ClassVar

from pifos.action import Action
from pifos.errors import ActionError


def _fd_copy(src_fd: int, dst_fd: int) -> None:
    """Kopiert Inhalt von src_fd nach dst_fd in 64-KiB-Blöcken.

    Args:
        src_fd: Quelldeskriptor (lesend geöffnet).
        dst_fd: Zieldeskriptor (schreibend geöffnet).

    Raises:
        OSError: Bei Lese- oder Schreibfehler.
    """
    while True:
        chunk = os.read(src_fd, 65536)
        if not chunk:
            break
        os.write(dst_fd, chunk)


class CopyFileAction(Action):
    """Kopiert eine Datei von einer Quelle zu einem Ziel.

    Im safe-mode (Voreinstellung) wird eine bestehende Zieldatei ohne
    explizite Freigabe (overwrite=True) nicht überschrieben. Bei gesetzter
    Freigabe wird die Zieldatei vorher gesichert (AKT-06). Der Sicherungsort
    ist einstellbar (AKT-07). Die Sicherung weitet die Zugriffsrechte nicht
    aus (SIC-13); der Sicherungspfad wird geprüft (SIC-14); Prüfung und
    Schreiben sind gegen Symlink-Manipulation und TOCTOU abgesichert (SIC-15).

    Attributes:
        PARAMS: Parameternamen der Aktion.
        src: Quelldatei-Pfad.
        dst: Zieldatei-Pfad.
        safe_mode: Schützt bestehende Zieldatei; Voreinstellung True.
        backup_location: Verzeichnis für die Sicherung oder None (dann
            gleiches Verzeichnis wie Zieldatei).
        overwrite: Erlaubt das Überschreiben einer bestehenden Zieldatei
            im safe-mode; Sicherung wird angelegt. Voreinstellung False.

    Example:
        action = CopyFileAction("/etc/hosts", "/tmp/hosts.bak",
                                safe_mode=False)
        action.run()
    """

    PARAMS: ClassVar[list[str]] = [
        "src",
        "dst",
        "safe_mode",
        "backup_location",
        "overwrite",
    ]

    def __init__(
        self,
        src: str,
        dst: str,
        safe_mode: bool = True,
        backup_location: str | None = None,
        overwrite: bool = False,
    ) -> None:
        """Initialisiert die Datei-Kopier-Aktion.

        Args:
            src: Quelldatei-Pfad.
            dst: Zieldatei-Pfad.
            safe_mode: Bei True wird eine bestehende Zieldatei geschützt.
                Ist overwrite ebenfalls True, wird sie vor dem Überschreiben
                gesichert (AKT-06).
            backup_location: Verzeichnis für die Sicherungsdatei; None legt
                die Sicherung im Verzeichnis der Zieldatei ab (AKT-07).
            overwrite: Gibt das Überschreiben einer bestehenden Zieldatei
                explizit frei. Nur wirksam, wenn safe_mode=True.
        """
        super().__init__()
        self.src = src
        self.dst = dst
        self.safe_mode = safe_mode
        self.backup_location = backup_location
        self.overwrite = overwrite

    def run(self) -> str:
        """Kopiert die Quelldatei zur Zieldatei und liefert den Ausführungsstatus.

        Bei safe_mode=True und vorhandener Zieldatei ohne overwrite=True
        wird ActionError erzeugt. Mit overwrite=True wird die Zieldatei
        vorher gesichert. Das Kopieren erfolgt über eine Temp-Datei und
        einen atomaren Austausch.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Bei fehlendem safe-mode-Schutz, Sicherungsfehler
                oder Kopierfehler.
        """
        self.status = "running"
        try:
            src_path = Path(self.src)
            dst_path = Path(self.dst)

            if not src_path.exists():
                self.status = "failed"
                raise ActionError(f"Quelldatei nicht gefunden: {self.src!r}")

            if self.safe_mode and dst_path.exists():
                if not self.overwrite:
                    self.status = "failed"
                    raise ActionError(
                        f"Zieldatei vorhanden, Überschreiben nicht freigegeben:"
                        f" {self.dst!r}"
                    )
                self._backup(dst_path)

            self._copy(src_path, dst_path)
        except ActionError:
            if self.status != "failed":
                self.status = "failed"
            raise
        except OSError as exc:
            self.status = "failed"
            raise ActionError(f"Dateifehler beim Kopieren: {exc}") from exc

        self.status = "finished"
        return self.status

    def _backup(self, dst_path: Path) -> None:
        """Sichert dst_path vor dem Überschreiben.

        Öffnet die Zieldatei mit O_NOFOLLOW (SIC-15), legt die Sicherung
        exklusiv mit denselben Rechten an (SIC-13) und schreibt den Inhalt
        per Dateideskriptor (SIC-15).

        Args:
            dst_path: Zu sichernde Zieldatei.

        Raises:
            ActionError: Bei ungültigem Sicherungsort, Rechteproblem,
                Symlink-Erkennung oder Schreibfehler.
        """
        # Sicherungsort prüfen (SIC-14)
        if self.backup_location is not None:
            backup_dir = Path(self.backup_location).resolve()
            if not backup_dir.is_dir():
                raise ActionError(
                    f"Sicherungsort ist kein Verzeichnis: {self.backup_location!r}"
                )
        else:
            backup_dir = dst_path.resolve().parent

        backup_path = backup_dir / (dst_path.name + ".bak")

        # Rechte der Originaldatei (SIC-13: nicht ausweiten)
        try:
            orig_mode = stat.S_IMODE(os.lstat(dst_path).st_mode)
        except OSError as exc:
            raise ActionError(f"Rechte der Zieldatei nicht lesbar: {exc}") from exc

        # Bestehende Zieldatei mit O_NOFOLLOW öffnen — erkennt Symlink-
        # Substitution zwischen Prüfung und Öffnen (SIC-15)
        try:
            src_fd = os.open(str(dst_path), os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            raise ActionError(f"Zieldatei für Sicherung nicht lesbar: {exc}") from exc

        # Sicherungsdatei exklusiv anlegen: O_EXCL (atomar, SIC-15),
        # O_NOFOLLOW (SIC-15), gleiche Rechte wie Original (SIC-13)
        try:
            bak_fd = os.open(
                str(backup_path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                orig_mode,
            )
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.close(src_fd)
            raise ActionError(
                f"Sicherungsdatei kann nicht angelegt werden"
                f" {str(backup_path)!r}: {exc}"
            ) from exc

        copy_error: OSError | None = None
        try:
            _fd_copy(src_fd, bak_fd)
        except OSError as exc:
            copy_error = exc
        finally:
            with contextlib.suppress(OSError):
                os.close(bak_fd)
            with contextlib.suppress(OSError):
                os.close(src_fd)
            if copy_error is not None:
                with contextlib.suppress(OSError):
                    backup_path.unlink(missing_ok=True)

        if copy_error is not None:
            raise ActionError(
                f"Fehler beim Schreiben der Sicherung: {copy_error}"
            ) from copy_error

    def _copy(self, src_path: Path, dst_path: Path) -> None:
        """Kopiert src_path nach dst_path über eine Temp-Datei (atomar).

        Legt eine Temp-Datei im Verzeichnis von dst_path an, kopiert den
        Inhalt samt Rechten und tauscht die Datei atomar aus (os.replace).
        Bei Fehler wird die Temp-Datei entfernt.

        Args:
            src_path: Quelldatei.
            dst_path: Zieldatei.

        Raises:
            ActionError: Bei Temp-Datei-, Kopier- oder Umbenennungsfehler.
        """
        dst_dir = dst_path.parent
        try:
            tmp_fd, tmp_str = tempfile.mkstemp(dir=str(dst_dir))
        except OSError as exc:
            raise ActionError(
                f"Temp-Datei konnte nicht erstellt werden: {exc}"
            ) from exc

        tmp_path = Path(tmp_str)
        fd_owned_by_fdopen = False
        try:
            with os.fdopen(tmp_fd, "wb") as tmp_file:
                fd_owned_by_fdopen = True
                with open(src_path, "rb") as src_file:
                    shutil.copyfileobj(src_file, tmp_file)
            src_mode = stat.S_IMODE(os.lstat(src_path).st_mode)
            os.chmod(tmp_str, src_mode)
            os.replace(tmp_str, str(dst_path))
        except OSError as exc:
            if not fd_owned_by_fdopen:
                with contextlib.suppress(OSError):
                    os.close(tmp_fd)
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
            raise ActionError(f"Fehler beim Kopieren: {exc}") from exc
