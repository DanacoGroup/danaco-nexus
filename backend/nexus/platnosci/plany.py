"""Katalog planów sprzedażowych: jedyne miejsce, w którym opisany jest plan.

Katalog rozstrzyga nazwy, opisy, zakres, przydział kredytów i limity; interfejs bierze
to wszystko z ``GET /api/platnosci/cennik`` i niczego o planach nie dopisuje od siebie.
Kwoty dopisuje środowisko (``NEXUS_PLATNOSCI_KWOTY``), bo ceny podawane są przy starcie
sprzedaży. Plan jest do kupienia dopiero wtedy, gdy sprzedaż jest włączona i plan ma
kwotę oraz identyfikator ceny Stripe – do tego czasu interfejs pokazuje go jako „Wkrótce”.

Z liczb opisujących plan egzekwowany jest dziś wyłącznie przydział kredytów
(``kredyty_okresowo``, ``nexus/platnosci/kredyty.py``) i tylko on jest pokazywany
w cenniku. Pozostałe pozycje ``limity`` są danymi dla ``sprawdz_limit`` bez wpięcia
w modułach; opisuje to ``docs/platnosci/README.md`` rozdz. 9.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from nexus.config import get_settings
from nexus.db import Database, utcnow
from nexus.platnosci.konfiguracja import UstawieniaPlatnosci
from nexus.platnosci.model import Plan

PLAN_DOMYSLNY = "osobisty"


@dataclass(frozen=True)
class PlanKatalogu:
    """Opis planu w katalogu (bez cen – te ustala środowisko).

    Okres próbny **nie jest osobnym planem**, tylko ograniczonym trybem planu, który go
    otwiera: ta sama subskrypcja, mniejsza przestrzeń, mniej kredytów i bez funkcji
    wymagających zaufania (poczta, synchronizacja, wersje). Dzięki temu Stripe prowadzi
    jedną subskrypcję od początku do końca, a użytkownik po 7 dniach nie musi niczego
    wybierać — dostaje pełny zakres planu, za który już podał kartę.
    """

    kod: str
    nazwa: str
    opis: str
    limity: dict[str, int]
    # Kredyty dopisywane do konta przy uruchomieniu planu i przy każdym odnowieniu.
    # Kredyt to jednostka pracy agenta, nie waluta — chroni wspólny limit silnika.
    kredyty_okresowo: int
    # Przestrzeń konta w MB — wspólna dla plików rozmów, chmury osobistej i skrzynek
    # pocztowych. Jeden licznik, bo użytkownik i tak myśli o „swoim miejscu”, a nie
    # o trzech osobnych pulach.
    przestrzen_mb: int
    # Ile skrzynek pocztowych w domenie Nexusa wolno założyć (0 = funkcja niedostępna).
    skrzynki_poczty: int
    # Wersje plików w chmurze i synchronizacja z komputerem — funkcje planów płatnych.
    wersjonowanie: bool
    synchronizacja: bool
    zawartosc: tuple[str, ...]
    kolejnosc: int
    # Plan bezpłatny nie przechodzi przez Stripe (przydzielany od razu po zalogowaniu).
    bezplatny: bool = False
    # Dni okresu próbnego przy zakupie. Karta jest podawana od razu, a po tym czasie
    # subskrypcja przechodzi w płatną bez dodatkowego kroku — użytkownik nie musi
    # niczego potwierdzać, a my widzimy, czy płatność weszła.
    okres_probny_dni: int = 0
    # Zakres w czasie okresu próbnego. Poczta i synchronizacja są wyłączone celowo:
    # darmowa skrzynka zakładana samoobsługowo to produkt, który spamerzy biorą masowo,
    # a koszt jednego takiego incydentu ponoszą wszyscy użytkownicy domeny naraz.
    probny_przestrzen_mb: int = 0
    probny_kredyty: int = 0
    znacznik: str = ""

    @property
    def przestrzen_gb(self) -> float:
        """Przestrzeń planu w gigabajtach — do wyświetlenia w cenniku."""
        return round(self.przestrzen_mb / 1024, 2)


KATALOG: tuple[PlanKatalogu, ...] = (
    PlanKatalogu(
        kod="osobisty",
        nazwa="Osobisty",
        opis=(
            "Dla jednej osoby, do pracy i do domu: rozmowa, dokumenty, zdjęcia, nagrania "
            "i własny adres e-mail. Pierwsze 7 dni bez opłaty."
        ),
        limity={"zadania_rownolegle": 1, "automatyzacje": 0, "konta": 1, "skrzynki": 1},
        kredyty_okresowo=2_000,
        przestrzen_mb=1_024,
        skrzynki_poczty=1,
        wersjonowanie=False,
        # Synchronizacja i wersje plików zaczynają się w planie Pro: to one są powodem,
        # dla którego ktoś z Osobistego przechodzi wyżej.
        synchronizacja=False,
        zawartosc=(
            "Rozmowa z Nexusem, także głosowa",
            "Dokumenty, zdjęcia i nagrania — wynikiem jest plik",
            "OCR skanów z językiem polskim",
            "Wyszukiwanie w Twoich plikach i notatkach",
            "1 GB przestrzeni na pliki i pocztę",
            "Adres e-mail w domenie Nexusa — w przygotowaniu",
            "Jedno zadanie naraz",
        ),
        kolejnosc=10,
        okres_probny_dni=7,
        probny_przestrzen_mb=100,
        probny_kredyty=300,
        znacznik="7 dni próbnych",
    ),
    PlanKatalogu(
        kod="pro",
        nazwa="Pro",
        opis=(
            "Dla codziennej pracy. Wersje plików, synchronizacja z komputerem i cztery "
            "zadania naraz — to są powody przejścia z planu Osobistego."
        ),
        limity={"zadania_rownolegle": 4, "automatyzacje": 20, "konta": 1, "skrzynki": 10},
        kredyty_okresowo=20_000,
        przestrzen_mb=2_048,
        skrzynki_poczty=10,
        wersjonowanie=True,
        synchronizacja=True,
        zawartosc=(
            "Wszystko z planu Osobistego",
            "Wersje plików — powrót do wczorajszej wersji dokumentu",
            "Synchronizacja z komputerem i telefonem",
            "Cztery zadania naraz zamiast jednego",
            "Dziesięciokrotnie większy zakres pracy",
            "2 GB przestrzeni na pliki i pocztę",
            "Do 10 adresów e-mail w domenie Nexusa — w przygotowaniu",
        ),
        kolejnosc=20,
    ),
    PlanKatalogu(
        kod="zespol",
        # Nazwa „Grupa”, bo tak działa: rodzina, wspólnicy, mały zespół — cena liczy się
        # za każdego użytkownika, a zakres pracy jest wspólny i kupuje go założyciel grupy.
        # „konta: 5” jest tylko wartością zastępczą, zanim powstanie subskrypcja: o liczbie
        # miejsc rozstrzyga to, za ile zapłacono w kasie (`platnosci.grupy.miejsca_grupy`).
        nazwa="Grupa",
        opis=(
            "Dla rodziny albo małego zespołu. Każdy pracuje na własnym koncie, a zakres "
            "pracy i 10 GB przestrzeni dzieli cała grupa. Cena liczy się za użytkownika."
        ),
        limity={"zadania_rownolegle": 8, "automatyzacje": 100, "konta": 5, "skrzynki": 10},
        kredyty_okresowo=60_000,
        przestrzen_mb=10_240,
        skrzynki_poczty=10,
        wersjonowanie=True,
        synchronizacja=True,
        zawartosc=(
            "Wszystko z planu Pro",
            "Własne konto i własna skrzynka dla każdej osoby w grupie",
            "Wspólny zakres pracy — przedłuża go założyciel grupy",
            "Osiem zadań naraz, więc kilka osób pracuje jednocześnie",
            "10 GB przestrzeni na pliki i pocztę",
            "Rolę założyciela można przekazać innej osobie",
            "Cena za każdego użytkownika w grupie",
        ),
        kolejnosc=30,
    ),
)
KATALOG_WG_KODU: dict[str, PlanKatalogu] = {pozycja.kod: pozycja for pozycja in KATALOG}


def pozycja_katalogu(kod: str) -> PlanKatalogu | None:
    """Plan z katalogu albo ``None``, gdy kod jest nieznany."""
    return KATALOG_WG_KODU.get(kod.strip().lower())


def limity_pozycji(pozycja: PlanKatalogu) -> dict[str, int]:
    """Limity planu wraz z rozmiarem pliku wziętym z ustawień instalacji.

    ``plik_mb`` nie jest cechą planu, tylko ustawieniem serwera
    (``NEXUS_UPLOAD_LIMIT_MB``, ``nexus/api/files.py``) wspólnym dla wszystkich planów.
    Przepisany do każdej pozycji katalogu rozjeżdżał się z tym, co serwer naprawdę
    przyjmuje. To co innego niż przestrzeń konta, która jest cechą planu
    (``przestrzen_mb``) i rośnie wraz z nim.
    """
    return {**pozycja.limity, "plik_mb": get_settings().upload_limit_mb}


async def synchronizuj_plany(database: Database, ustawienia: UstawieniaPlatnosci) -> None:
    """Zapisuje katalog planów w bazie wraz z kwotami z konfiguracji środowiska."""
    kwoty = ustawienia.kwoty_groszy
    async with database.session() as session:
        istniejace = {row.kod: row for row in (await session.scalars(select(Plan))).all()}
        for pozycja in KATALOG:
            rekord = istniejace.get(pozycja.kod)
            if rekord is None:
                rekord = Plan(kod=pozycja.kod)
                session.add(rekord)
            rekord.nazwa = pozycja.nazwa
            rekord.opis = pozycja.opis
            rekord.limity = limity_pozycji(pozycja)
            rekord.kolejnosc = pozycja.kolejnosc
            rekord.aktywny = True
            rekord.cena_miesiac_gr = 0 if pozycja.bezplatny else kwoty.get(f"{pozycja.kod}:miesiac", 0)
            rekord.cena_rok_gr = 0 if pozycja.bezplatny else kwoty.get(f"{pozycja.kod}:rok", 0)
            rekord.updated_at = utcnow()
        for kod, rekord in istniejace.items():
            if kod not in KATALOG_WG_KODU:
                rekord.aktywny = False


def do_kupienia(pozycja: PlanKatalogu, okres: str, ustawienia: UstawieniaPlatnosci, kwota_gr: int) -> bool:
    """Czy plan można kupić: sprzedaż włączona, jest kwota i identyfikator ceny Stripe.

    Brak klucza Stripe (także nieczytelny plik klucza) zatrzymuje zakup w API, więc
    znacznik „Dostępny” nie może się wtedy pojawić przy żadnym planie.
    """
    if pozycja.bezplatny or not ustawienia.skonfigurowane:
        return False
    return kwota_gr > 0 and bool(ustawienia.cena_stripe(pozycja.kod, okres))
