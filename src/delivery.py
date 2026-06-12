from __future__ import annotations

import json
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage

from config import Settings


def deliver(title: str, markdown: str, settings: Settings) -> list[str]:
    delivered: list[str] = []
    if settings.slack_webhook_url:
        _send_slack(title, markdown, settings.slack_webhook_url)
        delivered.append("Slack")
    if _email_enabled(settings):
        _send_email(title, markdown, settings)
        delivered.append("email")
    return delivered


def _send_slack(title: str, markdown: str, webhook_url: str) -> None:
    text = f"*{title}*\n\n{markdown[:3500]}"
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def _email_enabled(settings: Settings) -> bool:
    return all(
        [
            settings.smtp_host,
            settings.smtp_username,
            settings.smtp_password,
            settings.email_from,
            settings.email_to,
        ]
    )


def _send_email(title: str, markdown: str, settings: Settings) -> None:
    message = EmailMessage()
    message["Subject"] = title
    message["From"] = settings.email_from or ""
    message["To"] = settings.email_to or ""
    message.set_content(markdown)

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host or "", settings.smtp_port, timeout=30) as server:
        server.starttls(context=context)
        server.login(settings.smtp_username or "", settings.smtp_password or "")
        server.send_message(message)
