"""Konto i preferencje: to, co użytkownik ustawia o sobie i o pracy Nexusa.

Moduł Ustawienia w aplikacji miał do tej pory trzy kafelki motywu i listę głosów —
wszystko inne albo nie istniało, albo siedziało w ``localStorage`` jednej przeglądarki.
Tu są ustawienia, które należą do konta i jadą za nim na każde urządzenie: profil,
hasło, preferencje pracy, sesje zalogowanych przeglądarek i eksport danych.

Preferencje są dokumentem JSON w ``ustawienia_konta`` z wykazem dozwolonych kluczy
(``POLA``). Klucz spoza wykazu jest odrzucany, a nie zapisywany po cichu: dokument ma
zostać zbiorem ustawień, a nie workiem, do którego dowolny klient wrzuca, co chce.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from nexus.api.auth import (
    ADMIN_OWNER,
    COOKIE_NAME,
    DEFAULT_USERNAME,
    GOSC_PLAN,
    USERNAME_KEY,
    require_session,
    token_hash,
)
from nexus.db import Conversation, Database, Setting, UserSession, utcnow
from nexus.models.portal import PortalUser
from nexus.models.ustawienia import UstawieniaKonta
from nexus.portal import konta

router = APIRouter(prefix="/api/konto", tags=["konto"], dependencies=[Depends(require_session)])

# Dozwolone preferencje: nazwa → (typ, wartość domyślna, dopuszczalne wartości dla tekstu).
# Wykaz jest jednocześnie dokumentacją tego, co interfejs może ustawić.
POLA: dict[str, tuple[type, Any, tuple[str, ...]]] = {
    # Wygląd okna.
    "motyw": (str, "dark", ("system", "dark", "light")),
    "ograniczony_ruch": (bool, False, ()),
    # Rozmowa: czym wysyła się wiadomość i od czego zaczyna się praca po zalogowaniu.
    "wysylka": (str, "enter", ("enter", "ctrl-enter")),
    "modul_startowy": (str, "chat", ()),
    # Głos, którym Nexus czyta odpowiedzi (ten sam, którego używa okno rozmowy głosowej).
    "glos": (str, "", ()),
}

DOMYSLNE: dict[str, Any] = {nazwa: wartosc for nazwa, (_, wartosc, _) in POLA.items()}


def _baza(request: Request) -> Database:
    return request.app.state.database


async def _konto(session: Any, owner_id: uuid.UUID) -> PortalUser | None:
    if owner_id == ADMIN_OWNER:
        return None
    return await session.get(PortalUser, owner_id)


def _oczysc(dane: dict[str, Any]) -> dict[str, Any]:
    """Zostawia wyłącznie znane klucze o właściwym typie; resztę odrzuca."""
    wynik: dict[str, Any] = {}
    for nazwa, wartosc in dane.items():
        pole = POLA.get(nazwa)
        if pole is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Nieznane ustawienie: {nazwa}.")
        typ, _, dozwolone = pole
        if typ is bool:
            if not isinstance(wartosc, bool):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, f"Ustawienie {nazwa} ma być tak/nie."
                )
            wynik[nazwa] = wartosc
            continue
        if not isinstance(wartosc, str) or len(wartosc) > 60:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Ustawienie {nazwa} ma być krótkim tekstem."
            )
        if dozwolone and wartosc not in dozwolone:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Ustawienie {nazwa} przyjmuje: {', '.join(dozwolone)}.",
            )
        wynik[nazwa] = wartosc
    return wynik


class ZmianaProfilu(BaseModel):
    name: str = Field("", max_length=120)
    company: str = Field("", max_length=200)


class ZmianaHasla(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


@router.get("")
async def profil(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Kto jest zalogowany: nazwa, adres, plan i stan potwierdzenia adresu."""
    async with _baza(request).session() as session:
        konto = await _konto(session, sesja.owner_id)
        if konto is None:
            record = await session.get(Setting, USERNAME_KEY)
            return {
                "nazwa": record.value if record else DEFAULT_USERNAME,
                "email": "",
                "firma": "",
                "plan": "administrator",
                "gosc": False,
                "adres_potwierdzony": True,
                "wlasne_konto": False,
            }
        return {
            "nazwa": konto.name or konto.email,
            "email": konto.email,
            "firma": konto.company,
            "plan": konto.plan,
            "gosc": konto.plan == GOSC_PLAN,
            "adres_potwierdzony": konto.email_confirmed_at is not None,
            "wlasne_konto": True,
        }


@router.patch("")
async def zmien_profil(
    payload: ZmianaProfilu, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    """Zmienia nazwę wyświetlaną i firmę."""
    async with _baza(request).session() as session:
        konto = await _konto(session, sesja.owner_id)
        if konto is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Profil administratora instalacji zmienia się w panelu administratora.",
            )
        konto.name = payload.name.strip()[:120]
        konto.company = payload.company.strip()[:200]
        konto.updated_at = utcnow()
    return await profil(request, sesja)


