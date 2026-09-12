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
    host: str = "127.0.0.1"
    port: int = _int("PORT", 4000)
    app_url: str = os.getenv("APP_URL", "http://localhost:5173")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    database_url: str | None = os.getenv("DATABASE_URL")
    pg_host: str = os.getenv("PGHOST", "/var/run/postgresql")
    pg_port: int = _int("PGPORT", 5432)
    pg_database: str = os.getenv("PGDATABASE", "apointment_assitant")
    pg_user: str = os.getenv("PGUSER", "umair")
    pg_password: str | None = os.getenv("PGPASSWORD") or None
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
