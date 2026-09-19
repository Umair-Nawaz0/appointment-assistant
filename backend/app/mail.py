from __future__ import annotations

import asyncio
import html
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

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


def _deliver_appointment_sync(
    to: str,
    subject: str,
    html_body: str,
    ics_base64: str | None = None,
    ics_filename: str | None = "appointment.ics",
    sender_name: str | None = None,
) -> dict[str, Any]:
    import base64

    # Determine sender email and display name
    sender_email = settings.gmail_sender_email or settings.smtp_user or "no-reply@example.com"
    display_name = sender_name or "Appointment Assistant"
    from_header = f"{display_name} <{sender_email}>"

    # Check if SMTP / Gmail credentials are configured
    smtp_host = settings.smtp_host or "smtp.gmail.com"
    smtp_port = settings.smtp_port or 465
    smtp_user = settings.gmail_sender_email or settings.smtp_user
    smtp_password = (settings.gmail_api_secret_key or settings.smtp_password or "").replace(" ", "")

    if not smtp_user or not smtp_password:
        if settings.mail_mode == "console":
            print(f"[mail:console] Appointment Confirmation -> {to} ({subject})")
            return {
                "sent": True,
                "provider": "console",
                "recipient": to,
                "note": "Email logged to console. Configure GMAIL_SENDER_EMAIL and GMAIL_API_SECRET_KEY in .env to send live emails.",
            }
        raise RuntimeError("Gmail sender email and API secret key / App Password are not configured in .env")

    message = EmailMessage()
    message["From"] = from_header
    message["To"] = to
    message["Subject"] = subject
    message.set_content("Your appointment is confirmed. Please see the attached calendar invitation.")
    message.add_alternative(html_body, subtype="html")

    # Attach .ics calendar file if provided
    if ics_base64:
        try:
            ics_bytes = base64.b64decode(ics_base64)
            filename = ics_filename or "appointment.ics"
            message.add_attachment(
                ics_bytes,
                maintype="text",
                subtype="calendar",
                filename=filename,
                params={"method": "REQUEST", "name": filename},
            )
        except Exception as e:
            print(f"Warning: Failed to attach calendar .ics: {e}")

    context = ssl.create_default_context()
    if settings.smtp_secure or smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=25, context=context) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=25) as server:
            server.ehlo()
            if settings.smtp_require_tls:
                server.starttls(context=context)
                server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(message)

    return {
        "sent": True,
        "provider": "gmail_smtp",
        "sender": sender_email,
        "recipient": to,
        "subject": subject,
    }


async def deliver_appointment_email(
    to: str,
    subject: str,
    html_body: str,
    ics_base64: str | None = None,
    ics_filename: str | None = "appointment.ics",
    sender_name: str | None = None,
) -> dict[str, Any]:
    from typing import Any
    return await asyncio.to_thread(
        _deliver_appointment_sync,
        to,
        subject,
        html_body,
        ics_base64,
        ics_filename,
        sender_name,
    )