@router.post("/haslo")
async def zmien_haslo(
    payload: ZmianaHasla, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, bool]:
    """Zmienia hasło konta klienta (wymaga obecnego); nie dotyczy konta próbnego."""
    async with _baza(request).session() as session:
        konto = await _konto(session, sesja.owner_id)
        if konto is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Hasło administratora instalacji zmienia się w panelu administratora.",
            )
        if konto.plan == GOSC_PLAN:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Konto próbne nie ma hasła. Załóż własne konto, żeby zachować pracę.",
            )
        if not konta.haslo_zgodne(konto, payload.current_password):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Obecne hasło jest nieprawidłowe.")
        try:
            konta.sprawdz_nowe_haslo(konto, payload.new_password)
            # Bieżące okno zostaje zalogowane; pozostałe sesje konta kończy ``ustaw_haslo``.
            biezacy = request.cookies.get(COOKIE_NAME)
            await konta.ustaw_haslo(
                session, konto, payload.new_password, token_hash(biezacy) if biezacy else ""
            )
        except konta.BladKonta as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return {"ok": True}


@router.get("/preferencje")
async def preferencje(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Preferencje konta; brakujące pola wracają z wartościami domyślnymi."""
    async with _baza(request).session() as session:
        record = await session.get(UstawieniaKonta, sesja.owner_id)
        zapisane = dict(record.dane) if record and isinstance(record.dane, dict) else {}
    return {**DOMYSLNE, **{k: v for k, v in zapisane.items() if k in POLA}}


@router.put("/preferencje")
async def zapisz_preferencje(
    payload: dict[str, Any], request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    """Zapisuje przesłane preferencje (scalenie, nie podmiana całości)."""
    zmiany = _oczysc(payload)
    async with _baza(request).session() as session:
        record = await session.get(UstawieniaKonta, sesja.owner_id)
        if record is None:
            record = UstawieniaKonta(owner_id=sesja.owner_id, dane=zmiany)
            session.add(record)
        else:
            record.dane = {**(record.dane if isinstance(record.dane, dict) else {}), **zmiany}
            record.updated_at = utcnow()
    return await preferencje(request, sesja)


@router.get("/sesje")
async def sesje(request: Request, sesja: UserSession = Depends(require_session)) -> list[dict[str, Any]]:
    """Zalogowane przeglądarki tego konta — od ostatnio widzianej."""
    biezacy = request.cookies.get(COOKIE_NAME)
    skrot = token_hash(biezacy) if biezacy else ""
    async with _baza(request).session() as session:
        wpisy = (
            await session.scalars(
                select(UserSession)
                .where(UserSession.owner_id == sesja.owner_id)
                .order_by(UserSession.last_seen_at.desc())
                .limit(50)
            )
        ).all()
        return [
            {
                "biezaca": wpis.token_hash == skrot,
                "utworzona": wpis.created_at.isoformat(),
                "ostatnio": wpis.last_seen_at.isoformat(),
                "wygasa": wpis.expires_at.isoformat(),
                "adres_ip": wpis.ip_address,
                "przegladarka": wpis.user_agent[:200],
            }
            for wpis in wpisy
        ]


@router.post("/sesje/zakoncz-pozostale")
async def zakoncz_pozostale(
    request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, int]:
    """Wylogowuje wszystkie pozostałe przeglądarki tego konta; bieżąca zostaje."""
    biezacy = request.cookies.get(COOKIE_NAME)
    skrot = token_hash(biezacy) if biezacy else ""
    async with _baza(request).session() as session:
        wynik = await session.execute(
            delete(UserSession).where(
                UserSession.owner_id == sesja.owner_id, UserSession.token_hash != skrot
            )
        )
    return {"zakonczone": int(wynik.rowcount or 0)}


@router.get("/eksport")
async def eksport(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Dane konta w jednym dokumencie JSON (RODO, art. 20 — prawo do przenoszenia).

    Eksport obejmuje profil, preferencje i spis rozmów. Treść plików i rozmów pobiera się
    osobno — jeden dokument z całą pracą użytkownika potrafiłby mieć gigabajty.
    """
    dane = await profil(request, sesja)
    ustawienia = await preferencje(request, sesja)
    async with _baza(request).session() as session:
        rozmowy = (
            await session.scalars(
                select(Conversation)
                .where(Conversation.owner_id == sesja.owner_id)
                .order_by(Conversation.created_at.desc())
                .limit(2000)
            )
        ).all()
    return {
        "wygenerowano": utcnow().isoformat(),
        "profil": dane,
        "preferencje": ustawienia,
        "rozmowy": [
            {
                "id": str(rozmowa.id),
                "tytul": rozmowa.title,
                "utworzona": rozmowa.created_at.isoformat(),
            }
            for rozmowa in rozmowy
        ],
    }

