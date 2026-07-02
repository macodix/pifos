"""Tar-Archiv-Extraktions-Aktion für pifos.

Setzt SIC-13, SIC-14, SIC-15 sinngemäß für die Extraktion um:
ausschließlich über tarfile mit dem Extraktionsfilter "data" (PEP 706),
der Pfadausbruch, absolute Pfade, Symlink-Angriffe und Rechteausweitung
beim Entpacken abwehrt.
"""

import tarfile
from pathlib import Path
from typing import ClassVar

from pifos.action import Action
from pifos.errors import ActionError


class UntarAction(Action):
    """Entpackt ein tar-Archiv in ein bestehendes Zielverzeichnis.

    Die Komprimierung (gzip oder unkomprimiert) wird automatisch erkannt
    (tarfile-Lesemodus "r:*"). Das Zielverzeichnis muss existieren, die
    Aktion legt es nicht an.

    Die Extraktion läuft ausschließlich über tarfile.extractall mit dem
    Extraktionsfilter filter="data" (PEP 706, verfügbar ab Python 3.12).
    Der Filter weist absolute Pfade, Pfadausbruch aus dem Zielverzeichnis,
    Gerätedateien, Symlink-Angriffe auf Pfade außerhalb des Ziels und eine
    Rechteausweitung zurück und bricht die Extraktion mit einem Fehler ab.

    Ohne overwrite=True (Voreinstellung) wird vor der Extraktion geprüft,
    ob eine Archiv-Datei (kein Verzeichnis) im Zielverzeichnis bereits
    existiert; trifft das zu, wird ActionError erzeugt und nichts entpackt.
    Mit overwrite=True werden bestehende Dateien überschrieben. Es wird
    keine Sicherung einzelner Dateien angelegt (kein safe-mode-Backup).

    Attributes:
        PARAMS: Parameternamen der Aktion.
        src: Pfad des Archivs.
        dst_dir: Zielverzeichnis; muss existieren.
        overwrite: Erlaubt das Überschreiben bestehender Dateien im
            Zielverzeichnis. Voreinstellung False.

    Example:
        action = UntarAction("/var/backups/ssh.tar.gz", "/restore/ssh")
        action.run()
    """

    PARAMS: ClassVar[list[str]] = ["src", "dst_dir", "overwrite"]

    def __init__(self, src: str, dst_dir: str, overwrite: bool = False) -> None:
        """Initialisiert die Tar-Archiv-Extraktions-Aktion.

        Args:
            src: Pfad des zu entpackenden Archivs.
            dst_dir: Zielverzeichnis. Muss existieren.
            overwrite: Erlaubt das Überschreiben bestehender Dateien im
                Zielverzeichnis. Voreinstellung False.
        """
        super().__init__()
        self.src = src
        self.dst_dir = dst_dir
        self.overwrite = overwrite

    def run(self) -> str:
        """Entpackt das Archiv und liefert den Ausführungsstatus.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Bei fehlendem Archiv, fehlendem Zielverzeichnis,
                Dateikollision ohne overwrite=True oder Extraktionsfehler
                (u. a. bei Verstoß gegen den Extraktionsfilter "data").
        """
        self.status = "running"
        try:
            src_path = Path(self.src)
            dst_path = Path(self.dst_dir)

            if not src_path.exists():
                self.status = "failed"
                raise ActionError(f"Archiv nicht gefunden: {self.src!r}")
            if not dst_path.is_dir():
                self.status = "failed"
                raise ActionError(f"Zielverzeichnis nicht gefunden: {self.dst_dir!r}")

            self._extract(src_path, dst_path)
        except ActionError:
            if self.status != "failed":
                self.status = "failed"
            raise
        except OSError as exc:
            self.status = "failed"
            raise ActionError(f"Dateifehler beim Entpacken: {exc}") from exc
        except tarfile.TarError as exc:
            self.status = "failed"
            raise ActionError(f"Fehler beim Entpacken: {exc}") from exc

        self.status = "finished"
        return self.status

    def _extract(self, src_path: Path, dst_path: Path) -> None:
        """Prüft auf Kollisionen und entpackt das Archiv mit filter="data".

        Args:
            src_path: Archiv.
            dst_path: Zielverzeichnis.

        Raises:
            ActionError: Bei Dateikollision ohne overwrite=True.
            tarfile.TarError: Bei Verstoß gegen den Extraktionsfilter oder
                sonstigem Extraktionsfehler.
        """
        with tarfile.open(str(src_path), mode="r:*") as tar:
            members = tar.getmembers()
            if not self.overwrite:
                collisions = [
                    member.name
                    for member in members
                    if not member.isdir()
                    and (
                        (dst_path / member.name).exists()
                        or (dst_path / member.name).is_symlink()
                    )
                ]
                if collisions:
                    raise ActionError(f"Zieldateien bereits vorhanden: {collisions!r}")
            tar.extractall(path=str(dst_path), filter="data")
