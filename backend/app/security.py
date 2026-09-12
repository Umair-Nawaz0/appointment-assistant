from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets


async def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = await asyncio.to_thread(
        hashlib.scrypt, password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


async def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_hex, hash_hex = stored_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(hash_hex)
        actual = await asyncio.to_thread(
            hashlib.scrypt,
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=16384,
            r=8,
            p=1,
            dklen=len(expected),
        )
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def create_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(business_id: object, code_type: str, code: str) -> str:
    value = f"{business_id}:{code_type}:{code}"
    return hashlib.sha256(value.encode()).hexdigest()
