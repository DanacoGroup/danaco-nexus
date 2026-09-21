"""Znaczniki strony wstawiane po stronie serwera (podgląd odsyłacza, roboty).

Aplikacja i portal są jednostronicowe: przeglądarka podmienia tytuł, opis i Open Graph
w locie (``frontend/src/seo.ts``). Robot Facebooka, LinkedIna, Slacka czy WhatsAppa nie
uruchamia JavaScriptu — widzi wyłącznie to, co przyszło w HTML-u. Bez tego modułu każdy
odsyłacz do bloga, artykułu bazy wiedzy czy cennika pokazywał ten sam tytuł i opis
z ``index.html``.

Moduł podmienia znaczniki w serwowanym ``index.html`` dla adresów publicznych: stałych
(strona produktu, cennik, kontakt) i treści portalu (wpis bloga, artykuł, dokumentacja),
dla których dane biorą się z bazy. Ekrany za logowaniem zostają z „noindex”.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

#: Znaczniki podmieniane w dokumencie. Kolejność bez znaczenia — każdy ma własne wyrażenie.
TYTUL = re.compile(r"<title>.*?</title>", re.I | re.S)
META_NAZWA = "name"
META_WLASCIWOSC = "property"


@dataclass(frozen=True, slots=True)
class Znaczniki:
    """Komplet znaczników jednej strony."""

    tytul: str
    opis: str
    sciezka: str
    obraz: str = "/og.png"
    indeksuj: bool = True


#: Adresy publiczne o stałej treści. Odpowiednik ``PUBLICZNE`` z ``frontend/src/seo.ts``;
#: dwa źródła, bo robot dostaje HTML z serwera, a przeglądarka podmienia znaczniki sama.
#: Zgodność pilnuje test ``test_znaczniki``.
STALE: dict[str, Znaczniki] = {
    "/start": Znaczniki(
        "Danaco Nexus — osobisty asystent AI do pracy i domu",
        "Powiedz, co ma powstać. Nexus dobiera narzędzia, wykonuje pracę i oddaje gotowy plik: "
        "dokumenty, zdjęcia, nagrania, strony i poczta w jednym miejscu.",
        "/start",
    ),
    "/wyprobuj": Znaczniki(
        "Wypróbuj Danaco Nexus bez rejestracji",
        "Otwiera się pełna aplikacja na koncie próbnym — bez karty, bez zakładania konta. "
        "Rozmowy i pliki znikają razem z kontem próbnym.",
        "/wyprobuj",
    ),
    "/portal": Znaczniki(
        "Danaco Nexus — asystent AI dla firm i osób prywatnych",
        "Czym jest Danaco Nexus, co potrafi i ile kosztuje. Blog, baza wiedzy i dokumentacja.",
        "/portal",
    ),
    "/portal/cennik": Znaczniki(
        "Cennik Danaco Nexus — plany Osobisty, Pro i Grupa",
        "Siedem dni próbnych, potem plan miesięczny. Ceny, zakres pracy i to, co obejmuje każdy plan.",
        "/portal/cennik",
    ),
    "/portal/funkcje": Znaczniki(
        "Funkcje Danaco Nexus — co asystent robi na co dzień",
        "Dokumenty, zdjęcia, nagrania, poczta, kalendarz, badania, strony i kod — jedna rozmowa "
        "zamiast kilkunastu programów.",
        "/portal/funkcje",
    ),
    "/portal/kontakt": Znaczniki(
        "Kontakt — Danaco Nexus",
        "Napisz do nas: pytania o produkt, wdrożenia i współpracę.",
        "/portal/kontakt",
    ),
    # Poniższe strony miały znaczniki wyłącznie z przeglądarki (`usePozycjonowanie`), więc
    # odsyłacz wrzucony na komunikator albo portal społecznościowy pokazywał opis całej
    # witryny zamiast opisu strony — te serwisy nie uruchamiają skryptów. Treść idzie za
    # komponentami z `frontend/src/portal/strony/`.
    "/portal/oferta": Znaczniki(
        "Oferta Danaco Nexus — osiem rodzajów pracy",
        "Osiem rodzajów pracy, które Nexus przejmuje w całości: od skanu faktury, przez skrzynkę "
        "i kalendarz, po raport z przypisami i stronę opublikowaną pod adresem Nexusa.",
        "/portal/oferta",
    ),
    "/portal/zastosowania": Znaczniki(
        "Zastosowania Danaco Nexus — osiem sytuacji z życia i pracy",
        "Osiem sytuacji z życia i z pracy, w których wystarczy opisać zadanie zdaniem. Przy każdej "
        "widać, co dokładnie napisać, co wraca z powrotem i które narzędzia wykonują pracę.",
        "/portal/zastosowania",
    ),
    "/portal/narzedzia": Znaczniki(
        "Narzędzia agenta Danaco Nexus — pełny wykaz",
        "Wykaz narzędzi, po które Nexus sięga w Twoim imieniu — od poprawy zdjęcia i rozpoznania "
        "tekstu ze skanu po publikację strony i pracę na Twoim komputerze.",
        "/portal/narzedzia",
    ),
    "/portal/dokumentacja": Znaczniki(
        "Dokumentacja Danaco Nexus — jak zacząć i jak pracować",
        "Jak uruchomić Nexusa, podłączyć pocztę, kalendarz i chmurę oraz pracować z każdym modułem.",
        "/portal/dokumentacja",
    ),
    "/portal/blog": Znaczniki(
        "Blog Danaco Nexus — praca z asystentem i zmiany w produkcie",
        "Materiały o pracy z Danaco Nexus i zmianach w produkcie: co doszło, co się zmieniło "
        "i jak tego użyć.",
        "/portal/blog",
    ),
    "/portal/wiedza": Znaczniki(
        "Centrum wiedzy Danaco Nexus — poradniki i odpowiedzi",
        "Opracowania, poradniki i odpowiedzi na częste pytania — od pierwszego uruchomienia "
        "po pracę z każdym modułem.",
        "/portal/wiedza",
    ),
    "/portal/prywatnosc": Znaczniki(
        "Polityka prywatności — Danaco Nexus",
        "Jakie dane zbiera Danaco Nexus, po co, na jakiej podstawie, jak długo je trzyma "
        "i co trafia do modelu językowego.",
        "/portal/prywatnosc",
    ),
    "/portal/regulamin": Znaczniki(
        "Regulamin — Danaco Nexus",
        "Zasady korzystania z Danaco Nexus: zakres usług, konto, plany i płatności, reklamacje "
        "i odpowiedzialność.",
        "/portal/regulamin",
    ),
    "/portal/cookies": Znaczniki(
        "Pliki cookie — Danaco Nexus",
        "Trzy ciasteczka niezbędne do działania usługi, wpisy pamięci przeglądarki, dwa zasobniki "
        "pamięci podręcznej, zero narzędzi śledzących.",
        "/portal/cookies",
    ),
}

#: Strony portalu, które naprawdę istnieją. Indeksowane biorą się z mapy witryny
#: (``nexus.portal.kanaly.STRONY_STALE`` — jedno źródło dla mapy i dla tej kontroli),
#: a do nich dochodzą cztery zamknięte przed robotami: wyszukiwarka, konto, panel klienta
#: i panel administratora. Adres spoza tego zbioru nie jest stroną portalu, więc serwer
#: odpowiada 404 zamiast powłoki z kodem 200 („miękkie 404”).
#:
#: Nowa strona portalu musi trafić do ``STRONY_STALE`` — inaczej nie ma jej ani w mapie
#: witryny, ani we własnych znacznikach, a teraz także odpowie 404.
ZAMKNIETE_STRONY = frozenset({"/portal/szukaj", "/portal/konto", "/portal/panel", "/portal/admin"})


def strona_portalu(sciezka: str) -> bool:
    """Czy ``/portal/<nazwa>`` jest stroną portalu (dwa człony, bez pozycji treści)."""
    from nexus.portal.kanaly import STRONY_STALE

    czesci = [czesc for czesc in sciezka.strip("/").split("/") if czesc]
    if len(czesci) != 2 or czesci[0] != "portal":
        return True  # nie ta postać adresu — nie nam o niej rozstrzygać
    return sciezka in ZAMKNIETE_STRONY or any(sciezka == adres for adres, _, _ in STRONY_STALE)


#: Sekcje portalu z pozycjami treści: ``/portal/<sekcja>/<adres>`` → rodzaj treści w bazie.
SEKCJE_TRESCI: dict[str, str] = {
    "blog": "blog",
    "wiedza": "wiedza",
    "dokumentacja": "dokumentacja",
    "s": "strona",
}


def sciezka_tresci(sciezka: str) -> tuple[str, str] | None:
    """Rodzaj i adres pozycji treści portalu albo ``None``, gdy to nie ten adres."""
    czesci = [czesc for czesc in sciezka.strip("/").split("/") if czesc]
    if len(czesci) != 3 or czesci[0] != "portal":
        return None
    rodzaj = SEKCJE_TRESCI.get(czesci[1])
    if rodzaj is None or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", czesci[2]):
        return None
    return rodzaj, czesci[2]


def _meta(dokument: str, rodzaj: str, nazwa: str, wartosc: str) -> str:
    """Podmienia zawartość znacznika meta albo dokłada go przed ``</head>``."""
    wzorzec = re.compile(
        rf"""<meta\s+[^>]*{rodzaj}\s*=\s*["']{re.escape(nazwa)}["'][^>]*>""", re.I
    )
    nowy = f'<meta {rodzaj}="{nazwa}" content="{html.escape(wartosc, quote=True)}">'
    if wzorzec.search(dokument):
        return wzorzec.sub(nowy, dokument, count=1)
    return dokument.replace("</head>", f"  {nowy}\n</head>", 1)


