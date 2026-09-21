"""Moduł Grupa: skład grupy, zaproszenia, przekazanie roli założyciela.

Plan „Grupa” dawało się kupić, ale nie dawało się nikogo do grupy dodać — cennik obiecywał
mechanikę, której nie było. Te punkty ją udostępniają:

* ``GET  /api/grupa``                 — moja grupa: skład, miejsca, zaproszenia, moja rola;
* ``POST /api/grupa``                 — założenie grupy (tylko na planie grupowym);
* ``POST /api/grupa/zaproszenia``     — zaproszenie adresu e-mail (zwraca odsyłacz);
* ``POST /api/grupa/przyjmij``        — przyjęcie zaproszenia tokenem z odsyłacza;
* ``DELETE /api/grupa/czlonkowie/{id}`` — usunięcie członka albo własne wyjście;
* ``POST /api/grupa/zalozyciel``      — przekazanie roli założyciela;
* ``DELETE /api/grupa``               — rozwiązanie grupy.

Wszystko pod sesją i nagłówkiem aplikacji, jak reszta punktów zmieniających stan.
Rachunek trzyma się jednej zasady: praca członka schodzi z puli założyciela
(`platnosci.grupy.konto_rozliczeniowe`).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from nexus.api.auth import require_session
from nexus.db import Database, UserSession
from nexus.models.grupy import ROLA_ZALOZYCIEL, Grupa
from nexus.platnosci import grupy as uslugi

router = APIRouter(prefix="/api/grupa", tags=["grupa"])


class ZalozenieBody(BaseModel):
    nazwa: str = Field("", max_length=120)


class ZaproszenieBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PrzyjecieBody(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ZalozycielBody(BaseModel):
    uzytkownik_id: uuid.UUID


def _baza(request: Request) -> Database:
    return request.app.state.database


async def _moja_grupa(database: Database, sesja: UserSession) -> Grupa:
    grupa = await uslugi.grupa_uzytkownika(database, sesja.owner_id)
    if grupa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie należysz do żadnej grupy.")
    return grupa


def _odmowa(blad: uslugi.BladGrupy) -> HTTPException:
    """Powód odmowy idzie do użytkownika bez zmian — mówi, co zrobić dalej."""
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(blad))


async def _opis(database: Database, grupa: Grupa, ja: uuid.UUID) -> dict[str, Any]:
    skl = await uslugi.czlonkowie(database, grupa.id)
    zaproszenia = await uslugi.zaproszenia_oczekujace(database, grupa.id)
    return {
        "id": str(grupa.id),
        "nazwa": grupa.nazwa,
        "jestem_zalozycielem": grupa.zalozyciel_id == ja,
        "miejsca": await uslugi.miejsca_grupy(database, grupa.zalozyciel_id),
        "czlonkowie": [
            {
                "uzytkownik_id": str(pozycja.uzytkownik_id),
                "email": pozycja.email,
                "nazwa": pozycja.nazwa,
                "rola": pozycja.rola,
                "to_ja": pozycja.uzytkownik_id == ja,
            }
            for pozycja in skl
        ],
        "zaproszenia": [
            {"email": pozycja.email, "wygasa": pozycja.wygasa_at.isoformat()}
            for pozycja in zaproszenia
        ],
    }


@router.get("")
async def moja_grupa(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    """Grupa, do której należy konto — albo pusta odpowiedź, gdy do żadnej nie należy."""
    database = _baza(request)
    grupa = await uslugi.grupa_uzytkownika(database, sesja.owner_id)
    if grupa is None:
        return {"grupa": None, "miejsca": uslugi.miejsca_planu(uslugi.PLAN_GRUPY)}
    return {"grupa": await _opis(database, grupa, sesja.owner_id)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def zaloz_grupe(
    payload: ZalozenieBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    database = _baza(request)
    try:
        grupa = await uslugi.zaloz(database, sesja.owner_id, payload.nazwa)
    except uslugi.BladGrupy as blad:
        raise _odmowa(blad) from blad
    return {"grupa": await _opis(database, grupa, sesja.owner_id)}


@router.post("/zaproszenia", status_code=status.HTTP_201_CREATED)
async def zapros_do_grupy(
    payload: ZaproszenieBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    """Tworzy zaproszenie i zwraca odsyłacz do przekazania osobie zapraszanej.

    Odsyłacz wraca do interfejsu, a nie wychodzi pocztą: skrzynka bywa nieskonfigurowana,
    a wtedy zaproszenie przepadałoby bez śladu. Kto zaprasza, ten widzi odsyłacz i wysyła
    go tak, jak mu wygodnie.
    """
    database = _baza(request)
    grupa = await _moja_grupa(database, sesja)
    try:
        token = await uslugi.zapros(database, grupa, sesja.owner_id, payload.email)
    except uslugi.BladGrupy as blad:
        raise _odmowa(blad) from blad
    return {
        "odsylacz": f"/portal/grupa?zaproszenie={token}",
        "grupa": await _opis(database, grupa, sesja.owner_id),
    }


@router.post("/przyjmij")
async def przyjmij_zaproszenie(
    payload: PrzyjecieBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    database = _baza(request)
    try:
        grupa = await uslugi.przyjmij(database, payload.token, sesja.owner_id)
    except uslugi.BladGrupy as blad:
        raise _odmowa(blad) from blad
    return {"grupa": await _opis(database, grupa, sesja.owner_id)}


@router.delete("/czlonkowie/{uzytkownik_id}")
async def usun_z_grupy(
    uzytkownik_id: uuid.UUID, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    database = _baza(request)
    grupa = await _moja_grupa(database, sesja)
    try:
        await uslugi.usun_czlonka(database, grupa, sesja.owner_id, uzytkownik_id)
    except uslugi.BladGrupy as blad:
        raise _odmowa(blad) from blad
    if uzytkownik_id == sesja.owner_id:
        return {"grupa": None}
    return {"grupa": await _opis(database, grupa, sesja.owner_id)}


@router.post("/zalozyciel")
async def przekaz_role(
    payload: ZalozycielBody, request: Request, sesja: UserSession = Depends(require_session)
) -> dict[str, Any]:
    database = _baza(request)
    grupa = await _moja_grupa(database, sesja)
    try:
        await uslugi.przekaz_zalozyciela(database, grupa, sesja.owner_id, payload.uzytkownik_id)
    except uslugi.BladGrupy as blad:
        raise _odmowa(blad) from blad
    odswiezona = await uslugi.grupa_uzytkownika(database, sesja.owner_id)
    return {"grupa": await _opis(database, odswiezona, sesja.owner_id) if odswiezona else None}


@router.delete("")
async def rozwiaz_grupe(request: Request, sesja: UserSession = Depends(require_session)) -> dict[str, Any]:
    database = _baza(request)
    grupa = await _moja_grupa(database, sesja)
    try:
        await uslugi.rozwiaz(database, grupa, sesja.owner_id)
    except uslugi.BladGrupy as blad:
        raise _odmowa(blad) from blad
    return {"grupa": None}


__all__ = ["ROLA_ZALOZYCIEL", "router"]
