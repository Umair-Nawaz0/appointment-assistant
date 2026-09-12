from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Request

from .config import settings
from .db import execute, fetchrow
from .errors import AppError
from .security import hash_token


@dataclass(frozen=True, slots=True)
class AuthBusiness:
    business_id: UUID
    email: str
    business_name: str

    def json(self) -> dict[str, object]:
        return {
            "businessId": str(self.business_id), "email": self.email,
            "businessName": self.business_name,
        }


async def current_business(request: Request) -> AuthBusiness:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise AppError(401, "Please sign in to continue.", "UNAUTHENTICATED")
    row = await fetchrow(
        """SELECT s.id AS session_id, b.id AS business_id, b.email,
                  b.name AS business_name, s.last_seen_at
             FROM business_sessions s JOIN businesses b ON b.id=s.business_id
            WHERE s.token_hash=$1 AND s.revoked_at IS NULL AND s.expires_at>CURRENT_TIMESTAMP
              AND b.status='ACTIVE' AND b.email_verified_at IS NOT NULL""",
        hash_token(raw_token),
    )
    if not row:
        raise AppError(401, "Your session has expired. Please sign in again.", "UNAUTHENTICATED")
    await execute(
        "UPDATE business_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE id=$1 AND last_seen_at<CURRENT_TIMESTAMP-interval '15 minutes'",
        row["session_id"],
    )
    return AuthBusiness(row["business_id"], row["email"], row["business_name"])
