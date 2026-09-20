"""Przebieg scenariusza: wykonanie na żywo albo odtworzenie nagrania.

Na żywo każdy krok wywołuje narzędzie agenta (albo model) i mierzy własny czas.
Bez modelu lub programów scenariusz jest odtwarzany z pliku w ``przyklady/nagrania``;
wynik niesie wtedy tryb ``odtworzenie``, który interfejs pokazuje jako pokaz.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexus.config import Settings
from nexus.demo import model as model_cli
from nexus.demo.gotowosc import NA_ZYWO, ODTWORZENIE
from nexus.demo.scenariusze import NAGRANIA, Krok, Postep, Scenariusz
from nexus.demo.sesje import BladPiaskownicy, DemoPlik, DemoSesja, Piaskownica, bezpieczna_nazwa
from nexus.tools.base import FileRef, OutputFile, ToolCancelled, ToolContext, ToolError, ToolResult

logger = logging.getLogger(__name__)

LIMIT_PRZEBIEGU_S = 420
# Odtworzenie nie udaje prawdziwych czasów: krok trwa ułamek nagranego czasu, a w interfejsie
# widoczny jest czas z nagrania i wyraźne oznaczenie pokazu.
ODTWORZENIE_MNOZNIK = 0.12
ODTWORZENIE_MAX_S = 1.4
FINALNE = frozenset({"gotowe", "blad", "anulowane"})


@dataclass(slots=True)
class StanKroku:
    """Stan jednego kroku widoczny w interfejsie."""

    etykieta: str
    narzedzie: str
    rodzaj: str
    stan: str = "czeka"
    czas_ms: int = 0
    opis: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "etykieta": self.etykieta,
            "narzedzie": self.narzedzie,
            "rodzaj": self.rodzaj,
            "stan": self.stan,
            "czas_ms": self.czas_ms,
            "opis": self.opis,
        }


class Przebieg:
    """Jeden przebieg scenariusza wraz z rozgłaszaniem stanu do interfejsu."""

    def __init__(self, scenariusz: Scenariusz, tryb: str) -> None:
        self.id = uuid.uuid4().hex
        self.scenariusz = scenariusz.id
        self.tryb = tryb
        self.kroki = [StanKroku(krok.etykieta, krok.narzedzie, krok.rodzaj) for krok in scenariusz.kroki]
        self.stan = "trwa"
        self.odpowiedz = ""
        self.pliki: list[dict[str, Any]] = []
        self.blad = ""
        self.anuluj = threading.Event()
        self.zadanie: asyncio.Task[None] | None = None
        self._sluchacze: list[asyncio.Queue[dict[str, Any]]] = []

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenariusz": self.scenariusz,
            "tryb": self.tryb,
            "stan": self.stan,
            "kroki": [krok.payload() for krok in self.kroki],
            "odpowiedz": self.odpowiedz,
            "pliki": self.pliki,
            "blad": self.blad,
        }

    def rozglos(self) -> None:
        """Wysyła bieżący stan wszystkim otwartym strumieniom."""
        dane = self.payload()
        for kolejka in list(self._sluchacze):
            kolejka.put_nowait(dane)

    def subskrybuj(self) -> asyncio.Queue[dict[str, Any]]:
        """Nowy strumień stanu; pierwszy element to stan bieżący."""
        kolejka: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        kolejka.put_nowait(self.payload())
        self._sluchacze.append(kolejka)
        return kolejka

    def odsubskrybuj(self, kolejka: asyncio.Queue[dict[str, Any]]) -> None:
        if kolejka in self._sluchacze:
            self._sluchacze.remove(kolejka)


@dataclass(slots=True)
class Wykonanie:
    """Zależności przebiegu (osobno, aby dały się podmienić w testach)."""

    settings: Settings
    piaskownica: Piaskownica
    uruchamiacz_modelu: model_cli.Uruchamiacz | None = None
    pauza: bool = True


def ustawienia_demo(settings: Settings) -> Settings:
    """Ustawienia narzędzi dla pokazu: osobna kolekcja bazy wiedzy."""
    return settings.model_copy(update={"qdrant_collection": f"{settings.qdrant_collection}_demo"})


def _tekst_wyniku(wynik: ToolResult) -> str:
    """Tekst wyniku narzędzia przekazywany dalej (modelowi albo do podsumowania)."""
    dane = wynik.data
    if isinstance(dane, str):
        return dane
    for klucz in ("text", "transcript", "content"):
        wartosc = dane.get(klucz)
        if isinstance(wartosc, str) and wartosc.strip():
            return wartosc
    return json.dumps(dane, ensure_ascii=False, default=str)


def _opis_wyniku(wynik: ToolResult) -> str:
    return wynik.summary.strip()[:300]


def _kontekst(settings: Settings, sesja: DemoSesja, anuluj: threading.Event) -> ToolContext:
    """Kontekst narzędzia widzący wyłącznie pliki tej sesji gościa."""

    def znajdz(file_id: uuid.UUID) -> FileRef:
        plik = sesja.pliki.get(str(file_id))
        if plik is None or not plik.sciezka.is_file():
            raise ToolError("Ten plik nie należy do sesji pokazu.")
        return FileRef(file_id, plik.nazwa, plik.mime, plik.rozmiar, plik.sciezka, {})

    return ToolContext(
        settings,
        uuid.uuid4(),
        resolve_file=znajdz,
        cancel=anuluj,
        progress=lambda _: None,
    )


def _zapisz_wyniki(sesja: DemoSesja, pliki: list[OutputFile]) -> list[DemoPlik]:
    """Przenosi pliki wynikowe narzędzia do katalogu sesji gościa."""
    zapisane: list[DemoPlik] = []
    for wyjscie in pliki:
        if not wyjscie.path.is_file():
            continue
        nazwa = bezpieczna_nazwa(wyjscie.name)
        file_id = str(uuid.uuid4())
        cel = sesja.katalog_plikow() / f"{file_id}{Path(nazwa).suffix.lower()}"
        shutil.move(str(wyjscie.path), cel)
        plik = DemoPlik(
            id=file_id,
            nazwa=nazwa,
            mime=_mime(nazwa),
            rozmiar=cel.stat().st_size,
            sciezka=cel,
            zrodlo="wynik",
        )
        sesja.pliki[file_id] = plik
        zapisane.append(plik)
    return zapisane


def _mime(nazwa: str) -> str:
    from nexus.storage import guess_mime

    return guess_mime(nazwa)


def _krok_narzedzia(
    wykonanie: Wykonanie, sesja: DemoSesja, krok: Krok, postep: Postep, anuluj: threading.Event
) -> tuple[str, list[str], str]:
    """Wywołuje narzędzie agenta; zwraca opis, identyfikatory plików i tekst wyniku."""
    from nexus.tools import registry

    narzedzie = registry.get(krok.narzedzie)
    argumenty = krok.argumenty(postep) if krok.argumenty else {}
    wejscie = narzedzie.parse(argumenty)
    settings = ustawienia_demo(wykonanie.settings)
    kontekst = _kontekst(settings, sesja, anuluj)
    try:
        wynik = narzedzie.handler(kontekst, wejscie)
        zapisane = _zapisz_wyniki(sesja, wynik.files)
    finally:
        kontekst.cleanup()
    if krok.narzedzie == "index_documents":
        sesja.zaindeksowane.extend(uuid.UUID(file_id) for file_id in argumenty.get("file_ids", []))
    return _opis_wyniku(wynik), [plik.id for plik in zapisane], _tekst_wyniku(wynik)


def _krok_modelu(wykonanie: Wykonanie, sesja: DemoSesja, krok: Krok, postep: Postep) -> str:
    """Zadaje modelowi pytanie kroku i zwraca odpowiedź."""
    pytanie = krok.polecenie(postep) if krok.polecenie else ""
    katalog = sesja.katalog / "model"
    return model_cli.zapytaj(wykonanie.settings, pytanie, katalog, wykonanie.uruchamiacz_modelu)


async def _na_zywo(
    wykonanie: Wykonanie, sesja: DemoSesja, scenariusz: Scenariusz, przebieg: Przebieg, wejscie: list[str]
) -> None:
    """Wykonuje kolejne kroki scenariusza narzędziami serwera."""
    postep = Postep(wejscie=list(wejscie))
    wyniki: list[DemoPlik] = []
    for numer, krok in enumerate(scenariusz.kroki):
        stan = przebieg.kroki[numer]
        stan.stan = "trwa"
        przebieg.rozglos()
        start = time.monotonic()
        if krok.narzedzie:
            opis, pliki, tekst = await asyncio.to_thread(
                _krok_narzedzia, wykonanie, sesja, krok, postep, przebieg.anuluj
            )
        else:
            tekst = await asyncio.to_thread(_krok_modelu, wykonanie, sesja, krok, postep)
            opis, pliki = "Odpowiedź modelu", []
        stan.czas_ms = int((time.monotonic() - start) * 1000)
        stan.stan, stan.opis = "gotowe", opis
        postep.pliki.append(pliki)
        postep.teksty.append(tekst)
        if krok.rodzaj == "model":
            przebieg.odpowiedz = tekst
        wyniki.extend(sesja.pliki[file_id] for file_id in pliki)
        przebieg.pliki = [_plik_payload(plik) for plik in wyniki]
        przebieg.rozglos()
    if not przebieg.odpowiedz:
        przebieg.odpowiedz = postep.tekst(len(scenariusz.kroki) - 1)[:2000]


def _plik_payload(plik: DemoPlik) -> dict[str, Any]:
    return {
        "id": plik.id,
        "nazwa": plik.nazwa,
        "mime": plik.mime,
        "rozmiar": plik.rozmiar,
        "adres": f"/api/demo/pliki/{plik.id}",
    }


def wczytaj_nagranie(scenariusz: Scenariusz) -> dict[str, Any]:
    """Nagrany przebieg scenariusza (kroki, czasy, odpowiedź, pliki wynikowe)."""
    try:
        return json.loads(scenariusz.nagranie.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BladPiaskownicy("Nagranie tego scenariusza jest niedostępne.", 503) from error


async def _odtworzenie(
    wykonanie: Wykonanie, sesja: DemoSesja, scenariusz: Scenariusz, przebieg: Przebieg
) -> None:
    """Odtwarza nagrany przebieg: kroki z zapisanymi czasami i gotowe pliki wynikowe."""
    nagranie = wczytaj_nagranie(scenariusz)
    zapisane: list[dict[str, Any]] = []
    for numer, zapis in enumerate(nagranie.get("kroki", [])):
        if numer >= len(przebieg.kroki):
            break
        stan = przebieg.kroki[numer]
        stan.stan = "trwa"
        przebieg.rozglos()
        czas_ms = int(zapis.get("czas_ms", 0))
        if wykonanie.pauza:
            await asyncio.sleep(min(czas_ms / 1000 * ODTWORZENIE_MNOZNIK, ODTWORZENIE_MAX_S))
        stan.czas_ms = czas_ms
        stan.stan, stan.opis = "gotowe", str(zapis.get("opis", ""))[:300]
        przebieg.rozglos()
    for zapis in nagranie.get("pliki", []):
        plik = _skopiuj_z_nagrania(sesja, str(zapis.get("plik", "")))
        if plik is not None:
            zapisane.append(_plik_payload(plik))
    przebieg.odpowiedz = str(nagranie.get("odpowiedz", ""))
    przebieg.pliki = zapisane


def _skopiuj_z_nagrania(sesja: DemoSesja, wzgledna: str) -> DemoPlik | None:
    """Kopiuje plik nagrania do katalogu sesji (ścieżka musi zostać w katalogu nagrań)."""
    if not wzgledna:
        return None
    zrodlo = (NAGRANIA / "pliki" / wzgledna).resolve()
    if not zrodlo.is_file() or not zrodlo.is_relative_to((NAGRANIA / "pliki").resolve()):
        logger.warning("Nagranie wskazuje plik spoza katalogu nagrań: %s", wzgledna)
        return None
    file_id = str(uuid.uuid4())
    cel = sesja.katalog_plikow() / f"{file_id}{zrodlo.suffix.lower()}"
    shutil.copyfile(zrodlo, cel)
    plik = DemoPlik(
        id=file_id,
        nazwa=zrodlo.name,
        mime=_mime(zrodlo.name),
        rozmiar=cel.stat().st_size,
        sciezka=cel,
        zrodlo="nagranie",
    )
    sesja.pliki[file_id] = plik
    return plik


def uruchom(
    wykonanie: Wykonanie, sesja: DemoSesja, scenariusz: Scenariusz, tryb: str, wejscie: list[str]
) -> Przebieg:
    """Startuje przebieg scenariusza i zwraca jego stan (praca idzie w tle)."""
    trwajace = [item for item in sesja.przebiegi.values() if item.stan == "trwa"]
    if len(trwajace) >= wykonanie.piaskownica.limity.przebiegow_rownolegle:
        raise BladPiaskownicy("Poczekaj na zakończenie bieżącego przebiegu.", 429)
    przebieg = Przebieg(scenariusz, tryb)
    sesja.przebiegi[przebieg.id] = przebieg

    async def praca() -> None:
        try:
            if tryb == NA_ZYWO:
                await asyncio.wait_for(
                    _na_zywo(wykonanie, sesja, scenariusz, przebieg, wejscie), LIMIT_PRZEBIEGU_S
                )
            else:
                await _odtworzenie(wykonanie, sesja, scenariusz, przebieg)
            przebieg.stan = "gotowe"
        except TimeoutError:
            przebieg.anuluj.set()
            przebieg.stan, przebieg.blad = "blad", "Przebieg przekroczył limit czasu pokazu."
        except (ToolCancelled, asyncio.CancelledError):
            przebieg.stan, przebieg.blad = "anulowane", "Przebieg przerwany."
        except (ToolError, BladPiaskownicy, model_cli.BladModelu) as error:
            przebieg.stan, przebieg.blad = "blad", str(error)[:300]
        except Exception:  # noqa: BLE001 - błąd pokazu trafia do interfejsu
            # Treść nieprzewidzianego wyjątku (ścieżki, zapytania, dane połączeń) zostaje
            # w dzienniku: przebieg zleca gość bez konta, a widzi go każdy odwiedzający.
            logger.exception("Błąd przebiegu pokazu %s", scenariusz.id)
            przebieg.stan, przebieg.blad = "blad", "Błąd wewnętrzny pokazu. Spróbuj ponownie."
        finally:
            _oznacz_finalne(przebieg)
            przebieg.rozglos()

    przebieg.zadanie = asyncio.get_running_loop().create_task(praca())
    return przebieg


def _oznacz_finalne(przebieg: Przebieg) -> None:
    """Kroki, które nie zdążyły się wykonać, dostają stan końcowy."""
    for krok in przebieg.kroki:
        if krok.stan in {"czeka", "trwa"}:
            krok.stan = "gotowe" if przebieg.stan == "gotowe" else "blad"


def tryb_scenariusza(scenariusz: Scenariusz, braki: list[str]) -> str:
    """Tryb pracy scenariusza: na żywo albo odtworzenie nagrania."""
    if braki:
        return ODTWORZENIE
    return NA_ZYWO if scenariusz.kroki else ODTWORZENIE
