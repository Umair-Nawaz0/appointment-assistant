from __future__ import annotations

import logging

import asyncpg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("appointment_assistant.errors")


class AppError(Exception):
    def __init__(self, status: int, message: str, code: str = "REQUEST_ERROR", details: object = None):
        self.status = status
        self.message = message
        self.code = code
        self.details = details
        super().__init__(message)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, error: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": error.message, "details": error.details}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Please check the submitted fields.", "details": error.errors()}},
        )

    @app.exception_handler(asyncpg.UniqueViolationError)
    async def unique_handler(_request: Request, _error: asyncpg.UniqueViolationError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": {"code": "CONFLICT", "message": "That value is already in use."}})

    @app.exception_handler(asyncpg.PostgresError)
    async def database_handler(_request: Request, error: asyncpg.PostgresError) -> JSONResponse:
        logger.error("PostgreSQL error %s: %s", error.sqlstate, error)
        if error.sqlstate in {"23503", "23514", "22P02", "22023"}:
            return JSONResponse(status_code=400, content={"error": {"code": "DATABASE_VALIDATION_ERROR", "message": "The submitted data is invalid."}})
        return JSONResponse(status_code=500, content={"error": {"code": "DATABASE_ERROR", "message": "The database request failed."}})

    @app.exception_handler(Exception)
    async def unexpected_handler(_request: Request, error: Exception) -> JSONResponse:
        logger.exception("Unhandled API error", exc_info=error)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong. Please try again."}},
        )
