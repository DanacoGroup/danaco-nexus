"""Uwierzytelnianie administratora: hasło (Argon2), sesje w bazie, ochrona CSRF.

Sesja to losowy token w ciasteczku ``HttpOnly``; w bazie przechowywany jest
wyłącznie jego skrót SHA-256. Żądania zmieniające stan wymagają nagłówka
``X-Nexus-Request`` (niedostępnego dla formularzy innych witryn).
"""

from __future__ import annotations

import hashlib
import ipaddress
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import timedelta
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from nexus.db import ADMIN_OWNER, Database, DeviceToken, Setting, UserSession, utcnow

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


# Odwrotne proxy wdrożenia (Caddy) stoi na tej samej maszynie i łączy się z API po pętli
# zwrotnej, więc tylko stamtąd nagłówek ``X-Forwarded-For`` może pochodzić od proxy.
SIECI_PROXY = tuple(ipaddress.ip_network(zapis) for zapis in ("127.0.0.0/8", "::1/128"))


def _proxy_zaufane(adres: str) -> bool:
    """Czy żądanie przyszło od własnego proxy, czyli z pętli zwrotnej tej maszyny."""
    try:
        return any(ipaddress.ip_address(adres) in siec for siec in SIECI_PROXY)
    except ValueError:
        return False


def client_ip(request: Request) -> str:
    """Adres klienta odporny na podszycie nagłówkiem ``X-Forwarded-For``.

    Nagłówek liczy się wyłącznie w żądaniu z pętli zwrotnej i brany jest jego ostatni wpis –
    ten dopisuje proxy z adresu, który samo zobaczyło. Wpisy wcześniejsze przysyła klient,
    więc ufanie pierwszemu pozwalało obejść licznik logowań, limit kont próbnych i tempo
    piaskownicy jednym nagłówkiem.
    """
    peer = request.client.host if request.client else ""
    if not _proxy_zaufane(peer):
        return peer or "?"
    wpisy = [wpis.strip() for wpis in request.headers.get("x-forwarded-for", "").split(",") if wpis.strip()]
    return wpisy[-1][:64] if wpisy else peer


DEVICE_TOKEN_PREFIX = "nxd_"


