"""Unit-Tests für PifosCaller.write_log — korrekte Logstufen-Abbildung."""

import logging

import pytest
from pifos.caller import PifosCaller
from pifos.ipc import LogLevel


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
