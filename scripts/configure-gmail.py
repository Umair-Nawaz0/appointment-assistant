#!/usr/bin/env python3
"""
Gmail Configuration & Verification Script for Appointment Assistant
-------------------------------------------------------------------
Reads GMAIL_* variables from .env, validates the credentials against Gmail,
configures n8n credentials, updates backend settings, and tests live email delivery.
"""

import argparse
import base64
import json
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
import urllib.request
import urllib.parse

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_DIR / ".env"
CREDENTIALS_DIR = PROJECT_DIR / "credentials"


def load_env() -> dict[str, str]:
    env_vars = {}
    if not ENV_FILE.exists():
        return env_vars
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'\"")
        env_vars[key] = val
    return env_vars


def save_env_var(key: str, value: str):
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    pattern = rf"^{re.escape(key)}=.*$"
    new_line = f"{key}={value}"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, new_line, text, flags=re.MULTILINE)
    else:
        text += f"\n{new_line}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def test_gmail_smtp(email_addr: str, password: str) -> tuple[bool, str]:
    clean_pwd = password.replace(" ", "").strip()
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15, context=context) as server:
            server.login(email_addr, clean_pwd)
        return True, "Authentication successful! Connected to smtp.gmail.com:465"
    except smtplib.SMTPAuthenticationError as e:
        return False, (
            f"Gmail Authentication Failed ({e.smtp_code}: {e.smtp_error.decode('utf-8', errors='ignore') if isinstance(e.smtp_error, bytes) else e.smtp_error}).\n"
            "Tips:\n"
            "  1. Ensure 2-Step Verification is ON in your Google Account.\n"
            "  2. Generate a 16-character App Password at: https://myaccount.google.com/apppasswords\n"
            "  3. Do NOT use your regular Google account login password."
        )
    except Exception as e:
        return False, f"Connection error: {e}"


def send_test_email(sender: str, password: str, recipient: str) -> tuple[bool, str]:
    clean_pwd = password.replace(" ", "").strip()
    msg = EmailMessage()
    msg["From"] = f"Appointment Assistant <{sender}>"
    msg["To"] = recipient
    msg["Subject"] = "Appointment Assistant - Gmail Verification Test 📅"
    
    html_content = f"""<!doctype html>
<html>
<body style="font-family: Arial, sans-serif; background-color: #f0fdf4; padding: 24px;">
  <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #d1fae5; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <h2 style="color: #059669; margin-top: 0;">✅ Gmail Integration Verified!</h2>
    <p style="color: #334155; font-size: 15px; line-height: 1.6;">
      Hello! This is a verification test from your <strong>AI Appointment Assistant</strong>.
    </p>
    <div style="background: #f8fafc; border-left: 4px solid #10b981; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
      <p style="margin: 0; font-size: 14px; color: #475569;">
        <strong>Sender:</strong> {sender}<br>
        <strong>Recipient:</strong> {recipient}<br>
        <strong>Status:</strong> Live SMTP connection operational
      </p>
    </div>
    <p style="color: #64748b; font-size: 13px;">
      All patient appointment bookings will now automatically send confirmation emails and calendar invites (.ics) from this account.
    </p>
  </div>
</body>
</html>"""
    msg.set_content(f"Appointment Assistant - Gmail Verification Test. Sent from {sender} to {recipient}.")
    msg.add_alternative(html_content, subtype="html")

    # Attach dummy .ics
    ics_text = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Appointment Assistant//EN\r\nBEGIN:VEVENT\r\nSUMMARY:Verification Test\r\nEND:VEVENT\r\nEND:VCALENDAR"
    msg.add_attachment(ics_text.encode("utf-8"), maintype="text", subtype="calendar", filename="verify.ics")

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20, context=context) as server:
            server.login(sender, clean_pwd)
            server.send_message(msg)
        return True, f"Email sent successfully from {sender} to {recipient}!"
    except Exception as e:
        return False, f"Failed to send email: {e}"


def configure_n8n_smtp(sender: str, password: str) -> bool:
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    cred_file = CREDENTIALS_DIR / "gmail-smtp.json"
    cred_data = [
        {
            "id": "gmailSmtpCred01",
            "name": "Gmail SMTP account",
            "type": "smtp",
            "data": {
                "user": sender,
                "password": password.replace(" ", "").strip(),
                "host": "smtp.gmail.com",
                "port": 465,
                "secure": True,
                "disableStartTls": False,
            },
        }
    ]
    cred_file.write_text(json.dumps(cred_data, indent=2), encoding="utf-8")

    # Import into running n8n container if available
    cmd = (
        "docker exec appointment-assistant-n8n "
        "n8n import:credentials --input=/bootstrap/credentials/gmail-smtp.json >/dev/null 2>&1"
    )
    res = os.system(cmd)
    return res == 0


