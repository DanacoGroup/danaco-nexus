"""Aplikacja FastAPI: API czatu i serwowanie interfejsu WWW."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from email.utils import parsedate
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from nexus import __version__
from nexus.api import auth, conversations, files, modules, runs, voice, znaczniki
from nexus.config import Settings, get_settings
from nexus.db import Database
from nexus.events import EventBus
from nexus.knowledge import KnowledgeBase
from nexus.logging_setup import configure_logging
from nexus.storage import FileStorage
from nexus.voice import VoiceEngine

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(self), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "frame-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; "
        "worker-src 'self'; manifest-src 'self'"
    ),
}
# Pliki PWA, które przeglądarka musi zawsze sprawdzać (aktualizacje aplikacji).
NO_CACHE_FILES = frozenset(
    {"sw.js", "registerSW.js", "share-target.js", "manifest.webmanifest", "index.html"}
)
IMMUTABLE = "public, max-age=31536000, immutable"
# Typy podawane wprost: `mimetypes` zależy od pliku mime.types systemu, a bez poprawnego
# typu przeglądarka nie narysuje tła AVIF ani nie wczyta kroju i napisów.
MEDIA_TYPES = {
    ".webmanifest": "application/manifest+json",
    ".js": "text/javascript",
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".vtt": "text/vtt",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}
# Materiały marki: kroje, znak, ikony, tła, plakaty, nagrania i napisy. Nazwy są stałe i nie
# niosą skrótu treści, a `frontend/scripts/zasoby.py` przelicza je przy każdym `prebuild` —
# wieczysta ważność podawałaby starą treść pod tą samą nazwą. Doba bez zapytania, potem
# miesiąc podawania z pamięci z jednoczesnym odświeżeniem w tle. Odświeżenie jest tanie,
# bo trasa `spa` odpowiada na nie kodem 304, gdy plik się nie zmienił.
MEDIA_SUFFIXES = frozenset(
    {".woff2", ".mp4", ".webm", ".vtt", ".avif", ".webp", ".png", ".jpg", ".svg", ".ico"}
)
MEDIA_CACHE = "public, max-age=86400, stale-while-revalidate=2592000"
# Znaczniki wersji przenoszone do odpowiedzi 304: reszta nagłówków jest tam zbędna.
ZNACZNIKI_WERSJI = ("cache-control", "etag", "last-modified")


def niezmieniony(request: Request, odpowiedz: Response) -> bool:
    """Czy przeglądarka trzyma już tę wersję pliku (If-None-Match, If-Modified-Since)."""
    podane = request.headers.get("if-none-match")
    if podane:
        etag = odpowiedz.headers.get("etag", "")
        # „*” znaczy „dowolna wersja zasobu” (RFC 9110 §13.1.2): jeżeli plik w ogóle
        # istnieje, warunek jest spełniony i należy odpowiedzieć 304. Wcześniej wpadało
        # to w porównanie znaczników i wracało pełną treścią.
        if podane.strip() == "*":
            return True
        return bool(etag) and etag in [z.strip().removeprefix("W/") for z in podane.split(",")]
    od = parsedate(request.headers.get("if-modified-since", ""))
    zmiana = parsedate(odpowiedz.headers.get("last-modified", ""))
    return od is not None and zmiana is not None and od >= zmiana


def plik_z_warunkiem(sciezka: Path, cache: str, request: Request) -> Response:
    """Plik ze znacznikami wersji. Gdy kopia odwiedzającego jest aktualna — 304 bez treści.

    `FileResponse` samo nie obsługuje żądań warunkowych (robi to wyłącznie `StaticFiles`),
    więc bez tego kroku każde odświeżenie materiału pobierało go w całości od nowa.
    """
    odpowiedz = FileResponse(
        sciezka,
        media_type=MEDIA_TYPES.get(sciezka.suffix),
        headers={"Cache-Control": cache},
        stat_result=sciezka.stat(),
    )
    if not niezmieniony(request, odpowiedz):
        return odpowiedz
    znaczniki = {k: odpowiedz.headers[k] for k in ZNACZNIKI_WERSJI if k in odpowiedz.headers}
    return Response(status_code=304, headers=znaczniki)


def bez_tresci(odpowiedz: Response, request: Request) -> Response:
    """Odpowiedź na HEAD: te same nagłówki co przy GET, bez treści.

    Trasa zbiorcza była wcześniej wyłącznie ``GET``, więc każde ``HEAD`` — a tym pytają
    sprawdzarki odsyłaczy, monitoring dostępności i pośredniki — dostawało 405 na plik,
    który normalnie się pobiera. RFC 9110 wymaga, żeby HEAD odpowiadał tym samym, co GET,
    tylko bez ciała; ``content-length`` zostaje, bo mówi o rozmiarze zasobu.
    """
    if request.method != "HEAD":
        return odpowiedz
    pusta = Response(status_code=odpowiedz.status_code)
    pusta.raw_headers = list(odpowiedz.raw_headers)
    return pusta


class ImmutableStatic(StaticFiles):
    """Zasoby z nazwą zawierającą skrót treści – buforowane bezterminowo."""

    def file_response(self, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = IMMUTABLE
        return response


class SecurityHeaders(BaseHTTPMiddleware):
    """Nagłówki bezpieczeństwa dla wszystkich odpowiedzi."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


