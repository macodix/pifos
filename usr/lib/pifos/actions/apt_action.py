"""apt-Paketverwaltungs-Aktion für pifos.

Setzt SIC-03 (kein Shell-Aufruf), SIC-04 (Argumentliste) und SIC-06
(kontrollierter PATH) um; nutzt intern SysCmdAction.
"""

from typing import ClassVar

from pifos.action import Action
from pifos.actions.sys_cmd_action import SysCmdAction
from pifos.errors import ActionError

_APT_GET = "/usr/bin/apt-get"
_CONTROLLED_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


class AptAction(Action):
    """Installiert oder entfernt Debian/Ubuntu-Pakete über apt-get.

    Führt apt-get install -y bzw. apt-get remove -y nicht-interaktiv aus
    (DEBIAN_FRONTEND=noninteractive), ohne Shell, mit einer Zeitgrenze.
    Paketnamen werden als Argumentliste übergeben, nie als Shell-Text, und
    inhaltlich nicht geprüft — das macht das aufrufende Modul. Die Aktion
    delegiert den Prozessaufruf an SysCmdAction und übernimmt deren
    stdout, stderr und returncode.

    Attributes:
        PARAMS: Parameternamen der Aktion.
        packages: Zu installierende oder entfernende Paketnamen.
        state: "present" installiert, "absent" entfernt. Voreinstellung
            "present".
        timeout: Zeitgrenze in Sekunden. Voreinstellung 300.0.
        stdout: Standardausgabe von apt-get nach run().
        stderr: Fehlerausgabe von apt-get nach run().
        returncode: Rückgabewert von apt-get nach run(); -1 vor der
            Ausführung.

    Example:
        action = AptAction(["curl", "jq"], state="present", timeout=120.0)
        action.run()
    """

    PARAMS: ClassVar[list[str]] = ["packages", "state", "timeout"]

    def __init__(
        self,
        packages: list[str],
        state: str = "present",
        timeout: float = 300.0,
    ) -> None:
        """Initialisiert die apt-Paketverwaltungs-Aktion.

        Args:
            packages: Zu installierende oder entfernende Paketnamen.
            state: "present" installiert die Pakete, "absent" entfernt
                sie. Voreinstellung "present".
            timeout: Zeitgrenze in Sekunden für apt-get (SIC-05).
                Voreinstellung 300.0.
        """
        super().__init__()
        self.packages = packages
        self.state = state
        self.timeout = timeout
        self.stdout: str = ""
        self.stderr: str = ""
        self.returncode: int = -1

    def run(self) -> str:
        """Führt apt-get aus und liefert den Ausführungsstatus.

        Setzt self.stdout, self.stderr und self.returncode aus der
        zugrunde liegenden SysCmdAction — auch im Fehlerfall.

        Returns:
            Aktueller Status nach der Ausführung ("finished" oder "failed").

        Raises:
            ActionError: Bei Timeout, Returncode != 0 oder Startfehler
                von apt-get.
        """
        self.status = "running"
        subcommand = "remove" if self.state == "absent" else "install"
        command = [_APT_GET, subcommand, "-y", *self.packages]
        env = {
            "DEBIAN_FRONTEND": "noninteractive",
            "PATH": _CONTROLLED_PATH,
        }
        cmd_action = SysCmdAction(command, timeout=self.timeout, env=env)
        try:
            cmd_action.run()
        except ActionError:
            self.status = "failed"
            raise
        finally:
            self.stdout = cmd_action.stdout
            self.stderr = cmd_action.stderr
            self.returncode = cmd_action.returncode

        self.status = "finished"
        return self.status
