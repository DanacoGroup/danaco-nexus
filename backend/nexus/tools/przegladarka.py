"""Narzędzia przeglądarki: agent otwiera stronę, klika i wypełnia pola jak człowiek.

Dotąd sieć była dla agenta jednostronna: ``web_search`` znajdował adresy, ``web_fetch_page``
czytał treść po HTTP, ``web_screenshot`` robił jednorazowy zrzut. Wszystko, co zaczyna się
od kliknięcia — rozwijana lista, zakładka, wyszukiwarka wewnątrz serwisu, formularz, koszyk,
strona doczytywana skryptem — było poza zasięgiem. Tutaj agent dostaje jedno okno na czas
zadania i pracuje w nim krok po kroku.

Każde działanie zwraca ten sam obraz strony: adres, tytuł, tekst i wykaz elementów, w które
da się kliknąć albo coś wpisać. Dzięki temu model wskazuje element jego nazwą („Zaloguj się”,
„Szukaj”), a nie wymyślonym selektorem.

Treść strony to dane, nie polecenia — instrukcji znalezionych na stronie nie wykonujemy.
Adresy przechodzą przez tę samą ochronę przed SSRF co odczyt po HTTP, więc sieć wewnętrzna
serwera pozostaje zamknięta.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from PIL import Image
from pydantic import Field

from nexus.research.web import check_url
from nexus.tools.base import (
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tworczy.przegladarka import BladPrzegladarki, przegladarka

PODGLAD = 1280
# Wykaz elementów bywa długi; model potrzebuje z niego orientacji, nie pełnego drzewa.
ELEMENTY_W_WYNIKU = 40

ZRZUT_POLE = Field(
    False,
    description="Dołącz zrzut widocznego okna. Włączaj, gdy liczy się wygląd, nie sama treść.",
)


def _wynik(ctx: ToolContext, odpowiedz: dict[str, Any], opis: str, zrzut: str) -> ToolResult:
    """Wspólna postać wyniku: stan strony dla modelu plus ewentualny zrzut okna."""
    elementy = odpowiedz.get("elementy") or []
    dane = {
        "adres": odpowiedz.get("adres"),
        "tytul": odpowiedz.get("tytul"),
        "tekst": odpowiedz.get("tekst"),
        "elementy": elementy[:ELEMENTY_W_WYNIKU],
        "elementow_lacznie": len(elementy),
    }
    naglowek = f"{opis}: {odpowiedz.get('tytul') or odpowiedz.get('adres')}"
    plik = Path(zrzut) if zrzut else None
    if plik is None or not plik.is_file():
        return ToolResult(dane, naglowek)
    with Image.open(plik) as obraz:
        podglad = image_preview(obraz, PODGLAD)
    # Zrzut idzie do rozmowy jako podgląd; pliku wynikowego nie robimy — użytkownik ogląda
    # stronę, a nie zbiera obrazki z każdego kliknięcia agenta.
    return ToolResult(dane, naglowek, images=[podglad])


def _wykonaj(ctx: ToolContext, polecenie: dict[str, Any], opis: str, zrzut: bool) -> ToolResult:
    sciezka = str(ctx.output_path("widok-strony.png")) if zrzut else ""
    if sciezka:
        polecenie["zrzut"] = sciezka
    ctx.check_cancelled()
    ctx.progress(opis)
    try:
        odpowiedz = przegladarka().polecenie(polecenie)
    except BladPrzegladarki as blad:
        raise ToolError(str(blad)) from blad
    return _wynik(ctx, odpowiedz, opis, sciezka)


class OtworzInput(ToolInput):
    adres: str = Field(description="Pełny adres https:// strony do otwarcia.", max_length=2000)
    urzadzenie: Literal["telefon", "tablet", "komputer"] = Field(
        "komputer", description="Szerokość okna: telefon 390 px, tablet 820 px, komputer 1440 px."
    )
    zrzut: bool = ZRZUT_POLE


@registry.register(
    "browser_open",
    """Otwiera stronę w przeglądarce i zostawia ją otwartą — kolejne wywołania browser_click,
