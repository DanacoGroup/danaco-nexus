"""Kroje strony z serwera zamiast z Google.

Gotowe szablony wczytują kroje z `fonts.googleapis.com`. To nie jest sprawa samego wyglądu:
każde wejście na stronę wysyła adres IP odwiedzającego do Google, więc strona firmowa musi
to wpisać do informacji o przetwarzaniu — a bez internetu wygląd i tak się rozjeżdża.
Serwer ma te same rodziny u siebie (2050 pozycji, repozytorium Google Fonts) i program
`danaco-kroj`, który wycina z nich podzbiór z polskimi znakami i składa regułę `@font-face`.

Narzędzie robi całą drogę: znajduje odwołania do Google w szkicu strony, wkłada kroje do
szkicu, dopisuje własny arkusz i podmienia odwołania.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from pydantic import Field

from nexus.tools.base import ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tworczy.strony import SiteError, site_store

PROGRAM = "/danaco/programy/bin/danaco-kroj"
#: Katalog krojów wewnątrz szkicu strony.
KATALOG = "kroje"
ARKUSZ = f"{KATALOG}/kroje.css"
#: Wycięcie podzbioru i kompresja jednej rodziny trwa kilkanaście sekund.
CZAS_KROJU_S = 240
MAKS_RODZIN = 8

#: Odsyłacz do arkusza krojów Google — stąd bierzemy nazwy rodzin.
LINK_GOOGLE = re.compile(
    r"""<link\b[^>]*\bhref\s*=\s*["'](https://fonts\.googleapis\.com/[^"']+)["'][^>]*>""", re.I
)
#: ``preconnect``/``dns-prefetch`` do serwerów Google — po podmianie nie mają po co zostawać.
LACZE_GOOGLE = re.compile(
    r"""<link\b[^>]*\bhref\s*=\s*["']https://fonts\.(?:googleapis|gstatic)\.com[^"']*["'][^>]*>""",
    re.I,
)
#: Import arkusza Google w CSS.
IMPORT_GOOGLE = re.compile(
    r"""@import\s+(?:url\()?["']?https://fonts\.googleapis\.com/[^"')]+["']?\)?\s*;""", re.I
)
#: Nazwa rodziny w adresie. Kończy ją wszystko, co nie należy do nazwy: druga rodzina
#: (``&``), lista wag (``:``) oraz domknięcie zapisu w CSS (``')``, ``;``, cudzysłów).
RODZINA = re.compile(r"""family=([^&:;'")\s]+)""", re.I)


def _rodziny(tresc: str) -> list[str]:
    """Nazwy rodzin wypisane w odsyłaczach do Google, w kolejności wystąpienia."""
    wynik: list[str] = []
    for adres in [m.group(1) for m in LINK_GOOGLE.finditer(tresc)] + IMPORT_GOOGLE.findall(tresc):
        for nazwa in RODZINA.findall(adres):
            czysta = unquote(nazwa).replace("+", " ").strip()
            if czysta and czysta not in wynik:
                wynik.append(czysta)
    return wynik


def _pliki_tekstowe(store: Any, site: str) -> list[str]:
    return [
        pozycja["path"]
        for pozycja in store.list_files(site)
        if pozycja["path"].lower().endswith((".html", ".htm", ".css"))
    ]


class KrojeInput(ToolInput):
    site: str = Field(
        description="Adres strony użytkownika, której kroje przenosimy na serwer.", max_length=80
    )
    rodziny: list[str] = Field(
        default_factory=list,
        max_length=MAKS_RODZIN * 2,
        description=(
            "Rodziny do wstawienia (np. ['Inter', 'Lora']). Pusto = te, które strona wczytuje "
            "z Google — narzędzie znajdzie je samo."
        ),
    )


@registry.register(
    "site_fonts_local",
    """Przenosi kroje strony z serwerów Google na serwer Danaco: wycina z lokalnego
repozytorium podzbiór z polskimi znakami, wkłada pliki .woff2 do szkicu strony, dopisuje
arkusz `kroje/kroje.css` i podmienia odsyłacze do fonts.googleapis.com na własny arkusz
(usuwając przy okazji `preconnect` do Google). Użyj zawsze, gdy site_from_template albo
site_from_kit zgłosi zasoby z serwerów Google: bez tego każde wejście na stronę wysyła
adres IP odwiedzającego do Google i strona nie działa bez internetu. Rodziny możesz podać
wprost, ale zwykle nie trzeba — narzędzie czyta je z odsyłaczy w szkicu.""",
    KrojeInput,
)
def site_fonts_local(ctx: ToolContext, args: KrojeInput) -> ToolResult:
    if not Path(PROGRAM).exists():
        raise ToolError("Program do przygotowania krojów nie jest zainstalowany na tym serwerze.")
    store = site_store(ctx.settings, ctx.owner_id)
    if not store.exists(args.site):
        raise ToolError(f"Nie ma strony „{args.site}”. Najpierw załóż ją w module Strony.")

    sciezki = _pliki_tekstowe(store, args.site)
    tresci = {sciezka: store.read_text(args.site, sciezka) for sciezka in sciezki}
    rodziny = [nazwa.strip() for nazwa in args.rodziny if nazwa.strip()]
    if not rodziny:
        for tresc in tresci.values():
            for nazwa in _rodziny(tresc):
                if nazwa not in rodziny:
                    rodziny.append(nazwa)
    if not rodziny:
        raise ToolError(
            f"Strona „{args.site}” nie wczytuje krojów z Google, a rodziny nie zostały podane. "
            "Jeżeli chcesz wstawić krój mimo to, wymień go w polu `rodziny`."
        )
    if len(rodziny) > MAKS_RODZIN:
        raise ToolError(
            f"Strona używa {len(rodziny)} rodzin krojów (limit {MAKS_RODZIN}). Tyle krojów na "
            "jednej stronie i tak jest usterką projektu — wybierz najwyżej trzy i podaj je "
            "w polu `rodziny`."
        )

    katalog = ctx.output_path("kroje").parent
    arkusz: list[str] = []
    wstawione: list[str] = []
    pominiete: list[str] = []
    for rodzina in rodziny:
        ctx.check_cancelled()
        ctx.progress(f"Przygotowuję krój {rodzina}…")
        cel = katalog / rodzina.lower().replace(" ", "-")
        shutil.rmtree(cel, ignore_errors=True)
        cel.mkdir(parents=True, exist_ok=True)
        try:
            ctx.run_command(
                [PROGRAM, "web", rodzina, str(cel), "--latin-ext", "--url", KATALOG],
                timeout=CZAS_KROJU_S,
            )
        except ToolError:
            # Rodziny spoza repozytorium (kroje firmowe, płatne) po prostu zostają u siebie.
            pominiete.append(rodzina)
            continue
        for plik in sorted(cel.iterdir()):
            try:
                if plik.suffix == ".woff2":
                    store.write_bytes(args.site, f"{KATALOG}/{plik.name}", plik.read_bytes())
                elif plik.suffix == ".css":
                    arkusz.append(plik.read_text(encoding="utf-8").strip())
                elif plik.suffix == ".txt":
                    # Licencja kroju jedzie razem z plikami — OFL wymaga jej dołączenia.
                    store.write_text(
                        args.site, f"{KATALOG}/{plik.name}", plik.read_text(encoding="utf-8")
                    )
            except SiteError as blad:
                # Szkic strony przyjmuje wyłącznie nazwy z liter a–z, cyfr i „._-”. Rodzina
                # z nietypowym znakiem w nazwie pliku nie może przekreślić całej operacji.
                raise ToolError(
                    f"Krój {rodzina} ma plik o nazwie, której szkic strony nie przyjmie "
                    f"({plik.name}): {blad}"
                ) from blad
        wstawione.append(rodzina)

    if not wstawione:
        raise ToolError(
            "Żadnej z tych rodzin nie ma w repozytorium krojów serwera: "
            f"{', '.join(pominiete)}. Sprawdź pisownię albo wgraj plik kroju "
            "narzędziem site_import_file."
        )

    naglowek = (
        "/* Kroje z repozytorium serwera Danaco, podzbiór Latin + Latin Extended (polskie\n"
        "   znaki). Zastępują odsyłacze do fonts.googleapis.com: strona działa bez internetu,\n"
        "   a adres IP odwiedzającego nie wychodzi do Google. Licencje leżą obok. */\n"
    )
    store.write_text(args.site, ARKUSZ, naglowek + "\n\n".join(arkusz) + "\n")

    podmienione = 0
    for sciezka, tresc in tresci.items():
        nowa = tresc
        if sciezka.lower().endswith(".css"):
            nowa = IMPORT_GOOGLE.sub("", nowa)
        else:
            # Odsyłacz liczy się od miejsca podstrony: arkusz leży w korzeniu strony, więc
            # „cennik/index.html” musi wskazać go przez „../”. Bez tego podstrony w katalogach
            # szukałyby krojów u siebie i zostawały bez nich.
            przedrostek = "../" * sciezka.count("/")
            odsylacz = f'<link rel="stylesheet" href="{przedrostek}{ARKUSZ}">'
            # Pierwszy odsyłacz do Google zamieniamy na własny arkusz, resztę (preconnect,
            # dns-prefetch, kolejne rodziny) usuwamy — jeden arkusz wystarczy.
            if LINK_GOOGLE.search(nowa):
                # Domyślny argument wiąże wartość z tego obrotu pętli; przekazanie
                # odsyłacza jako wzorca zamiany interpretowałoby w nim odwołania „\g”.
                nowa = LINK_GOOGLE.sub(lambda _, cel=odsylacz: cel, nowa, count=1)
            nowa = LACZE_GOOGLE.sub("", nowa)
        if nowa != tresc:
            store.write_text(args.site, sciezka, nowa)
            podmienione += 1

    dane: dict[str, Any] = {
        "site": args.site,
        "rodziny": wstawione,
        "arkusz": ARKUSZ,
        "plikow_podmienionych": podmienione,
    }
    if pominiete:
        dane["poza_repozytorium"] = pominiete
    komunikat = (
        f"Kroje strony „{args.site}” są na serwerze: {', '.join(wstawione)} "
        f"(podmieniono odwołania w {podmienione} plikach)."
    )
    if pominiete:
        komunikat += f" Poza repozytorium serwera: {', '.join(pominiete)} — zostały bez zmian."
    return ToolResult(dane, komunikat)


__all__ = ["site_fonts_local"]
