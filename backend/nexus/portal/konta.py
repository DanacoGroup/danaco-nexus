"""Konta klientów portalu: rejestracja, logowanie, sesje, profil, odzyskiwanie hasła i usunięcie konta.

Mechanizmy są te same co w ``nexus.api.auth``: hasła haszuje Argon2 (``auth.hasher``), sesja to
losowy token w ciasteczku ``HttpOnly`` (w bazie wyłącznie skrót SHA-256), a żądania zmieniające
stan wymagają nagłówka ``X-Nexus-Request``. Konto klienta jest odrębne od konta administratora –
sesja administratora (ciasteczko ``nexus_session``) nie daje dostępu do panelu klienta i odwrotnie.

Adres klienta do licznika prób ustala ``adres_klienta``: nagłówkowi ``X-Forwarded-For`` wierzy
wyłącznie w żądaniu z pętli zwrotnej, czyli od Caddy stojącego na tej samej maszynie. Inaczej
limit prób omija się jednym nagłówkiem.

Adres poczty potwierdza się jednorazowym odsyłaczem (``token_potwierdzenia``, ``potwierdz_adres``).
Potwierdzenie niczego nie blokuje: konto działa od razu, a brak potwierdzenia widać w profilu.

Sesja gaśnie z dwóch powodów: po upływie czasu życia (``NEXUS_PORTAL_SESSION_DAYS``) oraz po
``BEZCZYNNOSC`` bez żadnego żądania. Usunięcie konta kasuje rekord klienta razem z sesjami i tokenami.
"""

from __future__ import annotations

import ipaddress
import secrets
from datetime import datetime, timedelta

from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.api import auth
from nexus.config import Settings
from nexus.db import DeviceToken, UserSession, utcnow
from nexus.models.portal import (
    PortalEmailConfirmation,
    PortalPasswordReset,
    PortalSession,
    PortalUser,
)
from nexus.portal.tresc import BladTresci, sprawdz_adres_poczty

COOKIE_NAME = "nexus_portal"
MIN_HASLO = 12
MAX_HASLO = 500
ODSWIEZ_PO = timedelta(minutes=5)
# Wygaszanie sesji bezczynnej: niezależnie od daty wygaśnięcia ciasteczka sesja przestaje działać,
# gdy klient nie korzystał z portalu przez ten czas. Krótsze z dwóch ograniczeń rozstrzyga.
BEZCZYNNOSC = timedelta(days=7)
POTWIERDZENIE_USUNIECIA = "USUWAM"
# Odsyłacz potwierdzający adres żyje dobę: klient czyta pocztę także następnego dnia, a token
# niczego nie odblokowuje, więc dłuższy termin nie jest potrzebny.
POTWIERDZENIE_WAZNE = timedelta(hours=24)
# Odwrotne proxy wdrożenia (Caddy) stoi na tej samej maszynie i łączy się z API po pętli
# zwrotnej, więc tylko stamtąd nagłówek ``X-Forwarded-For`` może pochodzić od proxy. Szersze
# zakresy prywatne obejmowałyby maszyny, które w tym wdrożeniu proxy nie są – a każda z nich
# mogłaby wtedy podstawić dowolny adres do licznika prób.
SIECI_PROXY = tuple(ipaddress.ip_network(zapis) for zapis in ("127.0.0.0/8", "::1/128"))
# Skrót porównywany, gdy konto nie istnieje – wyrównuje czas odpowiedzi logowania (brak wskazówki,
# czy adres jest zarejestrowany). Liczony raz przy starcie procesu.
HASLO_ZASTEPCZE = auth.hasher.hash(secrets.token_urlsafe(32))


def _proxy_zaufane(adres: str) -> bool:
    """Czy żądanie przyszło od własnego proxy, czyli z pętli zwrotnej tej maszyny."""
    try:
        return any(ipaddress.ip_address(adres) in siec for siec in SIECI_PROXY)
    except ValueError:
        return False


