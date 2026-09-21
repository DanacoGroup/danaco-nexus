"""Portal produktowy: treści (blog, baza wiedzy, dokumentacja, strony), konta klientów i kanały SEO.

Część publiczna (lista i szczegóły opublikowanych treści, wyszukiwanie, Atom, mapa witryny,
``robots.txt``) działa bez logowania. Redagowanie treści wymaga sesji administratora
(``nexus.api.auth.require_admin``), panel klienta – sesji konta portalu (``nexus.portal.konta``).
Ścieżki stron i model danych: ``docs/portal/README.md``.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.api.auth import COOKIE_NAME as COOKIE_ADMINISTRATORA
from nexus.api.auth import LoginThrottle, require_admin, token_hash
from nexus.config import Settings
from nexus.db import ADMIN_OWNER, Database, UserSession, utcnow
from nexus.models.portal import RODZAJE, PortalContent, PortalMessage, PortalUser
from nexus.portal import kanaly, konta, poczta_portalu, repozytorium, tresc
from nexus.portal.repozytorium import BrakTresci, DaneTresci
from nexus.portal.ustawienia import PortalSettings, portal_settings

MAX_TRESC = 400_000
CACHE_PUBLICZNY = "public, max-age=300"
# Ścieżka strony konta w portalu – odsyłacze w wiadomościach (potwierdzenie adresu,
# odzyskiwanie hasła, powiadomienie o zmianie hasła).
ADRES_KONTA = "/portal/konto"

publiczny = APIRouter(prefix="/api/portal", tags=["portal"])
kanal = APIRouter(tags=["portal"])
admin = APIRouter(prefix="/api/portal/admin", tags=["portal"], dependencies=[Depends(require_admin)])
konto = APIRouter(prefix="/api/portal/konto", tags=["portal"])


class Seo(BaseModel):
    """Metadane SEO pozycji treści."""

    meta_title: str = Field("", max_length=200)
    meta_description: str = Field("", max_length=320)
    og_image: str = Field("", max_length=500)
    canonical: str = Field("", max_length=500)
    noindex: bool = False


class NowaTresc(BaseModel):
    """Dane nowej pozycji treści."""

    kind: str
    slug: str = Field("", max_length=160)
    title: str = Field(min_length=1, max_length=200)
    excerpt: str = Field("", max_length=400)
    body: str = Field("", max_length=MAX_TRESC)
    author: str = Field("", max_length=120)
    tags: list[str] = Field(default_factory=list)
    status: str = "szkic"
    seo: Seo = Field(default_factory=Seo)
    position: int = Field(0, ge=0, le=10_000)


class ZmianaTresci(BaseModel):
    """Zmiana pozycji treści – przesyłane są wyłącznie pola do zmiany."""

    kind: str | None = None
    slug: str | None = Field(None, max_length=160)
    title: str | None = Field(None, min_length=1, max_length=200)
    excerpt: str | None = Field(None, max_length=400)
    body: str | None = Field(None, max_length=MAX_TRESC)
    author: str | None = Field(None, max_length=120)
    tags: list[str] | None = None
    status: str | None = None
    seo: Seo | None = None
    position: int | None = Field(None, ge=0, le=10_000)


class Publikacja(BaseModel):
    """Zmiana statusu publikacji."""

    status: str


class Rejestracja(BaseModel):
    """Dane rejestracji konta klienta."""

    email: str = Field(max_length=320)
    password: str = Field(max_length=konta.MAX_HASLO)
    name: str = Field("", max_length=120)
    company: str = Field("", max_length=200)


class Logowanie(BaseModel):
    """Dane logowania do portalu."""

    email: str = Field(max_length=320)
    password: str = Field(max_length=konta.MAX_HASLO)


class ZmianaProfilu(BaseModel):
    """Zmiana danych profilu."""

    name: str = Field("", max_length=120)
    company: str = Field("", max_length=200)


class ZmianaHasla(BaseModel):
    """Zmiana hasła zalogowanego klienta."""

    current_password: str = Field(max_length=konta.MAX_HASLO)
    new_password: str = Field(max_length=konta.MAX_HASLO)


class ProsbaOdzyskania(BaseModel):
    """Prośba o odsyłacz do ustawienia nowego hasła."""

    email: str = Field(max_length=320)


class NoweHaslo(BaseModel):
    """Ustawienie hasła tokenem odzyskiwania."""

    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=konta.MAX_HASLO)


class PotwierdzenieAdresu(BaseModel):
    """Potwierdzenie adresu poczty tokenem z wiadomości."""

    token: str = Field(min_length=10, max_length=200)


class UsuniecieKonta(BaseModel):
    """Potwierdzenie nieodwracalnego usunięcia konta klienta."""

    password: str = Field(max_length=konta.MAX_HASLO)
    confirmation: str = Field("", max_length=40)


class Kontakt(BaseModel):
    """Wiadomość z formularza kontaktowego."""

    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=320)
    subject: str = Field("", max_length=200)
    message: str = Field(min_length=10, max_length=5000)


def _ustawienia(request: Request) -> tuple[Settings, PortalSettings]:
    settings: Settings = request.app.state.settings
    return settings, portal_settings(settings)


def _baza(request: Request) -> Database:
    return request.app.state.database


def _limit(request: Request, nazwa: str, proby: int) -> LoginThrottle:
    """Licznik nieudanych prób dla operacji ``nazwa`` (wspólny dla procesu API).

    Licznik pamięta liczbę prób, z którą powstał: po zmianie zmiennej środowiskowej powstaje nowy,
    zgodnie z umową ``nexus.portal.ustawienia``. Zmiana limitu zeruje dotychczasowe zliczenia.
    """
    liczniki: dict[str, tuple[int, LoginThrottle]] | None = getattr(
        request.app.state, "portal_throttles", None
    )
    if liczniki is None:
        liczniki = {}
        request.app.state.portal_throttles = liczniki
    wpis = liczniki.get(nazwa)
    if wpis is None or wpis[0] != proby:
        wpis = (proby, LoginThrottle(proby))
        liczniki[nazwa] = wpis
    return wpis[1]


def _sprawdz_limit(licznik: LoginThrottle, adres: str) -> None:
    if licznik.blocked(adres):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Zbyt wiele prób z tego adresu. Spróbuj za 15 minut."
        )


def _blad(error: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))


def _identyfikator(wartosc: str) -> uuid.UUID:
    """Identyfikator pozycji z adresu; zły format daje 404, nie błąd walidacji."""
    try:
        return uuid.UUID(wartosc)
    except ValueError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono pozycji.") from error


def _adres_zewnetrzny(wartosc: str) -> str:
    """Adres SEO: tylko ścieżka tej witryny albo pełny adres http(s)."""
    oczyszczony = wartosc.strip()
    if not oczyszczony:
        return ""
    if oczyszczony.startswith("/") and not oczyszczony.startswith("//"):
        return oczyszczony
    if oczyszczony.startswith(("http://", "https://")):
        return oczyszczony
    raise _blad(ValueError("Adres w metadanych SEO musi być ścieżką lub adresem http(s)."))


def _seo(wartosc: Seo) -> dict[str, Any]:
    return {
        "meta_title": wartosc.meta_title.strip(),
        "meta_description": wartosc.meta_description.strip(),
        "og_image": _adres_zewnetrzny(wartosc.og_image),
        "canonical": _adres_zewnetrzny(wartosc.canonical),
        "noindex": wartosc.noindex,
    }


def _dane(record: PortalContent | None, payload: NowaTresc | ZmianaTresci) -> DaneTresci:
    """Komplet pól pozycji: wartości z żądania uzupełnione stanem zapisanym w bazie."""

    def pole(nazwa: str, domyslna: Any) -> Any:
        wartosc = getattr(payload, nazwa, None)
        return domyslna if wartosc is None else wartosc

    rodzaj = tresc.sprawdz_rodzaj(pole("kind", record.kind if record else "blog"))
    tytul = str(pole("title", record.title if record else "")).strip()
    if not tytul:
        raise _blad(ValueError("Tytuł jest wymagany."))
    podany_slug = str(pole("slug", record.slug if record else "")).strip()
    tresc_wpisu = str(pole("body", record.body if record else ""))
    # Zajawka wyliczona automatycznie podąża za treścią; zajawka wpisana przez redaktora zostaje.
    poprzednia = record.excerpt if record else ""
    if record is not None and payload.excerpt is None and poprzednia == tresc.zajawka("", record.body):
        poprzednia = ""
    seo = payload.seo
    return DaneTresci(
        kind=rodzaj,
        slug=tresc.sprawdz_slug(podany_slug or tytul),
        title=tytul,
        excerpt=str(pole("excerpt", poprzednia)),
        body=tresc_wpisu,
        author=str(pole("author", record.author if record else "")).strip(),
        tags=tresc.znaczniki(pole("tags", list(record.tags or []) if record else [])),
        status=tresc.sprawdz_status(pole("status", record.status if record else "szkic")),
        seo=_seo(seo) if seo is not None else dict(record.seo or {}) if record else {},
        position=int(pole("position", record.position if record else 0)),
    )


# --- część publiczna ------------------------------------------------------------------------------


@publiczny.get("/tresci")
async def lista_tresci(
    request: Request,
    typ: str = Query("", max_length=20),
    tag: str = Query("", max_length=40),
    q: str = Query("", max_length=200),
    strona: int = Query(1, ge=1, le=1000),
    na_stronie: int = Query(10, ge=1, le=repozytorium.MAX_NA_STRONIE),
) -> dict[str, Any]:
    """Opublikowane treści wybranego rodzaju (blog, wiedza, dokumentacja, strona)."""
    if typ and typ not in RODZAJE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nieznany rodzaj treści.")
    async with _baza(request).session() as session:
        return await repozytorium.lista(
            session, kind=typ or None, tag=tag, zapytanie=q, strona=strona, na_stronie=na_stronie
        )


@publiczny.get("/znaczniki")
async def znaczniki_tresci(request: Request, typ: str = Query("", max_length=20)) -> list[dict[str, Any]]:
    """Znaczniki opublikowanych treści wraz z liczbą pozycji (od najczęstszego)."""
    async with _baza(request).session() as session:
        pozycje = await repozytorium.opublikowane_do_kanalu(session, kind=typ or None, limit=500)
    liczniki: dict[str, int] = {}
    for record in pozycje:
        for znacznik in record.tags or []:
            liczniki[znacznik] = liczniki.get(znacznik, 0) + 1
    uporzadkowane = sorted(liczniki.items(), key=lambda pozycja: (-pozycja[1], pozycja[0]))
    return [{"tag": nazwa, "count": ile} for nazwa, ile in uporzadkowane]


@publiczny.get("/szukaj")
async def szukaj(
    request: Request,
    q: str = Query("", max_length=200),
    typ: str = Query("", max_length=20),
    limit: int = Query(20, ge=1, le=repozytorium.MAX_NA_STRONIE),
) -> dict[str, Any]:
    """Wyszukiwanie pełnotekstowe w opublikowanych treściach portalu."""
    rodzaje = [typ] if typ in RODZAJE else None
    async with _baza(request).session() as session:
        wyniki = await repozytorium.szukaj(session, q, rodzaje=rodzaje, limit=limit)
    return {"query": q, "items": wyniki, "total": len(wyniki)}


@publiczny.get("/tresci/{rodzaj}/{slug}")
async def szczegoly_tresci(rodzaj: str, slug: str, request: Request) -> dict[str, Any]:
    """Opublikowana pozycja treści wraz z metadanymi SEO."""
    if rodzaj not in RODZAJE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nieznany rodzaj treści.")
    async with _baza(request).session() as session:
        try:
            record = await repozytorium.pobierz(session, rodzaj, tresc.slug(slug))
        except BrakTresci as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        sasiednie = await repozytorium.lista(session, kind=rodzaj, na_stronie=5)
    powiazane = [pozycja for pozycja in sasiednie["items"] if pozycja["slug"] != record.slug][:4]
    return {**repozytorium.pelna(record), "related": powiazane}


@publiczny.post("/kontakt", status_code=status.HTTP_201_CREATED)
async def wyslij_kontakt(payload: Kontakt, request: Request) -> dict[str, bool]:
    """Przyjmuje wiadomość z formularza kontaktowego (zapis w bazie, odczyt w panelu)."""
    konta.sprawdz_naglowek(request)
    _, portal = _ustawienia(request)
    licznik = _limit(request, "kontakt", portal.contact_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    try:
        adres = tresc.sprawdz_adres_poczty(payload.email)
    except tresc.BladTresci as error:
        raise _blad(error) from error
    async with _baza(request).session() as session:
        session.add(
            PortalMessage(
                name=payload.name.strip(),
                email=adres,
                subject=payload.subject.strip(),
                body=payload.message.strip(),
            )
        )
    # Formularz jest publiczny – limit liczy wszystkie zgłoszenia z jednego adresu.
    licznik.failure(adres_ip)
    return {"ok": True}


@kanal.get("/portal/atom.xml", include_in_schema=False)
async def kanal_atom(request: Request) -> Response:
    """Kanał Atom 1.0 z wpisami bloga."""
    _, portal = _ustawienia(request)
    async with _baza(request).session() as session:
        pozycje = await repozytorium.opublikowane_do_kanalu(session, kind="blog", limit=50)
    return Response(
        kanaly.atom(portal.base_url, pozycje),
        media_type="application/atom+xml; charset=utf-8",
        headers={"Cache-Control": CACHE_PUBLICZNY},
    )


@kanal.get("/portal/rss.xml", include_in_schema=False)
async def kanal_rss(request: Request) -> Response:
    """Zgodny adres kanału (ta sama treść Atom co ``/portal/atom.xml``)."""
    return await kanal_atom(request)


@kanal.get("/sitemap.xml", include_in_schema=False)
async def mapa_witryny(request: Request) -> Response:
    """Mapa witryny ze stałymi stronami portalu i opublikowanymi treściami."""
    _, portal = _ustawienia(request)
    async with _baza(request).session() as session:
        pozycje = await repozytorium.opublikowane_do_kanalu(session, limit=2000)
    return Response(
        kanaly.sitemap(portal.base_url, pozycje),
        media_type="application/xml; charset=utf-8",
        headers={"Cache-Control": CACHE_PUBLICZNY},
    )


@kanal.get("/robots.txt", include_in_schema=False)
async def robots(request: Request) -> Response:
    """Reguły dla robotów wyszukiwarek."""
    _, portal = _ustawienia(request)
    return Response(
        kanaly.robots(portal.base_url),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": CACHE_PUBLICZNY},
    )


# --- panel administratora -------------------------------------------------------------------------


@admin.get("/tresci")
async def admin_lista(
    request: Request,
    typ: str = Query("", max_length=20),
    status_tresci: str = Query("", max_length=20, alias="status"),
    q: str = Query("", max_length=200),
    strona: int = Query(1, ge=1, le=1000),
    na_stronie: int = Query(20, ge=1, le=repozytorium.MAX_NA_STRONIE),
) -> dict[str, Any]:
    """Treści widziane przez redaktora – razem ze szkicami."""
    async with _baza(request).session() as session:
        wynik = await repozytorium.lista(
            session,
            kind=typ or None,
            tylko_opublikowane=False,
            zapytanie=q,
            strona=strona,
            na_stronie=na_stronie,
        )
    if status_tresci:
        pozycje = [item for item in wynik["items"] if item["status"] == status_tresci]
        wynik = {**wynik, "items": pozycje, "total": len(pozycje)}
    return wynik


@admin.post("/tresci", status_code=status.HTTP_201_CREATED)
async def admin_utworz(payload: NowaTresc, request: Request) -> dict[str, Any]:
    """Zakłada pozycję treści (domyślnie jako szkic)."""
    async with _baza(request).session() as session:
        try:
            record = await repozytorium.utworz(session, _dane(None, payload))
        except tresc.BladTresci as error:
            raise _blad(error) from error
        return repozytorium.pelna(record)


@admin.get("/tresci/{identyfikator}")
async def admin_szczegoly(identyfikator: str, request: Request) -> dict[str, Any]:
    """Pozycja treści do edycji (również szkic)."""
    async with _baza(request).session() as session:
        try:
            record = await repozytorium.pobierz_po_id(session, _identyfikator(identyfikator))
        except BrakTresci as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        return repozytorium.pelna(record)


@admin.patch("/tresci/{identyfikator}")
async def admin_zmien(identyfikator: str, payload: ZmianaTresci, request: Request) -> dict[str, Any]:
    """Zapisuje zmiany pozycji treści."""
    async with _baza(request).session() as session:
        try:
            record = await repozytorium.pobierz_po_id(session, _identyfikator(identyfikator))
            record = await repozytorium.zmien(session, record, _dane(record, payload))
        except BrakTresci as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        except tresc.BladTresci as error:
            raise _blad(error) from error
        return repozytorium.pelna(record)


@admin.post("/tresci/{identyfikator}/publikacja")
async def admin_publikacja(identyfikator: str, payload: Publikacja, request: Request) -> dict[str, Any]:
    """Publikuje pozycję albo wycofuje ją do szkicu."""
    async with _baza(request).session() as session:
        try:
            record = await repozytorium.pobierz_po_id(session, _identyfikator(identyfikator))
            record = await repozytorium.ustaw_status(session, record, tresc.sprawdz_status(payload.status))
        except BrakTresci as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        except tresc.BladTresci as error:
            raise _blad(error) from error
        return repozytorium.pelna(record)


@admin.delete("/tresci/{identyfikator}")
async def admin_usun(identyfikator: str, request: Request) -> dict[str, bool]:
    """Usuwa pozycję treści."""
    async with _baza(request).session() as session:
        try:
            await repozytorium.usun(session, _identyfikator(identyfikator))
        except BrakTresci as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return {"ok": True}


@admin.get("/wiadomosci")
async def admin_wiadomosci(request: Request, limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    """Wiadomości z formularza kontaktowego (od najnowszej)."""
    async with _baza(request).session() as session:
        rekordy = (
            await session.scalars(
                select(PortalMessage).order_by(PortalMessage.created_at.desc()).limit(limit)
            )
        ).all()
    return [
        {
            "id": str(record.id),
            "name": record.name,
            "email": record.email,
            "subject": record.subject,
            "body": record.body,
            "handled": record.handled,
            "created_at": record.created_at.isoformat(),
        }
        for record in rekordy
    ]


@admin.get("/klienci")
async def admin_klienci(request: Request, limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    """Konta klientów portalu (od najnowszego)."""
    async with _baza(request).session() as session:
        rekordy = (
            await session.scalars(select(PortalUser).order_by(PortalUser.created_at.desc()).limit(limit))
        ).all()
    return [konta.profil(record) for record in rekordy]


async def _wyslij_potwierdzenie(
    settings: Settings, portal: PortalSettings, odbiorca: str, token: str
) -> None:
    """Wysyła wiadomość z odsyłaczem potwierdzającym adres konta."""
    godziny = int(konta.POTWIERDZENIE_WAZNE.total_seconds() // 3600)
    temat, wiadomosc = poczta_portalu.tresc_potwierdzenia_adresu(
        f"{portal.base_url}{ADRES_KONTA}?potwierdzenie={token}", godziny
    )
    await asyncio.to_thread(poczta_portalu.wyslij, settings, portal, odbiorca, temat, wiadomosc)


# --- konto klienta --------------------------------------------------------------------------------


@konto.post("/rejestracja", status_code=status.HTTP_201_CREATED)
async def rejestracja(payload: Rejestracja, request: Request, response: Response) -> dict[str, Any]:
    """Zakłada konto klienta i loguje je od razu."""
    konta.sprawdz_naglowek(request)
    settings, portal = _ustawienia(request)
    if not portal.registration_open:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Rejestracja jest wyłączona. Napisz do nas przez formularz kontaktowy, aby dostać dostęp.",
        )
    licznik = _limit(request, "rejestracja", portal.login_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    async with _baza(request).session() as session:
        try:
            user = await konta.utworz_konto(
                session, payload.email, payload.password, payload.name, payload.company
            )
        except konta.BladKonta as error:
            licznik.failure(adres_ip)
            raise _blad(error) from error
        token, czas = await konta.zaloz_sesje(session, user, request, portal.session_days)
        potwierdzenie = await konta.token_potwierdzenia(session, user)
        adres_pocztowy = user.email
        dane = konta.profil(user)
    konta.ustaw_ciasteczko(response, token, czas, settings)
    # Odsyłacz wychodzi zawsze. Bez skonfigurowanej wysyłki trafia do dziennika, a konto i tak
    # działa – niepotwierdzony adres jest stanem widocznym w profilu, nie blokadą.
    await _wyslij_potwierdzenie(settings, portal, adres_pocztowy, potwierdzenie)
    return dane


@konto.post("/logowanie")
async def logowanie(payload: Logowanie, request: Request, response: Response) -> dict[str, Any]:
    """Logowanie klienta portalu (ograniczone tempo nieudanych prób z jednego adresu)."""
    konta.sprawdz_naglowek(request)
    settings, portal = _ustawienia(request)
    licznik = _limit(request, "logowanie", portal.login_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    async with _baza(request).session() as session:
        user = await konta.znajdz_konto(session, payload.email)
        if not konta.haslo_zgodne(user, payload.password) or user is None or not user.active:
            licznik.failure(adres_ip)
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Nieprawidłowy adres e-mail lub hasło. Sprawdź pisownię adresu albo ustaw nowe hasło.",
            )
        await konta.usun_wygasle(session)
        token, czas = await konta.zaloz_sesje(session, user, request, portal.session_days)
        dane = konta.profil(user)
    licznik.success(adres_ip)
    konta.ustaw_ciasteczko(response, token, czas, settings)
    return dane


@konto.post("/wylogowanie")
async def wylogowanie(request: Request, response: Response) -> dict[str, bool]:
    """Kończy sesję klienta portalu."""
    konta.sprawdz_naglowek(request)
    settings, _ = _ustawienia(request)
    token = request.cookies.get(konta.COOKIE_NAME, "")
    if token:
        async with _baza(request).session() as session:
            await konta.zakoncz_sesje(session, token)
    konta.usun_ciasteczko(response, settings)
    return {"ok": True}


@konto.get("/ja")
async def moje_konto(user: PortalUser = Depends(konta.wymagaj_konta)) -> dict[str, Any]:
    """Profil zalogowanego klienta."""
    return konta.profil(user)


@konto.get("/sesja")
async def stan_sesji(request: Request) -> dict[str, Any]:
    """Czy ktoś jest zalogowany — i kto, jeśli tak.

    Osobny punkt, bo to pytanie o stan, a nie sięgnięcie po zasób chroniony. Portal
    pytał o to przez ``/konto/ja``, które gościowi odpowiada 401 — przeglądarka
    zapisywała wtedy błąd w konsoli na każdej stronie publicznej, choć nic złego się nie
    działo. Tutaj brak sesji to zwykła odpowiedź: ``{"konto": null}``.
    """
    user = await konta.konto_sesji(request)
    return {"konto": konta.profil(user) if user is not None else None}


@konto.patch("/profil")
async def zmien_profil(
    payload: ZmianaProfilu, request: Request, user: PortalUser = Depends(konta.wymagaj_konta)
) -> dict[str, Any]:
    """Zmienia nazwę i firmę w profilu klienta."""
    async with _baza(request).session() as session:
        record = await session.get(PortalUser, user.id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Konto nie istnieje.")
        record.name = payload.name.strip()[:120]
        record.company = payload.company.strip()[:200]
        record.updated_at = utcnow()
        return konta.profil(record)


@konto.post("/haslo")
async def zmien_haslo(
    payload: ZmianaHasla,
    request: Request,
    response: Response,
    user: PortalUser = Depends(konta.wymagaj_konta),
) -> dict[str, bool]:
    """Zmienia hasło klienta (wymaga podania obecnego); kończy wszystkie sesje konta."""
    settings, portal = _ustawienia(request)
    licznik = _limit(request, "haslo", portal.login_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    async with _baza(request).session() as session:
        record = await session.get(PortalUser, user.id)
        if record is None or not konta.haslo_zgodne(record, payload.current_password):
            licznik.failure(adres_ip)
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Obecne hasło jest nieprawidłowe. Wpisz je ponownie albo odzyskaj hasło.",
            )
        try:
            konta.sprawdz_nowe_haslo(record, payload.new_password)
            await konta.ustaw_haslo(session, record, payload.new_password)
        except konta.BladKonta as error:
            raise _blad(error) from error
        adres_pocztowy = record.email
    licznik.success(adres_ip)
    # Sesje konta są skasowane w bazie – ciasteczko przeglądarki też, żeby klient nie nosił
    # unieważnionego tokenu do końca jego ważności.
    konta.usun_ciasteczko(response, settings)
    temat, wiadomosc = poczta_portalu.tresc_zmiany_hasla(f"{portal.base_url}{ADRES_KONTA}")
    await asyncio.to_thread(poczta_portalu.wyslij, settings, portal, adres_pocztowy, temat, wiadomosc)
    return {"ok": True}


@konto.post("/usuniecie")
async def usun_konto(
    payload: UsuniecieKonta,
    request: Request,
    response: Response,
    user: PortalUser = Depends(konta.wymagaj_konta),
) -> dict[str, bool]:
    """Usuwa konto klienta na zawsze: wymaga hasła i słowa potwierdzenia, kończy sesję."""
    settings, portal = _ustawienia(request)
    licznik = _limit(request, "usuniecie-konta", portal.login_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    if payload.confirmation.strip().upper() != konta.POTWIERDZENIE_USUNIECIA:
        raise _blad(
            ValueError(f"Aby usunąć konto, wpisz w polu potwierdzenia słowo {konta.POTWIERDZENIE_USUNIECIA}.")
        )
    async with _baza(request).session() as session:
        record = await session.get(PortalUser, user.id)
        if record is None or not konta.haslo_zgodne(record, payload.password):
            licznik.failure(adres_ip)
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Hasło jest nieprawidłowe. Wpisz je ponownie."
            )
        adres_pocztowy = record.email
        await konta.usun_konto(session, record)
    licznik.success(adres_ip)
    konta.usun_ciasteczko(response, settings)
    temat, wiadomosc = poczta_portalu.tresc_usuniecia_konta()
    await asyncio.to_thread(poczta_portalu.wyslij, settings, portal, adres_pocztowy, temat, wiadomosc)
    return {"ok": True}


@konto.post("/potwierdzenie")
async def potwierdzenie_adresu(payload: PotwierdzenieAdresu, request: Request) -> dict[str, bool]:
    """Potwierdza adres poczty tokenem z wiadomości (działa bez zalogowania)."""
    konta.sprawdz_naglowek(request)
    _, portal = _ustawienia(request)
    licznik = _limit(request, "potwierdzenie", portal.reset_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    async with _baza(request).session() as session:
        try:
            await konta.potwierdz_adres(session, payload.token)
        except konta.BladKonta as error:
            licznik.failure(adres_ip)
            raise _blad(error) from error
    licznik.success(adres_ip)
    return {"ok": True}


@konto.post("/potwierdzenie/wyslij")
async def wyslij_potwierdzenie(
    request: Request, user: PortalUser = Depends(konta.wymagaj_konta)
) -> dict[str, bool]:
    """Wysyła nowy odsyłacz potwierdzający adres zalogowanego konta."""
    settings, portal = _ustawienia(request)
    licznik = _limit(request, "potwierdzenie-wysylka", portal.reset_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    # Każda prośba liczy się do limitu – inaczej jednym kontem da się zasypać cudzą skrzynkę.
    licznik.failure(adres_ip)
    token, adres_pocztowy = "", ""
    async with _baza(request).session() as session:
        record = await session.get(PortalUser, user.id)
        if record is not None and record.email_confirmed_at is None:
            token = await konta.token_potwierdzenia(session, record)
            adres_pocztowy = record.email
    if token:
        await _wyslij_potwierdzenie(settings, portal, adres_pocztowy, token)
    return {"ok": True}


@konto.post("/odzyskiwanie")
async def odzyskiwanie(payload: ProsbaOdzyskania, request: Request) -> dict[str, bool]:
    """Wysyła odsyłacz do ustawienia nowego hasła.

    Odpowiedź nie zdradza, czy konto istnieje. Bez skonfigurowanej poczty wiadomość trafia do
    dziennika aplikacji (``NEXUS_PORTAL_MAIL_NADAWCA``).
    """
    konta.sprawdz_naglowek(request)
    settings, portal = _ustawienia(request)
    licznik = _limit(request, "odzyskiwanie", portal.reset_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    # Każda prośba liczy się do limitu – niezależnie od tego, czy konto istnieje.
    licznik.failure(adres_ip)
    token, adres_konta = "", ""
    async with _baza(request).session() as session:
        user = await konta.znajdz_konto(session, payload.email)
        if user is not None and user.active:
            token = await konta.token_odzyskiwania(session, user, portal.reset_ttl_minutes)
            adres_konta = user.email
    if token:
        temat, wiadomosc = poczta_portalu.tresc_odzyskiwania(
            f"{portal.base_url}{ADRES_KONTA}?token={token}", portal.reset_ttl_minutes
        )
        await asyncio.to_thread(
            poczta_portalu.wyslij, settings, portal, adres_konta, temat, wiadomosc
        )
    return {"ok": True}


@konto.post("/odzyskiwanie/potwierdz")
async def potwierdz_odzyskiwanie(payload: NoweHaslo, request: Request) -> dict[str, bool]:
    """Ustawia nowe hasło na podstawie tokenu odzyskiwania."""
    konta.sprawdz_naglowek(request)
    settings, portal = _ustawienia(request)
    licznik = _limit(request, "odzyskiwanie-potwierdzenie", portal.reset_attempts)
    adres_ip = konta.adres_klienta(request)
    _sprawdz_limit(licznik, adres_ip)
    async with _baza(request).session() as session:
        try:
            user = await konta.konto_z_tokenu(session, payload.token)
            await konta.ustaw_haslo(session, user, payload.password)
        except konta.BladKonta as error:
            licznik.failure(adres_ip)
            raise _blad(error) from error
        adres_pocztowy = user.email
    temat, wiadomosc = poczta_portalu.tresc_zmiany_hasla(f"{portal.base_url}{ADRES_KONTA}")
    await asyncio.to_thread(poczta_portalu.wyslij, settings, portal, adres_pocztowy, temat, wiadomosc)
    return {"ok": True}


@publiczny.get("/stan")
async def stan_portalu(request: Request) -> dict[str, Any]:
    """Stan portalu dla interfejsu: czy rejestracja jest otwarta i czy trwa sesja administratora."""
    _, portal = _ustawienia(request)
    administrator = False
    token = request.cookies.get(COOKIE_ADMINISTRATORA)
    if token:
        async with _baza(request).session() as session:
            record = await session.get(UserSession, token_hash(token))
        # Konto klienta i konto próbne też mają ważną sesję aplikacji, a panelu redakcyjnego
        # nie dostają — stan musi pytać o właściciela instalacji, nie o samo zalogowanie.
        administrator = (
            record is not None and record.expires_at >= utcnow() and record.owner_id == ADMIN_OWNER
        )
    return {"registration_open": portal.registration_open, "admin": administrator}


router = APIRouter()
for czesc in (publiczny, kanal, admin, konto):
    router.include_router(czesc)
