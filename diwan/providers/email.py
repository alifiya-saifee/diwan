"""The owner's own mailbox, over SMTP, so mail goes out from their address and sits in their Sent folder. Works with Gmail and Google
Workspace (app password), Outlook and most business mail. The password stays in .env. Only a person's yes reaches send()."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from diwan.config import env, offline

NEED = ("EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD")
TIMEOUT = 20


def available() -> bool:
    return not offline() and all(env(k) for k in NEED)


def send(to: str, subject: str, body: str) -> None:
    host, user = env("EMAIL_HOST"), env("EMAIL_USER")
    port = int(env("EMAIL_PORT", "465"))
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = env("EMAIL_FROM", user), to, subject
    m.set_content(body)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT) as s:
            s.login(user, env("EMAIL_PASSWORD"))
            s.send_message(m)
    else:
        with smtplib.SMTP(host, port, timeout=TIMEOUT) as s:
            s.starttls()
            s.login(user, env("EMAIL_PASSWORD"))
            s.send_message(m)
