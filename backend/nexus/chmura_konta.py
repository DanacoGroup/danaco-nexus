"""Własne konta Nextcloud dla kont klientów, których plan obejmuje synchronizację.

Instalacja ma w Nextcloud konto techniczne i w nim foldery ``/Konta/<owner>``. To wystarcza,
dopóki klient sięga do plików wyłącznie przez Nexusa. Synchronizacja z komputerem
i telefonem (aplikacje Nextcloud) wymaga jednak logowania do Nextcloud — a konto
techniczne widzi przestrzenie wszystkich. Dlatego konto z planem, który sprzedaje
synchronizację, dostaje w Nextcloud własne konto ``nexus-<owner>`` z limitem przestrzeni
planu. Pliki z folderu ``/Konta/<owner>`` przechodzą tam przy założeniu konta.

Hasło konta Nextcloud zna wyłącznie Nexus (plik obok hasła aplikacji konta technicznego).
Człowiek loguje się do chmury przez Nexusa: logowanie jednokrotne podaje Nextcloud nazwę
konta, a aplikacje Nextcloud przechodzą przez to samo logowanie w przeglądarce.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit
from xml.sax.saxutils import escape

import httpx

from nexus.config import Settings
from nexus.db import ADMIN_OWNER
from nexus.tools.cloud import katalog_konta

logger = logging.getLogger(__name__)

PRZEDROSTEK_UID = "nexus-"
TIMEOUT = httpx.Timeout(30.0, read=300.0)
DAV = "{DAV:}"


# Jedno zakładanie konta naraz: dwa równoległe żądania tego samego konta dawały drugie
# „konto już jest”, a nadanie nowego hasła unieważniało hasło zapisane przez pierwsze.
_blokady: dict[str, asyncio.Lock] = {}


class BladKontaChmury(Exception):
    """Nextcloud nie założył konta albo nie przyjął ustawień."""


@dataclass(frozen=True)
class KontoChmury:
    uid: str
    haslo: str


def uid_konta(owner: uuid.UUID) -> str:
    """Nazwa konta Nextcloud dla konta Nexusa (stała, bez danych osobowych)."""
    return f"{PRZEDROSTEK_UID}{owner.hex}"


def _katalog_hasel(settings: Settings) -> Path:
    return settings.chmura_token_file.parent / "chmura-konta"


def _znacznik_przeniesienia(settings: Settings, uid: str) -> Path:
    return _katalog_hasel(settings) / f"{uid}.przeniesione"


def _znacznik_kalendarzy(settings: Settings, uid: str) -> Path:
    return _katalog_hasel(settings) / f"{uid}.kalendarze"


def _zapisany_limit(settings: Settings, uid: str) -> Path:
    return _katalog_hasel(settings) / f"{uid}.limit"


def konto_chmury(settings: Settings, owner: uuid.UUID) -> KontoChmury | None:
    """Założone wcześniej konto Nextcloud konta Nexusa albo ``None``.

    Właściciel instalacji zawsze pracuje na koncie technicznym, więc dla niego ``None``.
    """
    if owner == ADMIN_OWNER:
        return None
    uid = uid_konta(owner)
    try:
        haslo = (_katalog_hasel(settings) / uid).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return KontoChmury(uid, haslo) if haslo else None


def _zapisz_haslo(settings: Settings, uid: str, haslo: str) -> None:
    katalog = _katalog_hasel(settings)
    katalog.mkdir(mode=0o700, parents=True, exist_ok=True)
    tymczasowy = katalog / f".{uid}.nowy"
    deskryptor = os.open(tymczasowy, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(deskryptor, "w", encoding="utf-8") as plik:
        plik.write(haslo + "\n")
    tymczasowy.replace(katalog / uid)


def usun_haslo(settings: Settings, uid: str) -> None:
    """Zapomina hasło i znacznik przeniesienia konta Nextcloud (po jego usunięciu)."""
    for plik in (
        _katalog_hasel(settings) / uid,
        _znacznik_przeniesienia(settings, uid),
        _znacznik_kalendarzy(settings, uid),
        _zapisany_limit(settings, uid),
    ):
        plik.unlink(missing_ok=True)


def _klient_techniczny(settings: Settings, transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    token = settings.chmura_token_file.read_text(encoding="utf-8").strip()
    return httpx.AsyncClient(
        base_url=settings.chmura_url.rstrip("/"),
        auth=(settings.chmura_user, token),
        timeout=TIMEOUT,
        follow_redirects=False,
        transport=transport,
    )


#: Wywołanie ``occ`` — argumenty i dodatkowe zmienne środowiska; zwraca kod wyjścia i wyjście.
Occ = Callable[[list[str], dict[str, str]], Awaitable[tuple[int, str]]]


def occ_uslugi(settings: Settings) -> Occ:
    """``occ`` przez skrypt ``deploy/chmura/occ.sh`` (proces działa jako konto usługi).

    Zakładanie kont idzie przez ``occ``, a nie przez API OCS: API wymaga potwierdzenia hasła
    logowania, a konto techniczne ma wyłącznie hasło aplikacji (odpowiedź 403).
    """

    async def wywolaj(argumenty: list[str], srodowisko: dict[str, str]) -> tuple[int, str]:
        proces = await asyncio.create_subprocess_exec(
            str(settings.chmura_occ),
            *argumenty,
            env={**os.environ, **srodowisko},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            wyjscie, _ = await asyncio.wait_for(proces.communicate(), timeout=120)
        except TimeoutError:
            # Zawieszony occ nie może zostać w tle z hasłem konta w środowisku.
            proces.kill()
            await proces.wait()
            return 124, "occ nie odpowiedział w 120 s"
        return proces.returncode or 0, wyjscie.decode("utf-8", errors="replace")

    return wywolaj


async def zapewnij_konto(
    settings: Settings,
    owner: uuid.UUID,
    przestrzen_mb: int,
    transport: httpx.AsyncBaseTransport | None = None,
    occ: Occ | None = None,
) -> KontoChmury:
    """Konto Nextcloud konta Nexusa — zakłada je przy pierwszym użyciu i ustawia limit planu.

    Nowe konto dostaje pliki z folderu ``/Konta/<owner>`` konta technicznego.
    """
    if owner == ADMIN_OWNER:
        raise BladKontaChmury("Właściciel instalacji pracuje na koncie technicznym chmury.")
    occ = occ or occ_uslugi(settings)
    uid = uid_konta(owner)
    async with _blokady.setdefault(uid, asyncio.Lock()), _klient_techniczny(settings, transport) as http:
        konto = konto_chmury(settings, owner)
        if konto is None:
            haslo = secrets.token_urlsafe(32)
            haslo_env = {"OC_PASS": haslo}
            kod, wyjscie = await occ(
                ["user:add", "--password-from-env", "--display-name", "Nexus", uid], haslo_env
            )
            if kod != 0 and "already exists" in wyjscie:
                # Konto jest, ale Nexus zgubił hasło (np. odtworzony katalog danych):
                # nadajemy nowe, zamiast zakładać drugie konto obok.
                kod, wyjscie = await occ(["user:resetpassword", "--password-from-env", uid], haslo_env)
            if kod != 0:
                raise BladKontaChmury(f"Nextcloud nie założył konta {uid}: {wyjscie.strip()[-300:]}")
            _zapisz_haslo(settings, uid, haslo)
            konto = KontoChmury(uid, haslo)
            logger.info("Założono konto chmury %s", uid)
        # Przeniesienie przerwane w połowie (awaria sieci, restart) jest powtarzane przy
        # następnym wywołaniu; znacznik powstaje dopiero po całym przeniesieniu.
        if not _znacznik_przeniesienia(settings, uid).exists():
            await przenies_pliki(settings, owner, konto, http, transport)
            _znacznik_przeniesienia(settings, uid).touch()
        if not _znacznik_kalendarzy(settings, uid).exists():
            await przenies_kalendarze(settings, owner, konto, http, transport)
            _znacznik_kalendarzy(settings, uid).touch()
        kod, wyjscie = await occ(["user:setting", uid, "files", "quota", f"{max(przestrzen_mb, 1)} MB"], {})
        if kod != 0:
            raise BladKontaChmury(f"Nextcloud nie przyjął limitu konta {uid}: {wyjscie.strip()[-300:]}")
        _zapisany_limit(settings, uid).write_text(str(przestrzen_mb), encoding="utf-8")
    return konto


async def przenies_pliki(
    settings: Settings,
    owner: uuid.UUID,
    konto: KontoChmury,
    techniczny: httpx.AsyncClient,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    """Kopiuje ``/Konta/<owner>`` konta technicznego do nowego konta i usuwa oryginał.

    Oryginał trafia do kosza konta technicznego, więc przez czas przechowywania kosza da się
    go odzyskać. Zwraca liczbę przeniesionych plików.
    """
    zrodlo = f"/remote.php/dav/files/{quote(settings.chmura_user)}{quote(katalog_konta(owner))}"
    baza = unquote(zrodlo).rstrip("/")
    katalogi: list[str] = []
    pliki: list[str] = []
    do_przejrzenia = [""]
    while do_przejrzenia:
        biezacy = do_przejrzenia.pop()
        adres = zrodlo + quote(biezacy) + "/"
        odpowiedz = await techniczny.request("PROPFIND", adres, headers={"Depth": "1"})
        if odpowiedz.status_code == 404 and not biezacy:
            return 0
        if odpowiedz.status_code != 207:
            raise BladKontaChmury(f"Nie da się odczytać plików konta ({odpowiedz.status_code}).")
        for element in ET.fromstring(odpowiedz.content).findall(f"{DAV}response"):
            sciezka = unquote(urlsplit(element.findtext(f"{DAV}href", "")).path).rstrip("/")
            wzgledna = sciezka.removeprefix(baza)
            if wzgledna in ("", biezacy):
                continue
            if element.find(f"{DAV}propstat/{DAV}prop/{DAV}resourcetype/{DAV}collection") is not None:
                katalogi.append(wzgledna)
                do_przejrzenia.append(wzgledna)
            else:
                pliki.append(wzgledna)

    cel = f"/remote.php/dav/files/{quote(konto.uid)}"
    async with httpx.AsyncClient(
        base_url=settings.chmura_url.rstrip("/"),
        auth=(konto.uid, konto.haslo),
        timeout=TIMEOUT,
        follow_redirects=False,
        transport=transport,
    ) as uzytkownik:
        for katalog in sorted(katalogi, key=lambda s: s.count("/")):
            response = await uzytkownik.request("MKCOL", cel + quote(katalog))
            if response.status_code not in (201, 405):
                raise BladKontaChmury(f"Nie da się założyć folderu {katalog} ({response.status_code}).")
        for plik in pliki:
            async with techniczny.stream("GET", zrodlo + quote(plik)) as pobranie:
                if pobranie.status_code != 200:
                    raise BladKontaChmury(f"Nie da się pobrać {plik} ({pobranie.status_code}).")
                zapis = await uzytkownik.put(cel + quote(plik), content=pobranie.aiter_bytes())
            if zapis.status_code not in (201, 204):
                raise BladKontaChmury(f"Nie da się zapisać {plik} ({zapis.status_code}).")
    usuniecie = await techniczny.request("DELETE", zrodlo)
    if usuniecie.status_code not in (204, 404):
        logger.warning("Folder %s został po przeniesieniu (%s)", zrodlo, usuniecie.status_code)
    logger.info("Przeniesiono %s plików do konta chmury %s", len(pliki), konto.uid)
    return len(pliki)


CALDAV = "{urn:ietf:params:xml:ns:caldav}"
WSZYSTKIE_WYDARZENIA = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
    "<d:prop><c:calendar-data/></d:prop>"
    '<c:filter><c:comp-filter name="VCALENDAR"/></c:filter>'
    "</c:calendar-query>"
)
LISTA_KALENDARZY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:displayname/></d:prop></d:propfind>'
)


async def przenies_kalendarze(
    settings: Settings,
    owner: uuid.UUID,
    konto: KontoChmury,
    techniczny: httpx.AsyncClient,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    """Przenosi kalendarze ``konto-<owner>-*`` z konta technicznego do konta klienta.

    Kalendarz dostaje w nowym koncie nazwę bez przedrostka, wydarzenia przechodzą jako te
    same pliki .ics, a oryginał trafia do kosza konta technicznego. Zwraca liczbę wydarzeń.
    """
    from nexus.calendar import przedrostek_konta

    przedrostek = przedrostek_konta(owner)
    zrodlo = f"/remote.php/dav/calendars/{quote(settings.chmura_user)}/"
    cel = f"/remote.php/dav/calendars/{quote(konto.uid)}/"
    odpowiedz = await techniczny.request(
        "PROPFIND",
        zrodlo,
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=LISTA_KALENDARZY,
    )
    if odpowiedz.status_code != 207:
        raise BladKontaChmury(f"Nie da się odczytać kalendarzy konta ({odpowiedz.status_code}).")
    kalendarze: list[tuple[str, str]] = []
    for element in ET.fromstring(odpowiedz.content).findall(f"{DAV}response"):
        nazwa = unquote(urlsplit(element.findtext(f"{DAV}href", "")).path).rstrip("/").rsplit("/", 1)[-1]
        prop = element.find(f"{DAV}propstat/{DAV}prop")
        if prop is None or prop.find(f"{DAV}resourcetype/{CALDAV}calendar") is None:
            continue
        if nazwa.startswith(przedrostek):
            kalendarze.append((nazwa, prop.findtext(f"{DAV}displayname") or "Kalendarz"))
    przeniesione = 0
    async with httpx.AsyncClient(
        base_url=settings.chmura_url.rstrip("/"),
        auth=(konto.uid, konto.haslo),
        timeout=TIMEOUT,
        follow_redirects=False,
        transport=transport,
    ) as uzytkownik:
        for nazwa, wyswietlana in kalendarze:
            nowa = nazwa.removeprefix(przedrostek) or settings.kalendarz_default
            utworz = await uzytkownik.request(
                "MKCALENDAR",
                cel + quote(nowa) + "/",
                headers={"Content-Type": "application/xml; charset=utf-8"},
                content=(
                    '<?xml version="1.0" encoding="utf-8"?>'
                    '<c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
                    f"<d:set><d:prop><d:displayname>{escape(wyswietlana)}</d:displayname>"
                    '<c:supported-calendar-component-set><c:comp name="VEVENT"/>'
                    "</c:supported-calendar-component-set></d:prop></d:set></c:mkcalendar>"
                ).encode(),
            )
            if utworz.status_code not in (201, 405):
                raise BladKontaChmury(f"Nie da się założyć kalendarza {nowa} ({utworz.status_code}).")
            wydarzenia = await techniczny.request(
                "REPORT",
                zrodlo + quote(nazwa) + "/",
                headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
                content=WSZYSTKIE_WYDARZENIA,
            )
            if wydarzenia.status_code != 207:
                raise BladKontaChmury(
                    f"Nie da się odczytać wydarzeń kalendarza {nazwa} ({wydarzenia.status_code})."
                )
            for element in ET.fromstring(wydarzenia.content).findall(f"{DAV}response"):
                dane = element.findtext(f"{DAV}propstat/{DAV}prop/{CALDAV}calendar-data")
                plik = unquote(urlsplit(element.findtext(f"{DAV}href", "")).path).rsplit("/", 1)[-1]
                if not dane or not plik:
                    continue
                zapis = await uzytkownik.put(
                    cel + quote(nowa) + "/" + quote(plik),
                    content=dane.encode("utf-8"),
                    headers={"Content-Type": "text/calendar; charset=utf-8"},
                )
                if zapis.status_code not in (201, 204):
                    raise BladKontaChmury(f"Nie da się zapisać wydarzenia {plik} ({zapis.status_code}).")
                przeniesione += 1
            await techniczny.request("DELETE", zrodlo + quote(nazwa) + "/")
    logger.info("Przeniesiono %s wydarzeń do kalendarzy konta %s", przeniesione, konto.uid)
    return przeniesione


async def konto_wedlug_planu(
    settings: Settings,
    database: Any,
    owner: uuid.UUID,
    transport: httpx.AsyncBaseTransport | None = None,
    odswiez: bool = False,
) -> KontoChmury | None:
    """Konto Nextcloud konta klienta: istniejące albo zakładane, gdy plan obejmuje synchronizację.

    Konto zostaje także po zmianie planu na niższy — pliki i kalendarze są w nim i nie mogą
    zniknąć. ``odswiez`` ponawia ustawienie limitu przestrzeni (ekrany synchronizacji).
    """
    from nexus.platnosci.uprawnienia import limity_uzytkownika

    if owner == ADMIN_OWNER:
        return None
    istniejace = konto_chmury(settings, owner)
    limity = await limity_uzytkownika(database, str(owner))
    if istniejace is not None:
        # Limit przestrzeni idzie za planem: po zmianie planu Nextcloud dostaje nowy limit
        # przy najbliższym wejściu, także po obniżeniu planu (konto i pliki zostają).
        try:
            zapisany = int(_zapisany_limit(settings, istniejace.uid).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            zapisany = -1
        if zapisany == limity.przestrzen_mb and not odswiez:
            return istniejace
        try:
            return await zapewnij_konto(settings, owner, limity.przestrzen_mb, transport)
        except (BladKontaChmury, httpx.HTTPError, OSError) as blad:
            # Konto już jest: nieudane uzgodnienie limitu nie może odciąć klienta od plików.
            logger.warning("Nie udało się uzgodnić limitu konta %s: %s", istniejace.uid, blad)
            return istniejace
    if not limity.synchronizacja:
        return None
    return await zapewnij_konto(settings, owner, limity.przestrzen_mb, transport)


async def uzgodnij_limit_po_zmianie_planu(settings: Settings, database: Any, owner: uuid.UUID) -> None:
    """Po zdarzeniu subskrypcji: konto z własnym Nextcloudem dostaje limit nowego planu od razu.

    Bez tego klient, który synchronizuje wyłącznie aplikacją Nextcloud na komputerze, zostawał
    ze starym limitem do czasu wejścia do Nexusa. Konto bez własnego Nextclouda — bez zmian.
    """
    if owner == ADMIN_OWNER or konto_chmury(settings, owner) is None:
        return
    await konto_wedlug_planu(settings, database, owner)
