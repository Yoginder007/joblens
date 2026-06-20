"""
Transactional email delivery (stdlib SMTP — no extra dependency).

Sends via SMTP when ``SMTP_*`` settings are configured; otherwise logs the
message and reports it as not-sent, so alert delivery degrades gracefully on a
free tier with no SMTP account (this preserves the prior log-only behaviour).

A real SMTP failure raises, so the caller can record the delivery as ``failed``.
"""
import logging
import re
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
    """Send one email. Returns True when actually dispatched via SMTP, False when
    email isn't configured (the message is logged instead). Raises on SMTP error."""
    settings = get_settings()
    if not settings.email_enabled:
        logger.info("EMAIL (unconfigured, logged only) → %s | %s", to, subject)
        return False

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text_body or _strip_html(html_body))
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
    logger.info("EMAIL sent → %s | %s", to, subject)
    return True
