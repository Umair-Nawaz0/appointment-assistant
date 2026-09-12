from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT_DIR, settings
from .db import connect, disconnect, fetchrow
from .errors import install_error_handlers
from .routers import appointments, auth, business, conversations, customers, dashboard


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await connect()
    yield
    await disconnect()


app = FastAPI(
    title="Appointment Assistant API",
    version="1.0.0",
    docs_url="/docs" if not settings.production else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
install_error_handlers(app)

_auth_attempts: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.url.path.startswith("/api") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.allowed_origins:
            return JSONResponse(status_code=403, content={"error": {"code": "UNTRUSTED_ORIGIN", "message": "Untrusted request origin."}})
    if request.url.path.startswith("/api/auth/") and request.method == "POST":
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = _auth_attempts[key]
        while bucket and bucket[0] < now - 900:
            bucket.popleft()
        if len(bucket) >= 30:
            return JSONResponse(status_code=429, content={"error": {"code": "RATE_LIMITED", "message": "Too many authentication requests. Try again later."}})
        bucket.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/api/health", tags=["System"])
async def health() -> dict[str, str]:
    await fetchrow("SELECT 1")
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(business.router)
app.include_router(customers.router)
app.include_router(appointments.router)
app.include_router(conversations.router)

frontend_dist = ROOT_DIR / "frontend" / "dist"
if frontend_dist.is_dir():
    assets = frontend_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND", "message": "Route not found."}})
        candidate = (frontend_dist / path).resolve()
        if candidate.is_file() and frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")