browser_type, browser_scroll i browser_back działają na tej samej karcie. Zwraca tytuł,
tekst strony i wykaz elementów, w które da się kliknąć albo coś wpisać. Używaj, gdy sama
treść nie wystarcza: strona doczytuje się skryptem, wymaga kliknięcia, przejścia zakładki
albo wypełnienia formularza. Do samego odczytu artykułu wystarczy web_fetch_page, a do
oceny wyglądu strony użytkownika — web_screenshot.""",
    OtworzInput,
)
def browser_open(ctx: ToolContext, args: OtworzInput) -> ToolResult:
    try:
        adres = check_url(args.adres)
    except Exception as blad:  # noqa: BLE001 - komunikat idzie do modelu
        raise ToolError(f"Nie mogę otworzyć tego adresu: {blad}") from blad
    return _wykonaj(
        ctx,
        {"akcja": "otworz", "adres": adres, "urzadzenie": args.urzadzenie},
        "Otwieram stronę",
        args.zrzut,
    )


class KlikInput(ToolInput):
    co: str = Field(
        description="Napis na elemencie albo jego etykieta, np. „Zaloguj się”, „Cennik”. "
        "Nazwy bierz z pola `elementy` poprzedniego wyniku. Selektor CSS podaj jako 'css=…'.",
        max_length=200,
    )
    zrzut: bool = ZRZUT_POLE


@registry.register(
    "browser_click",
    "Klika element na otwartej stronie (przycisk, odsyłacz, zakładkę) i zwraca nowy stan strony.",
    KlikInput,
)
def browser_click(ctx: ToolContext, args: KlikInput) -> ToolResult:
    return _wykonaj(ctx, {"akcja": "klik", "co": args.co}, f"Klikam „{args.co}”", args.zrzut)


class WpiszInput(ToolInput):
    pole: str = Field(
        description="Etykieta albo podpowiedź pola, np. „Szukaj”, „Adres e-mail”.", max_length=200
    )
    tekst: str = Field(description="Treść do wpisania.", max_length=2000)
    zatwierdz: bool = Field(True, description="Naciśnij Enter po wpisaniu (wyszukiwarki, formularze).")
    zrzut: bool = ZRZUT_POLE


@registry.register(
    "browser_type",
    """Wpisuje tekst w pole na otwartej stronie i (domyślnie) zatwierdza Enterem.
Nie wpisuj cudzych danych logowania ani danych płatniczych.""",
    WpiszInput,
)
def browser_type(ctx: ToolContext, args: WpiszInput) -> ToolResult:
    return _wykonaj(
        ctx,
        {"akcja": "wpisz", "pole": args.pole, "tekst": args.tekst, "zatwierdz": args.zatwierdz},
        f"Wpisuję w pole „{args.pole}”",
        args.zrzut,
    )


class PrzewinInput(ToolInput):
    ile: int = Field(800, ge=-20000, le=20000, description="Ile pikseli w dół (ujemnie = w górę).")
    zrzut: bool = ZRZUT_POLE


@registry.register(
    "browser_scroll",
    "Przewija otwartą stronę i zwraca treść, która po przewinięciu weszła w pole widzenia.",
    PrzewinInput,
)
def browser_scroll(ctx: ToolContext, args: PrzewinInput) -> ToolResult:
    return _wykonaj(ctx, {"akcja": "przewin", "ile": args.ile}, "Przewijam stronę", args.zrzut)


class WsteczInput(ToolInput):
    zrzut: bool = ZRZUT_POLE


@registry.register("browser_back", "Wraca na poprzednią stronę w otwartej karcie.", WsteczInput)
def browser_back(ctx: ToolContext, args: WsteczInput) -> ToolResult:
    return _wykonaj(ctx, {"akcja": "wstecz"}, "Wracam na poprzednią stronę", args.zrzut)


__all__ = ["browser_back", "browser_click", "browser_open", "browser_scroll", "browser_type"]
