"""Moduł Pliki: jedna przestrzeń konta na pliki własne i wytworzone przez agenta.

Zastępuje podział na „chmurę” i „bazę wiedzy” jako osobne ekrany. Użytkownik widzi swoje
pliki w jednym miejscu, układa je we własne katalogi i projekty, wyszukuje i filtruje.
Skąd plik pochodzi — z wgrania, z rozmowy czy z pracy narzędzia — jest cechą pliku,
a nie osobnym światem.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update

from nexus.api.auth import require_session, wlasciciel
from nexus.api.conversations import file_payload
from nexus.db import Database, StoredFile, utcnow
from nexus.models.pliki import RODZAJE, KatalogPlikow
from nexus.platnosci.uprawnienia import limity_uzytkownika, opis_przestrzeni
from nexus.storage import FileStorage

router = APIRouter(prefix="/api/pliki", tags=["pliki"], dependencies=[Depends(require_session)])

# Rodzaje treści rozpoznawane na pierwszy rzut oka — po nich filtruje pasek nad listą.
RODZAJE_TRESCI: dict[str, tuple[str, ...]] = {
    "zdjecia": ("image/",),
    "dokumenty": ("application/pdf", "application/vnd", "application/msword", "text/"),
    "nagrania": ("audio/", "video/"),
    "archiwa": ("application/zip", "application/x-tar", "application/gzip", "application/x-7z"),
}


class KatalogBody(BaseModel):
    """Nowy katalog albo projekt użytkownika."""

    nazwa: str = Field(min_length=1, max_length=160)
    opis: str = Field("", max_length=2000)
    rodzaj: str = Field("katalog", max_length=20)
    kolor: str = Field("", max_length=20)
    parent_id: uuid.UUID | None = None


class KatalogPatch(BaseModel):
    """Zmiana katalogu: nazwa, opis, kolor, przypięcie albo przeniesienie."""

    nazwa: str | None = Field(None, min_length=1, max_length=160)
    opis: str | None = Field(None, max_length=2000)
    kolor: str | None = Field(None, max_length=20)
    przypiety: bool | None = None
    parent_id: uuid.UUID | None = None


class PrzypiszBody(BaseModel):
    """Przeniesienie plików do katalogu (``katalog_id`` puste = wyjęcie z katalogu)."""

    pliki: list[uuid.UUID] = Field(min_length=1, max_length=500)
    katalog_id: uuid.UUID | None = None


class TytulBody(BaseModel):
    """Własna nazwa pliku nadana przez użytkownika."""

    tytul: str = Field("", max_length=300)


def _database(request: Request) -> Database:
    return request.app.state.database


def _katalog_payload(rekord: KatalogPlikow, plikow: int = 0) -> dict[str, Any]:
    return {
        "id": str(rekord.id),
        "parent_id": str(rekord.parent_id) if rekord.parent_id else None,
        "nazwa": rekord.nazwa,
        "opis": rekord.opis,
        "rodzaj": rekord.rodzaj,
        "kolor": rekord.kolor,
        "przypiety": rekord.przypiety,
        "plikow": plikow,
        "updated_at": rekord.updated_at.isoformat(),
    }


async def _katalog(database: Database, katalog_id: uuid.UUID, owner: uuid.UUID) -> KatalogPlikow:
    """Katalog należący do konta; cudzy daje 404 jak nieistniejący."""
    async with database.session() as session:
        rekord = await session.get(KatalogPlikow, katalog_id)
    if rekord is None or rekord.owner_id != owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono katalogu.")
    return rekord


@router.get("/katalogi")
async def lista_katalogow(
    request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> list[dict[str, Any]]:
    """Katalogi i projekty konta wraz z liczbą plików w każdym."""
    async with _database(request).session() as session:
        rekordy = (
            await session.scalars(
                select(KatalogPlikow)
                .where(KatalogPlikow.owner_id == owner)
                .order_by(KatalogPlikow.przypiety.desc(), KatalogPlikow.nazwa)
            )
        ).all()
        liczby = dict(
            (
                await session.execute(
                    select(StoredFile.katalog_id, func.count())
                    .where(StoredFile.owner_id == owner, StoredFile.katalog_id.is_not(None))
                    .group_by(StoredFile.katalog_id)
                )
            ).all()
        )
    return [_katalog_payload(rekord, int(liczby.get(rekord.id, 0))) for rekord in rekordy]


@router.post("/katalogi", status_code=status.HTTP_201_CREATED)
async def utworz_katalog(
    payload: KatalogBody, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Zakłada katalog albo projekt w przestrzeni konta."""
    database = _database(request)
    if payload.parent_id is not None:
        await _katalog(database, payload.parent_id, owner)
    rodzaj = payload.rodzaj.strip().lower()
    if rodzaj not in RODZAJE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Nieznany rodzaj: {payload.rodzaj}.")
    rekord = KatalogPlikow(
        owner_id=owner,
        parent_id=payload.parent_id,
        nazwa=" ".join(payload.nazwa.split()),
        opis=payload.opis.strip(),
        rodzaj=rodzaj,
        kolor=payload.kolor.strip(),
    )
    async with database.session() as session:
        session.add(rekord)
    return _katalog_payload(rekord)