def zastosuj(dokument: str, znaczniki: Znaczniki, adres_bazowy: str) -> str:
    """Zwraca ``index.html`` z podmienionymi znacznikami strony."""
    baza = adres_bazowy.rstrip("/")
    pelny = f"{baza}{znaczniki.sciezka}" if baza else znaczniki.sciezka
    obraz = f"{baza}{znaczniki.obraz}" if baza else znaczniki.obraz
    wynik = TYTUL.sub(f"<title>{html.escape(znaczniki.tytul)}</title>", dokument, count=1)
    wynik = _meta(wynik, META_NAZWA, "description", znaczniki.opis)
    wynik = _meta(
        wynik,
        META_NAZWA,
        "robots",
        "index, follow, max-image-preview:large" if znaczniki.indeksuj else "noindex, nofollow",
    )
    wynik = _meta(wynik, META_WLASCIWOSC, "og:title", znaczniki.tytul)
    wynik = _meta(wynik, META_WLASCIWOSC, "og:description", znaczniki.opis)
    wynik = _meta(wynik, META_WLASCIWOSC, "og:url", pelny)
    wynik = _meta(wynik, META_WLASCIWOSC, "og:image", obraz)
    wynik = _meta(wynik, META_NAZWA, "twitter:title", znaczniki.tytul)
    wynik = _meta(wynik, META_NAZWA, "twitter:description", znaczniki.opis)
    wynik = _meta(wynik, META_NAZWA, "twitter:image", obraz)
    kanoniczny = re.compile(r"""<link\s+[^>]*rel\s*=\s*["']canonical["'][^>]*>""", re.I)
    nowy_kanoniczny = f'<link rel="canonical" href="{html.escape(pelny, quote=True)}">'
    if kanoniczny.search(wynik):
        return kanoniczny.sub(nowy_kanoniczny, wynik, count=1)
    return wynik.replace("</head>", f"  {nowy_kanoniczny}\n</head>", 1)


__all__ = ["SEKCJE_TRESCI", "STALE", "Znaczniki", "sciezka_tresci", "zastosuj"]
