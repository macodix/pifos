"""Verzeichnis-Anlege-Aktion für pifos.

Setzt SIC-13 (Rechte nicht ausweiten, exakte Rechtevergabe unabhängig
vom umask) um.
"""

import os
from pathlib import Path
from typing import ClassVar

from pifos.action import Action
from pifos.errors import ActionError


class MakeDirAction(Action):
    """Legt ein Verzeichnis an.

    Existiert path bereits als Verzeichnis (kein Symlink), ist die Aktion
    idempotent: keine Änderung, Status finished, die bestehenden Rechte
    bleiben unangetastet — auch wenn sie von mode abweichen. Existiert
    path bereits als Datei oder als Symlink (unabhängig von dessen Ziel),
    wird ActionError erzeugt; ein Symlink wird nie transparent wie ein
    Verzeichnis behandelt.

    mode wird über os.chmod nach dem Anlegen explizit gesetzt (nicht nur
    über den mode-Parameter von os.mkdir), damit das umask der
    Ausführungsumgebung die Rechte nicht unbemerkt einschränkt (SIC-13).

    Mit parents=True werden auch fehlende Elternverzeichnisse angelegt;
    im Unterschied zu Path.mkdir(parents=True, mode=...) (das mode nur
    auf das Zielverzeichnis anwendet, siehe pathlib-Dokumentation)
    erhalten hier auch neu angelegte Elternverzeichnisse explizit mode.
    Mit parents=False (Voreinstellung) muss das Elternverzeichnis bereits
    bestehen, sonst wird ActionError erzeugt.

    Attributes:
        PARAMS: Parameternamen der Aktion.
        path: Anzulegendes Verzeichnis.
        mode: Rechte des Verzeichnisses (und neu angelegter
            Elternverzeichnisse). Voreinstellung 0o700.
        parents: Legt fehlende Elternverzeichnisse mit an. Voreinstellung
            False.

    Example:
        action = MakeDirAction("/var/lib/pifos/state", parents=True)
        action.run()
    """

    PARAMS: ClassVar[list[str]] = ["path", "mode", "parents"]

    def __init__(
        self,
        path: str,
        mode: int = 0o700,
        parents: bool = False,
    ) -> None:
        """Initialisiert die Verzeichnis-Anlege-Aktion.

        Args:
            path: Anzulegendes Verzeichnis.
            mode: Rechte des Verzeichnisses (und neu angelegter
                Elternverzeichnisse bei parents=True). Voreinstellung
                0o700.
            parents: Bei True werden fehlende Elternverzeichnisse mit
                mode angelegt; bei False (Voreinstellung) muss das
                Elternverzeichnis bereits bestehen.
        """
        super().__init__()
        self.path = path
        self.mode = mode
        self.parents = parents

    def run(self) -> str:
        """Legt das Verzeichnis an und liefert den Ausführungsstatus.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Wenn path bereits als Datei oder Symlink
                existiert, oder bei Anlegefehler (u. a. fehlendes
                Elternverzeichnis bei parents=False).
        """
        self.status = "running"
        try:
            path = Path(self.path)

            if path.is_symlink():
                self.status = "failed"
                raise ActionError(
                    f"Pfad ist ein Symlink, kein Verzeichnis: {self.path!r}"
                )
            if path.is_dir():
                self.status = "finished"
                return self.status
            if path.exists():
                self.status = "failed"
                raise ActionError(
                    f"Pfad existiert bereits, ist aber kein Verzeichnis: {self.path!r}"
                )

            if self.parents:
                self._create_with_parents(path)
            else:
                os.mkdir(str(path))
                os.chmod(str(path), self.mode)
        except ActionError:
            if self.status != "failed":
                self.status = "failed"
            raise
        except OSError as exc:
            self.status = "failed"
            raise ActionError(f"Fehler beim Anlegen des Verzeichnisses: {exc}") from exc

        self.status = "finished"
        return self.status

    def _create_with_parents(self, path: Path) -> None:
        """Legt path und fehlende Elternverzeichnisse mit mode an.

        Args:
            path: Anzulegendes Verzeichnis.

        Raises:
            OSError: Bei Anlegefehler.
        """
        missing: list[Path] = []
        current = path
        while not current.exists():
            missing.append(current)
            parent = current.parent
            if parent == current:
                break
            current = parent

        for directory in reversed(missing):
            os.mkdir(str(directory))
            os.chmod(str(directory), self.mode)
