"""Unit-Tests für PifosCaller: Logstufen-Abbildung und configure_logging."""

import logging
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from pifos.caller import PifosCaller
from pifos.config.config import Config
from pifos.errors import ConfigError
from pifos.ipc import LogLevel


@pytest.fixture(autouse=True)
def _reset_caller_logger() -> Iterator[None]:
    """Sichert und restauriert den geteilten Logger 'PifosCaller' je Test.

    configure_logging verändert Handler, Level und propagate des über den
    Klassennamen geteilten Loggers; ohne Wiederherstellung würden Tests
    einander beeinflussen.
    """
    logger = logging.getLogger("PifosCaller")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    yield
    for h in list(logger.handlers):
        logger.removeHandler(h)
    for h in saved[0]:
        logger.addHandler(h)
    logger.setLevel(saved[1])
    logger.propagate = saved[2]


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (LogLevel.INFO, logging.INFO),
        (LogLevel.WARN, logging.WARNING),
        (LogLevel.ERROR, logging.ERROR),
        (LogLevel.CRITICAL, logging.CRITICAL),
    ],
)
def test_write_log_uses_matching_level(
    level: LogLevel,
    expected: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """write_log protokolliert mit der zur pifos-Stufe passenden logging-Stufe."""
    caller = PifosCaller(loglevel=LogLevel.INFO)
    with caplog.at_level(logging.INFO, logger="PifosCaller"):
        caller.write_log("Meldung", level)
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == expected


def test_write_log_defaults_to_info(caplog: pytest.LogCaptureFixture) -> None:
    """Ohne Stufenangabe protokolliert write_log als INFO."""
    caller = PifosCaller(loglevel=LogLevel.INFO)
    with caplog.at_level(logging.INFO, logger="PifosCaller"):
        caller.write_log("Meldung")
    assert caplog.records[0].levelno == logging.INFO


def test_write_log_strips_control_chars(caplog: pytest.LogCaptureFixture) -> None:
    """Steuerzeichen werden vor dem Schreiben durch Leerzeichen ersetzt (SIC-19)."""
    caller = PifosCaller(loglevel=LogLevel.INFO)
    with caplog.at_level(logging.INFO, logger="PifosCaller"):
        caller.write_log("Zeile1\nZeile2\tEnde", LogLevel.WARN)
    assert "\n" not in caplog.records[0].message
    assert "\t" not in caplog.records[0].message
    assert caplog.records[0].message == "Zeile1 Zeile2 Ende"


def _caller_with_config(logfile: Path, loglevel: str) -> PifosCaller:
    """Erzeugt einen Aufrufer mit einer In-Memory-Konfiguration."""
    caller = PifosCaller()
    cfg = Config()
    cfg.load_dict({"logfile": str(logfile), "loglevel": loglevel})
    caller.config = cfg
    return caller


def test_configure_logging_sets_level_from_config(tmp_path: Path) -> None:
    """configure_logging übernimmt die Logstufe aus der Konfiguration (LOG-04)."""
    caller = _caller_with_config(tmp_path / "pifos.log", "WARN")
    caller.configure_logging()
    assert caller.loglevel == LogLevel.WARN


def test_configure_logging_creates_logfile_0600(tmp_path: Path) -> None:
    """Die Logdatei wird mit engen Rechten 0600 angelegt (SIC-27)."""
    logfile = tmp_path / "pifos.log"
    caller = _caller_with_config(logfile, "INFO")
    caller.configure_logging()
    assert logfile.exists()
    assert stat.S_IMODE(logfile.stat().st_mode) == 0o600


def test_configure_logging_writes_to_logfile(tmp_path: Path) -> None:
    """Nach configure_logging landen Meldungen in der konfigurierten Datei."""
    logfile = tmp_path / "pifos.log"
    caller = _caller_with_config(logfile, "INFO")
    caller.configure_logging()
    caller.write_log("Testmeldung", LogLevel.ERROR)
    logging.getLogger("PifosCaller").handlers[0].flush()
    content = logfile.read_text(encoding="utf-8")
    assert "Testmeldung" in content
    assert "ERROR" in content


def test_configure_logging_filters_below_level(tmp_path: Path) -> None:
    """Meldungen unterhalb der konfigurierten Stufe erscheinen nicht im Logfile."""
    logfile = tmp_path / "pifos.log"
    caller = _caller_with_config(logfile, "WARN")
    caller.configure_logging()
    caller.write_log("nur-info", LogLevel.INFO)
    caller.write_log("ein-fehler", LogLevel.ERROR)
    logging.getLogger("PifosCaller").handlers[0].flush()
    content = logfile.read_text(encoding="utf-8")
    assert "nur-info" not in content
    assert "ein-fehler" in content


def test_configure_logging_without_config_raises() -> None:
    """Ohne geladene Konfiguration schlägt configure_logging fehl."""
    caller = PifosCaller()
    with pytest.raises(ConfigError):
        caller.configure_logging()


def test_configure_logging_unknown_level_raises(tmp_path: Path) -> None:
    """Eine unbekannte Logstufe in der Konfiguration führt zu ConfigError."""
    caller = _caller_with_config(tmp_path / "pifos.log", "VERBOSE")
    with pytest.raises(ConfigError):
        caller.configure_logging()
