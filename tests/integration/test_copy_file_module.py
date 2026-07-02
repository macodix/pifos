"""Integrationstest für CopyFileModule.

Testet das Zusammenspiel CopyFileModule ↔ CopyFileAction ↔ IPC über den
vollständigen Weg: PifosCaller startet einen echten Subprozess (spawn),
das Modul kopiert die Datei und meldet per IPC, der Test prüft Zieldatei
und empfangene Meldungen.

check() und rollback() werden direkt am Modul-Objekt getestet, da sie
nicht über die IPC-Befehlsschleife des Runners erreichbar sind.
"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pifos.caller import ModuleHandle, PifosCaller
from pifos.config.config import Config
from pifos.ipc import IpcMessage, LogLevel, MessageKind

from tests.integration.copy_file_module import CopyFileModule

_TIMEOUT = 30  # Sekunden — Sicherheitsnetz gegen hängende Subprozesse


def _drain_until_result(
    caller: PifosCaller,
    handle: ModuleHandle,
    name: str,
) -> list[IpcMessage]:
    """Empfängt IPC-Meldungen bis zum RESULT für den angegebenen Befehl.

    Args:
        caller: Aktiver PifosCaller.
        handle: Handle des laufenden Moduls.
        name: Erwarteter Name des RESULT.

    Returns:
        Alle empfangenen Meldungen einschließlich des RESULT.

    Raises:
        RuntimeError: Wenn eine EXCEPTION-Meldung eintrifft.
    """
    messages: list[IpcMessage] = []
    while True:
        msg = caller.receive_result(handle)
        messages.append(msg)
        if msg.kind == MessageKind.EXCEPTION:
            raise RuntimeError(f"Modul-Ausnahme: {msg.payload}")
        if msg.kind == MessageKind.RESULT and msg.name == name:
            break
    return messages


def _cleanup(handle: ModuleHandle) -> None:
    """Stellt sicher, dass der Modulprozess beendet ist.

    Args:
        handle: Handle des Modulprozesses.
    """
    if handle.process.is_alive():
        handle.process.kill()
        handle.process.join(timeout=5)


@pytest.fixture()
def src_file(tmp_path: Path) -> Path:
    """Legt eine Quelldatei mit bekanntem Inhalt an.

    Args:
        tmp_path: Von pytest bereitgestelltes temporäres Verzeichnis.

    Returns:
        Pfad zur Quelldatei.
    """
    f = tmp_path / "source.txt"
    f.write_text("Testinhalt fuer CopyFileModule\n", encoding="utf-8")
    return f


@pytest.fixture()
def dst_file(tmp_path: Path) -> Path:
    """Liefert den Pfad zur noch nicht vorhandenen Zieldatei.

    Args:
        tmp_path: Von pytest bereitgestelltes temporäres Verzeichnis.

    Returns:
        Pfad zur Zieldatei (existiert noch nicht).
    """
    return tmp_path / "target.txt"


class TestCopyFileModuleSubprocess:
    """End-to-End-Tests über echten Subprozess."""

    def test_subprocess_copies_file(
        self,
        src_file: Path,
        dst_file: Path,
    ) -> None:
        """Modul kopiert Quelldatei in einem echten Subprozess.

        Prüft: Zieldatei entsteht, Inhalt stimmt, RESULT-Exitcode ist 0,
        eine LOG-Meldung copy_done kommt an.

        Args:
            src_file: Vorbereitete Quelldatei.
            dst_file: Pfad zur erwarteten Zieldatei.
        """
        cfg = Config()
        cfg.load_dict({"source": str(src_file), "target": str(dst_file)})

        caller = PifosCaller(loglevel=LogLevel.INFO)
        handle = caller.start_module(CopyFileModule, cfg)
        try:
            caller.send_command(handle, "start")
            messages = _drain_until_result(caller, handle, "start")
            caller.terminate_module(handle)
        finally:
            _cleanup(handle)

        assert dst_file.exists(), "Zieldatei wurde nicht angelegt"
        assert dst_file.read_bytes() == src_file.read_bytes(), (
            "Dateiinhalt stimmt nicht"
        )

        result_msgs = [
            m for m in messages if m.kind == MessageKind.RESULT and m.name == "start"
        ]
        assert result_msgs, "Kein RESULT für 'start' empfangen"
        result_payload = result_msgs[0].payload
        assert isinstance(result_payload, int)
        assert result_payload == 0, "Exitcode ungleich 0"

        log_msgs = [
            m for m in messages if m.kind == MessageKind.LOG and m.name == "copy_done"
        ]
        assert log_msgs, "Keine copy_done-Meldung empfangen"

    def test_subprocess_fails_for_missing_source(self, tmp_path: Path) -> None:
        """Modul meldet Fehler, wenn Quelldatei nicht vorhanden ist.

        Prüft: RESULT-Exitcode ist ungleich 0, copy_failed-Meldung kommt an,
        keine Zieldatei wird angelegt.

        Args:
            tmp_path: Von pytest bereitgestelltes temporäres Verzeichnis.
        """
        src = tmp_path / "nonexistent.txt"
        dst = tmp_path / "target.txt"
        cfg = Config()
        cfg.load_dict({"source": str(src), "target": str(dst)})

        caller = PifosCaller(loglevel=LogLevel.INFO)
        handle = caller.start_module(CopyFileModule, cfg)
        try:
            caller.send_command(handle, "start")
            messages = _drain_until_result(caller, handle, "start")
            caller.terminate_module(handle)
        finally:
            _cleanup(handle)

        assert not dst.exists(), "Zieldatei darf bei Fehler nicht entstehen"

        result_msgs = [
            m for m in messages if m.kind == MessageKind.RESULT and m.name == "start"
        ]
        assert result_msgs, "Kein RESULT für 'start' empfangen"
        result_payload = result_msgs[0].payload
        assert isinstance(result_payload, int)
        assert result_payload != 0, (
            "Exitcode sollte bei fehlender Quelle ungleich 0 sein"
        )

        fail_msgs = [
            m for m in messages if m.kind == MessageKind.LOG and m.name == "copy_failed"
        ]
        assert fail_msgs, "Keine copy_failed-Meldung empfangen"


class TestCopyFileModuleDirect:
    """Direkte Tests von check() und rollback() ohne Subprozess."""

    def test_check_false_before_copy(
        self,
        src_file: Path,
        dst_file: Path,
    ) -> None:
        """check() gibt False zurück, wenn Zieldatei noch nicht existiert.

        Args:
            src_file: Vorbereitete Quelldatei.
            dst_file: Pfad zur noch nicht vorhandenen Zieldatei.
        """
        conn = MagicMock(spec=object)
        mod = CopyFileModule(conn=conn, loglevel=LogLevel.INFO)
        mod.source = str(src_file)
        mod.target = str(dst_file)
        assert mod.check() is False

    def test_check_true_after_copy(
        self,
        src_file: Path,
        dst_file: Path,
    ) -> None:
        """check() gibt True zurück, wenn Zieldatei identisch mit Quelle ist.

        Args:
            src_file: Vorbereitete Quelldatei.
            dst_file: Pfad zur Zieldatei (wird hier angelegt).
        """
        shutil.copy2(str(src_file), str(dst_file))
        conn = MagicMock(spec=object)
        mod = CopyFileModule(conn=conn, loglevel=LogLevel.INFO)
        mod.source = str(src_file)
        mod.target = str(dst_file)
        assert mod.check() is True

    def test_rollback_removes_target(
        self,
        src_file: Path,
        dst_file: Path,
    ) -> None:
        """rollback() entfernt die Zieldatei und gibt True zurück.

        Args:
            src_file: Vorbereitete Quelldatei.
            dst_file: Pfad zur Zieldatei (wird hier angelegt und dann entfernt).
        """
        shutil.copy2(str(src_file), str(dst_file))
        conn = MagicMock(spec=object)
        mod = CopyFileModule(conn=conn, loglevel=LogLevel.INFO)
        mod.source = str(src_file)
        mod.target = str(dst_file)
        result = mod.rollback()
        assert result is True
        assert not dst_file.exists(), "Zieldatei sollte nach rollback() fehlen"

    def test_rollback_succeeds_if_target_absent(self, tmp_path: Path) -> None:
        """rollback() gibt True zurück, wenn Zieldatei bereits fehlt.

        Args:
            tmp_path: Von pytest bereitgestelltes temporäres Verzeichnis.
        """
        conn = MagicMock(spec=object)
        mod = CopyFileModule(conn=conn, loglevel=LogLevel.INFO)
        mod.source = str(tmp_path / "src.txt")
        mod.target = str(tmp_path / "nonexistent.txt")
        result = mod.rollback()
        assert result is True