async def device_session(request: Request) -> UserSession | None:
    """Sesja urządzenia z nagłówka ``Authorization: Bearer nxd_…`` (lub ``None``)."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    if not token.startswith(DEVICE_TOKEN_PREFIX):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nieprawidłowy klucz urządzenia.")
    database: Database = request.app.state.database
    async with database.session() as session:
        record = await session.scalar(select(DeviceToken).where(DeviceToken.token_hash == token_hash(token)))
        if record is None or record.revoked:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Klucz urządzenia jest nieważny lub cofnięty.")
        if record.last_used_at is None or (utcnow() - record.last_used_at) > timedelta(minutes=5):
            record.last_used_at = utcnow()
        request.state.device = {"id": str(record.id), "name": record.name, "kind": record.kind}
    now = utcnow()
    return UserSession(
        token_hash=f"device:{record.id}",
        owner_id=record.owner_id,
        created_at=now,
        expires_at=now + timedelta(days=1),
        last_seen_at=now,
    )


async def require_session(request: Request) -> UserSession:
    """Zależność FastAPI: wymaga ważnej sesji (i nagłówka CSRF dla zmian stanu).

    Urządzenia (Android, Desktop, rozszerzenie) uwierzytelniają się kluczem w nagłówku
    ``Authorization`` – takie żądania nie korzystają z ciasteczek, więc nie wymagają CSRF.
    """
    device = await device_session(request)
    if device is not None:
        return device
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


async def wlasciciel(sesja: UserSession = Depends(require_session)) -> uuid.UUID:
    """Konto, do którego należą rozmowy, pliki i przebiegi obsługiwane w tym żądaniu."""
    return sesja.owner_id


async def require_admin(sesja: UserSession = Depends(require_session)) -> UserSession:
    """Zależność FastAPI: sesja właściciela instalacji, nie dowolnego konta.

    Sama ważna sesja nie wystarcza do części administracyjnych: konto klienta portalu
    i konto próbne dostają taką samą sesję przy logowaniu, więc sprawdzenie musi pytać
    o właściciela, a nie o to, że ktokolwiek jest zalogowany.
    """
    if sesja.owner_id != ADMIN_OWNER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Ta część panelu jest dostępna tylko dla administratora instalacji."
        )
    return sesja


async def _konto_portalu(database: Database, login: str, haslo: str) -> tuple[uuid.UUID, str] | None:
    """Konto klienta portalu o podanym adresie e-mail, gdy hasło się zgadza.

    Import jest lokalny, bo moduł portalu korzysta z tego pliku (zależność w drugą stronę).
    """
    from nexus.models.portal import PortalUser

    adres = login.strip().lower()
    if "@" not in adres:
        return None
    async with database.session() as session:
        user = await session.scalar(select(PortalUser).where(PortalUser.email == adres))
        if user is None or not user.active:
            return None
        try:
            zgodne = hasher.verify(user.password_hash, haslo)
        except (VerificationError, InvalidHashError):
            return None
        if not zgodne:
            return None
        return user.id, user.name or user.email


def _ciasteczko_sesji(response: Response, settings, token: str, czas: timedelta) -> None:
    """Ustawia ciasteczko sesji — identycznie dla logowania i dla konta próbnego."""
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(czas.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        # Z domeną nadrzędną ciasteczko trafia też do chmury (logowanie jednokrotne).
        domain=settings.cookie_domain or None,
    )


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
        password_ok = hasher.verify(password_hash, payload.password) if username_ok else False
    except (VerificationError, InvalidHashError):
        password_ok = False
    owner = ADMIN_OWNER
    nazwa = stored.get(USERNAME_KEY, DEFAULT_USERNAME)
    if not (username_ok and password_ok):
        # Aplikacja przyjmuje też konta klientów założone w portalu. Każde ma własną
        # przestrzeń: rozmowy, pliki i przebiegi widzi wyłącznie właściciel.
        konto = await _konto_portalu(database, payload.username, payload.password)
        if konto is None:
            throttle.failure(ip)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nieprawidłowy login lub hasło.")
        owner, nazwa = konto
    throttle.success(ip)
    token = secrets.token_urlsafe(32)
    lifetime = timedelta(days=settings.session_days)
    async with database.session() as session:
        session.add(
            UserSession(
                token_hash=token_hash(token),
                owner_id=owner,
                expires_at=utcnow() + lifetime,
                ip_address=ip[:64],
                user_agent=request.headers.get("user-agent", "")[:300],
            )
        )
        if owner == ADMIN_OWNER and hasher.check_needs_rehash(password_hash):
            record = await session.get(Setting, PASSWORD_KEY)
            if record is not None:
                record.value = hasher.hash(payload.password)
    _ciasteczko_sesji(response, settings, token, lifetime)
    return {"username": nazwa}


class LimitKontGoscia:
    """Ile kont próbnych wolno założyć z jednego adresu IP w oknie czasu."""

    def __init__(self, ile: int, okno_sekund: int = 86_400) -> None:
        self._ile = ile
        self._okno = okno_sekund
        self._wpisy: dict[str, deque[float]] = defaultdict(deque)

    def _swieze(self, ip: str) -> deque[float]:
        wpisy = self._wpisy[ip]
        prog = time.monotonic() - self._okno
        while wpisy and wpisy[0] < prog:
            wpisy.popleft()
        return wpisy

    def przekroczony(self, ip: str) -> bool:
        return len(self._swieze(ip)) >= self._ile

    def dopisz(self, ip: str) -> None:
        self._swieze(ip).append(time.monotonic())


# Konto próbne: pełna aplikacja bez rejestracji. Adres jest techniczny (nikt go nie
# podaje i nie odbiera poczty), hasło losowe i nigdzie nie ujawniane — wejście daje
# wyłącznie ciasteczko sesji wydane przy zakładaniu konta.
GOSC_DOMENA = "goscie.danaco-nexus.local"
GOSC_PLAN = "probny"
GOSC_NAZWA = "Konto próbne"
GOSC_DNI = 2
GOSC_NA_ADRES = 5


async def _konto_goscia(database: Database) -> tuple[uuid.UUID, str]:
    """Zakłada świeże konto próbne i zwraca jego identyfikator oraz nazwę."""
    from nexus.models.portal import PortalUser

    znacznik = secrets.token_hex(8)
    uzytkownik = PortalUser(
        email=f"probny-{znacznik}@{GOSC_DOMENA}",
        password_hash=hasher.hash(secrets.token_urlsafe(32)),
        name=GOSC_NAZWA,
        plan=GOSC_PLAN,
        active=True,
    )
    async with database.session() as session:
        session.add(uzytkownik)
        await session.flush()
        owner = uzytkownik.id
    return owner, GOSC_NAZWA


@router.post("/gosc")
async def gosc(request: Request, response: Response) -> dict[str, str]:
    """Wejście do aplikacji bez rejestracji: własne konto próbne, własna przestrzeń.

    Gość dostaje to samo okno co klient płacący — rozmowę, pliki i narzędzia — tyle że
    na koncie, które wygasa i ma przydział startowy z okresu próbnego. Bez tego przycisk
    „Wypróbuj” pokazywałby makietę zamiast produktu.
    """
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Brak nagłówka żądania aplikacji.")
    settings = request.app.state.settings
    database: Database = request.app.state.database
    limit: LimitKontGoscia = request.app.state.goscie
    ip = client_ip(request)
    if limit.przekroczony(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Z tego łącza założono już kilka kont próbnych. Załóż zwykłe konto albo spróbuj jutro.",
        )
    owner, nazwa = await _konto_goscia(database)
    limit.dopisz(ip)

    from nexus.platnosci import kredyty as ksiega

    await ksiega.przydziel(
        database, owner, _kredyty_goscia(), "start", "Przydział konta próbnego"
    )
    token = secrets.token_urlsafe(32)
    czas = timedelta(days=GOSC_DNI)
    async with database.session() as session:
        session.add(
            UserSession(
                token_hash=token_hash(token),
                owner_id=owner,
                expires_at=utcnow() + czas,
                ip_address=ip[:64],
                user_agent=request.headers.get("user-agent", "")[:300],
            )
        )
    _ciasteczko_sesji(response, settings, token, czas)
    return {"username": nazwa, "gosc": "1"}


def _kredyty_goscia() -> int:
    """Przydział kredytów konta próbnego — tyle, ile daje okres próbny planu domyślnego."""
    from nexus.platnosci.plany import PLAN_DOMYSLNY, pozycja_katalogu

    pozycja = pozycja_katalogu(PLAN_DOMYSLNY)
    return pozycja.probny_kredyty if pozycja else 300


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


async def _sesja_ciasteczka(request: Request) -> UserSession | None:
    """Nieprzeterminowana sesja z ciasteczka (dowolne konto) albo ``None``."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    database: Database = request.app.state.database
    async with database.session() as session:
        record = await session.get(UserSession, token_hash(token))
    return record if record is not None and record.expires_at >= utcnow() else None


