"""
Outbound email sender — SMTP via Gmail using the existing IMAP_EMAIL +
IMAP_PASSWORD app-password credentials (no new OAuth flow).

Used by the auto-email scheduled report path. Kept deliberately small:
one function, plain-text body + .xlsx attachment. If multi-attachment or
HTML bodies are ever needed, extend here.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable

from backend.config import get_settings

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


class EmailNotConfigured(RuntimeError):
    """Raised when IMAP_EMAIL / IMAP_PASSWORD env vars aren't set so we
    can't send. Callers should log + skip rather than crash the request."""


def send_xlsx_email(
    recipients: Iterable[str],
    subject: str,
    body: str,
    xlsx_bytes: bytes,
    xlsx_filename: str,
) -> int:
    """Send a plain-text email with an .xlsx attachment.

    Returns the number of recipients we successfully handed to the SMTP
    server. Raises `EmailNotConfigured` if credentials aren't set.
    Raises smtplib.SMTPException on send failures.
    """
    settings = get_settings()
    sender = (settings.IMAP_EMAIL or "").strip()
    password = (settings.IMAP_PASSWORD or "").strip()
    if not sender or not password:
        raise EmailNotConfigured(
            "IMAP_EMAIL / IMAP_PASSWORD must be set on the server to send mail"
        )

    to_list = [r.strip() for r in recipients if r and r.strip()]
    if not to_list:
        logger.warning("send_xlsx_email called with no recipients — skipping")
        return 0

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(
        xlsx_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=xlsx_filename,
    )

    # SMTP_SSL on 465 also works for Gmail; we use STARTTLS on 587 since
    # that's the path the existing IMAP setup matches.
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.send_message(msg)

    logger.info("Sent xlsx email to %s (subject=%s)", to_list, subject)
    return len(to_list)
