"""Repozytorium treści portalu: listowanie, odczyt, zapis, publikacja i wyszukiwanie.

Wyszukiwanie: warunek ``LIKE`` na kolumnie ``search_text`` zawęża zbiór w bazie (wszystkie słowa
zapytania muszą wystąpić), a kolejność wyników ustala ocena liczona w Pythonie – trafienie w tytule
waży najwięcej, potem zajawka, znaczniki i treść. Działa jednakowo w PostgreSQL i SQLite.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.db import utcnow
from nexus.models.portal import PortalContent
from nexus.portal import tresc

# Największa liczba pozycji zwracanych na jednej stronie listy i w wyszukiwaniu.
MAX_NA_STRONIE = 50
KANDYDACI_WYSZUKIWANIA = 200
# Wagi oceny trafności: tytuł, zajawka, znaczniki, treść.
WAGI = (8, 3, 3, 1)


class BrakTresci(LookupError):
    """Pozycja treści nie istnieje albo nie jest opublikowana."""


@dataclass(frozen=True)
class DaneTresci:
    """Komplet pól pozycji treści przyjmowany przez repozytorium."""

    kind: str
    slug: str
    title: str
    excerpt: str
    body: str
    author: str
    tags: list[str]
    status: str
    seo: dict[str, Any]
    position: int


def _daty(record: PortalContent) -> dict[str, str | None]:
    return {
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "published_at": record.published_at.isoformat() if record.published_at else None,
    }


def skrot(record: PortalContent) -> dict[str, Any]:
    """Pozycja na liście (bez treści Markdown)."""
    return {
        "id": str(record.id),
        "kind": record.kind,
        "slug": record.slug,
        "title": record.title,
        "excerpt": record.excerpt,
        "author": record.author,
        "tags": list(record.tags or []),
        "status": record.status,
        "position": record.position,
        **_daty(record),
    }


def pelna(record: PortalContent) -> dict[str, Any]:
    """Pozycja z treścią Markdown i metadanymi SEO."""
    return {**skrot(record), "body": record.body, "seo": dict(record.seo or {})}


def _opublikowane(zapytanie: Select[Any]) -> Select[Any]:
    return zapytanie.where(PortalContent.status == "opublikowany")


def _kolejnosc(zapytanie: Select[Any], kind: str | None) -> Select[Any]:
    if kind == "dokumentacja":
        return zapytanie.order_by(PortalContent.position, PortalContent.title)
    return zapytanie.order_by(PortalContent.published_at.desc().nullslast(), PortalContent.created_at.desc())


async def lista(
    session: AsyncSession,
    *,
    kind: str | None = None,
    tylko_opublikowane: bool = True,
    tag: str = "",
    zapytanie: str = "",
    strona: int = 1,
    na_stronie: int = 10,
) -> dict[str, Any]:
    """Strona listy treści: ``{"items": [...], "total": n, "page": s, "pages": p}``."""
    na_stronie = max(1, min(MAX_NA_STRONIE, na_stronie))
    strona = max(1, strona)
    warunki = select(PortalContent)
    if kind:
        warunki = warunki.where(PortalContent.kind == kind)
    if tylko_opublikowane:
        warunki = _opublikowane(warunki)
    for slowo in tresc.slowa_zapytania(zapytanie):
        warunki = warunki.where(PortalContent.search_text.like(f"%{slowo}%"))
    if tag.strip():
        warunki = warunki.where(PortalContent.search_text.like(f"%{tresc.znormalizuj(tag)}%"))
    razem = await session.scalar(select(func.count()).select_from(warunki.subquery())) or 0
    strony = max(1, -(-razem // na_stronie))
    rekordy = (
        await session.scalars(
            _kolejnosc(warunki, kind).offset((strona - 1) * na_stronie).limit(na_stronie)
        )
    ).all()
    return {
        "items": [skrot(record) for record in rekordy],
        "total": razem,
        "page": strona,
        "pages": strony,
        "per_page": na_stronie,
    }


async def pobierz(
    session: AsyncSession, kind: str, slug: str, *, tylko_opublikowane: bool = True
) -> PortalContent:
    """Pozycja po rodzaju i adresie; ``BrakTresci``, gdy nie istnieje lub jest szkicem."""
    zapytanie = select(PortalContent).where(PortalContent.kind == kind, PortalContent.slug == slug)
    if tylko_opublikowane:
        zapytanie = _opublikowane(zapytanie)
    record = await session.scalar(zapytanie)
    if record is None:
        raise BrakTresci(f"Nie znaleziono pozycji {kind}/{slug}.")
    return record


async def pobierz_po_id(session: AsyncSession, identyfikator: uuid.UUID) -> PortalContent:
    """Pozycja po identyfikatorze (panel administratora, także szkice)."""
    record = await session.get(PortalContent, identyfikator)
    if record is None:
        raise BrakTresci("Nie znaleziono pozycji treści.")
    return record


async def wolny_slug(
    session: AsyncSession, kind: str, proponowany: str, pomijany: uuid.UUID | None = None
) -> str:
    """Adres nieużywany w obrębie rodzaju; przy kolizji dopisuje kolejny numer."""
    podstawa, adres, licznik = proponowany, proponowany, 2
    while True:
        zapytanie = select(PortalContent.id).where(
            PortalContent.kind == kind, PortalContent.slug == adres
        )
        if pomijany is not None:
            zapytanie = zapytanie.where(PortalContent.id != pomijany)
        if await session.scalar(zapytanie) is None:
            return adres
        adres = f"{podstawa[:tresc.MAX_SLUG - 6]}-{licznik}"
        licznik += 1


def _uzupelnij(record: PortalContent, dane: DaneTresci, teraz: datetime) -> PortalContent:
    record.kind = dane.kind
    record.slug = dane.slug
    record.title = dane.title
    record.excerpt = tresc.zajawka(dane.excerpt, dane.body)
    record.body = dane.body
    record.author = dane.author
    record.tags = dane.tags
    record.seo = dane.seo
    record.position = dane.position
    record.search_text = tresc.tekst_wyszukiwania(dane.title, record.excerpt, dane.body, dane.tags)
    record.updated_at = teraz
    if dane.status != record.status:
        record.status = dane.status
        record.published_at = teraz if dane.status == "opublikowany" else None
    elif dane.status == "opublikowany" and record.published_at is None:
        record.published_at = teraz
    return record


async def utworz(session: AsyncSession, dane: DaneTresci) -> PortalContent:
    """Zakłada pozycję treści (adres unikalny w obrębie rodzaju)."""
    teraz = utcnow()
    record = PortalContent(kind=dane.kind, status="szkic", created_at=teraz, updated_at=teraz)
    record.slug = await wolny_slug(session, dane.kind, dane.slug)
    _uzupelnij(record, DaneTresci(**{**dane.__dict__, "slug": record.slug}), teraz)
    session.add(record)
    await session.flush()
    return record


async def zmien(session: AsyncSession, record: PortalContent, dane: DaneTresci) -> PortalContent:
    """Zapisuje zmiany pozycji; przy zmianie adresu pilnuje unikalności."""
    if dane.slug != record.slug or dane.kind != record.kind:
        dane = DaneTresci(
            **{**dane.__dict__, "slug": await wolny_slug(session, dane.kind, dane.slug, record.id)}
        )
    return _uzupelnij(record, dane, utcnow())


async def ustaw_status(session: AsyncSession, record: PortalContent, status: str) -> PortalContent:
    """Publikuje pozycję albo wycofuje ją do szkicu."""
    teraz = utcnow()
    record.status = status
    record.published_at = teraz if status == "opublikowany" else None
    record.updated_at = teraz
    await session.flush()
    return record


async def usun(session: AsyncSession, identyfikator: uuid.UUID) -> None:
    """Usuwa pozycję treści."""
    record = await pobierz_po_id(session, identyfikator)
    await session.execute(delete(PortalContent).where(PortalContent.id == record.id))


def _ocena(record: PortalContent, slowa: list[str]) -> int:
    """Trafność pozycji: waga zależy od pola, w którym wystąpiło słowo zapytania."""
    pola = (
        tresc.znormalizuj(record.title),
        tresc.znormalizuj(record.excerpt),
        tresc.znormalizuj(" ".join(record.tags or [])),
        record.search_text,
    )
    return sum(waga for slowo in slowa for waga, pole in zip(WAGI, pola, strict=True) if slowo in pole)


async def szukaj(
    session: AsyncSession, zapytanie: str, *, rodzaje: list[str] | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Wyszukiwanie pełnotekstowe w opublikowanych treściach, wynik posortowany trafnością."""
    slowa = tresc.slowa_zapytania(zapytanie)
    if not slowa:
        return []
    warunki = _opublikowane(select(PortalContent))
    if rodzaje:
        warunki = warunki.where(or_(*[PortalContent.kind == rodzaj for rodzaj in rodzaje]))
    for slowo in slowa:
        warunki = warunki.where(PortalContent.search_text.like(f"%{slowo}%"))
    kandydaci = (await session.scalars(warunki.limit(KANDYDACI_WYSZUKIWANIA))).all()
    najlepsze = sorted(kandydaci, key=lambda record: (-_ocena(record, slowa), record.title))
    return [
        {**skrot(record), "score": _ocena(record, slowa)}
        for record in najlepsze[: max(1, min(MAX_NA_STRONIE, limit))]
    ]


async def opublikowane_do_kanalu(
    session: AsyncSession, *, kind: str | None = None, limit: int = 50
) -> list[PortalContent]:
    """Opublikowane pozycje od najnowszej – kanał Atom i mapa witryny."""
    zapytanie = _opublikowane(select(PortalContent))
    if kind:
        zapytanie = zapytanie.where(PortalContent.kind == kind)
    return list((await session.scalars(_kolejnosc(zapytanie, None).limit(limit))).all())
