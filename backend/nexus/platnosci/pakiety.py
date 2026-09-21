"""Pakiety kredytów kupowane jednorazowo, poza subskrypcją.

Subskrypcja przydziela kredyty co okres, ale praca nie rozkłada się równo: użytkownik
potrafi zużyć miesięczny przydział w tydzień. Bez możliwości dokupienia zostawałyby dwa
wyjścia — czekać do odnowienia albo przechodzić na wyższy plan — i oba są złe dla kogoś,
kto ma jedno duże zadanie raz na kwartał.

Pakiet to jednorazowa płatność Stripe (``mode: "payment"``). Kredyty dopisuje webhook po
potwierdzeniu wpłaty, nigdy powrót z przeglądarki: adres powrotu może zostać otwarty
ponownie albo podrobiony.
"""

from __future__ import annotations

from dataclasses import dataclass

# Pierwszy człon klucza cennika odróżniający pakiet od subskrypcji planu: pakiet kupuje
# się jednorazowo, więc jego pozycja nie ma okresu rozliczeniowego, tylko kod pakietu.
# Parser cennika (``nexus/platnosci/konfiguracja.py``) rozpoznaje po tym przedrostku,
# że drugiego członu nie należy sprawdzać w wykazie okresów.
PRZEDROSTEK_PAKIETU = "pakiet"


# Rozmiary pakietów dobrane tak, żeby największy odpowiadał mniej więcej miesięcznemu
# przydziałowi planu Pro. Identyfikatory ceny Stripe wskazuje NEXUS_PLATNOSCI_CENY
# pod kluczem ``pakiet:<kod>``.
@dataclass(frozen=True)
class PakietKredytow:
    """Pozycja w katalogu pakietów: ile kredytów i pod jakim kluczem szukać ceny."""

    kod: str
    nazwa: str
    kredyty: int
    opis: str

    @property
    def klucz_ceny(self) -> str:
        return f"{PRZEDROSTEK_PAKIETU}:{self.kod}"


KATALOG_PAKIETOW: tuple[PakietKredytow, ...] = (
    PakietKredytow(
        kod="maly",
        nazwa="Mały pakiet",
        kredyty=5_000,
        opis="Na dokończenie zadania, gdy zakres z planu skończył się o włos za wcześnie.",
    ),
    PakietKredytow(
        kod="sredni",
        nazwa="Średni pakiet",
        kredyty=20_000,
        opis="Miesiąc intensywnej pracy ponad przydział planu.",
    ),
    PakietKredytow(
        kod="duzy",
        nazwa="Duży pakiet",
        kredyty=60_000,
        opis="Duże zadanie jednorazowe: stos skanów, długie nagrania, seria zdjęć.",
    ),
)

PAKIETY_WG_KODU: dict[str, PakietKredytow] = {pozycja.kod: pozycja for pozycja in KATALOG_PAKIETOW}


def pakiet(kod: str) -> PakietKredytow | None:
    """Pakiet z katalogu albo ``None``, gdy kod jest nieznany."""
    return PAKIETY_WG_KODU.get(kod.strip().lower())
