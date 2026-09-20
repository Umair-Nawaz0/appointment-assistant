from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = os.getenv("NODE_ENV", os.getenv("ENVIRONMENT", "development"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _int("PORT", 4000)
    app_url: str = os.getenv("APP_URL", "http://localhost:5173")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    database_url: str | None = os.getenv("DATABASE_URL")
    pg_host: str = os.getenv("PGHOST", "127.0.0.1")
    pg_port: int = _int("PGPORT", 5432)
    pg_database: str = os.getenv("PGDATABASE", "apointment_assitant")
    pg_user: str = os.getenv("PGUSER", "umair")
    pg_password: str | None = os.getenv("PGPASSWORD", "postgres") or None
    backend_api_key: str = os.getenv("BACKEND_API_KEY", "appt_dcef54701d6e66eba727d4061616c70be6f1a8a450234f09ba585470e931c891")
    n8n_webhook_base_url: str = os.getenv("N8N_WEBHOOK_BASE_URL", os.getenv("N8N_WEBHOOK_URL", os.getenv("WEBHOOK_URL", "http://127.0.0.1:5678"))).rstrip("/")
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "appointment_session")
    session_ttl_days: int = _int("SESSION_TTL_DAYS", 7)
    verification_ttl_minutes: int = _int("EMAIL_VERIFICATION_CODE_TTL_MINUTES", 15)
    reset_ttl_minutes: int = _int("PASSWORD_RESET_TTL_MINUTES", 60)
    mail_mode: str = os.getenv("MAIL_MODE", "console")
    mail_from: str = os.getenv("MAIL_FROM", "Appointment Assistant <no-reply@example.com>")
    smtp_host: str | None = os.getenv("SMTP_HOST") or None
    smtp_port: int = _int("SMTP_PORT", 587)
    smtp_secure: bool = _bool("SMTP_SECURE")
    smtp_require_tls: bool = _bool("SMTP_REQUIRE_TLS", True)
    smtp_user: str | None = os.getenv("SMTP_USER") or None
    smtp_password: str | None = os.getenv("SMTP_PASSWORD") or None

    # Gmail Integration Settings
    gmail_sender_email: str | None = os.getenv("GMAIL_SENDER_EMAIL") or os.getenv("GMAIL_USER") or None
    gmail_api_secret_key: str | None = os.getenv("GMAIL_API_SECRET_KEY") or os.getenv("GMAIL_APP_PASSWORD") or None
    gmail_client_id: str | None = os.getenv("GMAIL_CLIENT_ID") or None
    gmail_client_secret: str | None = os.getenv("GMAIL_CLIENT_SECRET") or None
    gmail_refresh_token: str | None = os.getenv("GMAIL_REFRESH_TOKEN") or None
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        configured = os.getenv("FRONTEND_ORIGINS", "")
        origins = {
            value.strip().rstrip("/")
            for value in configured.split(",")
            if value.strip()
        }
        origins.update({self.frontend_origin.rstrip("/"), self.app_url.rstrip("/")})
        if not self.production:
            for origin in tuple(origins):
                parsed = urlsplit(origin)
                if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
                    "localhost", "127.0.0.1",
                }:
                    continue
                port = f":{parsed.port}" if parsed.port else ""
                origins.add(f"{parsed.scheme}://localhost{port}")
                origins.add(f"{parsed.scheme}://127.0.0.1{port}")
            origins.update({
                f"http://localhost:{self.port}",
                f"http://127.0.0.1:{self.port}",
            })
        return tuple(sorted(origins))

    def validate(self) -> None:
        # Auto-configure Gmail SMTP if Gmail credentials are provided
        if self.gmail_sender_email and self.gmail_api_secret_key:
            if not self.smtp_host:
                self.smtp_host = "smtp.gmail.com"
                self.smtp_port = 465
                self.smtp_secure = True
                self.smtp_user = self.gmail_sender_email
                self.smtp_password = self.gmail_api_secret_key.replace(" ", "")
                if self.mail_mode == "console":
                    self.mail_mode = "smtp"
                if "no-reply@example.com" in self.mail_from:
                    self.mail_from = f"Appointment Assistant <{self.gmail_sender_email}>"

        if self.mail_mode not in {"console", "smtp"}:
            raise RuntimeError("MAIL_MODE must be console or smtp")
        if self.mail_mode == "smtp" and not all((self.smtp_host, self.smtp_user, self.smtp_password)):
            raise RuntimeError("SMTP_HOST, SMTP_USER, and SMTP_PASSWORD are required in smtp mode")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
                raise RuntimeError(f"Invalid frontend origin: {origin}")


settings = Settings()
settings.validate()