def adres_klienta(request: Request) -> str:
    """Adres klienta odporny na podszycie nagłówkiem ``X-Forwarded-For``.

    Nagłówek liczy się wyłącznie w żądaniu z pętli zwrotnej i brany jest jego ostatni wpis – ten
    dopisuje proxy z adresu, który samo zobaczyło. Wpisy wcześniejsze przysyła klient, więc
    ufanie pierwszemu pozwalało obejść licznik prób jednym nagłówkiem. We wdrożeniu adres klienta
    wyznacza już uvicorn (``--proxy-headers --forwarded-allow-ips 127.0.0.1``) i gałąź nagłówka
    się nie wykonuje; zostaje jako zabezpieczenie uruchomienia API bez tych przełączników.
    """
    peer = request.client.host if request.client else ""
    if not _proxy_zaufane(peer):
        return peer or "?"
    wpisy = [wpis.strip() for wpis in request.headers.get("x-forwarded-for", "").split(",") if wpis.strip()]
    return wpisy[-1][:64] if wpisy else peer


class BladKonta(ValueError):
    """Niepoprawne dane konta (adres, hasło, zajęty adres)."""


def sprawdz_haslo_polityka(haslo: str, email: str = "") -> str:
    """Hasło zgodne z polityką: długość w zakresie i treść inna niż adres konta."""
    if len(haslo) < MIN_HASLO:
        raise BladKonta(
            f"Hasło jest za krótkie – dopisz znaki tak, aby było ich co najmniej {MIN_HASLO}."
        )
    if len(haslo) > MAX_HASLO:
        raise BladKonta(f"Hasło jest za długie – skróć je do {MAX_HASLO} znaków.")
    if email and haslo.strip().lower() == email.strip().lower():
        raise BladKonta("Hasło nie może być powtórzeniem adresu e-mail. Wpisz inne hasło.")
    return haslo


def sprawdz_nowe_haslo(user: PortalUser, haslo: str) -> None:
    """Nowe hasło nie może być powtórzeniem obecnego (reguła serwera, nie tylko interfejsu)."""
    if haslo_zgodne(user, haslo):
        raise BladKonta("Nowe hasło musi się różnić od obecnego. Wpisz inne hasło.")


