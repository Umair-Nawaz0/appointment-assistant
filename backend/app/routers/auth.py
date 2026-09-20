from __future__ import annotations

import hmac
from datetime import timedelta

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends, Request, Response

from ..config import settings
from ..db import execute, fetchrow, transaction
from ..dependencies import AuthBusiness, current_business
from ..errors import AppError
from ..mail import send_password_reset, send_verification
from ..schemas import CodeInput, EmailInput, Login, ResetPassword, Signup
from ..security import create_code, create_token, hash_code, hash_password, hash_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
MAX_CODE_ATTEMPTS = 5


async def _issue_code(business_id: object, code_type: str) -> str:
    duration = (
        timedelta(minutes=settings.verification_ttl_minutes)
        if code_type == "EMAIL_VERIFICATION"
        else timedelta(minutes=settings.reset_ttl_minutes)
    )
    for _attempt in range(10):
        code = create_code()
        try:
            await execute(
                """WITH auth_lock AS MATERIALIZED (
                     SELECT pg_advisory_xact_lock(
                         hashtextextended($1::uuid::text || ':' || $2::text, 0)
                     )
                   ), consumed AS (
                     UPDATE business_auth_codes AS code SET consumed_at=CURRENT_TIMESTAMP
                       FROM auth_lock
                      WHERE code.business_id=$1::uuid
                        AND code.code_type=$2::business_auth_code_type
                        AND code.consumed_at IS NULL
                   )
                   INSERT INTO business_auth_codes (business_id,code_type,code_hash,expires_at)
                   SELECT $1::uuid,$2::business_auth_code_type,$3,CURRENT_TIMESTAMP+$4::interval
                     FROM auth_lock""",
                business_id,
                code_type,
                hash_code(business_id, code_type, code),
                duration,
            )
            return code
        except UniqueViolationError:
            continue
    raise RuntimeError("Could not allocate a unique authentication code")


