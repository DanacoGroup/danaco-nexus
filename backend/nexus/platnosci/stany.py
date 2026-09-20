"""Stany sprzedaży i subskrypcji: jeden opis dla serwera, interfejsu i testów.

Każdy stan niesie tytuł, komunikat mówiący, co zrobić dalej, oraz kod działania,
który interfejs zamienia na przycisk. Treść rozstrzyga serwer, więc moduł Płatności,
portal i testy pokazują ten sam komunikat w tej samej sytuacji.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nexus.db import utcnow
from nexus.platnosci.model import (
    STATUS_ANULOWANA,
    STATUS_NIEPELNA,
    STATUS_PROBNA,
    STATUS_ZALEGLA,
    STATUSY_UPRAWNIAJACE,
    Faktura,
    Subskrypcja,
)
from nexus.platnosci.plany import PLAN_DOMYSLNY, pozycja_katalogu

# Kody działań; interfejs zamienia je na przycisk obok komunikatu.
DZIALANIE_BRAK = "brak"
DZIALANIE_WYBIERZ_PLAN = "wybierz_plan"
DZIALANIE_PORTAL = "portal"
DZIALANIE_ZAPLAC = "zaplac_fakture"

# Stany Stripe faktury, która wciąż czeka na zapłatę.
STATUSY_FAKTURY_DO_ZAPLATY = frozenset({"open", "uncollectible"})

# Komunikat serwera, gdy sprzedaż nie jest włączona (brak klucza Stripe).
KOMUNIKAT_SPRZEDAZ_WYLACZONA = (
    "Sprzedaż nie jest jeszcze włączona na tym serwerze. Konto pracuje na przydzielonych "
    "kredytach i nie wymaga od Ciebie niczego."
)

# Powody odrzucenia kodu rabatowego wraz z podpowiedzią, co zrobić dalej.
KOMUNIKATY_KUPONU = {
    "nieznany": "Nie znamy takiego kodu rabatowego. Sprawdź pisownię albo kup plan bez kodu.",
    "nieaktywny": "Ten kod rabatowy został wyłączony. Kup plan bez kodu albo poproś o aktualny.",
    "wygasl": "Ten kod rabatowy stracił ważność. Kup plan bez kodu albo poproś o aktualny.",
    "wyczerpany": "Ten kod rabatowy został już wykorzystany. Kup plan bez kodu albo poproś o inny.",
}


@dataclass(frozen=True)
class StanSprzedazy:
    """Stan widoczny dla użytkownika: co się dzieje i co zrobić dalej."""

    kod: str
    tytul: str
    komunikat: str
    dzialanie: str = DZIALANIE_BRAK
    etykieta_dzialania: str = ""
    ton: str = "informacja"

    def mapa(self) -> dict[str, str]:
        """Stan w postaci odpowiedzi API."""
        return {
            "kod": self.kod,
            "tytul": self.tytul,
            "komunikat": self.komunikat,
            "dzialanie": self.dzialanie,
            "etykieta_dzialania": self.etykieta_dzialania,
            "ton": self.ton,
        }


def zapis_daty(wartosc: datetime | None) -> str:
    """Data w zapisie dziennym; pusta wartość daje pusty tekst."""
    return wartosc.strftime("%d.%m.%Y") if wartosc else ""


def _nazwa_planu(kod: str) -> str:
    """Nazwa planu z katalogu; nieznany kod daje nazwę planu domyślnego."""
    pozycja = pozycja_katalogu(kod) or pozycja_katalogu(PLAN_DOMYSLNY)
    return pozycja.nazwa if pozycja else kod


def _dzialanie_platnosci(faktura: Faktura | None) -> tuple[str, str]:
    """Działanie przy nieopłaconej należności: zapłata faktury albo portal rozliczeniowy."""
    if faktura is not None and faktura.strona_url:
        return DZIALANIE_ZAPLAC, "Zapłać fakturę"
    return DZIALANIE_PORTAL, "Popraw płatność"


def _wygasla(subskrypcja: Subskrypcja, teraz: datetime) -> bool:
    """Czy opłacony okres minął, choć Stripe nie przysłał jeszcze zakończenia."""
    return subskrypcja.okres_do is not None and subskrypcja.okres_do < teraz


def stan_sprzedazy(
    subskrypcja: Subskrypcja,
    sprzedaz_aktywna: bool,
    faktura: Faktura | None = None,
    teraz: datetime | None = None,
) -> StanSprzedazy:
    """Rozstrzyga stan konta w sprzedaży: od konta bez planu po odrzuconą płatność."""
    chwila = teraz or utcnow()
    nazwa = _nazwa_planu(subskrypcja.plan_kod)
    do_kiedy = zapis_daty(subskrypcja.okres_do)

    if subskrypcja.status == STATUS_NIEPELNA:
        dzialanie, etykieta = _dzialanie_platnosci(faktura)
        return StanSprzedazy(
            kod="platnosc_niedokonczona",
            tytul="Płatność nie została dokończona",
            komunikat=(
                f"Bank nie potwierdził płatności za plan {nazwa}. Dokończ płatność, a plan "
                "włączy się od razu. Do tego czasu konto pracuje na planie Osobistym."
            ),
            dzialanie=dzialanie,
            etykieta_dzialania=etykieta,
            ton="blad",
        )

    if subskrypcja.status == STATUS_ZALEGLA:
        dzialanie, etykieta = _dzialanie_platnosci(faktura)
        koniec = f" Plan {nazwa} działa jeszcze do {do_kiedy}." if do_kiedy else ""
        return StanSprzedazy(
            kod="platnosc_odrzucona",
            tytul="Płatność została odrzucona",
            komunikat=(
                f"Ostatnia płatność za plan {nazwa} nie przeszła. Popraw dane karty albo "
                f"zapłać fakturę.{koniec}"
            ),
            dzialanie=dzialanie,
            etykieta_dzialania=etykieta,
            ton="blad",
        )

    if subskrypcja.status == STATUS_ANULOWANA:
        kiedy = f" {do_kiedy}" if do_kiedy else ""
        return StanSprzedazy(
            kod="subskrypcja_wygasla",
            tytul="Subskrypcja wygasła",
            komunikat=(
                f"Płatny plan zakończył się{kiedy}. Konto pracuje na planie Osobistym — "
                "wybierz plan, żeby wrócić do wyższych limitów."
            ),
            dzialanie=DZIALANIE_WYBIERZ_PLAN,
            etykieta_dzialania="Wybierz plan",
            ton="uwaga",
        )

    # Złożona rezygnacja rozstrzyga przed zamkniętym okresem: odnowienia nie miało być,
    # więc komunikat o braku potwierdzenia ze Stripe podpowiadałby niewłaściwe działanie.
    if subskrypcja.anuluj_na_koniec and subskrypcja.status in STATUSY_UPRAWNIAJACE:
        kiedy = f" {do_kiedy}" if do_kiedy else " wraz z opłaconym okresem"
        if _wygasla(subskrypcja, chwila):
            return StanSprzedazy(
                kod="rezygnacja_zlozona",
                tytul="Opłacony okres się skończył",
                komunikat=(
                    f"Plan {nazwa} skończył się{kiedy} zgodnie ze złożoną rezygnacją. Stripe "
                    "domyka rozliczenie — konto wraca na plan Osobisty. Plan wybierzesz na nowo."
                ),
                dzialanie=DZIALANIE_WYBIERZ_PLAN,
                etykieta_dzialania="Wybierz plan",
                ton="uwaga",
            )
        return StanSprzedazy(
            kod="rezygnacja_zlozona",
            tytul="Plan kończy się po opłaconym okresie",
            komunikat=(
                f"Rezygnacja została przyjęta. Plan {nazwa} działa do{kiedy} i nie odnowi się. "
                "Do tego dnia możesz go wznowić w portalu rozliczeniowym."
            ),
            dzialanie=DZIALANIE_PORTAL,
            etykieta_dzialania="Wznów plan",
            ton="uwaga",
        )

    if subskrypcja.status in STATUSY_UPRAWNIAJACE and _wygasla(subskrypcja, chwila):
        return StanSprzedazy(
            kod="subskrypcja_wygasla",
            tytul="Opłacony okres minął",
            komunikat=(
                f"Okres opłacony planem {nazwa} skończył się {do_kiedy}, a Stripe nie "
                "potwierdził jeszcze odnowienia. Sprawdź rozliczenia albo wybierz plan na nowo."
            ),
            dzialanie=DZIALANIE_PORTAL,
            etykieta_dzialania="Sprawdź rozliczenia",
            ton="uwaga",
        )

    if subskrypcja.status == STATUS_PROBNA:
        kiedy = f" do {do_kiedy}" if do_kiedy else ""
        return StanSprzedazy(
            kod="okres_probny",
            tytul=f"Plan {nazwa} w okresie próbnym",
            komunikat=(
                f"Okres próbny trwa{kiedy}. Potem plan odnowi się automatycznie — rezygnację "
                "złożysz w każdej chwili, bez kontaktu z nami."
            ),
            dzialanie=DZIALANIE_PORTAL,
            etykieta_dzialania="Zarządzaj planem",
            ton="informacja",
        )

    if subskrypcja.status in STATUSY_UPRAWNIAJACE:
        kiedy = f"Kolejne odnowienie {do_kiedy}. " if do_kiedy else ""
        return StanSprzedazy(
            kod="plan_aktywny",
            tytul=f"Plan {nazwa} jest aktywny",
            komunikat=f"{kiedy}Fakturę za każdy okres znajdziesz niżej, razem z plikiem PDF.",
            dzialanie=DZIALANIE_PORTAL,
            etykieta_dzialania="Zarządzaj planem",
            ton="sukces",
        )

    if not sprzedaz_aktywna:
        return StanSprzedazy(
            kod="sprzedaz_wylaczona",
            tytul="Sprzedaż nie jest jeszcze włączona",
            komunikat=(
                f"{KOMUNIKAT_SPRZEDAZ_WYLACZONA} Plany pojawią się w cenniku, "
                "gdy ruszy sprzedaż."
            ),
            dzialanie=DZIALANIE_BRAK,
            ton="informacja",
        )

    # Kod stanu pozostaje historyczny (``plan_bezplatny``), bo rozpoznaje go interfejs;
    # dziś oznacza konto bez wykupionego planu, pracujące na przydzielonych kredytach.
    return StanSprzedazy(
        kod="plan_bezplatny",
        tytul="Konto bez wykupionego planu",
        komunikat=(
            "Pracujesz na kredytach przydzielonych do konta. Plany, przydziały kredytów "
            "i kwoty znajdziesz w cenniku; najniższy zaczyna się okresem próbnym."
        ),
        dzialanie=DZIALANIE_WYBIERZ_PLAN,
        etykieta_dzialania="Wybierz plan",
        ton="informacja",
    )