def profil(user: PortalUser) -> dict[str, str | bool | None]:
    """Dane konta zwracane interfejsowi (bez skrótu hasła)."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "company": user.company,
        "plan": user.plan,
        "email_confirmed": user.email_confirmed_at is not None,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


async def znajdz_konto(session: AsyncSession, email: str) -> PortalUser | None:
    """Konto o podanym adresie albo ``None``."""
    return await session.scalar(select(PortalUser).where(PortalUser.email == email.strip().lower()))


async def utworz_konto(
    session: AsyncSession, email: str, haslo: str, name: str = "", company: str = ""
) -> PortalUser:
    """Zakłada konto klienta; adres musi być wolny, hasło zgodne z polityką."""
    try:
        adres = sprawdz_adres_poczty(email)
    except BladTresci as error:
        raise BladKonta(str(error)) from error
    sprawdz_haslo_polityka(haslo, adres)
    zajety = BladKonta("Konto o tym adresie już istnieje. Zaloguj się albo odzyskaj hasło.")
    if await znajdz_konto(session, adres) is not None:
        raise zajety
    user = PortalUser(
        email=adres,
        password_hash=auth.hasher.hash(haslo),
        name=name.strip()[:120],
        company=company.strip()[:200],
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as error:
        # Dwa zgłoszenia tego samego adresu naraz – unikalność rozstrzyga baza, nie sprawdzenie wyżej.
        raise zajety from error
    return user


def haslo_zgodne(user: PortalUser | None, haslo: str) -> bool:
    """Czy hasło pasuje do konta (przy braku konta liczy skrót zastępczy)."""
    try:
        return auth.hasher.verify(user.password_hash if user else HASLO_ZASTEPCZE, haslo)
    except (VerificationError, InvalidHashError):
        return False


async def ustaw_haslo(
    session: AsyncSession, user: PortalUser, haslo: str, zachowaj_sesje_aplikacji: str = ""
) -> None:
    """Zmienia hasło konta i unieważnia wszystkie jego sesje, tokeny odzyskiwania i klucze okien.

    Dotyczy to także sesji okna aplikacji (``sessions``), nie tylko portalu: hasło zmienia
    się zwykle po to, żeby odciąć urządzenie, które je zna, a okno aplikacji na telefonie
    i w Nexus Desktop trzyma własną sesję do 30 dni. ``zachowaj_sesje_aplikacji`` to skrót
    tokenu sesji, z której klient zmienia hasło w aplikacji — ta jedna zostaje.
    """
    sprawdz_haslo_polityka(haslo, user.email)
    user.password_hash = auth.hasher.hash(haslo)
    user.updated_at = utcnow()
    await session.execute(delete(PortalSession).where(PortalSession.user_id == user.id))
    await session.execute(delete(PortalPasswordReset).where(PortalPasswordReset.user_id == user.id))
    await session.execute(
        delete(UserSession).where(
            UserSession.owner_id == user.id, UserSession.token_hash != zachowaj_sesje_aplikacji
        )
    )
    # Zgubiony telefon: natywna część aplikacji (panel, głos, SMS) działa kluczem także po
    # wylogowaniu okna, a klucz może wskazywać starą sesję sprzed ponownego logowania. Cofamy
    # więc klucze okien poza bieżącym; klucze bez sesji (rozszerzenie, wklejony) zostają.
    await session.execute(
        update(DeviceToken)
        .where(
            DeviceToken.owner_id == user.id,
            DeviceToken.sesja_hash.is_not(None),
            DeviceToken.sesja_hash != zachowaj_sesje_aplikacji,
        )
        .values(revoked=True)
    )


async def zaloz_sesje(
    session: AsyncSession, user: PortalUser, request: Request, dni: int
) -> tuple[str, timedelta]:
    """Zakłada sesję klienta i zwraca token oraz czas jej życia."""
    token = secrets.token_urlsafe(32)
    czas = timedelta(days=dni)
    session.add(
        PortalSession(
            token_hash=auth.token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + czas,
            ip_address=adres_klienta(request)[:64],
            user_agent=request.headers.get("user-agent", "")[:300],
        )
    )
    user.last_login_at = utcnow()
    return token, czas


def ustaw_ciasteczko(response: Response, token: str, czas: timedelta, settings: Settings) -> None:
    """Zapisuje ciasteczko sesji portalu (``HttpOnly``, ``SameSite=Lax``)."""
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(czas.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain or None,
    )


def usun_ciasteczko(response: Response, settings: Settings) -> None:
    """Kasuje ciasteczko sesji portalu."""
    response.delete_cookie(COOKIE_NAME, path="/", domain=settings.cookie_domain or None)


def sprawdz_naglowek(request: Request) -> None:
    """Ochrona CSRF: żądanie musi pochodzić z aplikacji (nagłówek ``X-Nexus-Request``)."""
    if request.headers.get(auth.CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Brak nagłówka żądania aplikacji.")


def sesja_wazna(record: PortalSession, teraz: datetime) -> bool:
    """Czy sesja nie wygasła: ani z upływu czasu życia, ani z bezczynności klienta."""
    return record.expires_at >= teraz and (teraz - record.last_seen_at) <= BEZCZYNNOSC


async def konto_sesji(request: Request) -> PortalUser | None:
    """Konto z ważnej sesji portalu albo ``None`` — bez wyjątku, gdy nikt nie jest zalogowany.

    ``wymagaj_konta`` odmawia 401, bo strzeże zasobów. Pytanie „czy ktoś tu jest” to co
    innego: brak sesji jest poprawną odpowiedzią, nie błędem.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    database = request.app.state.database
    async with database.session() as session:
        record = await session.get(PortalSession, auth.token_hash(token))
        if record is None or not sesja_wazna(record, utcnow()):
            return None
        user = await session.get(PortalUser, record.user_id)
    return user if user is not None and user.active else None