async def _consume_code(connection, business_id: object, code_type: str, supplied_code: str) -> bool:
    row = await connection.fetchrow(
        """SELECT id,code_hash,attempt_count
             FROM business_auth_codes
            WHERE business_id=$1 AND code_type=$2::business_auth_code_type
              AND consumed_at IS NULL AND expires_at>CURRENT_TIMESTAMP
            ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
        business_id,
        code_type,
    )
    valid = bool(row) and hmac.compare_digest(
        row["code_hash"], hash_code(business_id, code_type, supplied_code)
    )
    if not valid:
        if row:
            attempts = row["attempt_count"] + 1
            await connection.execute(
                """UPDATE business_auth_codes
                      SET attempt_count=$1::smallint,
                          consumed_at=CASE WHEN $1::smallint >= $2::smallint THEN CURRENT_TIMESTAMP ELSE consumed_at END
                    WHERE id=$3::uuid""",
                attempts,
                MAX_CODE_ATTEMPTS,
                row["id"],
            )
        return False
    await connection.execute(
        "UPDATE business_auth_codes SET consumed_at=CURRENT_TIMESTAMP WHERE id=$1", row["id"]
    )
    return True


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.production,
        samesite="lax",
        path="/",
    )


def _public_business(row) -> dict[str, str]:
    return {
        "businessId": str(row["id"]),
        "email": row["email"],
        "businessName": row["name"],
    }


@router.post("/signup", status_code=201)
async def signup(payload: Signup) -> dict[str, object]:
    email = str(payload.email).lower()
    password_hash = await hash_password(payload.password)
    async with transaction() as connection:
        existing = await connection.fetchval("SELECT 1 FROM businesses WHERE email=$1", email)
        if existing:
            raise AppError(409, "A business with this email already exists.", "EMAIL_EXISTS")
        business = await connection.fetchrow(
            """INSERT INTO businesses (name,email,password_hash,industry,timezone)
               VALUES ($1,$2,$3,$4,$5) RETURNING id,name,email""",
            payload.businessName,
            email,
            password_hash,
            payload.industry,
            payload.timezone,
        )
        await connection.execute("INSERT INTO business_settings (business_id) VALUES ($1)", business["id"])
    code = await _issue_code(business["id"], "EMAIL_VERIFICATION")
    await send_verification(email, business["name"], code)
    return {
        "message": "Workspace created. Enter the code sent to your business email.",
        "email": email,
    }


@router.post("/verify-email")
async def verify_email(payload: CodeInput) -> dict[str, str]:
    email = str(payload.email).lower()
    valid = False
    async with transaction() as connection:
        business = await connection.fetchrow(
            "SELECT id,email_verified_at FROM businesses WHERE email=$1 AND status='ACTIVE' FOR UPDATE",
            email,
        )
        if business and business["email_verified_at"] is not None:
            return {"message": "Email is already verified. You can sign in."}
        if business:
            valid = await _consume_code(
                connection, business["id"], "EMAIL_VERIFICATION", payload.code
            )
            if valid:
                await connection.execute(
                    "UPDATE businesses SET email_verified_at=CURRENT_TIMESTAMP WHERE id=$1", business["id"]
                )
    if not valid:
        raise AppError(400, "This code is invalid or expired.", "INVALID_CODE")
    return {"message": "Email verified. You can now sign in."}


@router.post("/resend-verification")
async def resend(payload: EmailInput) -> dict[str, object]:
    email = str(payload.email).lower()
    business = await fetchrow(
        "SELECT id,name FROM businesses WHERE email=$1 AND email_verified_at IS NULL AND status='ACTIVE'",
        email,
    )
    result: dict[str, object] = {
        "message": "If the business email is awaiting verification, a new code has been sent."
    }
    if business:
        code = await _issue_code(business["id"], "EMAIL_VERIFICATION")
        await send_verification(email, business["name"], code)
    return result


@router.post("/login")
async def login(payload: Login, response: Response) -> dict[str, object]:
    email = str(payload.email).lower()
    business = await fetchrow(
        """SELECT id,name,email,password_hash,status::text,email_verified_at
             FROM businesses WHERE email=$1""",
        email,
    )
    if not business or not await verify_password(payload.password, business["password_hash"]):
        raise AppError(401, "Email or password is incorrect.", "INVALID_CREDENTIALS")
    if business["status"] != "ACTIVE":
        raise AppError(403, "This business is not active.", "BUSINESS_DISABLED")
    if business["email_verified_at"] is None:
        raise AppError(403, "Verify your business email before signing in.", "EMAIL_NOT_VERIFIED")
    raw = create_token()
    async with transaction() as connection:
        await connection.execute(
            "INSERT INTO business_sessions (business_id,token_hash,expires_at) VALUES ($1,$2,CURRENT_TIMESTAMP+$3::interval)",
            business["id"],
            hash_token(raw),
            timedelta(days=settings.session_ttl_days),
        )
        await connection.execute(
            "UPDATE businesses SET last_login_at=CURRENT_TIMESTAMP WHERE id=$1", business["id"]
        )
    _set_cookie(response, raw)
    return {"business": _public_business(business)}


@router.post("/forgot-password")
async def forgot(payload: EmailInput) -> dict[str, object]:
    email = str(payload.email).lower()
    business = await fetchrow(
        """SELECT id,name FROM businesses
            WHERE email=$1 AND status='ACTIVE' AND email_verified_at IS NOT NULL""",
        email,
    )
    result: dict[str, object] = {
        "message": "If an active business exists, a password reset code has been sent."
    }
    if business:
        code = await _issue_code(business["id"], "PASSWORD_RESET")
        await send_password_reset(email, business["name"], code)
    return result


@router.post("/reset-password")
async def reset(payload: ResetPassword) -> dict[str, str]:
    email = str(payload.email).lower()
    new_hash = await hash_password(payload.password)
    valid = False
    async with transaction() as connection:
        business = await connection.fetchrow(
            """SELECT id FROM businesses
                WHERE email=$1 AND status='ACTIVE' AND email_verified_at IS NOT NULL FOR UPDATE""",
            email,
        )
        if business:
            valid = await _consume_code(
                connection, business["id"], "PASSWORD_RESET", payload.code
            )
            if valid:
                await connection.execute(
                    "UPDATE businesses SET password_hash=$1 WHERE id=$2", new_hash, business["id"]
                )
                await connection.execute(
                    "UPDATE business_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE business_id=$1 AND revoked_at IS NULL",
                    business["id"],
                )
    if not valid:
        raise AppError(400, "This code is invalid or expired.", "INVALID_CODE")
    return {"message": "Password updated. Sign in with your new password."}


@router.get("/me")
async def me(business: AuthBusiness = Depends(current_business)) -> dict[str, object]:
    return {"business": business.json()}


@router.post("/logout", status_code=204)
async def logout(request: Request, _business: AuthBusiness = Depends(current_business)) -> Response:
    raw = request.cookies.get(settings.session_cookie_name)
    if raw:
        await execute(
            "UPDATE business_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE token_hash=$1 AND revoked_at IS NULL",
            hash_token(raw),
        )
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.production,
        httponly=True,
        samesite="lax",
    )
    return response
