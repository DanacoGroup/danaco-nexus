"""Uwierzytelnianie administratora: hasło (Argon2), sesje w bazie, ochrona CSRF.

Sesja to losowy token w ciasteczku ``HttpOnly``; w bazie przechowywany jest
wyłącznie jego skrót SHA-256. Żądania zmieniające stan wymagają nagłówka
``X-Nexus-Request`` (niedostępnego dla formularzy innych witryn).
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from nexus.db import Database, Setting, UserSession, utcnow

COOKIE_NAME = "nexus_session"
CSRF_HEADER = "x-nexus-request"
USERNAME_KEY = "admin_username"
PASSWORD_KEY = "admin_password_hash"
DEFAULT_USERNAME = "admin"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

hasher = PasswordHasher()
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=500)


def token_hash(token: str) -> str:
    """Skrót tokenu sesji przechowywany w bazie."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def set_admin_credentials(database: Database, username: str, password: str) -> None:
    """Ustawia login i hasło administratora; unieważnia wszystkie sesje."""
    if len(password) < 12:
        raise ValueError("Hasło musi mieć co najmniej 12 znaków.")
    async with database.session() as session:
        for key, value in ((USERNAME_KEY, username), (PASSWORD_KEY, hasher.hash(password))):
            existing = await session.get(Setting, key)
            if existing is None:
                session.add(Setting(key=key, value=value))
            else:
                existing.value, existing.updated_at = value, utcnow()
        await session.execute(delete(UserSession))


class LoginThrottle:
    """Ograniczenie liczby nieudanych logowań z jednego adresu IP."""

    def __init__(self, attempts: int, window_seconds: int = 900) -> None:
        self._attempts = attempts
        self._window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, ip: str) -> deque[float]:
        entries = self._failures[ip]
        cutoff = time.monotonic() - self._window
        while entries and entries[0] < cutoff:
            entries.popleft()
        return entries

    def blocked(self, ip: str) -> bool:
        return len(self._recent(ip)) >= self._attempts

    def failure(self, ip: str) -> None:
        self._recent(ip).append(time.monotonic())

    def success(self, ip: str) -> None:
        self._failures.pop(ip, None)


def client_ip(request: Request) -> str:
    """Adres klienta (za zaufanym proxy – z nagłówka X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "?"


async def require_session(request: Request) -> UserSession:
    """Zależność FastAPI: wymaga ważnej sesji (i nagłówka CSRF dla zmian stanu)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wymagane logowanie.")
    database: Database = request.app.state.database
    async with database.session() as session:
        record = await session.get(UserSession, token_hash(token))
        if record is None or record.expires_at < utcnow():
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesja wygasła – zaloguj się ponownie.")
        if (utcnow() - record.last_seen_at) > timedelta(minutes=5):
            record.last_seen_at = utcnow()
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Brak nagłówka żądania aplikacji.")
    return record


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, str]:
    """Logowanie administratora."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Brak nagłówka żądania aplikacji.")
    settings = request.app.state.settings
    throttle: LoginThrottle = request.app.state.login_throttle
    ip = client_ip(request)
    if throttle.blocked(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Zbyt wiele nieudanych prób logowania. Spróbuj za 15 minut."
        )
    database: Database = request.app.state.database
    async with database.session() as session:
        stored = {
            row.key: row.value
            for row in (
                await session.scalars(select(Setting).where(Setting.key.in_([USERNAME_KEY, PASSWORD_KEY])))
            ).all()
        }
    password_hash = stored.get(PASSWORD_KEY)
    if not password_hash:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Hasło administratora nie jest ustawione. Na serwerze uruchom: deploy/nexus-cli.sh set-password",
        )
    username_ok = secrets.compare_digest(
        payload.username.strip().lower(), stored.get(USERNAME_KEY, DEFAULT_USERNAME).lower()
    )
    try:
        password_ok = hasher.verify(password_hash, payload.password)
    except (VerificationError, InvalidHashError):
        password_ok = False
    if not (username_ok and password_ok):
        throttle.failure(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nieprawidłowy login lub hasło.")
    throttle.success(ip)
    token = secrets.token_urlsafe(32)
    lifetime = timedelta(days=settings.session_days)
    async with database.session() as session:
        session.add(
            UserSession(
                token_hash=token_hash(token),
                expires_at=utcnow() + lifetime,
                ip_address=ip[:64],
                user_agent=request.headers.get("user-agent", "")[:300],
            )
        )
        if hasher.check_needs_rehash(password_hash):
            record = await session.get(Setting, PASSWORD_KEY)
            if record is not None:
                record.value = hasher.hash(payload.password)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        # Z domeną nadrzędną ciasteczko trafia też do chmury (logowanie jednokrotne).
        domain=settings.cookie_domain or None,
    )
    return {"username": stored.get(USERNAME_KEY, DEFAULT_USERNAME)}


@router.post("/logout")
async def logout(
    request: Request, response: Response, _: UserSession = Depends(require_session)
) -> dict[str, bool]:
    """Wylogowanie (usunięcie sesji)."""
    token = request.cookies.get(COOKIE_NAME, "")
    database: Database = request.app.state.database
    async with database.session() as session:
        await session.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))
    response.delete_cookie(COOKIE_NAME, path="/", domain=request.app.state.settings.cookie_domain or None)
    return {"ok": True}


SSO_USER_HEADER = "X-Nexus-User"
CLOUD_LOGIN_PATHS = frozenset({"/login", "/index.php/login"})


async def _valid_session(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    database: Database = request.app.state.database
    async with database.session() as session:
        record = await session.get(UserSession, token_hash(token))
    return record is not None and record.expires_at >= utcnow()


@router.get("/sso", include_in_schema=False)
async def sso(request: Request) -> Response:
    """Logowanie jednokrotne do chmury osobistej (wywoływane przez ``forward_auth`` Caddy).

    Przy ważnej sesji Nexusa odpowiedź niesie nagłówek ``X-Nexus-User`` z kontem
    Nextcloud – Caddy przekazuje go do chmury, która loguje użytkownika bez hasła.
    Bez sesji: strona logowania chmury przekierowuje do logowania Nexusa (powrót do
    chmury po zalogowaniu), pozostałe adresy (udostępnienia, zasoby) przechodzą dalej.
    """
    settings = request.app.state.settings
    if await _valid_session(request):
        return Response(
            status_code=status.HTTP_204_NO_CONTENT, headers={SSO_USER_HEADER: settings.chmura_user}
        )
    original = urlsplit(request.headers.get("x-forwarded-uri", "/"))
    direct = "direct=1" in original.query.split("&")
    if original.path in CLOUD_LOGIN_PATHS and not direct and settings.public_url:
        return Response(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": f"{settings.public_url.rstrip('/')}/?next=cloud"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(request: Request, _: UserSession = Depends(require_session)) -> dict[str, str]:
    """Dane zalogowanego użytkownika i adres chmury osobistej (pusty, gdy brak)."""
    database: Database = request.app.state.database
    async with database.session() as session:
        record = await session.get(Setting, USERNAME_KEY)
    return {
        "username": record.value if record else DEFAULT_USERNAME,
        "cloud_url": request.app.state.settings.chmura_public_url,
    }
