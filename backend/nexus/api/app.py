"""Aplikacja FastAPI: API czatu i serwowanie interfejsu WWW."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from nexus import __version__
from nexus.api import auth, conversations, files, modules, runs, voice
from nexus.config import Settings, get_settings
from nexus.db import Database
from nexus.events import EventBus
from nexus.knowledge import KnowledgeBase
from nexus.logging_setup import configure_logging
from nexus.storage import FileStorage
from nexus.voice import VoiceEngine

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(self), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "frame-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; "
        "worker-src 'self'; manifest-src 'self'"
    ),
}
# Pliki PWA, które przeglądarka musi zawsze sprawdzać (aktualizacje aplikacji).
NO_CACHE_FILES = frozenset(
    {"sw.js", "registerSW.js", "share-target.js", "manifest.webmanifest", "index.html"}
)
IMMUTABLE = "public, max-age=31536000, immutable"
# Typy podawane wprost: `mimetypes` zależy od pliku mime.types systemu, a bez poprawnego
# typu przeglądarka nie narysuje tła AVIF ani nie wczyta kroju i napisów.
MEDIA_TYPES = {
    ".webmanifest": "application/manifest+json",
    ".js": "text/javascript",
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".vtt": "text/vtt",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


class ImmutableStatic(StaticFiles):
    """Zasoby z nazwą zawierającą skrót treści – buforowane bezterminowo."""

    def file_response(self, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = IMMUTABLE
        return response


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
        app.state.goscie = auth.LimitKontGoscia(auth.GOSC_NA_ADRES)
        app.state.events = EventBus(settings.redis_url)
        app.state.voice = VoiceEngine(settings)
        if settings.voice_warm_up:
            asyncio.get_running_loop().run_in_executor(None, app.state.voice.warm_up)
        app.state.knowledge = KnowledgeBase(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_model,
            settings.cache_dir / "fastembed",
        )
        yield
        await app.state.events.close()
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
    for module in (auth, conversations, files, runs, voice):
        app.include_router(module.router)
    # Moduły aplikacji (nexus/api/modules/*.py) – podłączane automatycznie.
    for router in modules.routers():
        app.include_router(router)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    static = settings.static_dir
    if (static / "index.html").is_file():
        if (static / "assets").is_dir():
            app.mount("/assets", ImmutableStatic(directory=static / "assets"), name="assets")

        @app.post("/share-target", include_in_schema=False)
        async def share_target() -> Response:
            # Udostępnianie obsługuje service worker; bez niego (pierwsze uruchomienie)
            # wracamy do aplikacji zamiast błędu.
            return RedirectResponse("/", status_code=303)

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> Response:
            if path.startswith("api/"):
                return JSONResponse({"detail": "Nie znaleziono."}, status_code=404)
            candidate = (static / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(static.resolve()):
                cache = "no-cache" if candidate.name in NO_CACHE_FILES else "public, max-age=86400"
                if candidate.name.startswith("workbox-"):
                    cache = IMMUTABLE
                return FileResponse(
                    candidate,
                    media_type=MEDIA_TYPES.get(candidate.suffix),
                    headers={"Cache-Control": cache},
                )
            return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
