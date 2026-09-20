"""Wysyłka poczty portalu (potwierdzenie adresu, odzyskiwanie hasła, zmiana hasła, usunięcie konta).

Domyślnie działa nadawca zapisujący wiadomość w dzienniku aplikacji – instalacja bez skonfigurowanej
poczty nie traci tokenów, ale też niczego nie wysyła. Po ustawieniu ``NEXUS_PORTAL_MAIL_NADAWCA=smtp``
wiadomości idą przez konto SMTP aplikacji (``nexus.mail``). Szczegóły: ``docs/portal/README.md``.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Protocol

from nexus.config import Settings
from nexus.portal.ustawienia import NADAWCA_SMTP, PortalSettings

logger = logging.getLogger("nexus.portal.poczta")


class BladWysylki(RuntimeError):
    """Wiadomości nie udało się wysłać."""


class NadawcaPoczty(Protocol):
    """Interfejs nadawcy wiadomości portalu."""

    def wyslij(self, odbiorca: str, temat: str, tresc: str) -> None:
        """Wysyła wiadomość tekstową do jednego odbiorcy."""


class NadawcaDoDziennika:
    """Nadawca zastępczy: zapisuje wiadomość w dzienniku zamiast wysyłać."""

    def wyslij(self, odbiorca: str, temat: str, tresc: str) -> None:
        logger.info("Poczta portalu (tylko dziennik) do %s: %s\n%s", odbiorca, temat, tresc)


class NadawcaSmtp:
    """Nadawca korzystający z konta SMTP aplikacji (plik ``NEXUS_POCZTA_CONFIG_FILE``)."""

    def __init__(self, settings: Settings, adres_nadawcy: str = "") -> None:
        self._settings = settings
        self._adres = adres_nadawcy

    def wyslij(self, odbiorca: str, temat: str, tresc: str) -> None:
        from nexus import mail

        try:
            konto = mail.load_config(self._settings)
        except mail.MailError as error:
            raise BladWysylki(f"Poczta portalu nie jest skonfigurowana: {error}") from error
        wiadomosc = EmailMessage()
        wiadomosc["From"] = self._adres or konto.address
        wiadomosc["To"] = odbiorca
        wiadomosc["Subject"] = temat
        wiadomosc.set_content(tresc)
        try:
            mail.send_message(konto, wiadomosc, timeout=self._settings.poczta_timeout_s)
        except mail.MailError as error:
            raise BladWysylki(str(error)) from error


def nadawca(settings: Settings, portal: PortalSettings) -> NadawcaPoczty:
    """Nadawca wskazany konfiguracją; przy braku poczty wraca do zapisu w dzienniku."""
    if portal.mail_sender != NADAWCA_SMTP:
        return NadawcaDoDziennika()
    from nexus import mail

    if not mail.is_configured(settings):
        logger.warning("Wybrano nadawcę SMTP, ale poczta aplikacji nie jest skonfigurowana.")
        return NadawcaDoDziennika()
    return NadawcaSmtp(settings, portal.mail_from)


def tresc_odzyskiwania(adres_resetu: str, minuty: int) -> tuple[str, str]:
    """Temat i treść wiadomości z odsyłaczem do ustawienia nowego hasła."""
    temat = "Danaco Nexus – ustawienie nowego hasła"
    tresc = (
        "Otrzymaliśmy prośbę o ustawienie nowego hasła do konta w portalu Danaco Nexus.\n\n"
        f"Odsyłacz jest ważny {minuty} minut i działa tylko raz:\n{adres_resetu}\n\n"
        "Jeżeli prośba nie pochodzi od Ciebie, zignoruj tę wiadomość – hasło pozostanie bez zmian."
    )
    return temat, tresc


def tresc_potwierdzenia_adresu(adres_potwierdzenia: str, godziny: int) -> tuple[str, str]:
    """Temat i treść wiadomości z odsyłaczem potwierdzającym adres konta."""
    temat = "Danaco Nexus – potwierdź adres e-mail"
    tresc = (
        "Dziękujemy za założenie konta w portalu Danaco Nexus. Konto działa od razu; potwierdź\n"
        "adres, abyśmy mieli pewność, że wiadomości o koncie trafiają do Ciebie.\n\n"
        f"Odsyłacz jest ważny {godziny} godzin i działa tylko raz:\n{adres_potwierdzenia}\n\n"
        "Jeżeli konta nie zakładałeś, zignoruj tę wiadomość."
    )
    return temat, tresc


def tresc_zmiany_hasla(adres_konta: str) -> tuple[str, str]:
    """Powiadomienie o zmianie hasła – klient widzi zmianę, której sam nie zlecił."""
    temat = "Danaco Nexus – hasło zostało zmienione"
    tresc = (
        "Hasło do konta w portalu Danaco Nexus zostało właśnie zmienione. Wszystkie sesje tego\n"
        "konta zostały zakończone – zaloguj się nowym hasłem.\n\n"
        f"Jeżeli zmiana nie pochodzi od Ciebie, natychmiast ustaw nowe hasło pod adresem:\n{adres_konta}"
    )
    return temat, tresc


def tresc_usuniecia_konta() -> tuple[str, str]:
    """Potwierdzenie usunięcia konta klienta."""
    temat = "Danaco Nexus – konto zostało usunięte"
    tresc = (
        "Konto w portalu Danaco Nexus zostało usunięte razem z danymi profilu i sesjami.\n"
        "Operacji nie da się cofnąć – aby wrócić, załóż konto od nowa.\n\n"
        "Jeżeli usunięcie nie pochodzi od Ciebie, napisz do nas przez formularz kontaktowy."
    )
    return temat, tresc


def wyslij(settings: Settings, portal: PortalSettings, odbiorca: str, temat: str, tresc: str) -> None:
    """Wysyła wiadomość portalu; przy błędzie wysyłki treść trafia do dziennika, nie ginie."""
    try:
        nadawca(settings, portal).wyslij(odbiorca, temat, tresc)
    except BladWysylki:
        logger.warning("Wysyłka poczty portalu nie powiodła się – treść trafia do dziennika.")
        NadawcaDoDziennika().wyslij(odbiorca, temat, tresc)
