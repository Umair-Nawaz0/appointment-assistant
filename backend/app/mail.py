from __future__ import annotations

import asyncio
import html
import smtplib
import ssl
from email.message import EmailMessage

from .config import settings


def _deliver(to: str, subject: str, text: str, html_body: str) -> None:
    if settings.mail_mode == "console":
        print(f"[mail:console] {subject} -> {to}\n{text}")
        return
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    if settings.smtp_secure:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.ehlo()
            if settings.smtp_require_tls:
                server.starttls(context=context)
                server.ehlo()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)


async def send_verification(email: str, business_name: str, code: str) -> None:
    safe_name = html.escape(business_name)
    await asyncio.to_thread(
        _deliver, email, "Verify your Appointment Assistant account",
        f"Hello {business_name}, your email verification code is {code}. It expires soon.",
        f"<p>Hello {safe_name},</p><p>Your email verification code is:</p><p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">{code}</p><p>This code expires soon.</p>",
    )


async def send_password_reset(email: str, business_name: str, code: str) -> None:
    safe_name = html.escape(business_name)
    await asyncio.to_thread(
        _deliver, email, "Reset your Appointment Assistant password",
        f"Hello {business_name}, your password reset code is {code}. It expires soon.",
        f"<p>Hello {safe_name},</p><p>Your password reset code is:</p><p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">{code}</p><p>This code expires soon. If you did not request it, ignore this email.</p>",
    )