async def wymagaj_konta(request: Request) -> PortalUser:
    """Zależność FastAPI: ważna sesja klienta portalu (i nagłówek CSRF przy zmianach stanu)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Zaloguj się do portalu, aby zobaczyć dane konta."
        )
    database = request.app.state.database
    async with database.session() as session:
        record = await session.get(PortalSession, auth.token_hash(token))
        teraz = utcnow()
        if record is None or not sesja_wazna(record, teraz):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesja wygasła – zaloguj się ponownie.")
        user = await session.get(PortalUser, record.user_id)
        if user is None or not user.active:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Konto jest nieaktywne. Napisz do nas przez formularz kontaktowy, aby je odblokować.",
            )
        if (teraz - record.last_seen_at) > ODSWIEZ_PO:
            record.last_seen_at = teraz
    if request.method not in auth.SAFE_METHODS:
        sprawdz_naglowek(request)
    return user


async def zakoncz_sesje(session: AsyncSession, token: str) -> None:
    """Usuwa sesję klienta o podanym tokenie."""
    await session.execute(
        delete(PortalSession).where(PortalSession.token_hash == auth.token_hash(token))
    )


async def token_odzyskiwania(session: AsyncSession, user: PortalUser, minuty: int) -> str:
    """Wydaje jednorazowy token odzyskiwania hasła; wcześniejsze tokeny konta przestają działać."""
    await session.execute(delete(PortalPasswordReset).where(PortalPasswordReset.user_id == user.id))
    token = secrets.token_urlsafe(32)
    session.add(
        PortalPasswordReset(
            token_hash=auth.token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(minutes=minuty),
        )
    )
    return token


async def konto_z_tokenu(session: AsyncSession, token: str) -> PortalUser:
    """Konto wskazane ważnym, niewykorzystanym tokenem odzyskiwania."""
    record = await session.get(PortalPasswordReset, auth.token_hash(token))
    if record is None or record.used_at is not None or record.expires_at < utcnow():
        raise BladKonta(
            "Odsyłacz wygasł albo został już użyty. Wróć na stronę konta i poproś o nowy."
        )
    user = await session.get(PortalUser, record.user_id)
    if user is None or not user.active:
        raise BladKonta(
            "Konto jest nieaktywne. Napisz do nas przez formularz kontaktowy, aby je odblokować."
        )
    record.used_at = utcnow()
    return user


async def token_potwierdzenia(session: AsyncSession, user: PortalUser) -> str:
    """Wydaje jednorazowy token potwierdzenia adresu; wcześniejsze tokeny konta przestają działać."""
    await session.execute(
        delete(PortalEmailConfirmation).where(PortalEmailConfirmation.user_id == user.id)
    )
    token = secrets.token_urlsafe(32)
    session.add(
        PortalEmailConfirmation(
            token_hash=auth.token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + POTWIERDZENIE_WAZNE,
        )
    )
    return token


async def potwierdz_adres(session: AsyncSession, token: str) -> PortalUser:
    """Oznacza adres konta jako potwierdzony ważnym, niewykorzystanym tokenem."""
    record = await session.get(PortalEmailConfirmation, auth.token_hash(token))
    if record is None or record.used_at is not None or record.expires_at < utcnow():
        raise BladKonta(
            "Odsyłacz wygasł albo został już użyty. Zaloguj się i poproś o nowy odsyłacz."
        )
    user = await session.get(PortalUser, record.user_id)
    if user is None or not user.active:
        raise BladKonta(
            "Konto jest nieaktywne. Napisz do nas przez formularz kontaktowy, aby je odblokować."
        )
    teraz = utcnow()
    record.used_at = teraz
    if user.email_confirmed_at is None:
        user.email_confirmed_at = teraz
        user.updated_at = teraz
    await session.execute(
        delete(PortalEmailConfirmation).where(PortalEmailConfirmation.user_id == user.id)
    )
    return user


async def usun_konto(session: AsyncSession, user: PortalUser) -> None:
    """Usuwa konto klienta wraz z sesjami i tokenami (operacja nieodwracalna)."""
    await session.execute(delete(PortalSession).where(PortalSession.user_id == user.id))
    await session.execute(delete(PortalPasswordReset).where(PortalPasswordReset.user_id == user.id))
    await session.execute(
        delete(PortalEmailConfirmation).where(PortalEmailConfirmation.user_id == user.id)
    )
    await session.delete(user)


async def usun_wygasle(session: AsyncSession) -> None:
    """Sprząta sesje wygasłe i bezczynne oraz przeterminowane tokeny (wywoływane przy logowaniu)."""
    teraz = utcnow()
    await session.execute(
        delete(PortalSession).where(
            or_(
                PortalSession.expires_at < teraz,
                PortalSession.last_seen_at < teraz - BEZCZYNNOSC,
            )
        )
    )
    await session.execute(delete(PortalPasswordReset).where(PortalPasswordReset.expires_at < teraz))
    await session.execute(
        delete(PortalEmailConfirmation).where(PortalEmailConfirmation.expires_at < teraz)
    )
