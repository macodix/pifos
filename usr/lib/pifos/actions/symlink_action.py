"""Symlink-Anlege-Aktion für pifos.

Setzt SIC-11/SIC-15 sinngemäß für Symlinks um: atomarer Austausch über
Temp-Symlink und os.replace, unvorhersagbarer Temp-Name über secrets.
"""

import os
import secrets
from pathlib import Path
from typing import ClassVar

from pifos.action import Action
from pifos.errors import ActionError

_MAX_SYMLINK_ATTEMPTS = 100


def _create_symlink_atomic(link_dir: Path, link_name: str, target: str) -> None:
    """Legt target als Symlink unter link_dir/link_name atomar an.

    Erstellt zunächst einen Symlink unter einem unvorhersagbaren
    temporären Namen im selben Verzeichnis (kryptografisch sicherer
    Zufall über secrets, SIC-15) und tauscht ihn per os.replace atomar
    gegen link_name aus — auch wenn dort bereits ein Eintrag liegt.
    Kollidiert der temporäre Name (praktisch ausgeschlossen), wird mit
    neuem Namen erneut versucht, bis zu _MAX_SYMLINK_ATTEMPTS Mal.

    Args:
        link_dir: Verzeichnis, in dem der Symlink liegt/entstehen soll.
        link_name: Dateiname des Symlinks (ohne Verzeichnisanteil).
        target: Ziel, auf das der Symlink zeigen soll.

    Raises:
        ActionError: Wenn nach allen Versuchen kein temporärer Symlink
            angelegt werden konnte.
        OSError: Bei sonstigem Anlege- oder Austauschfehler.
    """
    for _ in range(_MAX_SYMLINK_ATTEMPTS):
        tmp_path = link_dir / f".{link_name}.tmp-{secrets.token_hex(8)}"
        try:
            os.symlink(target, str(tmp_path))
        except FileExistsError:
            continue
        os.replace(str(tmp_path), str(link_dir / link_name))
        return

    raise ActionError(
        f"Temporärer Symlink konnte nach {_MAX_SYMLINK_ATTEMPTS} Versuchen"
        f" nicht angelegt werden: {link_name!r}"
    )


class SymlinkAction(Action):
    """Legt einen Symlink an, der auf target zeigt.

    target muss nicht existieren — ein toter Symlink (Ziel fehlt) ist
    zulässig und wird nicht geprüft; das entspricht dem Grundsatz, dass
    Aktionen Parameter nicht inhaltlich prüfen.

    Existiert am link_path bereits ein Eintrag, wird ohne overwrite=True
    ActionError erzeugt (safe-mode-Gedanke wie bei den anderen Datei-
    Aktionen). Mit overwrite=True wird nur ein vorhandener Symlink
    ersetzt — atomar über einen temporären Symlink und os.replace,
    siehe _create_symlink_atomic. Eine reguläre Datei oder ein
    Verzeichnis am link_path wird dagegen nie ersetzt, auch nicht mit
    overwrite=True; das erzeugt ActionError.

    Für einen Symlink gibt es keine Sicherung (safe-mode-Backup): ein
    Symlink hat keinen eigenen Inhalt, der gesichert werden könnte — nur
    ein Ziel-Pfad als Zeichenkette. Ein Rückbau ist über einen erneuten
    SymlinkAction-Aufruf mit dem vorherigen target möglich.

    Attributes:
        PARAMS: Parameternamen der Aktion.
        link_path: Pfad des anzulegenden Symlinks.
        target: Ziel, auf das der Symlink zeigen soll.
        overwrite: Erlaubt das Ersetzen eines bestehenden Symlinks an
            link_path. Voreinstellung False.

    Example:
        action = SymlinkAction("/etc/pifos/config.ini", "config.d/prod.ini")
        action.run()
    """

    PARAMS: ClassVar[list[str]] = ["link_path", "target", "overwrite"]

    def __init__(
        self,
        link_path: str,
        target: str,
        overwrite: bool = False,
    ) -> None:
        """Initialisiert die Symlink-Anlege-Aktion.

        Args:
            link_path: Pfad des anzulegenden Symlinks.
            target: Ziel, auf das der Symlink zeigen soll. Muss nicht
                existieren (toter Link zulässig).
            overwrite: Erlaubt das Ersetzen eines bestehenden Symlinks an
                link_path; eine bestehende reguläre Datei oder ein
                Verzeichnis wird dadurch nicht ersetzt. Voreinstellung
                False.
        """
        super().__init__()
        self.link_path = link_path
        self.target = target
        self.overwrite = overwrite

    def run(self) -> str:
        """Legt den Symlink an und liefert den Ausführungsstatus.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Bei vorhandenem Eintrag ohne overwrite=True,
                bei einer bestehenden Datei/einem Verzeichnis am
                link_path (auch mit overwrite=True) oder bei Anlege-
                bzw. Austauschfehler.
        """
        self.status = "running"
        try:
            link_path = Path(self.link_path)
            is_symlink = link_path.is_symlink()
            exists = is_symlink or link_path.exists()

            if exists:
                if not self.overwrite:
                    self.status = "failed"
                    raise ActionError(
                        f"Pfad vorhanden, Überschreiben nicht freigegeben:"
                        f" {self.link_path!r}"
                    )
                if not is_symlink:
                    self.status = "failed"
                    raise ActionError(
                        f"Pfad ist eine Datei oder ein Verzeichnis, wird"
                        f" nie ersetzt: {self.link_path!r}"
                    )
                _create_symlink_atomic(link_path.parent, link_path.name, self.target)
            else:
                os.symlink(self.target, str(link_path))
        except ActionError:
            if self.status != "failed":
                self.status = "failed"
            raise
        except OSError as exc:
            self.status = "failed"
            raise ActionError(f"Fehler beim Anlegen des Symlinks: {exc}") from exc

        self.status = "finished"
        return self.status
