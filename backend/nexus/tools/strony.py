"""Narzędzia Twórcy stron: pliki szkicu strony, wersje i prośba o publikację.

Strony są statyczne (HTML, CSS, JS, obrazy) i leżą w ``<dane>/strony/<adres>/``.
Szkic jest widoczny na żywo w podglądzie modułu Strony; publikację pod ``/s/<adres>/``
zatwierdza wyłącznie użytkownik w interfejsie.
"""

from __future__ import annotations

from pydantic import Field

from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tworczy.strony import SiteError, SiteStore, check_file_path, site_store

SITE_FIELD = Field(description="Adres strony (np. 'kawiarnia-pod-lipami') z nagłówka [Strona: …] rozmowy.")


def _store(ctx: ToolContext) -> SiteStore:
    return site_store(ctx.settings)


def _format_size(size: int) -> str:
    return f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"


class SiteListInput(ToolInput):
    site: str | None = Field(None, description="Adres strony; bez adresu – lista wszystkich stron.")


@registry.register(
    "site_list",
    """Lista stron WWW użytkownika albo – z podanym adresem – lista plików szkicu strony
(ścieżki, rozmiary, stan publikacji i wersje).""",
    SiteListInput,
)
def site_list(ctx: ToolContext, args: SiteListInput) -> ToolResult:
    store = _store(ctx)
    try:
        if not args.site:
            sites = [
                {
                    "site": item["address"],
                    "title": item.get("title"),
                    "published": bool(item.get("published_at")),
                }
                for item in store.list_sites()
            ]
            return ToolResult({"sites": sites}, f"Strony: {len(sites)}")
        meta = store.meta(args.site)
        files = store.list_files(args.site)
    except SiteError as error:
        raise ToolError(str(error)) from error
    data = {
        "site": meta["address"],
        "title": meta.get("title"),
        "description": meta.get("description"),
        "published_at": meta.get("published_at"),
        "public_url": f"/s/{meta['address']}/",
        "files": files,
        "versions": [
            f"{v['id']} {v['created_at']} {v.get('note', '')}".strip() for v in meta.get("versions", [])
        ][-10:],
    }
    return ToolResult(data, f"Pliki strony {meta['address']}: {len(files)}")


class SiteReadInput(ToolInput):
    site: str = SITE_FIELD
    path: str = Field(description="Ścieżka pliku tekstowego w stronie, np. 'index.html', 'css/style.css'.")


@registry.register(
    "site_read_file",
    "Odczytuje plik tekstowy szkicu strony (HTML, CSS, JS, JSON, SVG…) przed jego zmianą.",
    SiteReadInput,
)
def site_read_file(ctx: ToolContext, args: SiteReadInput) -> ToolResult:
    try:
        content = _store(ctx).read_text(args.site, args.path)
    except SiteError as error:
        raise ToolError(str(error)) from error
    return ToolResult({"path": args.path, "content": content}, f"Odczytano {args.path}")


class SiteWriteInput(ToolInput):
    site: str = SITE_FIELD
    path: str = Field(description="Ścieżka pliku, np. 'index.html', 'css/style.css', 'js/app.js'.")
    content: str = Field(description="Pełna nowa treść pliku (UTF-8). Plik jest zastępowany w całości.")


@registry.register(
    "site_write_file",
    """Zapisuje (tworzy albo zastępuje w całości) plik tekstowy szkicu strony: HTML, CSS, JS, JSON,
SVG, TXT, MD, XML. Podgląd strony u użytkownika odświeża się na żywo po każdym zapisie.""",
    SiteWriteInput,
)
def site_write_file(ctx: ToolContext, args: SiteWriteInput) -> ToolResult:
    try:
        written = _store(ctx).write_text(args.site, args.path, args.content)
    except SiteError as error:
        raise ToolError(str(error)) from error
    return ToolResult(written, f"Zapisano {written['path']} ({_format_size(written['size'])})")


