"""Egzekwowanie limitów planu po stronie serwera.

Limity rozstrzyga aktywna subskrypcja użytkownika, nigdy dane przysłane przez klienta.
Członek opłaconej grupy bierze je z subskrypcji założyciela (``limity_uzytkownika``).
Egzekwowane są dziś: przydział kredytów (``nexus/platnosci/kredyty.py``), liczba zadań
naraz (``nexus/api/conversations.py``) i przestrzeń konta (``nexus/api/files.py``).
Rozmiar jednego pliku pozostaje ustawieniem serwera (``NEXUS_UPLOAD_LIMIT_MB``) wspólnym
dla wszystkich planów, a ``automatyzacje`` nie mają jeszcze modułu, w którym dałoby się
je sprawdzić — i dlatego katalog ich nie sprzedaje. Miejsca wpięcia i stan egzekwowania:
``docs/platnosci/README.md`` rozdz. 9.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from nexus.db import ADMIN_OWNER, Database
from nexus.platnosci.grupy import subskrypcja_grupy
from nexus.platnosci.model import STATUS_PROBNA, STATUSY_UPRAWNIAJACE, Subskrypcja
from nexus.platnosci.plany import PLAN_DOMYSLNY, limity_pozycji, pozycja_katalogu
from nexus.platnosci.uslugi import subskrypcja_uzytkownika

# Nazwa limitu → dopełniacz używany w komunikacie dla użytkownika.
OPISY = {
    "zadania_rownolegle": "liczba zadań wykonywanych jednocześnie",
    "plik_mb": "rozmiar jednego pliku w MB",
    "automatyzacje": "liczba automatyzacji",
    "konta": "liczba kont w zespole",
}


class LimitPrzekroczony(Exception):
    """Żądanie wykracza poza limit aktywnego planu."""

    def __init__(self, rodzaj: str, limit: int, wartosc: int, plan: str) -> None:
        opis = OPISY.get(rodzaj, rodzaj)
        if limit <= 0:
            komunikat = f"Plan {plan} nie obejmuje tej możliwości ({opis})."
        else:
            komunikat = f"Plan {plan} dopuszcza {opis}: {limit}. Żądanie: {wartosc}."
        super().__init__(komunikat)
        self.rodzaj, self.limit, self.wartosc, self.plan = rodzaj, limit, wartosc, plan
        # 402 Payment Required: dalsze korzystanie wymaga wyższego planu.
        self.status = 402


@dataclass(frozen=True)
class Limity:
    """Limity obowiązujące użytkownika wraz z planem, z którego wynikają."""

    plan: str
    nazwa_planu: str
    status: str
    zadania_rownolegle: int
    plik_mb: int
    automatyzacje: int
    konta: int
    # Przestrzeń konta w MB — wspólna dla plików, chmury i skrzynek pocztowych.
    przestrzen_mb: int = 0
    skrzynki: int = 0
    wersjonowanie: bool = False
    synchronizacja: bool = False
    # Czy konto jest w okresie próbnym: zakres jest wtedy węższy niż w opłaconym planie.
    probny: bool = False

    def limit(self, rodzaj: str) -> int:
        """Wartość limitu o podanej nazwie (0 = możliwość niedostępna)."""
        return int(getattr(self, rodzaj, 0))

    def mapa(self) -> dict[str, int]:
        """Limity jako słownik (odpowiedź API, interfejs)."""
        return {
            "zadania_rownolegle": self.zadania_rownolegle,
            "plik_mb": self.plik_mb,
            "automatyzacje": self.automatyzacje,
            "konta": self.konta,
            "przestrzen_mb": self.przestrzen_mb,
            "skrzynki": self.skrzynki,
            "wersjonowanie": int(self.wersjonowanie),
            "synchronizacja": int(self.synchronizacja),
        }


def opis_przestrzeni(mb: int) -> str:
    """Przestrzeń w postaci, w jakiej mówi o niej człowiek: „100 MB”, „1 GB”, „10 GB”."""
    if mb < 1024:
        return f"{mb} MB"
    gb = mb / 1024
    return f"{gb:.0f} GB" if gb == int(gb) else f"{gb:.1f} GB"


def limity_planu(kod: str, status: str) -> Limity:
    """Limity dla kodu planu; nieznany plan i brak opłaty dają plan domyślny.

    Okres próbny (``status`` = ``probna``) nie jest osobnym planem: to ten sam plan
    z węższym zakresem. Poczta i wersje plików są wtedy wyłączone, a przestrzeń
    zmniejszona — darmowa skrzynka zakładana samoobsługowo jest dokładnie tym, co
    spamerzy biorą masowo, a blokada domeny dotyka wszystkich użytkowników naraz.
    """
    uprawniony = status in STATUSY_UPRAWNIAJACE
    pozycja = pozycja_katalogu(kod) if uprawniony else None
    if pozycja is None:
        pozycja = pozycja_katalogu(PLAN_DOMYSLNY)
    assert pozycja is not None  # katalog zawsze zawiera plan domyślny
    wartosci = limity_pozycji(pozycja)
    # Konto bez opłaconego planu ma ten sam wąski zakres co okres próbny. Żaden plan nie
    # jest już bezpłatny, więc rezygnacja albo brak zakupu nie może zostawiać pełnego
    # miejsca ani skrzynki pocztowej.
    probny = not uprawniony or (status == STATUS_PROBNA and pozycja.okres_probny_dni > 0)
    return Limity(
        plan=pozycja.kod,
        nazwa_planu=pozycja.nazwa,
        status=status,
        zadania_rownolegle=int(wartosci.get("zadania_rownolegle", 1)),
        plik_mb=int(wartosci.get("plik_mb", 0)),
        automatyzacje=0 if probny else int(wartosci.get("automatyzacje", 0)),
        konta=int(wartosci.get("konta", 1)),
        przestrzen_mb=(pozycja.probny_przestrzen_mb if probny else pozycja.przestrzen_mb),
        skrzynki=0 if probny else pozycja.skrzynki_poczty,
        wersjonowanie=pozycja.wersjonowanie and not probny,
        synchronizacja=pozycja.synchronizacja and not probny,
        probny=probny,
    )


def limity_subskrypcji(subskrypcja: Subskrypcja | None) -> Limity:
    """Limity wynikające z rekordu subskrypcji (brak rekordu = plan domyślny)."""
    if subskrypcja is None:
        return limity_planu(PLAN_DOMYSLNY, "brak")
    return limity_planu(subskrypcja.plan_kod, subskrypcja.status)


async def limity_uzytkownika(database: Database, uzytkownik: str = "") -> Limity:
    """Limity wskazanego konta; bez wskazania — konta administratora instalacji.

    Kluczem subskrypcji jest identyfikator konta (``UserSession.owner_id``), a nie login:
    limity, kredyty i rozmowy mają się rozstrzygać po tym samym koncie.

    Członek opłaconej grupy ma limity planu Grupa z subskrypcji założyciela
    (``grupy.subskrypcja_grupy``) — tak jak założyciel, choć sam planu nie kupował.
    """
    nazwa = uzytkownik or str(ADMIN_OWNER)
    try:
        konto: uuid.UUID | None = uuid.UUID(nazwa)
    except ValueError:
        # Login zamiast identyfikatora konta (administrator instalacji) — poza grupami.
        konto = None
    grupowa = await subskrypcja_grupy(database, konto) if konto is not None else None
    if grupowa is not None:
        return limity_subskrypcji(grupowa)
    return limity_subskrypcji(await subskrypcja_uzytkownika(database, nazwa))


def sprawdz(limity: Limity, rodzaj: str, wartosc: int) -> None:
    """Sprawdza jedną wartość wobec limitu; przekroczenie zgłasza ``LimitPrzekroczony``."""
    limit = limity.limit(rodzaj)
    if limit <= 0 or wartosc > limit:
        raise LimitPrzekroczony(rodzaj, limit, wartosc, limity.nazwa_planu)


async def sprawdz_limit(database: Database, rodzaj: str, wartosc: int, uzytkownik: str = "") -> Limity:
    """Sprawdza limit planu przed wykonaniem działania i zwraca obowiązujące limity."""
    limity = await limity_uzytkownika(database, uzytkownik)
    sprawdz(limity, rodzaj, wartosc)
    return limity
