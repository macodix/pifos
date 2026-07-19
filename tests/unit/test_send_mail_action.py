"""Tests für pifos.actions.send_mail_action."""

import smtplib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pifos.actions.send_mail_action import SendMailAction
from pifos.errors import ActionError


def _fake_mailer(
    tmp_path: Path,
    stdin_out: Path,
    args_out: Path,
    exit_code: int = 0,
    stderr_text: str = "",
) -> str:
    """Legt ein Fake-Versandprogramm an, das stdin und argv festhält."""
    lines = [
        "#!/bin/sh",
        f'cat > "{stdin_out}"',
        f'printf "%s\\n" "$@" > "{args_out}"',
    ]
    if stderr_text:
        lines.append(f'printf "%s" "{stderr_text}" >&2')
    lines.append(f"exit {exit_code}")
    script = tmp_path / "fake-mailer"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


# --- lokaler Weg, Stil sendmail ---


def test_sendmail_style_builds_mime(tmp_path: Path) -> None:
    """sendmail-Stil: volle MIME über stdin, Kopfzeilen und Text korrekt."""
    body = tmp_path / "stdin.eml"
    args = tmp_path / "argv.txt"
    binp = _fake_mailer(tmp_path, body, args)
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "Betreff",
        "Hallo Welt\n",
        mailer=binp,
        timeout=10.0,
    )
    assert action.run() == "finished"
    assert action.returncode == 0
    msg = body.read_text(encoding="utf-8")
    assert "From: root@example.org" in msg
    assert "To: a@example.org" in msg
    assert "Subject: Betreff" in msg
    assert "Hallo Welt" in msg
    argv = args.read_text(encoding="utf-8").splitlines()
    assert "a@example.org" in argv
    assert "-f" in argv
    assert "root@example.org" in argv


def test_sendmail_style_cc_in_header_bcc_not(tmp_path: Path) -> None:
    """cc steht in den Kopfzeilen, bcc nicht; beide im Umschlag (argv)."""
    body = tmp_path / "stdin.eml"
    args = tmp_path / "argv.txt"
    binp = _fake_mailer(tmp_path, body, args)
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "S",
        "B",
        mailer=binp,
        cc=["c@example.org"],
        bcc=["b@example.org"],
        timeout=10.0,
    )
    action.run()
    msg = body.read_text(encoding="utf-8")
    assert "Cc: c@example.org" in msg
    assert "b@example.org" not in msg
    argv = args.read_text(encoding="utf-8").splitlines()
    assert "c@example.org" in argv
    assert "b@example.org" in argv


def test_sendmail_style_with_attachment(tmp_path: Path) -> None:
    """Ein Dateianhang landet mit Dateiname in der MIME-Nachricht."""
    att = tmp_path / "report.txt"
    att.write_text("INHALT-XYZ", encoding="utf-8")
    body = tmp_path / "stdin.eml"
    args = tmp_path / "argv.txt"
    binp = _fake_mailer(tmp_path, body, args)
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "S",
        "B",
        mailer=binp,
        attachments=[str(att)],
        timeout=10.0,
    )
    action.run()
    assert "report.txt" in body.read_text(encoding="utf-8")


def test_local_nonzero_raises(tmp_path: Path) -> None:
    """Rückgabewert != 0 erzeugt ActionError, Status failed, stderr erfasst."""
    body = tmp_path / "stdin.eml"
    args = tmp_path / "argv.txt"
    binp = _fake_mailer(tmp_path, body, args, exit_code=1, stderr_text="boom")
    action = SendMailAction(
        "root@example.org", ["a@example.org"], "S", "B", mailer=binp, timeout=10.0
    )
    with pytest.raises(ActionError):
        action.run()
    assert action.status == "failed"
    assert action.returncode == 1
    assert "boom" in action.stderr


def test_local_mailer_missing(tmp_path: Path) -> None:
    """Fehlendes Versandprogramm erzeugt ActionError (keine Installation)."""
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "S",
        "B",
        mailer=str(tmp_path / "nicht-da"),
        timeout=10.0,
    )
    with pytest.raises(ActionError, match="nicht vorhanden"):
        action.run()
    assert action.status == "failed"


# --- lokaler Weg, Stil mail ---


def test_mail_style_builds_command(tmp_path: Path) -> None:
    """mail-Stil: -s/-c/-b/-a und Empfänger als Argumente, Text über stdin."""
    body = tmp_path / "stdin.txt"
    args = tmp_path / "argv.txt"
    binp = _fake_mailer(tmp_path, body, args)
    att = tmp_path / "r.txt"
    att.write_text("X", encoding="utf-8")
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "Betreff Text",
        "KOERPER\n",
        mailer=binp,
        mailer_style="mail",
        cc=["c@example.org"],
        bcc=["b@example.org"],
        attachments=[str(att)],
        timeout=10.0,
    )
    assert action.run() == "finished"
    argv = args.read_text(encoding="utf-8").splitlines()
    assert argv[:2] == ["-s", "Betreff Text"]
    assert "-c" in argv
    assert "c@example.org" in argv
    assert "-b" in argv
    assert "b@example.org" in argv
    assert "-a" in argv
    assert str(att) in argv
    assert "a@example.org" in argv
    assert body.read_text(encoding="utf-8") == "KOERPER\n"