@router.get("/sso", include_in_schema=False)
async def sso(request: Request) -> Response:
    """Logowanie jednokrotne do chmury osobistej (wywoływane przez ``forward_auth`` Caddy).

    Nagłówek ``X-Nexus-User`` niesie konto Nextcloud właściciela instalacji, więc wydaje
    go wyłącznie sesja właściciela. Konto klienta portalu i konto próbne mają taką samą
    sesję, a ciasteczko jedzie na poddomenę chmury — dostają 204 bez nagłówka, czyli
    własne logowanie chmury. Bez sesji strona logowania chmury przekierowuje do Nexusa.
    """
    settings = request.app.state.settings
    sesja = await _sesja_ciasteczka(request)
    if sesja is not None and sesja.owner_id == ADMIN_OWNER:
        return Response(
            status_code=status.HTTP_204_NO_CONTENT, headers={SSO_USER_HEADER: settings.chmura_user}
        )
    original = urlsplit(request.headers.get("x-forwarded-uri", "/"))
    direct = "direct=1" in original.query.split("&")
    if sesja is None and original.path in CLOUD_LOGIN_PATHS and not direct and settings.public_url:
        return Response(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": f"{settings.public_url.rstrip('/')}/?next=cloud"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, str]:
    """Dane zalogowanego użytkownika i adres chmury osobistej (pusty, gdy brak).

    Konto klienta widzi własną nazwę, nie nazwę administratora instalacji: nazwa z ustawień
    dotyczy wyłącznie właściciela instalacji.

    Adres chmury dostaje wyłącznie właściciel. Logowanie jednokrotne (``sso``) wpuszcza do
    Nextcloud tylko jego, a klienci nie mają tam jeszcze własnych kont — odsyłacz prowadziłby
    ich na ekran logowania, którego nie przejdą. Pliki klienta działają w Nexusie bez zmian.
    """
    from nexus.models.portal import PortalUser

    database: Database = request.app.state.database
    async with database.session() as session:
        if sesja.owner_id != ADMIN_OWNER:
            konto = await session.get(PortalUser, sesja.owner_id)
            if konto is not None:
                return {
                    "username": konto.name or konto.email,
                    "cloud_url": "",
                    "gosc": "1" if konto.plan == GOSC_PLAN else "",
                }
        record = await session.get(Setting, USERNAME_KEY)
    return {
        "username": record.value if record else DEFAULT_USERNAME,
        "cloud_url": request.app.state.settings.chmura_public_url,
        "gosc": "",
    }