class SiteImportInput(ToolInput):
    site: str = SITE_FIELD
    file_id: str = Field(description="Plik z rozmowy (np. zdjęcie, logo, czcionka) do skopiowania do strony.")
    path: str = Field(description="Ścieżka docelowa w stronie, np. 'img/logo.png'.")


@registry.register(
    "site_import_file",
    """Kopiuje plik z rozmowy (obraz, logo, czcionkę, wideo, PDF) do szkicu strony pod podaną ścieżką,
aby można go było użyć w HTML/CSS (np. <img src="img/logo.png">).""",
    SiteImportInput,
)
def site_import_file(ctx: ToolContext, args: SiteImportInput) -> ToolResult:
    file = ctx.file(args.file_id)
    store = _store(ctx)
    try:
        path = check_file_path(args.path)
        store.meta(args.site)
        data = file.path.read_bytes()
        written = store.write_bytes(args.site, path, data)
    except SiteError as error:
        raise ToolError(str(error)) from error
    return ToolResult(written, f"Dodano {file.name} jako {written['path']}")


class SiteDeleteInput(ToolInput):
    site: str = SITE_FIELD
    path: str = Field(description="Ścieżka pliku do usunięcia ze szkicu strony.")


@registry.register("site_delete_file", "Usuwa plik ze szkicu strony.", SiteDeleteInput)
def site_delete_file(ctx: ToolContext, args: SiteDeleteInput) -> ToolResult:
    try:
        _store(ctx).delete_file(args.site, args.path)
    except SiteError as error:
        raise ToolError(str(error)) from error
    return ToolResult({"deleted": args.path}, f"Usunięto {args.path}")


class SiteVersionInput(ToolInput):
    site: str = SITE_FIELD
    note: str = Field("", max_length=300, description="Krótki opis wersji, np. 'Nowa sekcja cennika'.")


@registry.register(
    "site_save_version",
    """Zapisuje bieżący szkic strony jako wersję (użytkownik może do niej wrócić w module Strony).
Używaj przed dużymi zmianami układu.""",
    SiteVersionInput,
)
def site_save_version(ctx: ToolContext, args: SiteVersionInput) -> ToolResult:
    try:
        version = _store(ctx).snapshot(args.site, args.note)
    except SiteError as error:
        raise ToolError(str(error)) from error
    return ToolResult(version, f"Zapisano wersję {version['id']}")


@registry.register(
    "site_publish",
    """Zgłasza prośbę o publikację strony pod publicznym adresem /s/<adres>/. Publikacja NIE następuje
od razu: użytkownik musi ją zatwierdzić przyciskiem w module Strony. Wywołuj tylko, gdy użytkownik
prosi o publikację; w odpowiedzi poinformuj go, że czeka ona na potwierdzenie.""",
    SiteVersionInput,
)
def site_publish(ctx: ToolContext, args: SiteVersionInput) -> ToolResult:
    store = _store(ctx)
    try:
        if not (store.draft_dir(args.site) / "index.html").is_file():
            raise ToolError("Strona nie ma pliku index.html – najpierw go utwórz.")
        store.request_publish(args.site, args.note)
    except SiteError as error:
        raise ToolError(str(error)) from error
    return ToolResult(
        {"status": "czeka_na_potwierdzenie", "public_url": f"/s/{args.site.strip().lower()}/"},
        "Prośba o publikację czeka na potwierdzenie użytkownika",
    )


class SiteUnpublishInput(ToolInput):
    site: str = SITE_FIELD


@registry.register(
    "site_unpublish",
    "Wycofuje publikację strony – adres publiczny przestaje działać (szkic i wersje zostają).",
    SiteUnpublishInput,
)
def site_unpublish(ctx: ToolContext, args: SiteUnpublishInput) -> ToolResult:
    try:
        _store(ctx).unpublish(args.site)
    except SiteError as error:
        raise ToolError(str(error)) from error
    return ToolResult({"status": "wycofana"}, "Wycofano publikację strony")
