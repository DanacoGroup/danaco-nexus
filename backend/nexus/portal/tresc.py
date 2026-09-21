"""Przetwarzanie treści portalu: adresy (slug), tekst wyszukiwania, zajawka i walidacja pól.

Wyszukiwanie pełnotekstowe działa na kolumnie ``search_text`` (tytuł, zajawka, znaczniki i treść
bez znaków diakrytycznych, małymi literami). Rozwiązanie jest przenośne: ta sama implementacja
obsługuje PostgreSQL produkcji i SQLite testów, bez rozszerzeń bazy.
"""

from __future__ import annotations

import re
import unicodedata

from nexus.models.portal import RODZAJE, STATUSY

MAX_SLUG = 120
MAX_SEARCH = 200_000
MAX_ZAJAWKA = 400
TRANSLITERACJA = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
NIE_SLOWO = re.compile(r"[^a-z0-9]+")
# Konstrukcje Markdown usuwane przed zbudowaniem tekstu wyszukiwania i zajawki.
BLOK_KODU = re.compile(r"```.*?```", re.DOTALL)
OBRAZEK = re.compile(r"!\[[^\]]*\]\([^)]*\)")
ODSYLACZ = re.compile(r"\[([^\]]*)\]\([^)]*\)")
ZNACZNIK = re.compile(r"[#>*_`~|-]+")
SPACJE = re.compile(r"\s+")
#: Spacja, która została po zdjęciu znacznika Markdown tuż przed interpunkcją.
#: `**gotowy plik**,` po zdjęciu gwiazdek daje `gotowy plik ,` — w zajawce widać to jak
#: błąd składu, bo zajawka jest zwykłym tekstem, a nie Markdownem.
SPACJA_PRZED_INTERPUNKCJA = re.compile(r"\s+([,.;:!?…)\]])")
# Adres pocztowy: kontrola formatu przy rejestracji i odzyskiwaniu hasła (bez zapytań DNS).
ADRES_POCZTY = re.compile(r"^[^@\s,;<>]{1,64}@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9-]+)+$", re.IGNORECASE)


class BladTresci(ValueError):
    """Niepoprawne dane treści portalu (adres, rodzaj, status)."""


def slug(tekst: str) -> str:
    """Adres pozycji z tytułu: ``Pierwsze kroki w Nexusie`` → ``pierwsze-kroki-w-nexusie``."""
    wartosc = unicodedata.normalize("NFKD", tekst.translate(TRANSLITERACJA))
    wartosc = wartosc.encode("ascii", "ignore").decode("ascii").lower()
    return NIE_SLOWO.sub("-", wartosc).strip("-")[:MAX_SLUG].strip("-")


def sprawdz_slug(wartosc: str) -> str:
    """Zwraca poprawny adres albo zgłasza ``BladTresci``."""
    oczyszczony = slug(wartosc)
    if not oczyszczony:
        raise BladTresci("Adres pozycji może zawierać tylko litery, cyfry i łącznik.")
    return oczyszczony


def sprawdz_rodzaj(wartosc: str) -> str:
    """Rodzaj treści z listy ``RODZAJE``."""
    if wartosc not in RODZAJE:
        raise BladTresci(f"Nieznany rodzaj treści: {wartosc}. Dozwolone: {', '.join(RODZAJE)}.")
    return wartosc


def sprawdz_status(wartosc: str) -> str:
    """Status publikacji z listy ``STATUSY``."""
    if wartosc not in STATUSY:
        raise BladTresci(f"Nieznany status: {wartosc}. Dozwolone: {', '.join(STATUSY)}.")
    return wartosc


def sprawdz_adres_poczty(wartosc: str) -> str:
    """Adres pocztowy małymi literami albo ``BladTresci``."""
    oczyszczony = wartosc.strip().lower()
    if len(oczyszczony) > 320 or not ADRES_POCZTY.match(oczyszczony):
        raise BladTresci("Podaj poprawny adres e-mail.")
    return oczyszczony


