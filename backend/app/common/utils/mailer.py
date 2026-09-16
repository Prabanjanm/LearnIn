"""
Outbound transactional email via the Brevo SMTP relay.

A thin smtplib wrapper, not a queue or a template engine - callers build the
message body themselves and this just handles the STARTTLS handshake and
auth against `settings.SMTP_*`.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, html: bool = False) -> None:
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS and settings.SENDER_EMAIL):
        raise RuntimeError(
            "SMTP is not configured - set SMTP_HOST, SMTP_USER, SMTP_PASS and "
            "SENDER_EMAIL in the environment before sending email."
        )

    message = EmailMessage()
    message["From"] = settings.SENDER_EMAIL
    message["To"] = to
    message["Subject"] = subject

    if html:
        message.set_content("This email requires an HTML-capable client.")
        message.add_alternative(body, subtype="html")
    else:
        message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as client:
        client.starttls()
        client.login(settings.SMTP_USER, settings.SMTP_PASS)
        client.send_message(message)

    logger.info("Sent email to %s (subject=%r)", to, subject)
