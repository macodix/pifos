"""Konkretes Datei-Kopier-Modul als Testmodul für den pifos-Bausatz.

CopyFileModule dient ausschließlich dem End-to-End-Test und zeigt das
Zusammenspiel von Module, CopyFileAction und IPC.
"""

from multiprocessing.connection import Connection
from pathlib import Path
from typing import ClassVar

from pifos.actions.copy_file_action import CopyFileAction
from pifos.ipc import LogLevel
from pifos.module import Module


class CopyFileModule(Module):
    """Kopiert eine Datei von source nach target.

    Liest Quell- und Zielpfad aus der Konfiguration, führt CopyFileAction
    aus und meldet das Ergebnis per IPC an den Aufrufer.

    Attributes:
        CONFIG: Benötigte Konfigurationswerte.
        source: Quelldatei-Pfad; wird durch check_config gesetzt.
        target: Zieldatei-Pfad; wird durch check_config gesetzt.

    Example:
        cfg = Config()
        cfg.load_dict({"source": "/etc/hosts", "target": "/tmp/hosts.bak"})
        handle = caller.start_module(CopyFileModule, cfg)
        caller.send_command(handle, "start")
    """

    CONFIG: ClassVar[list[str]] = ["source", "target"]

    def __init__(self, conn: Connection, loglevel: LogLevel) -> None:
        """Initialisiert das Modul mit IPC-Verbindung und Logstufe.

        Args:
            conn: Pipe-Verbindung zum Aufrufer.
            loglevel: Logstufe, weitergegeben vom Aufrufer.
        """
        super().__init__(conn=conn, loglevel=loglevel)
        self.source: str = ""
        self.target: str = ""

    def start(self) -> int:
        """Kopiert source nach target und meldet das Ergebnis per IPC.

        Erzeugt eine CopyFileAction ohne safe-mode, damit eine vorhandene
        Zieldatei überschrieben werden kann. Meldet Erfolg oder Fehler
        an den Aufrufer.

        Returns:
            0 bei Erfolg, 1 bei Fehler.
        """
        action = CopyFileAction(src=self.source, dst=self.target, safe_mode=False)
        rc = self.run_action(action)
        if rc == 0:
            self.send_message(
                LogLevel.INFO,
                "copy_done",
                f"Datei kopiert nach {self.target!r}",
            )
        else:
            self.send_message(
                LogLevel.ERROR,
                "copy_failed",
                f"Kopieren nach {self.target!r} fehlgeschlagen",
            )
        return rc

    def check(self) -> bool | None:
        """Prüft ob Zieldatei existiert und inhaltlich mit Quelldatei übereinstimmt.

        Returns:
            True, wenn Zieldatei vorhanden und Inhalt identisch;
            False sonst.
        """
        src = Path(self.source)
        dst = Path(self.target)
        if not dst.exists():
            return False
        try:
            return dst.read_bytes() == src.read_bytes()
        except OSError:
            return False

    def rollback(self) -> bool | None:
        """Entfernt die angelegte Zieldatei.

        Returns:
            True, wenn die Datei entfernt wurde oder bereits fehlte;
            False bei Fehler.
        """
        dst = Path(self.target)
        if not dst.exists():
            return True
        try:
            dst.unlink()
            return True
        except OSError:
            return False