def czysty_tekst(markdown: str) -> str:
    """Treść Markdown sprowadzona do zwykłego tekstu (zajawka, tekst wyszukiwania)."""
    bez_kodu = BLOK_KODU.sub(" ", markdown)
    bez_obrazkow = OBRAZEK.sub(" ", bez_kodu)
    bez_odsylaczy = ODSYLACZ.sub(r"\1", bez_obrazkow)
    plaski = SPACJE.sub(" ", ZNACZNIK.sub(" ", bez_odsylaczy))
    return SPACJA_PRZED_INTERPUNKCJA.sub(r"\1", plaski).strip()


def _wstep(markdown: str) -> str:
    """Treść **przed pierwszym śródtytułem** — czyli wstęp, którym zaczyna się materiał.

    Bez tego zajawka powstawała z całej treści sprowadzonej do jednej linii, a wtedy
    śródtytuł sklejał się z akapitem pod nim: „Tu zbieramy to, co widać gołym okiem. Ruch
    w oknie aplikacji Treść, która dociera po odpowiedzi serwera…”. Widać to było na
    kartach spisu w portalu i czytało się jak błąd składu. Wstęp jest zresztą z definicji
    tym, co autor napisał na zachętę — lepszej zajawki i tak nie ma.
    """
    wiersze = markdown.splitlines()
    koniec = next((i for i, wiersz in enumerate(wiersze) if wiersz.lstrip().startswith("#")), None)
    wstep = "\n".join(wiersze if koniec is None else wiersze[:koniec]).strip()
    return wstep


def zajawka(podana: str, markdown: str) -> str:
    """Zajawka podana przez redaktora albo wstęp materiału (do ``MAX_ZAJAWKA`` znaków)."""
    if podana.strip():
        return podana.strip()[:MAX_ZAJAWKA]
    # Materiał bez wstępu (zaczyna się od razu śródtytułem) wraca do dawnego zachowania:
    # lepsza sklejona zajawka niż żadna.
    tekst = czysty_tekst(_wstep(markdown)) or czysty_tekst(markdown)
    if len(tekst) <= MAX_ZAJAWKA:
        return tekst
    uciety = tekst[:MAX_ZAJAWKA]
    granica = uciety.rfind(" ")
    return (uciety[:granica] if granica > 80 else uciety).rstrip(" ,;:-") + "…"


def znormalizuj(tekst: str) -> str:
    """Tekst bez znaków diakrytycznych, małymi literami – postać porównywana w wyszukiwaniu."""
    wartosc = unicodedata.normalize("NFKD", tekst.translate(TRANSLITERACJA))
    return wartosc.encode("ascii", "ignore").decode("ascii").lower()


def tekst_wyszukiwania(tytul: str, zajawka_tekst: str, markdown: str, znaczniki: list[str]) -> str:
    """Zawartość kolumny ``search_text`` dla pozycji treści."""
    czesci = [tytul, zajawka_tekst, " ".join(znaczniki), czysty_tekst(markdown)]
    return znormalizuj(SPACJE.sub(" ", " ".join(czesci)))[:MAX_SEARCH]


def slowa_zapytania(zapytanie: str, limit: int = 8) -> list[str]:
    """Znormalizowane słowa zapytania (bez powtórzeń, najwyżej ``limit``)."""
    slowa: list[str] = []
    for slowo in NIE_SLOWO.split(znormalizuj(zapytanie)):
        if len(slowo) >= 2 and slowo not in slowa:
            slowa.append(slowo)
        if len(slowa) == limit:
            break
    return slowa


def znaczniki(wartosci: list[str] | None) -> list[str]:
    """Znaczniki: bez powtórzeń i pustych, najwyżej 12, po 40 znaków."""
    wynik: list[str] = []
    for wartosc in wartosci or []:
        oczyszczony = SPACJE.sub(" ", wartosc).strip()[:40]
        if oczyszczony and oczyszczony not in wynik:
            wynik.append(oczyszczony)
        if len(wynik) == 12:
            break
    return wynik
