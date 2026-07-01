"""Smoke-Tests für pifos.ipc."""

from pifos.ipc import IpcMessage, LogLevel, MessageKind


def test_message_kind_has_expected_values() -> None:
    """MessageKind enthält alle spezifizierten Werte."""
    assert MessageKind.COMMAND
    assert MessageKind.LOG
    assert MessageKind.MESSAGE
    assert MessageKind.REQUEST
    assert MessageKind.RESULT
    assert MessageKind.EXCEPTION


def test_log_level_has_expected_values() -> None:
    """LogLevel enthält alle vier Stufen."""
    levels = list(LogLevel)
    assert len(levels) == 4
    assert LogLevel.INFO in levels
    assert LogLevel.WARN in levels
    assert LogLevel.ERROR in levels
    assert LogLevel.CRITICAL in levels


def test_ipc_message_creation() -> None:
    """IpcMessage lässt sich mit allen Feldern anlegen."""
    msg = IpcMessage(
        kind=MessageKind.LOG,
        level=LogLevel.INFO,
        name="test",
        payload="daten",
    )
    assert msg.kind == MessageKind.LOG
    assert msg.level == LogLevel.INFO
    assert msg.name == "test"
    assert msg.payload == "daten"


def test_ipc_message_none_level() -> None:
    """IpcMessage akzeptiert None als level für nicht-logging-relevante Nachrichten."""
    msg = IpcMessage(
        kind=MessageKind.COMMAND,
        level=None,
        name="start",
        payload=None,
    )
    assert msg.level is None


def test_ipc_message_payload_any_type() -> None:
    """IpcMessage akzeptiert verschiedene einfache Datentypen als payload."""
    for payload in [42, 3.14, True, [1, 2], {"a": "b"}, None]:
        msg = IpcMessage(kind=MessageKind.RESULT, level=None, name="x", payload=payload)
        assert msg.payload == payload
