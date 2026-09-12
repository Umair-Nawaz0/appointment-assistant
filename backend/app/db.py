from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from .config import settings

pool: asyncpg.Pool | None = None


async def _initialize_connection(connection: asyncpg.Connection) -> None:
    await connection.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await connection.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def connect() -> None:
    global pool
    kwargs: dict[str, object] = {
        "min_size": 1,
        "max_size": 15,
        "command_timeout": 20,
        "server_settings": {"application_name": "appointment_assistant_fastapi"},
        "init": _initialize_connection,
    }
    if settings.database_url:
        pool = await asyncpg.create_pool(dsn=settings.database_url, **kwargs)
    else:
        pool = await asyncpg.create_pool(
            host=settings.pg_host,
            port=settings.pg_port,
            database=settings.pg_database,
            user=settings.pg_user,
            password=settings.pg_password,
            **kwargs,
        )


async def disconnect() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    return pool


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    async with get_pool().acquire() as connection:
        async with connection.transaction():
            yield connection


async def fetch(query: str, *values: object) -> list[asyncpg.Record]:
    return list(await get_pool().fetch(query, *values))


async def fetchrow(query: str, *values: object) -> asyncpg.Record | None:
    return await get_pool().fetchrow(query, *values)


async def execute(query: str, *values: object) -> str:
    return await get_pool().execute(query, *values)
