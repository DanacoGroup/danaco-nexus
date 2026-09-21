"""Zasoby z cudzych serwerów ściągnięte do strony użytkownika.

Gotowe szablony wczytują skrypty, arkusze i zdjęcia z CDN-ów — przegląd kolekcji z 20
września 2026: 48 z 81 zbudowanych szablonów. Każde takie odwołanie ma dwa skutki: strona
nie działa bez internetu, a przeglądarka odwiedzającego łączy się z cudzym serwerem, więc
jego adres IP trafia do jego właściciela (patrz rejestr czynności, CZ-15).

Narzędzie przechodzi szkic strony, pobiera te pliki na serwer i podmienia odwołania na
własne. Kroje Google mają własną drogę (``site_fonts_local``) — tam zamiast pobierania
wycinamy podzbiór z repozytorium serwera.

Bezpieczeństwo: adresy przechodzą przez ``check_url`` (tylko http/https, tylko publiczne
adresy IP — bez sieci lokalnej), pobieranie ma limit rozmiaru i czasu, a zapis idzie przez
``SiteStore``, który dopuszcza wyłącznie znane typy plików.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from pydantic import Field

from nexus.research.web import BlockedAddressError, FetchError, check_url, safe_client
from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tworczy.strony import ALLOWED_SUFFIXES, SiteError, site_store

#: Katalog w szkicu, do którego trafiają pobrane pliki.
KATALOG = "zewnetrzne"
#: Ile najwyżej plików pobieramy w jednym wywołaniu.
MAKS_PLIKOW = 60
#: Limit jednego pliku. Biblioteki z CDN-ów mieszczą się w tym z zapasem.
MAKS_BAJTOW = 8 * 1024 * 1024
CZAS_POBRANIA_S = 25

#: Adres zasobu wczytywanego przez stronę. Liczy się element, nie sam atrybut: ``href``
#: na ``<link>`` to arkusz do pobrania, ``href`` na ``<a>`` to odsyłacz w treści — tego
#: drugiego nie wolno ściągać ani podmieniać, bo to cudza strona, a nie zasób.
ADRES_W_ATRYBUCIE = re.compile(
    r"""<(?:script|img|source|iframe|video|audio)\b[^>]*?\s(?:src|poster|data-src)\s*=\s*["']"""
    r"""(https?://[^"']+)"""
    r"""|<link\b[^>]*?\shref\s*=\s*["'](https?://[^"']+)""",
    re.I,
)
ADRES_W_STYLU = re.compile(r"""url\(\s*["']?(https?://[^"')]+)""", re.I)
#: Serwery obsługiwane osobno: kroje bierze site_fonts_local z repozytorium serwera.
KROJE_GOOGLE = ("fonts.googleapis.com", "fonts.gstatic.com")


def _adresy(tresc: str) -> list[str]:
    """Adresy zasobów wczytywanych z sieci, w kolejności wystąpienia, bez powtórzeń."""
    wynik: list[str] = []
    z_atrybutow = [
        dopasowanie.group(1) or dopasowanie.group(2)
        for dopasowanie in ADRES_W_ATRYBUCIE.finditer(tresc)
    ]
    for adres in z_atrybutow + ADRES_W_STYLU.findall(tresc):
        czysty = adres.strip().rstrip("\\")
        host = urlsplit(czysty).hostname or ""
        if host.endswith(KROJE_GOOGLE):
            continue
        if czysty not in wynik:
            wynik.append(czysty)
    return wynik


def _nazwa_lokalna(adres: str) -> str:
    """Ścieżka w szkicu dla pobranego pliku: ``zewnetrzne/<serwer>/<nazwa>``.

    Nazwa bierze się z adresu, ale przechodzi przez sito dozwolonych znaków — szkic strony
    nie przyjmie pliku z zapytaniem, ukośnikiem wstecznym ani polską literą w nazwie.
    """
    czesci = urlsplit(adres)
    host = re.sub(r"[^a-z0-9.-]", "-", (czesci.hostname or "serwer").lower())
    nazwa = unquote(PurePosixPath(czesci.path).name) or "plik"
    nazwa = re.sub(r"[^A-Za-z0-9._-]", "-", nazwa).strip("-._") or "plik"
    if "." not in nazwa:
        nazwa = f"{nazwa}.txt"
    return f"{KATALOG}/{host}/{nazwa}"