@router.patch("/katalogi/{katalog_id}")
async def zmien_katalog(
    katalog_id: uuid.UUID,
    payload: KatalogPatch,
    request: Request,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Zmienia nazwę, opis, kolor, przypięcie albo katalog nadrzędny."""
    database = _database(request)
    await _katalog(database, katalog_id, owner)
    if payload.parent_id is not None:
        if payload.parent_id == katalog_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Katalog nie może być swoim rodzicem.")
        await _katalog(database, payload.parent_id, owner)
    async with database.session() as session:
        rekord = await session.get(KatalogPlikow, katalog_id)
        assert rekord is not None
        if payload.nazwa is not None:
            rekord.nazwa = " ".join(payload.nazwa.split())
        if payload.opis is not None:
            rekord.opis = payload.opis.strip()
        if payload.kolor is not None:
            rekord.kolor = payload.kolor.strip()
        if payload.przypiety is not None:
            rekord.przypiety = payload.przypiety
        if payload.parent_id is not None:
            rekord.parent_id = payload.parent_id
        rekord.updated_at = utcnow()
    return _katalog_payload(rekord)


@router.delete("/katalogi/{katalog_id}")
async def usun_katalog(
    katalog_id: uuid.UUID,
    request: Request,
    owner: uuid.UUID = Depends(wlasciciel),
    z_plikami: bool = Query(False, description="Usuń też pliki z katalogu"),
) -> dict[str, Any]:
    """Usuwa katalog. Pliki domyślnie zostają — wracają do widoku „Wszystkie”.

    Kasowanie plików razem z katalogiem musi być wyborem, nie skutkiem ubocznym
    porządkowania: katalog jest etykietą, a nie pudełkiem, w którym plik istnieje.
    """
    database = _database(request)
    await _katalog(database, katalog_id, owner)
    storage: FileStorage = request.app.state.storage
    usuniete = 0
    async with database.session() as session:
        if z_plikami:
            pliki = (
                await session.scalars(
                    select(StoredFile).where(
                        StoredFile.katalog_id == katalog_id, StoredFile.owner_id == owner
                    )
                )
            ).all()
            for plik in pliki:
                storage.delete(plik)
            usuniete = len(pliki)
            await session.execute(
                delete(StoredFile).where(
                    StoredFile.katalog_id == katalog_id, StoredFile.owner_id == owner
                )
            )
        else:
            await session.execute(
                update(StoredFile)
                .where(StoredFile.katalog_id == katalog_id, StoredFile.owner_id == owner)
                .values(katalog_id=None)
            )
        await session.execute(
            delete(KatalogPlikow).where(
                KatalogPlikow.id == katalog_id, KatalogPlikow.owner_id == owner
            )
        )
    return {"ok": True, "usuniete_pliki": usuniete}


@router.get("")
async def lista_plikow(
    request: Request,
    owner: uuid.UUID = Depends(wlasciciel),
    katalog_id: uuid.UUID | None = None,
    rodzaj: str = Query("", description="zdjecia, dokumenty, nagrania, archiwa"),
    q: str = Query("", max_length=200),
    bez_katalogu: bool = False,
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    """Pliki konta z filtrem katalogu, rodzaju treści i wyszukiwaniem po nazwie."""
    database = _database(request)
    if katalog_id is not None:
        await _katalog(database, katalog_id, owner)
    zapytanie = select(StoredFile).where(StoredFile.owner_id == owner)
    if katalog_id is not None:
        zapytanie = zapytanie.where(StoredFile.katalog_id == katalog_id)
    elif bez_katalogu:
        zapytanie = zapytanie.where(StoredFile.katalog_id.is_(None))
    przedrostki = RODZAJE_TRESCI.get(rodzaj.strip().lower())
    if przedrostki:
        zapytanie = zapytanie.where(or_(*(StoredFile.mime.startswith(p) for p in przedrostki)))
    szukane = q.strip()
    if szukane:
        # `%` i `_` są w LIKE znakami wieloznacznymi. Bez zasłonięcia ich szukanie
        # „50%” oddawało wszystkie pliki, a „raport_2026” trafiał też w „raport-2026”.
        wzorzec = "%" + szukane.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        zapytanie = zapytanie.where(
            or_(
                StoredFile.name.ilike(wzorzec, escape="\\"),
                StoredFile.tytul.ilike(wzorzec, escape="\\"),
            )
        )
    async with database.session() as session:
        rekordy = (
            await session.scalars(zapytanie.order_by(StoredFile.created_at.desc()).limit(limit))
        ).all()
        zajete = int(
            await session.scalar(
                select(func.coalesce(func.sum(StoredFile.size), 0)).where(StoredFile.owner_id == owner)
            )
            or 0
        )
    limity = await limity_uzytkownika(database, str(owner))
    return {
        "pliki": [
            {**file_payload(rekord), "katalog_id": str(rekord.katalog_id) if rekord.katalog_id else None,
             "tytul": rekord.tytul}
            for rekord in rekordy
        ],
        "przestrzen": {
            "zajete": zajete,
            "limit": limity.przestrzen_mb * 1024 * 1024,
            "opis_limitu": opis_przestrzeni(limity.przestrzen_mb),
            "plan": limity.nazwa_planu,
        },
    }


@router.post("/przypisz")
async def przypisz_do_katalogu(
    payload: PrzypiszBody, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, Any]:
    """Przenosi wskazane pliki do katalogu albo wyjmuje je z katalogu."""
    database = _database(request)
    if payload.katalog_id is not None:
        await _katalog(database, payload.katalog_id, owner)
    async with database.session() as session:
        wynik = await session.execute(
            update(StoredFile)
            .where(StoredFile.id.in_(payload.pliki), StoredFile.owner_id == owner)
            .values(katalog_id=payload.katalog_id)
        )
    return {"ok": True, "przeniesione": int(wynik.rowcount or 0)}


@router.patch("/{file_id}")
async def zmien_tytul(
    file_id: uuid.UUID,
    payload: TytulBody,
    request: Request,
    owner: uuid.UUID = Depends(wlasciciel),
) -> dict[str, Any]:
    """Nadaje plikowi własną nazwę; nazwa z dysku zostaje bez zmian.

    Nazwa pliku bywa nieczytelna („scan_0012.pdf”), ale zmiana jej na dysku zerwałaby
    odwołania w rozmowach, w których ten plik już wystąpił.
    """
    database = _database(request)
    async with database.session() as session:
        rekord = await session.get(StoredFile, file_id)
        if rekord is None or rekord.owner_id != owner:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono pliku.")
        rekord.tytul = " ".join(payload.tytul.split())[:300]
    return {**file_payload(rekord), "tytul": rekord.tytul}


@router.delete("/{file_id}")
async def usun_plik(
    file_id: uuid.UUID, request: Request, owner: uuid.UUID = Depends(wlasciciel)
) -> dict[str, bool]:
    """Usuwa plik konta wraz z jego zawartością na dysku."""
    database = _database(request)
    storage: FileStorage = request.app.state.storage
    async with database.session() as session:
        rekord = await session.get(StoredFile, file_id)
        if rekord is None or rekord.owner_id != owner:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono pliku.")
        storage.delete(rekord)
        await session.delete(rekord)
    return {"ok": True}
