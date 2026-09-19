"""Twórca stron: zarządzanie stronami, podgląd szkicu i publikacja pod ``/s/<adres>/``.

Strony użytkownika są serwowane z osobną, restrykcyjną polityką CSP z dyrektywą ``sandbox``:
dokument dostaje nieprzezroczyste pochodzenie, więc jego skrypty nie mają dostępu do ciasteczek,
magazynu ani API aplikacji. Podgląd szkicu działa przez podpisany, wygasający adres
``/api/strony/<adres>/podglad/<token>/…`` wydawany wyłącznie zalogowanemu użytkownikowi
(osadzony w interfejsie w ramce ``iframe sandbox`` bez ``allow-same-origin``).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from nexus.api.auth import require_session
from nexus.db import Conversation, Database
from nexus.storage import guess_mime
from nexus.tworczy.strony import SiteError, SiteStore, check_address, site_store

PREVIEW_TTL_SECONDS = 12 * 3600
SITE_CSP = (
    "sandbox allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals "
    "allow-downloads; default-src 'self' https: data: blob:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net "
    "https://cdnjs.cloudflare.com https://esm.sh https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' https:; img-src 'self' https: data: blob:; "
    "font-src 'self' https: data:; media-src 'self' https: data: blob:; connect-src https:; "
    "frame-src https:; worker-src 'none'; "
    "object-src 'none'; base-uri 'self'; form-action https:; frame-ancestors 'self'"
)
TEXT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".xml": "application/xml",
    ".csv": "text/plain; charset=utf-8",
    ".webmanifest": "application/manifest+json",
}
TRANSLITERATION = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

api = APIRouter(prefix="/api/strony", tags=["strony"], dependencies=[Depends(require_session)])
public = APIRouter(tags=["strony"])


class NewSite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    address: str | None = Field(None, max_length=48)
    description: str = Field("", max_length=4000)


class SiteUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)


class VersionNote(BaseModel):
    note: str = Field("", max_length=300)


def slugify(text: str) -> str:
    """Adres strony z tytułu: ``Kawiarnia Pod Lipą`` → ``kawiarnia-pod-lipa``."""
    value = unicodedata.normalize("NFKD", text.translate(TRANSLITERATION))
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:48].strip("-")
    return value or "strona"


def _store(request: Request) -> SiteStore:
    return site_store(request.app.state.settings)


def _error(error: SiteError) -> HTTPException:
    missing = "nie istnieje" in str(error)
    return HTTPException(status.HTTP_404_NOT_FOUND if missing else 422, str(error))


def _preview_key(store: SiteStore) -> bytes:
    """Klucz podpisu adresów podglądu (plik 600 w katalogu stron, tworzony raz)."""
    path = store.root / ".klucz"
    try:
        return path.read_bytes()
    except FileNotFoundError:
        store.root.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(32)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return path.read_bytes()
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(key)
        return key


def _signature(key: bytes, address: str, expires: int) -> str:
    digest = hmac.new(key, f"{address}:{expires}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:24]).decode("ascii")


def preview_token(store: SiteStore, address: str, now: float | None = None) -> str:
    """Podpisany token podglądu szkicu ważny ``PREVIEW_TTL_SECONDS``."""
    expires = int((now or time.time()) + PREVIEW_TTL_SECONDS)
    return f"{expires}.{_signature(_preview_key(store), address, expires)}"


def check_preview_token(store: SiteStore, address: str, token: str, now: float | None = None) -> bool:
    """Czy token podglądu jest ważny dla tej strony."""
    expires_text, _, signature = token.partition(".")
    if not expires_text.isdigit() or int(expires_text) < (now or time.time()):
        return False
    return hmac.compare_digest(signature, _signature(_preview_key(store), address, int(expires_text)))


def _site_payload(store: SiteStore, meta: dict[str, Any]) -> dict[str, Any]:
    address = meta["address"]
    return {
        "address": address,
        "title": meta.get("title", address),
        "description": meta.get("description", ""),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "published_at": meta.get("published_at"),
        "published_version": meta.get("published_version"),
        "publish_request": meta.get("publish_request"),
        "conversation_id": meta.get("conversation_id"),
        "versions": list(reversed(meta.get("versions", []))),
        "public_url": f"/s/{address}/",
    }


async def _new_conversation(request: Request, address: str, title: str) -> str:
    database: Database = request.app.state.database
    conversation = Conversation(title=f"Strona: {title}"[:200], meta={"mode": "strona", "site": address})
    async with database.session() as session:
        session.add(conversation)
    return str(conversation.id)


@api.get("")
async def list_sites(request: Request) -> list[dict[str, Any]]:
    """Strony użytkownika (od ostatnio zmienianej)."""
    store = _store(request)
    return [_site_payload(store, meta) for meta in await asyncio.to_thread(store.list_sites)]


@api.post("", status_code=status.HTTP_201_CREATED)
async def create_site(payload: NewSite, request: Request) -> dict[str, Any]:
    """Zakłada stronę (z rozmową w trybie ``strona``); adres powstaje z tytułu, gdy go nie podano."""
    store = _store(request)
    try:
        if payload.address:
            address = check_address(payload.address)
        else:
            base = slugify(payload.title)
            address, counter = base, 2
            while store.exists(address) or store.draft_dir(address).exists():
                address = f"{base[:44]}-{counter}"
                counter += 1
        meta = await asyncio.to_thread(store.create, address, payload.title, payload.description)
    except SiteError as error:
        exists = "już istnieje" in str(error)
        raise HTTPException(status.HTTP_409_CONFLICT if exists else 422, str(error)) from error
    conversation_id = await _new_conversation(request, address, meta["title"])
    meta = store.update_meta(address, conversation_id=conversation_id)
    return _site_payload(store, meta)


@api.get("/{address}")
async def get_site(address: str, request: Request) -> dict[str, Any]:
    """Strona z listą plików szkicu i adresem podglądu."""
    store = _store(request)
    try:
        meta = store.meta(address)
        files = await asyncio.to_thread(store.list_files, address)
    except SiteError as error:
        raise _error(error) from error
    token = preview_token(store, meta["address"])
    return {
        **_site_payload(store, meta),
        "files": files,
        "preview_url": f"/api/strony/{meta['address']}/podglad/{token}/",
    }


@api.patch("/{address}")
async def update_site(address: str, payload: SiteUpdate, request: Request) -> dict[str, Any]:
    """Zmienia tytuł lub opis strony."""
    store = _store(request)
    values = {key: value.strip() for key, value in payload.model_dump(exclude_none=True).items()}
    try:
        meta = store.update_meta(address, **values)
    except SiteError as error:
        raise _error(error) from error
    return _site_payload(store, meta)


@api.delete("/{address}")
async def delete_site(address: str, request: Request) -> dict[str, bool]:
    """Usuwa stronę (szkic, wersje i publikację). Rozmowa zostaje w historii."""
    store = _store(request)
    try:
        await asyncio.to_thread(store.delete_site, address)
    except SiteError as error:
        raise _error(error) from error
    return {"ok": True}


@api.post("/{address}/rozmowa")
async def site_conversation(address: str, request: Request) -> dict[str, str]:
    """Rozmowa edycji strony – istniejąca albo nowa, gdy poprzednią usunięto."""
    store = _store(request)
    try:
        meta = store.meta(address)
    except SiteError as error:
        raise _error(error) from error
    current = meta.get("conversation_id")
    if current:
        database: Database = request.app.state.database
        async with database.session() as session:
            if await session.get(Conversation, uuid.UUID(current)) is not None:
                return {"conversation_id": current}
    conversation_id = await _new_conversation(request, meta["address"], meta.get("title", address))
    store.update_meta(address, conversation_id=conversation_id)
    return {"conversation_id": conversation_id}


@api.get("/{address}/pliki/{path:path}")
async def read_site_file(address: str, path: str, request: Request) -> dict[str, str]:
    """Treść pliku tekstowego szkicu (podgląd kodu)."""
    try:
        content = await asyncio.to_thread(_store(request).read_text, address, path)
    except SiteError as error:
        raise _error(error) from error
    return {"path": path, "content": content}


@api.post("/{address}/wersje", status_code=status.HTTP_201_CREATED)
async def save_version(address: str, payload: VersionNote, request: Request) -> dict[str, Any]:
    """Zapisuje bieżący szkic jako wersję."""
    try:
        return await asyncio.to_thread(_store(request).snapshot, address, payload.note)
    except SiteError as error:
        raise _error(error) from error


@api.post("/{address}/wersje/{version_id}/przywroc")
async def restore_version(address: str, version_id: str, request: Request) -> dict[str, Any]:
    """Przywraca szkic z wersji (bieżący stan zostaje zapisany jako wersja)."""
    store = _store(request)
    try:
        meta = await asyncio.to_thread(store.restore, address, version_id)
    except SiteError as error:
        raise _error(error) from error
    return _site_payload(store, meta)


@api.post("/{address}/publikuj")
async def publish_site(address: str, request: Request) -> dict[str, Any]:
    """Publikuje bieżący szkic pod ``/s/<adres>/`` (akcja użytkownika potwierdzona w interfejsie)."""
    store = _store(request)
    try:
        meta = await asyncio.to_thread(store.publish, address)
    except SiteError as error:
        raise _error(error) from error
    return _site_payload(store, meta)


@api.post("/{address}/wycofaj")
async def unpublish_site(address: str, request: Request) -> dict[str, Any]:
    """Wycofuje publikację strony."""
    store = _store(request)
    try:
        meta = await asyncio.to_thread(store.unpublish, address)
    except SiteError as error:
        raise _error(error) from error
    return _site_payload(store, meta)


@api.post("/{address}/odrzuc-publikacje")
async def reject_publish_request(address: str, request: Request) -> dict[str, Any]:
    """Odrzuca prośbę asystenta o publikację."""
    store = _store(request)
    try:
        meta = store.update_meta(address, publish_request=None)
    except SiteError as error:
        raise _error(error) from error
    return _site_payload(store, meta)


# --- serwowanie stron (bez sesji aplikacji) ------------------------------------------------------


def _site_response(path: Path, status_code: int = 200, cache: str = "no-cache") -> Response:
    media_type = TEXT_TYPES.get(path.suffix.lower()) or guess_mime(path.name)
    return FileResponse(
        path,
        status_code=status_code,
        media_type=media_type,
        headers={
            "Content-Security-Policy": SITE_CSP,
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": cache,
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
            "Cross-Origin-Opener-Policy": "same-origin",
            # Dokument w piaskownicy ma pochodzenie „null”: skrypty modułowe, czcionki i fetch
            # własnych plików strony wymagają CORS. Treść strony nie zależy od ciasteczek.
            "Access-Control-Allow-Origin": "*",
        },
    )


def _not_found() -> Response:
    return Response(
        "Nie znaleziono strony.",
        status_code=status.HTTP_404_NOT_FOUND,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Security-Policy": SITE_CSP, "Cache-Control": "no-cache"},
    )


def _serve(store: SiteStore, address: str, path: str, published: bool) -> Response:
    try:
        address = check_address(address)
    except SiteError:
        return _not_found()
    if published and not store.published_dir(address).is_dir():
        return _not_found()
    cache = "public, max-age=300" if published else "no-store"
    found = store.resolve(address, path, published=published)
    if found is not None:
        return _site_response(found, cache=cache)
    missing_page = store.resolve(address, "404.html", published=published)
    if missing_page is not None:
        return _site_response(missing_page, status.HTTP_404_NOT_FOUND, cache=cache)
    return _not_found()


@public.get("/s/{address}", include_in_schema=False)
async def published_root(address: str) -> Response:
    return RedirectResponse(f"/s/{address}/", status_code=status.HTTP_308_PERMANENT_REDIRECT)


@public.get("/s/{address}/{path:path}", include_in_schema=False)
async def published_file(address: str, path: str, request: Request) -> Response:
    """Opublikowana strona (publiczna)."""
    return await asyncio.to_thread(_serve, _store(request), address, path, True)


@public.get("/api/strony/{address}/podglad/{token}/{path:path}", include_in_schema=False)
async def preview_file(address: str, token: str, path: str, request: Request) -> Response:
    """Szkic strony – tylko z ważnym tokenem wydanym zalogowanemu użytkownikowi."""
    store = _store(request)
    if not check_preview_token(store, address.lower(), token):
        return Response(
            "Podgląd wygasł – odśwież stronę modułu.",
            status_code=status.HTTP_403_FORBIDDEN,
            media_type="text/plain; charset=utf-8",
        )
    return await asyncio.to_thread(_serve, store, address, path, False)


router = APIRouter()
router.include_router(api)
router.include_router(public)
