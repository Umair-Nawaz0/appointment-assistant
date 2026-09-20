from __future__ import annotations

import asyncio
import html
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from .config import settings


def _deliver(to: str, subject: str, text: str, html_body: str) -> None:
    smtp_user = settings.smtp_user or settings.gmail_sender_email
    raw_pass = settings.smtp_password or settings.gmail_api_secret_key or settings.gmail_app_password
    smtp_password = raw_pass.replace(" ", "") if raw_pass else None
    smtp_host = settings.smtp_host or "smtp.gmail.com"
    smtp_port = settings.smtp_port or 465

    # If mail_mode is console and no credentials configured, fallback to console log
    if settings.mail_mode == "console" and (not smtp_user or not smtp_password):
        print(f"[mail:console] {subject} -> {to}\n{text}")
        return

    if not smtp_user or not smtp_password:
        raise RuntimeError("SMTP credentials (SMTP_USER / SMTP_PASSWORD or GMAIL_APP_PASSWORD) are not configured.")

    from_header = settings.mail_from or f"Appointment Assistant <{smtp_user}>"

    message = EmailMessage()
    message["From"] = from_header
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html_body, subtype="html")

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


async def send_verification(email: str, business_name: str, code: str) -> None:
    safe_name = html.escape(business_name)
    ttl = settings.verification_ttl_minutes
    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #0f172a; margin-top: 0; font-size: 20px;">Verify your business email</h2>
      <p style="color: #475569; font-size: 15px; line-height: 1.5;">Hello <strong>{safe_name}</strong>,</p>
      <p style="color: #475569; font-size: 15px; line-height: 1.5;">Thank you for registering your workspace with Appointment Assistant. Use the following verification code to complete your signup:</p>
      <div style="margin: 24px 0; text-align: center;">
        <div style="display: inline-block; background: #f8fafc; border: 2px dashed #0284c7; border-radius: 10px; padding: 14px 32px; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #0284c7; font-family: monospace;">
          {code}
        </div>
      </div>
      <p style="color: #64748b; font-size: 13px; margin-bottom: 0;">This code will expire in {ttl} minutes. If you did not create an account, you can safely ignore this email.</p>
    </div>
    """
    await asyncio.to_thread(
        _deliver,
        email,
        "Verify your Appointment Assistant account",
        f"Hello {business_name}, your email verification code is {code}. It expires in {ttl} minutes.",
        html_content,
    )


async def send_password_reset(email: str, business_name: str, code: str) -> None:
    safe_name = html.escape(business_name)
    ttl = settings.reset_ttl_minutes
    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #0f172a; margin-top: 0; font-size: 20px;">Reset your password</h2>
      <p style="color: #475569; font-size: 15px; line-height: 1.5;">Hello <strong>{safe_name}</strong>,</p>
      <p style="color: #475569; font-size: 15px; line-height: 1.5;">We received a request to reset your password. Use the code below to complete the reset:</p>
      <div style="margin: 24px 0; text-align: center;">
        <div style="display: inline-block; background: #f8fafc; border: 2px dashed #0284c7; border-radius: 10px; padding: 14px 32px; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #0284c7; font-family: monospace;">
          {code}
        </div>
      </div>
      <p style="color: #64748b; font-size: 13px; margin-bottom: 0;">This code will expire in {ttl} minutes. If you did not request a password reset, please ignore this email.</p>
    </div>
    """
    await asyncio.to_thread(
        _deliver,
        email,
        "Reset your Appointment Assistant password",
        f"Hello {business_name}, your password reset code is {code}. It expires in {ttl} minutes.",
        html_content,
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