def _pobierz(adres: str) -> bytes:
    """Zawartość pliku spod adresu; błąd zrozumiały dla użytkownika zamiast wyjątku httpx."""
    try:
        sprawdzony = check_url(adres)
    except BlockedAddressError as blad:
        raise ToolError(str(blad)) from blad
    with safe_client(timeout=CZAS_POBRANIA_S) as klient:
        try:
            odpowiedz = klient.get(sprawdzony)
        except Exception as blad:  # noqa: BLE001 — httpx ma wiele klas błędów sieci
            raise ToolError(f"Nie udało się pobrać {adres[:120]}: {blad}") from blad
    if odpowiedz.status_code >= 400:
        raise ToolError(f"Serwer odpowiedział {odpowiedz.status_code} na {adres[:120]}.")
    dane = odpowiedz.content
    if len(dane) > MAKS_BAJTOW:
        raise ToolError(
            f"Plik spod {adres[:80]} ma {len(dane) // 1024} kB (limit {MAKS_BAJTOW // 1024} kB)."
        )
    return dane


class ZasobyInput(ToolInput):
    site: str = Field(
        description="Adres strony użytkownika, której zasoby ściągamy na serwer.", max_length=80
    )
    limit: int = Field(
        default=MAKS_PLIKOW,
        ge=1,
        le=MAKS_PLIKOW,
        description="Ile plików najwyżej pobrać w tym wywołaniu.",
    )


@registry.register(
    "site_vendor_assets",
    """Ściąga do strony użytkownika pliki, które wczytuje ona z cudzych serwerów (skrypty
i arkusze z CDN-ów, zdjęcia ze stocków), i podmienia odwołania na własne. Po tym strona
działa bez internetu, a przeglądarka odwiedzającego nie łączy się z obcym serwerem — co
przy stronie firmowej trzeba by wpisać do informacji o przetwarzaniu. Użyj, gdy
site_from_template albo site_from_kit zgłosi w polu `uwagi` zasoby z sieci. Kroje Google
pomija: te przenosi site_fonts_local z repozytorium serwera, bez pobierania.""",
    ZasobyInput,
)
def site_vendor_assets(ctx: ToolContext, args: ZasobyInput) -> ToolResult:
    store = site_store(ctx.settings, ctx.owner_id)
    if not store.exists(args.site):
        raise ToolError(f"Nie ma strony „{args.site}”. Najpierw załóż ją w module Strony.")

    sciezki = [
        pozycja["path"]
        for pozycja in store.list_files(args.site)
        if pozycja["path"].lower().endswith((".html", ".htm", ".css"))
    ]
    tresci = {sciezka: store.read_text(args.site, sciezka) for sciezka in sciezki}
    kolejka: list[str] = []
    for tresc in tresci.values():
        for adres in _adresy(tresc):
            if adres not in kolejka:
                kolejka.append(adres)
    if not kolejka:
        raise ToolError(
            f"Strona „{args.site}” nie wczytuje niczego z cudzych serwerów (poza krojami, "
            "którymi zajmuje się site_fonts_local)."
        )

    mapa: dict[str, str] = {}
    pominiete: list[dict[str, str]] = []
    for adres in kolejka[: args.limit]:
        ctx.check_cancelled()
        cel = _nazwa_lokalna(adres)
        if PurePosixPath(cel).suffix.lower() not in ALLOWED_SUFFIXES:
            pominiete.append({"adres": adres, "powod": "typ pliku, którego strona nie przyjmuje"})
            continue
        ctx.progress(f"Pobieram {adres[:90]}")
        try:
            dane = _pobierz(adres)
            store.write_bytes(args.site, cel, dane)
        except (ToolError, SiteError, FetchError) as blad:
            pominiete.append({"adres": adres, "powod": str(blad)[:160]})
            continue
        mapa[adres] = cel

    if not mapa:
        powody = "; ".join(f"{p['adres'][:60]} — {p['powod']}" for p in pominiete[:3])
        raise ToolError(f"Nie udało się pobrać żadnego z tych plików. {powody}")

    podmienione = 0
    for sciezka, tresc in tresci.items():
        przedrostek = "../" * sciezka.count("/")
        nowa = tresc
        for adres, cel in mapa.items():
            nowa = nowa.replace(adres, f"{przedrostek}{cel}")
        if nowa != tresc:
            store.write_text(args.site, sciezka, nowa)
            podmienione += 1

    dane_wyniku: dict[str, Any] = {
        "site": args.site,
        "pobranych": len(mapa),
        "plikow_podmienionych": podmienione,
        "katalog": KATALOG,
        "zostalo_w_sieci": max(0, len(kolejka) - args.limit),
    }
    if pominiete:
        dane_wyniku["pominiete"] = pominiete[:10]
    komunikat = (
        f"Strona „{args.site}”: pobrano {len(mapa)} plików z cudzych serwerów, "
        f"podmieniono odwołania w {podmienione} plikach."
    )
    if pominiete:
        komunikat += f" Nie udało się przy {len(pominiete)} — patrz „pominiete”."
    if dane_wyniku["zostalo_w_sieci"]:
        komunikat += f" Poza limitem zostało {dane_wyniku['zostalo_w_sieci']} — wywołaj jeszcze raz."
    return ToolResult(dane_wyniku, komunikat)


__all__ = ["site_vendor_assets"]