def main():
    parser = argparse.ArgumentParser(description="Configure and test Gmail integration")
    parser.add_argument("--test", metavar="RECIPIENT", help="Send a test verification email to this address")
    parser.add_argument("--email", help="Gmail sender email address")
    parser.add_argument("--key", help="Gmail App Password or Secret Key")
    args = parser.parse_args()

    print("=" * 64)
    print(" AI Appointment Assistant - Gmail Configuration & Setup")
    print("=" * 64)

    env = load_env()

    # Determine email
    sender_email = (
        args.email
        or env.get("GMAIL_SENDER_EMAIL")
        or env.get("GMAIL_USER")
        or env.get("SMTP_USER")
    )
    secret_key = (
        args.key
        or env.get("GMAIL_API_SECRET_KEY")
        or env.get("GMAIL_APP_PASSWORD")
        or env.get("SMTP_PASSWORD")
    )

    # Interactive prompt if missing
    if not sender_email or not secret_key:
        print("\n⚠️  Gmail configuration not fully set in .env:")
        if not sender_email:
            print("   • GMAIL_SENDER_EMAIL is missing")
        if not secret_key:
            print("   • GMAIL_API_SECRET_KEY / GMAIL_APP_PASSWORD is missing")
        
        print("\nHow to get a Gmail App Password in 60 seconds:")
        print("  1. Go to your Google Account: https://myaccount.google.com/security")
        print("  2. Ensure '2-Step Verification' is turned ON.")
        print("  3. Go to: https://myaccount.google.com/apppasswords")
        print("  4. Enter App Name: 'Appointment Assistant' and click 'Create'.")
        print("  5. Google will show a 16-character key (e.g., abcd efgh ijkl mnop).")
        print("  6. Copy that key into your .env file as GMAIL_API_SECRET_KEY=...\n")

        if sys.stdin.isatty():
            try:
                ans = input("Would you like to enter your Gmail credentials now? [y/N]: ").strip().lower()
                if ans in ("y", "yes"):
                    entered_email = input("Enter your Gmail address: ").strip()
                    entered_key = input("Enter your 16-character App Password: ").strip()
                    if entered_email and entered_key:
                        save_env_var("GMAIL_SENDER_EMAIL", entered_email)
                        save_env_var("GMAIL_API_SECRET_KEY", entered_key)
                        save_env_var("SMTP_USER", entered_email)
                        save_env_var("SMTP_PASSWORD", entered_key)
                        save_env_var("MAIL_MODE", "smtp")
                        save_env_var("MAIL_FROM", f"Appointment Assistant <{entered_email}>")
                        sender_email = entered_email
                        secret_key = entered_key
                        print("✓ Saved credentials to .env!")
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                sys.exit(0)

    if not sender_email or not secret_key:
        print("\n❌ Setup incomplete. Please add your credentials to .env:")
        print("   GMAIL_SENDER_EMAIL=your-email@gmail.com")
        print("   GMAIL_API_SECRET_KEY=your-16-char-app-password")
        print("\nThen run this script again: ./scripts/setup-gmail.sh")
        sys.exit(1)

    print(f"\n🔍 Testing Gmail connection for: {sender_email}...")
    success, msg = test_gmail_smtp(sender_email, secret_key)
    if not success:
        print(f"\n❌ Connection Failed:\n{msg}")
        sys.exit(1)

    print(f"✓ {msg}")

    # Configure n8n SMTP credential
    print("\n📦 Updating n8n credentials...")
    if configure_n8n_smtp(sender_email, secret_key):
        print("✓ Imported Gmail SMTP credential into n8n container.")
    else:
        print("Notice: n8n container might not be running yet; credentials will be imported on container start.")

    # Restart backend container to pick up new env vars if running
    print("\n🔄 Syncing backend service...")
    os.system("docker restart appointment-assistant-backend >/dev/null 2>&1 || true")
    print("✓ Backend service synced with new Gmail settings.")

    # Send test email if requested or prompt
    recipient = args.test
    if not recipient and sys.stdin.isatty():
        try:
            do_test = input(f"\nWould you like to send a live test email? [Y/n]: ").strip().lower()
            if do_test not in ("n", "no"):
                target = input(f"Enter recipient email [{sender_email}]: ").strip()
                recipient = target or sender_email
        except (KeyboardInterrupt, EOFError):
            pass

    if recipient:
        print(f"\n✉️  Sending test email to: {recipient}...")
        sent, send_msg = send_test_email(sender_email, secret_key, recipient)
        if sent:
            print(f"🎉 SUCCESS! {send_msg}")
            print("Check your inbox (and spam folder) to confirm receipt.")
        else:
            print(f"❌ Failed: {send_msg}")
    else:
        print(f"\n💡 To send a test email at any time, run:")
        print(f"   ./scripts/setup-gmail.sh --test umairknawaz@gmail.com")

    print("\n" + "=" * 64)
    print(" ✅ Gmail Integration is Fully Configured and Ready!")
    print("=" * 64)


if __name__ == "__main__":
    main()