def test_unknown_mailer_style(tmp_path: Path) -> None:
    """Unbekannter mailer_style erzeugt ActionError."""
    body = tmp_path / "stdin"
    args = tmp_path / "argv"
    binp = _fake_mailer(tmp_path, body, args)
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "S",
        "B",
        mailer=binp,
        mailer_style="telepathie",
    )
    with pytest.raises(ActionError, match="mailer_style"):
        action.run()
    assert action.status == "failed"


# --- Injektionsschutz ---


def test_rejects_newline_in_subject() -> None:
    """Zeilenumbruch im Betreff (Kopf-Injektion) erzeugt ActionError."""
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "Betreff\nBcc: evil@example.org",
        "B",
        mailer="/bin/true",
        timeout=10.0,
    )
    with pytest.raises(ActionError, match="Zeilenumbruch"):
        action.run()
    assert action.status == "failed"


def test_rejects_option_like_recipient(tmp_path: Path) -> None:
    """Empfänger mit führendem '-' (Options-Injektion) erzeugt ActionError."""
    body = tmp_path / "stdin"
    args = tmp_path / "argv"
    binp = _fake_mailer(tmp_path, body, args)
    action = SendMailAction(
        "root@example.org", ["-froot"], "S", "B", mailer=binp, timeout=10.0
    )
    with pytest.raises(ActionError, match="beginnen"):
        action.run()
    assert action.status == "failed"


def test_unknown_transport() -> None:
    """Unbekannter Transport erzeugt ActionError und Status failed."""
    action = SendMailAction(
        "root@example.org", ["a@example.org"], "S", "B", transport="brieftaube"
    )
    with pytest.raises(ActionError, match="unbekannter Transport"):
        action.run()
    assert action.status == "failed"


# --- SMTP-Transport (smtplib gemockt) ---


def test_smtp_starttls_and_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """SMTP mit starttls und Anmeldung; Umschlag enthält to+cc+bcc."""
    fake = MagicMock()
    fake.__enter__.return_value = fake
    ctor = MagicMock(return_value=fake)
    monkeypatch.setattr(smtplib, "SMTP", ctor)
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "S",
        "B",
        transport="smtp",
        smtp_host="mail.example.org",
        smtp_port=587,
        smtp_security="starttls",
        smtp_user="u",
        smtp_password="p",  # noqa: S106
        cc=["c@example.org"],
        bcc=["b@example.org"],
        timeout=5.0,
    )
    assert action.run() == "finished"
    ctor.assert_called_once_with("mail.example.org", 587, timeout=5.0)
    assert fake.starttls.called
    fake.login.assert_called_once_with("u", "p")
    _, kwargs = fake.send_message.call_args
    assert kwargs["from_addr"] == "root@example.org"
    assert set(kwargs["to_addrs"]) == {
        "a@example.org",
        "c@example.org",
        "b@example.org",
    }


def test_smtp_ssl_no_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """SMTP über ssl ohne Anmeldung: kein starttls, kein login, Versand erfolgt."""
    fake = MagicMock()
    fake.__enter__.return_value = fake
    ctor = MagicMock(return_value=fake)
    monkeypatch.setattr(smtplib, "SMTP_SSL", ctor)
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "S",
        "B",
        transport="smtp",
        smtp_host="mail.example.org",
        smtp_port=465,
        smtp_security="ssl",
        timeout=5.0,
    )
    assert action.run() == "finished"
    ctor.assert_called_once_with("mail.example.org", 465, timeout=5.0)
    assert not fake.starttls.called
    assert not fake.login.called
    assert fake.send_message.called


def test_smtp_requires_host() -> None:
    """transport='smtp' ohne smtp_host erzeugt ActionError."""
    action = SendMailAction(
        "root@example.org", ["a@example.org"], "S", "B", transport="smtp"
    )
    with pytest.raises(ActionError, match="smtp_host"):
        action.run()
    assert action.status == "failed"


def test_smtp_unknown_security() -> None:
    """Unbekannte smtp_security erzeugt ActionError."""
    action = SendMailAction(
        "root@example.org",
        ["a@example.org"],
        "S",
        "B",
        transport="smtp",
        smtp_host="mail.example.org",
        smtp_security="komisch",
    )
    with pytest.raises(ActionError, match="smtp_security"):
        action.run()
    assert action.status == "failed"
