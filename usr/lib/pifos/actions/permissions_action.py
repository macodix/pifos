"""Rechte- und Eigentümer-Aktion für pifos.

Setzt SIC-13, SIC-15 um: kein Folgen von Symlinks bei Eigentümer- und
Rechteänderung.
"""

import grp
import os
import pwd
from pathlib import Path
from typing import ClassVar

from pifos.action import Action
from pifos.errors import ActionError


class PermissionsAction(Action):
    """Setzt Rechte und/oder Eigentümer eines bestehenden Dateisystemobjekts.

    Gilt für Dateien und Verzeichnisse gleichermaßen. Mindestens einer von
    mode, owner, group muss gesetzt sein, sonst wird ActionError erzeugt.
    owner und group akzeptieren einen Namen (Auflösung über pwd/grp) oder
    direkt eine numerische UID/GID; ein unbekannter Name erzeugt
    ActionError.

    Eigentümerwechsel laufen über os.lchown, das grundsätzlich nie einem
    Symlink folgt. Für Rechteänderungen wird os.chmod mit
    follow_symlinks=False versucht; unterstützt die Plattform das nicht
    (os.chmod not in os.supports_follow_symlinks — u. a. auf Linux, das
    kein lchmod kennt), wird ein Symlink als path mit ActionError
    abgelehnt, statt transparent durch den Symlink hindurch zu wirken
    (SIC-15). Ist path kein Symlink, wird mode ohne Einschränkung gesetzt.

    Attributes:
        PARAMS: Parameternamen der Aktion.
        path: Datei oder Verzeichnis, dessen Rechte/Eigentümer geändert
            werden.
        mode: Neue Rechte oder None (unverändert).
        owner: Neuer Eigentümer (Name oder UID) oder None (unverändert).
        group: Neue Gruppe (Name oder GID) oder None (unverändert).

    Example:
        action = PermissionsAction("/etc/pifos/config.ini", mode=0o600,
                                    owner="root", group="root")
        action.run()
    """

    PARAMS: ClassVar[list[str]] = ["path", "mode", "owner", "group"]

    def __init__(
        self,
        path: str,
        mode: int | None = None,
        owner: str | int | None = None,
        group: str | int | None = None,
    ) -> None:
        """Initialisiert die Rechte- und Eigentümer-Aktion.

        Args:
            path: Datei oder Verzeichnis, dessen Rechte/Eigentümer
                geändert werden. Muss existieren.
            mode: Neue Rechte oder None (unverändert).
            owner: Neuer Eigentümer als Name (Auflösung über pwd) oder
                UID, oder None (unverändert).
            group: Neue Gruppe als Name (Auflösung über grp) oder GID,
                oder None (unverändert).
        """
        super().__init__()
        self.path = path
        self.mode = mode
        self.owner = owner
        self.group = group

    def run(self) -> str:
        """Setzt Rechte und/oder Eigentümer und liefert den Status.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Wenn weder mode noch owner noch group gesetzt
                ist, bei fehlendem path, unbekanntem Benutzer-/Gruppen-
                namen, bei einem Symlink als path, wenn die Plattform
                keine Rechteänderung ohne Symlink-Folgen unterstützt,
                oder bei sonstigem Fehler.
        """
        self.status = "running"
        try:
            if self.mode is None and self.owner is None and self.group is None:
                self.status = "failed"
                raise ActionError(
                    "Mindestens einer von mode, owner, group muss gesetzt sein"
                )

            path = Path(self.path)
            if not path.exists() and not path.is_symlink():
                self.status = "failed"
                raise ActionError(f"Pfad nicht gefunden: {self.path!r}")

            if self.owner is not None or self.group is not None:
                uid = self._resolve_uid(self.owner) if self.owner is not None else -1
                gid = self._resolve_gid(self.group) if self.group is not None else -1
                os.lchown(str(path), uid, gid)

            if self.mode is not None:
                self._apply_mode(path, self.mode)
        except ActionError:
            if self.status != "failed":
                self.status = "failed"
            raise
        except OSError as exc:
            self.status = "failed"
            raise ActionError(f"Dateifehler bei der Rechteänderung: {exc}") from exc

        self.status = "finished"
        return self.status

    def _resolve_uid(self, owner: str | int) -> int:
        """Löst owner zu einer UID auf.

        Args:
            owner: Benutzername oder UID.

        Returns:
            UID.

        Raises:
            ActionError: Bei unbekanntem Benutzernamen.
        """
        if isinstance(owner, int):
            return owner
        try:
            return pwd.getpwnam(owner).pw_uid
        except KeyError as exc:
            raise ActionError(f"Unbekannter Benutzer: {owner!r}") from exc

    def _resolve_gid(self, group: str | int) -> int:
        """Löst group zu einer GID auf.

        Args:
            group: Gruppenname oder GID.

        Returns:
            GID.

        Raises:
            ActionError: Bei unbekanntem Gruppennamen.
        """
        if isinstance(group, int):
            return group
        try:
            return grp.getgrnam(group).gr_gid
        except KeyError as exc:
            raise ActionError(f"Unbekannte Gruppe: {group!r}") from exc

    def _apply_mode(self, path: Path, mode: int) -> None:
        """Setzt die Rechte von path, ohne Symlinks zu folgen (SIC-15).

        Args:
            path: Datei oder Verzeichnis.
            mode: Zu setzende Rechte.

        Raises:
            ActionError: Wenn path ein Symlink ist und die Plattform
                keine Rechteänderung ohne Symlink-Folgen unterstützt.
        """
        if path.is_symlink():
            if os.chmod not in os.supports_follow_symlinks:
                raise ActionError(
                    f"Rechteänderung für Symlinks wird auf diesem System"
                    f" nicht unterstützt: {self.path!r}"
                )
            os.chmod(str(path), mode, follow_symlinks=False)
        else:
            os.chmod(str(path), mode)
