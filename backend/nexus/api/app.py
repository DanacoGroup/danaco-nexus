"""Aplikacja FastAPI: API czatu i serwowanie interfejsu WWW."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from nexus import __version__
from nexus.api import auth, conversations, files, runs
from nexus.config import Settings, get_settings
from nexus.db import Database
from nexus.knowledge import KnowledgeBase
from nexus.logging_setup import configure_logging
from nexus.storage import FileStorage

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "frame-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


class SecurityHeaders(BaseHTTPMiddleware):
    """Nagłówki bezpieczeństwa dla wszystkich odpowiedzi."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Tworzy aplikację z podanymi (lub środowiskowymi) ustawieniami."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.data_dir / "logs", "api")
        database = Database(settings.database_url)
        await database.create_schema()
        app.state.settings = settings
        app.state.database = database
        app.state.storage = FileStorage(settings.files_dir)
        app.state.login_throttle = auth.LoginThrottle(settings.login_attempts_per_15_min)
        app.state.knowledge = KnowledgeBase(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_model,
            settings.cache_dir / "fastembed",
        )
        yield
        await database.close()

    app = FastAPI(
        title="Danaco Nexus",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(SecurityHeaders)
    for module in (auth, conversations, files, runs):
        app.include_router(module.router)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    static = settings.static_dir
    if (static / "index.html").is_file():
        if (static / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> Response:
            if path.startswith("api/"):
                return JSONResponse({"detail": "Nie znaleziono."}, status_code=404)
            candidate = (static / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(static.resolve()):
                return FileResponse(candidate)
            return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