#: Najczęstsze powody odrzucenia danych — po polsku i tak, żeby dało się poprawić.
#:
#: Reszta trafia na zdanie ogólne. Wykaz jest krótki celowo: ma pokrywać to, co klient
#: naprawdę zobaczy (za długi tekst, brak pola, zła liczba), a nie wszystkie kody pydantica.
POWODY_ODRZUCENIA: dict[str, str] = {
    "missing": "Brakuje pola „{pole}”.",
    "string_too_long": "Pole „{pole}” jest za długie.",
    "string_too_short": "Pole „{pole}” jest za krótkie.",
    "int_parsing": "Pole „{pole}” musi być liczbą.",
    "float_parsing": "Pole „{pole}” musi być liczbą.",
    "bool_parsing": "Pole „{pole}” musi być wartością tak/nie.",
    "uuid_parsing": "Pole „{pole}” musi być poprawnym identyfikatorem.",
    "value_error": "Nieprawidłowa wartość pola „{pole}”.",
    "greater_than_equal": "Wartość pola „{pole}” jest za mała.",
    "less_than_equal": "Wartość pola „{pole}” jest za duża.",
}


def _po_polsku(pole: str, rodzaj: str) -> str:
    """Zdanie o jednym odrzuconym polu — z powodem, jeżeli go znamy."""
    return POWODY_ODRZUCENIA.get(rodzaj, "Nieprawidłowa wartość pola „{pole}”.").format(pole=pole)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Tworzy aplikację z podanymi (lub środowiskowymi) ustawieniami."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.data_dir / "logs", "api")
        database = Database(settings.database_url)
        await database.create_schema()
        app.state.settings = settings
        app.state.database = database
        app.state.storage = FileStorage(settings.files_dir)
        app.state.login_throttle = auth.LoginThrottle(settings.login_attempts_per_15_min)
        app.state.goscie = auth.LimitKontGoscia(settings.goscie_na_adres)
        app.state.events = EventBus(settings.redis_url)
        app.state.voice = VoiceEngine(settings)
        if settings.voice_warm_up:
            asyncio.get_running_loop().run_in_executor(None, app.state.voice.warm_up)
        app.state.knowledge = KnowledgeBase(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_model,
            settings.cache_dir / "fastembed",
        )
        yield
        await app.state.events.close()
        await database.close()

    app = FastAPI(
        title="Danaco Nexus",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(SecurityHeaders)

    @app.exception_handler(RequestValidationError)
    async def bledne_dane(_: Request, blad: RequestValidationError) -> JSONResponse:
        """Odpowiedź 422 zrozumiała dla człowieka i po polsku.

        Domyślna odpowiedź FastAPI to **lista** obiektów z angielskim opisem
        („Input should be a valid integer…”) i nazwą pola z wnętrza schematu. Interfejs
        bierze `detail` tylko wtedy, gdy jest napisem, więc użytkownik widział z tego
        „Błąd serwera (422)” — komunikat i nieprawdziwy (to nie serwer się pomylił,
        tylko dane), i nic nie mówiący. Zostawiamy kod 422 i wykaz pól pod `pola`
        (przydaje się przy diagnozie), a `detail` mówi po polsku, czego dotyczy sprawa.
        """
        wpisy = blad.errors()
        pola = [
            ".".join(str(czesc) for czesc in wpis.get("loc", ()) if czesc not in {"body", "query", "path"})
            for wpis in wpisy
        ]
        nazwane = [nazwa for nazwa in pola if nazwa]
        rodzaje = {str(wpis.get("type", "")) for wpis in wpisy}
        if len(nazwane) == 1:
            tresc = _po_polsku(nazwane[0], str(wpisy[0].get("type", "")))
        elif nazwane and rodzaje == {"missing"}:
            # Pola, których nie przysłano, nie są „nieprawidłowe” — po prostu ich nie ma.
            # Przy jednym polu mówiliśmy to poprawnie, przy dwóch nagle nie.
            tresc = "Brakuje pól: " + ", ".join(f"„{nazwa}”" for nazwa in nazwane) + "."
        elif nazwane:
            tresc = "Nieprawidłowe wartości pól: " + ", ".join(f"„{nazwa}”" for nazwa in nazwane) + "."
        else:
            tresc = "Nieprawidłowe dane w żądaniu."
        return JSONResponse({"detail": tresc, "pola": nazwane}, status_code=422)

    for module in (auth, conversations, files, runs, voice):
        app.include_router(module.router)
    # Moduły aplikacji (nexus/api/modules/*.py) – podłączane automatycznie.
    for router in modules.routers():
        app.include_router(router)

    # `HEAD` obok `GET`, bo trasy FastAPI (`APIRoute`) nie dokładają `HEAD` samoczynnie —
    # inaczej niż zwykłe trasy Starlette. Żądanie `HEAD /api/health` nie pasowało więc do tej
    # trasy, spadało do zapasu SPA niżej (ten `HEAD` przyjmuje) i tam trafiało na gałąź
    # „wszystko pod `api/` to 404”. Efekt: `GET` zwracał 200, a `HEAD` na tym samym adresie
    # **404**. Sondy dostępności pytają zwykle metodą `HEAD`, bo nie potrzebują ciała
    # odpowiedzi, więc monitor zgłaszałby działającą usługę jako niedostępną.
    @app.api_route("/api/health", methods=["GET", "HEAD"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    static = settings.static_dir
    if (static / "index.html").is_file():
        if (static / "assets").is_dir():
            app.mount("/assets", ImmutableStatic(directory=static / "assets"), name="assets")

        @app.post("/share-target", include_in_schema=False)
        async def share_target(request: Request) -> Response:
            # Udostępnianie obsługuje service worker. Bez niego — czyli **przy pierwszym
            # uruchomieniu po instalacji**, a to właśnie wtedy ktoś najczęściej próbuje
            # udostępnić pierwszą rzecz — żądanie trafiało tutaj i wracało na „/”, gubiąc
            # po cichu wszystko, co użytkownik wysłał. Tekst da się przenieść adresem,
            # więc go przenosimy; pliki nie przeżyją przekierowania i po nie trzeba wrócić,
            # gdy service worker już stoi.
            formularz = await request.form()
            czesci = [str(formularz.get(pole) or "").strip() for pole in ("title", "text", "url")]
            tekst = "\n".join(czesc for czesc in czesci if czesc)
            cel = f"/?tekst={quote(tekst, safe='')}" if tekst else "/"
            return RedirectResponse(cel, status_code=303)

        async def _znaczniki_tresci(rodzaj: str, adres: str) -> znaczniki.Znaczniki | None | str:
            """Znaczniki pozycji portalu z bazy.

            ``None`` znaczy „pozycji nie ma albo jest szkicem” (wtedy adres zasługuje na 404),
            a ``"nieznane"`` — „baza nie odpowiedziała”. Bez tego rozróżnienia chwilowa awaria
            bazy kazałaby wyszukiwarkom uznać opublikowany wpis za usunięty.
            """
            from nexus.portal import repozytorium, tresc
            from nexus.portal.repozytorium import BrakTresci

            baza: Database = app.state.database
            try:
                async with baza.session() as session:
                    record = await repozytorium.pobierz(session, rodzaj, tresc.slug(adres))
            except BrakTresci:
                return None
            except Exception:
                return "nieznane"
            seo = record.seo if isinstance(record.seo, dict) else {}
            return znaczniki.Znaczniki(
                tytul=str(seo.get("meta_title") or record.title),
                opis=str(seo.get("meta_description") or record.excerpt or "")[:300],
                sciezka=f"/portal/{ 'blog' if rodzaj == 'blog' else rodzaj }/{record.slug}"
                if rodzaj != "strona"
                else f"/portal/s/{record.slug}",
                obraz=str(seo.get("og_image") or "/og.png"),
                indeksuj=not seo.get("noindex"),
            )

        def _powloka_404(plik: Path) -> Response:
            """Powłoka aplikacji z kodem 404 — klient dorysuje „nie znaleziono”."""
            try:
                dokument = plik.read_text(encoding="utf-8")
            except OSError:
                return Response(status_code=404)
            return HTMLResponse(dokument, status_code=404, headers={"Cache-Control": "no-cache"})

        async def _strona_spa(
            plik: Path, sciezka: str, request: Request, ustawienia: Settings
        ) -> Response:
            """``index.html`` ze znacznikami adresu — dla robotów, które nie mają JavaScriptu.

            Podmiana dotyczy wyłącznie adresów publicznych. Pozostałe idą bez zmian, więc
            zachowują żądania warunkowe (304) i nie kosztują ani jednego zapytania do bazy.
            """
            adres = "/" + sciezka.strip("/")
            # Strona portalu, której nie ma w mapie witryny, jest po prostu nieistniejąca —
            # kod 200 z powłoką trzymałby taki adres w indeksie wyszukiwarki.
            if not znaczniki.strona_portalu(adres):
                return _powloka_404(plik)
            znaleziony: znaczniki.Znaczniki | None | str = znaczniki.STALE.get(adres)
            brak_pozycji = False
            if znaleziony is None and (pozycja := znaczniki.sciezka_tresci(adres)) is not None:
                znaleziony = await _znaczniki_tresci(*pozycja)
                brak_pozycji = znaleziony is None
            if brak_pozycji:
                # Adres wpisu, którego nie ma: powłoka aplikacji, ale ze statusem 404.
                # Kod 200 na nieistniejącym wpisie to „miękkie 404” — wyszukiwarka trzyma
                # taki adres w indeksie i pokazuje go zamiast działającej strony.
                return _powloka_404(plik)
            if not isinstance(znaleziony, znaczniki.Znaczniki):
                return plik_z_warunkiem(plik, "no-cache", request)
            try:
                dokument = plik.read_text(encoding="utf-8")
            except OSError:
                return plik_z_warunkiem(plik, "no-cache", request)
            return HTMLResponse(
                znaczniki.zastosuj(dokument, znaleziony, ustawienia.public_url),
                headers={"Cache-Control": "no-cache"},
            )

        @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
        async def spa(path: str, request: Request) -> Response:
            if path.startswith("api/"):
                return JSONResponse({"detail": "Nie znaleziono."}, status_code=404)
            candidate = (static / path).resolve()
            # Brakujący **plik** to 404, nie strona aplikacji.
            #
            # Zapas jednostronicowy odpowiadał dotąd stroną i kodem **200** na każdy adres,
            # także na `/ruch/stany/ilustracja.webm`, którego nie ma. Przeglądarka dostawała
            # wtedy HTML w miejsce nagrania (i po cichu brała następne źródło), pamięci
            # podręczne zapisywały „sukces”, a literówka w ścieżce zasobu nie odzywała się
            # niczym. Adresy aplikacji nie mają kropki w ostatnim członie (`/c/<uuid>`,
            # `/m/<id>`, `/portal/…`), a adresy plików mają — i po tym je rozróżniamy.
            # Strony użytkownika spod `/s/<adres>/` obsługuje wcześniejszy router, więc
            # ta gałąź ich nie dotyczy.
            if path and "." in path.rsplit("/", 1)[-1] and not candidate.is_file():
                return JSONResponse({"detail": "Nie znaleziono pliku."}, status_code=404)
            if path and candidate.is_file() and candidate.is_relative_to(static.resolve()):
                cache = "no-cache" if candidate.name in NO_CACHE_FILES else "public, max-age=86400"
                if candidate.name.startswith("workbox-"):
                    cache = IMMUTABLE
                elif candidate.name not in NO_CACHE_FILES and candidate.suffix in MEDIA_SUFFIXES:
                    cache = MEDIA_CACHE
                return bez_tresci(plik_z_warunkiem(candidate, cache, request), request)
            return bez_tresci(await _strona_spa(static / "index.html", path, request, settings), request)

    return app


app = create_app()
