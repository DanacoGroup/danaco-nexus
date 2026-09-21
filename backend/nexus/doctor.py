"""Diagnostyka środowiska: baza, usługi pomocnicze, programy narzędziowe, Claude Code CLI.

Każda kontrola zwraca wynik z opisem. Bez ``--online`` żadna nie korzysta
z modelu; z ``--online`` CLI wykonuje jedno krótkie zapytanie testowe.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import httpx

from nexus.config import Settings
from nexus.db import Database
from nexus.ocr.pdf_processor import PdfProcessingError, find_text_layer_font

REQUIRED_TESSERACT_LANGUAGES = ("pol", "eng", "osd")
TOKEN_PATTERN = re.compile(r"sk-ant-oat01-[A-Za-z0-9_-]{60,}")
PROGRAMS = ("soffice", "ffmpeg", "ffprobe", "magick", "unpaper", "inkscape")
#: Programy wywoływane przez narzędzia agenta przez ``_program()``. Narzędzie widnieje
#: w rejestrze niezależnie od tego, czy jego program jest na ścieżce — brak wychodzi
#: dopiero przy wywołaniu, komunikatem „… jest niedostępne na tym serwerze”, czyli już
#: przy użytkowniku. Dlatego pyta o nie diagnostyka. Zgodności tej listy ze źródłami
#: pilnuje ``backend/tests/test_tools.py``.
PROGRAMY_NARZEDZI = (
    "danaco-dokument-na-tekst",
    "danaco-glebia",
    "danaco-koloryzacja",
    "danaco-lottie",
    "danaco-odszum",
    "danaco-ozyw-zdjecie",
    "danaco-retusz-twarzy",
    "danaco-rozdziel-audio",
    "danaco-transkrypcja",
    "danaco-twarze-indeks",
    "danaco-usun-obiekt",
    "ffmpeg",
    "gifski",
    "gitleaks",
    "jscpd",
    "lighthouse",
    "osv-scanner",
    "oxipng",
    "pa11y",
    "pandoc",
    "playwright",
    "ruff",
    "semgrep",
    "shellcheck",
    "srt",
    "svgo",
    "typos",
    "typst",
)


@dataclass(slots=True)
class Check:
    """Wynik jednej kontroli."""

    name: str
    ok: bool
    detail: str


def _run(
    arguments: list[str], timeout: int = 60, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False, env=env)


def check_programs() -> list[Check]:
    """Obecność programów narzędziowych i języków Tesseract."""
    checks = []
    tesseract = shutil.which("tesseract")
    if tesseract:
        languages = {line.strip() for line in _run([tesseract, "--list-langs"]).stdout.splitlines()[1:]}
        missing = [lang for lang in REQUIRED_TESSERACT_LANGUAGES if lang not in languages]
        checks.append(
            Check(
                "tesseract",
                not missing,
                f"języki: {', '.join(sorted(languages))}" + (f"; brak: {missing}" if missing else ""),
            )
        )
    else:
        checks.append(Check("tesseract", False, "brak programu"))
    for program in PROGRAMS:
        path = shutil.which(program)
        checks.append(Check(program, path is not None, path or "brak programu"))
    return checks


def check_realesrgan(settings: Settings) -> Check:
    """Real-ESRGAN: plik wykonywalny, modele i test na obrazie 16×16 (Vulkan na CPU)."""
    root = settings.realesrgan_dir
    executable = root / "realesrgan-ncnn-vulkan"
    if not executable.is_file():
        return Check("real-esrgan", False, f"brak {executable}")
    from PIL import Image

    from nexus.tools.images import _lavapipe_icd

    with tempfile.TemporaryDirectory() as directory:
        source, target = Path(directory) / "a.png", Path(directory) / "b.png"
        Image.new("RGB", (16, 16), "white").save(source)
        completed = _run(
            [
                str(executable),
                "-i",
                str(source),
                "-o",
                str(target),
                "-n",
                "realesr-animevideov3-x2",
                "-s",
                "2",
                "-m",
                str(root / "models"),
            ],
            timeout=120,
            env={**os.environ, "VK_ICD_FILENAMES": _lavapipe_icd()},
        )
        ok = target.is_file()
    return Check(
        "real-esrgan",
        ok,
        "działa (Vulkan: " + (_lavapipe_icd() or "domyślny") + ")" if ok else completed.stderr.strip()[-300:],
    )


def check_font() -> Check:
    """Czcionka warstwy tekstowej PDF."""
    try:
        return Check("czcionka PDF", True, str(find_text_layer_font()))
    except PdfProcessingError as error:
        return Check("czcionka PDF", False, str(error))


def check_data_dir(settings: Settings) -> Check:
    """Katalog danych z prawem zapisu."""
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.data_dir):
            pass
        return Check("katalog danych", True, str(settings.data_dir))
    except OSError as error:
        return Check("katalog danych", False, f"{settings.data_dir}: {error}")


def check_tika_app(settings: Settings) -> Check:
    """Apache Tika w trybie wsadowym (tika-app)."""
    if not settings.tika_app_jar.is_file():
        return Check("tika", False, f"brak {settings.tika_app_jar}")
    completed = _run([settings.java_bin, "-jar", str(settings.tika_app_jar), "--version"], timeout=120)
    version = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    return Check("tika", completed.returncode == 0, version or completed.stderr.strip()[-300:])


def check_chmura(settings: Settings) -> Check:
    """Chmura osobista: Nextcloud zainstalowany i dostęp WebDAV hasłem aplikacji Nexusa."""
    from nexus.tools.base import ToolError
    from nexus.tools.cloud import CloudClient

    try:
        status = httpx.get(f"{settings.chmura_url}/status.php", timeout=10).json()
    except (httpx.HTTPError, ValueError) as error:
        return Check("chmura", False, f"{settings.chmura_url}: {error.__class__.__name__}")
    if not status.get("installed"):
        return Check("chmura", False, "Nextcloud nie jest zainstalowany")
    try:
        client = CloudClient(settings)
        try:
            entries = client.list("/")
        finally:
            client.close()
    except ToolError as error:
        return Check("chmura", False, f"Nextcloud {status.get('versionstring')}: {error}")
    return Check(
        "chmura", True, f"Nextcloud {status.get('versionstring')}, WebDAV OK ({len(entries)} pozycji)"
    )


def check_redis(settings: Settings) -> Check:
    """Redis (Valkey) projektu – powiadomienia o zdarzeniach zadań."""
    if not settings.redis_url:
        return Check("redis", True, "wyłączony (strumienie odpytują bazę)")
    import redis

    try:
        client = redis.from_url(settings.redis_url, socket_timeout=5, socket_connect_timeout=2)
        info = client.info("server")
        client.close()
    except redis.RedisError as error:
        return Check("redis", False, f"{error.__class__.__name__}: {error}"[:300])
    name = "Valkey" if info.get("valkey_version") else "Redis"
    return Check("redis", True, f"{name} {info.get('valkey_version') or info.get('redis_version')}")


def check_whisper(settings: Settings) -> Check:
    """Transkrypcja mowy: interpreter z faster-whisper i model."""
    if not Path(settings.whisper_python).is_file():
        return Check("transkrypcja", False, f"brak {settings.whisper_python}")
    if not (settings.whisper_model_dir / "model.bin").is_file():
        return Check("transkrypcja", False, f"brak modelu w {settings.whisper_model_dir}")
    completed = _run(
        [settings.whisper_python, "-c", "import faster_whisper; print(faster_whisper.__version__)"]
    )
    version = completed.stdout.strip()
    return Check(
        "transkrypcja", bool(version), f"faster-whisper {version}" if version else completed.stderr[-300:]
    )


def check_google_speech(settings: Settings) -> Check:
    """Mowa Google Cloud: lista głosów, synteza i rozpoznanie próbki (gdy zapisano klucz)."""
    from nexus.voice_google import GoogleSpeech, GoogleSpeechError

    google = GoogleSpeech(settings.voice_google_key_file)
    if not google.available():
        return Check("mowa google", True, "brak klucza – rozmowa głosowa używa modeli lokalnych")
    try:
        voices = google.voices()
        if not voices:
            return Check(
                "mowa google", False, "brak polskich głosów – sprawdź, czy Text-to-Speech API jest włączone"
            )
        audio = google.speak("Dzień dobry, tu Nexus.", voices[0]["id"])
        with tempfile.NamedTemporaryFile(suffix=".mp3") as sample:
            sample.write(audio)
            sample.flush()
            text, _ = google.transcribe(Path(sample.name))
    except (GoogleSpeechError, ValueError) as error:
        return Check("mowa google", False, str(error)[:300])
    except OSError as error:
        # Rozpoznanie mowy przepuszcza nagranie przez ffmpeg; brak programu to brak
        # programu, a nie powód do przerwania diagnostyki.
        brakujacy = error.filename or ""
        return Check("mowa google", False, f"{error.strerror or error} {brakujacy}".strip())
    finally:
        google.close()
    return Check(
        "mowa google", bool(text), f"{len(voices)} głosów ({voices[0]['name']}…), rozpoznano: „{text}”"
    )


def check_http(name: str, url: str) -> Check:
    """Dostępność usługi HTTP."""
    try:
        response = httpx.get(url, timeout=10)
        return Check(name, response.status_code < 500, f"{url} → HTTP {response.status_code}")
    except httpx.HTTPError as error:
        return Check(name, False, f"{url}: {error.__class__.__name__}")


async def check_database(settings: Settings) -> Check:
    """Połączenie z bazą i schemat."""
    database = Database(settings.database_url)
    try:
        await database.create_schema()
        return Check("baza danych", True, settings.database_url.split("@")[-1])
    except Exception as error:  # noqa: BLE001 - wynik diagnostyki
        return Check("baza danych", False, f"{error.__class__.__name__}: {error}"[:300])
    finally:
        await database.close()


# Po tylu minutach w kolejce zadanie nie czeka już na wolne miejsce, tylko na proces,
# którego nie ma. Najdłuższy przebieg ma limit dwóch godzin, ale *podjęcie* zadania to
# ułamek sekundy — proces roboczy odpytuje bazę co sekundę.
KOLEJKA_ALARM_MIN = 5


async def check_poczta_portalu(settings: Settings) -> Check:
    """Czy wiadomości portalu mają jak dotrzeć do klienta.

    Portal wysyła dwie wiadomości, bez których konta nie da się używać: potwierdzenie
    adresu przy rejestracji i odsyłacz do nowego hasła. Domyślny nadawca zapisuje je
    **do dziennika** — ekran i tak mówi „wysłaliśmy odsyłacz”, więc brak wysyłki wychodzi
    dopiero wtedy, gdy klient czeka na wiadomość, która nigdy nie przyjdzie.

    Zamknięcie rejestracji nie zdejmuje sprawy: odzyskanie hasła dotyczy kont, które już
    są. Dlatego kontrola pyta też bazę, ile ich jest.
    """
    from sqlalchemy import func, select

    from nexus import mail
    from nexus.models.portal import PortalUser
    from nexus.portal.ustawienia import NADAWCA_SMTP, portal_settings

    portal = portal_settings(settings)
    if portal.mail_sender == NADAWCA_SMTP and mail.is_configured(settings):
        return Check("poczta portalu", True, "wysyłka kontem aplikacji (SMTP)")
    powod = (
        "nadawca „dziennik”"
        if portal.mail_sender != NADAWCA_SMTP
        else "wybrano SMTP, ale konto pocztowe nie jest podłączone"
    )
    database = Database(settings.database_url)
    try:
        async with database.session() as session:
            konta = int(await session.scalar(select(func.count()).select_from(PortalUser)) or 0)
    except Exception:  # noqa: BLE001 - brak bazy rozstrzyga inna kontrola
        konta = 0
    finally:
        await database.close()
    if not portal.registration_open and not konta:
        return Check("poczta portalu", True, f"{powod}; rejestracja zamknięta i nie ma kont klientów")
    kto_czeka = (
        "potwierdzenie adresu i odzyskanie hasła nie dotrą do klienta"
        if portal.registration_open
        else f"odzyskanie hasła nie dotrze do {konta} założonych kont"
    )
    return Check("poczta portalu", False, f"{powod} — {kto_czeka}")


#: Narzędzia agenta oparte na modelach o licencji **niekomercyjnej**.
#:
#: Wpis to nazwa narzędzia i to, co blokuje jego sprzedaż. Wykaz jest krótki celowo:
#: nie prowadzimy tu spisu wszystkich zależności, tylko tych, których licencja zabrania
#: pobierania opłat. Zależność licencyjną sprawdza się przy dokładaniu modelu, nie przy
#: każdym uruchomieniu — dlatego wykaz jest ręczny, a nie czytany z dysku.
NARZEDZIA_NIEKOMERCYJNE: dict[str, str] = {
    "find_faces": "modele InsightFace — licencja wyłącznie niekomercyjna",
}


#: Poniżej tylu procent wolnego miejsca kontrola dysku zgłasza błąd.
WOLNE_MIEJSCE_PROG = 10

#: Powyżej tylu wydań na dysku warto posprzątać (`deploy/wydania/sprzataj.sh`).
WYDAN_PROG = 20


def check_miejsce(settings: Settings) -> Check:
    """Czy na dysku zostaje miejsce — i czy nie zjadają go stare wydania.

    Każde wydanie to ok. 0,65 GB, a powstaje ich po kilkanaście dziennie. Nic ich nie
    kasuje samoczynnie: `sprzataj.sh` uruchamia człowiek. Brak miejsca odbija się na
    wszystkim naraz — baza przestaje zapisywać, kopia zapasowa się nie kończy, agent nie
    ma gdzie odłożyć wyniku — a widać to dopiero po awarii. Dlatego pyta o to diagnostyka.
    """
    try:
        uzycie = shutil.disk_usage(settings.data_dir if settings.data_dir.exists() else Path("/"))
    except OSError as error:
        return Check("miejsce na dysku", False, f"nie udało się odczytać: {error}")
    wolne_gb = uzycie.free / 1024**3
    wolne_proc = uzycie.free * 100 / uzycie.total if uzycie.total else 0

    # Katalog wydań leży w korzeniu repozytorium, a nie obok danych: przedsionek trzyma
    # swoje dane **wewnątrz** `wydania/`, więc wyprowadzanie ścieżki z `data_dir` dawało
    # dla niego `wydania/wydania/wersje`. Korzeń liczymy od położenia tego modułu.
    wersje = Path(__file__).resolve().parents[2] / "wydania" / "wersje"
    ile_wydan = len(list(wersje.iterdir())) if wersje.is_dir() else 0
    ogon = f"; wydań na dysku: {ile_wydan}" if ile_wydan else ""

    if wolne_proc < WOLNE_MIEJSCE_PROG:
        rada = " — uruchom deploy/wydania/sprzataj.sh --wykonaj" if ile_wydan > WYDAN_PROG else ""
        return Check(
            "miejsce na dysku",
            False,
            f"wolne {wolne_gb:.0f} GB ({wolne_proc:.0f}%){ogon}{rada}",
        )
    if ile_wydan > WYDAN_PROG:
        return Check(
            "miejsce na dysku",
            True,
            f"wolne {wolne_gb:.0f} GB ({wolne_proc:.0f}%); {ile_wydan} wydań — "
            "warto posprzątać (deploy/wydania/sprzataj.sh)",
        )
    return Check("miejsce na dysku", True, f"wolne {wolne_gb:.0f} GB ({wolne_proc:.0f}%){ogon}")


#: Po ilu godzinach brak nowej kopii zapasowej jest błędem.
#:
#: Timer chodzi raz na dobę (`danaco-nexus-kopia.timer`), więc czterdzieści osiem godzin
#: to dwie przepuszczone doby — czyli nie „opóźnienie”, tylko coś nie działa.
KOPIA_ALARM_H = 48


#: Składniki, bez których kopia nie jest kopią. Nazwy z `deploy/kopia-zapasowa.sh`.
SKLADNIKI_KOPII = ("zrodla.tar.zst", "sekrety.tar.zst", "SUMY.sha256")
#: Poniżej tego rozmiaru plik jest urwany, a nie mały (najmniejszy z trójki to SUMY.sha256).
KOPIA_MIN_BAJTOW = 128


def check_kopia_zapasowa(settings: Settings) -> Check:
    """Czy kopia zapasowa w ogóle powstaje — i czy nie jest sprzed tygodnia.

    Kopia robi się z timera i nie mówi o sobie nic, dopóki jej nie potrzeba. Zepsuty
    timer, pełny dysk albo zmieniona ścieżka wychodzą wtedy dopiero w dniu, w którym
    trzeba coś odtworzyć — czyli najgorszym możliwym. Dlatego pyta o to diagnostyka.
    """
    katalog = settings.data_dir.parent / "kopie" if settings.data_dir.name == "app" else Path("")
    if not katalog.is_dir():
        return Check("kopia zapasowa", False, f"nie ma katalogu kopii ({katalog or 'nieznany'})")
    kopie = sorted((p for p in katalog.iterdir() if p.is_dir()), key=lambda p: p.name)
    if not kopie:
        return Check("kopia zapasowa", False, f"katalog {katalog} jest pusty — kopia nigdy nie powstała")
    najnowsza = kopie[-1]
    wiek_h = (time.time() - najnowsza.stat().st_mtime) / 3600
    opis = f"{najnowsza.name}, sprzed {wiek_h:.0f} h, kopii na dysku: {len(kopie)}"
    if wiek_h > KOPIA_ALARM_H:
        return Check("kopia zapasowa", False, f"{opis} — sprawdź danaco-nexus-kopia.timer")

    # Sama obecność katalogu nie wystarcza. Skrypt kopii kończy każdy krok `|| true`, żeby
    # jeden nieudany element nie przewrócił całego biegu — skutek uboczny jest taki, że
    # brakujący składnik nie zgłasza się sam. Najdotkliwszy byłby brak kodu: od 21 września
    # 2026 kopia obejmuje `zrodla.tar.zst`, bo drzewo robocze bywa jedynym miejscem, gdzie
    # kod istnieje (praca poza commitami).
    braki = [nazwa for nazwa in SKLADNIKI_KOPII if not (najnowsza / nazwa).is_file()]
    if braki:
        return Check("kopia zapasowa", False, f"{opis} — brakuje: {', '.join(braki)}")
    pusty = [
        nazwa
        for nazwa in SKLADNIKI_KOPII
        if (najnowsza / nazwa).stat().st_size < KOPIA_MIN_BAJTOW
    ]
    if pusty:
        return Check("kopia zapasowa", False, f"{opis} — plik pusty albo urwany: {', '.join(pusty)}")
    return Check("kopia zapasowa", True, opis)


def check_licencje_narzedzi(settings: Settings) -> Check:
    """Czy sprzedajemy dostęp do narzędzia, którego licencja zabrania sprzedaży.

    Sprzeczność powstaje sama, bez niczyjej zmiany w kodzie: wystarczy wpisać klucz Stripe.
    Narzędzie stoi w rejestrze od dawna i działa, a warunek „dopóki produkt nie jest
    sprzedawany” przestaje obowiązywać w chwili, gdy ktoś włączy sprzedaż — i nikt tego
    nie zauważa, bo nic się nie psuje. Dlatego pyta o to diagnostyka, a nie tylko dokument
    zgodności: sprzeczność ma być widoczna przy każdym wdrożeniu.
    """
    from nexus.platnosci.konfiguracja import UstawieniaPlatnosci
    from nexus.tools import registry

    obecne = [nazwa for nazwa in NARZEDZIA_NIEKOMERCYJNE if nazwa in set(registry.names())]
    if not obecne:
        return Check("licencje narzędzi", True, "żadne narzędzie niekomercyjne nie jest w rejestrze")
    platnosci = UstawieniaPlatnosci()
    if not platnosci.skonfigurowane:
        return Check(
            "licencje narzędzi",
            True,
            f"sprzedaż wyłączona; niekomercyjne: {', '.join(obecne)}",
        )
    if platnosci.tryb_probny:
        # Klucz testowy Stripe nie przyjmuje prawdziwych pieniędzy — zakupy robią testerzy
        # kartami próbnymi. To nie jest jeszcze sprzedaż w rozumieniu licencji, więc
        # kontrola mówi o stanie, zamiast zapalać czerwone światło przy każdym wdrożeniu.
        # Czerwone światło wraca samo w chwili wpisania klucza produkcyjnego.
        return Check(
            "licencje narzędzi",
            True,
            f"sprzedaż w trybie próbnym (klucz testowy Stripe); niekomercyjne: {', '.join(obecne)} "
            "— przed kluczem produkcyjnym trzeba to rozstrzygnąć",
        )
    powody = "; ".join(f"{nazwa} ({NARZEDZIA_NIEKOMERCYJNE[nazwa]})" for nazwa in obecne)
    return Check(
        "licencje narzędzi",
        False,
        f"sprzedaż włączona, a w rejestrze stoi {powody} — potrzebny model komercyjny, "
        "zgoda autorów albo wyłączenie funkcji",
    )


def check_programy_narzedzi() -> Check:
    """Czy każdy program wywoływany przez narzędzia agenta jest na ścieżce usługi."""
    brakujace = [program for program in PROGRAMY_NARZEDZI if shutil.which(program) is None]
    if not brakujace:
        return Check("programy narzędzi", True, f"{len(PROGRAMY_NARZEDZI)} programów na ścieżce")
    return Check(
        "programy narzędzi",
        False,
        f"poza ścieżką: {', '.join(brakujace)} — sprawdź PATH w .env",
    )


async def check_kolejka(settings: Settings) -> Check:
    """Czy ktokolwiek odbiera zadania z kolejki.

    Kolejką jest tabela ``runs``; zadanie czeka w stanie ``queued``, dopóki nie weźmie go
    proces roboczy. Instalacja bez procesu roboczego dla tej właśnie bazy przyjmuje zadania
    i nigdy ich nie wykonuje — API odpowiada 202, a w oknie w nieskończoność migają kropki.
    Widać to wyłącznie po zaległości w kolejce, więc kontrola pyta o nią wprost.
    """
    from sqlalchemy import func, select

    from nexus.db import Run, utcnow

    database = Database(settings.database_url)
    prog = utcnow() - timedelta(minutes=KOLEJKA_ALARM_MIN)
    try:
        async with database.session() as session:
            zalegle = await session.scalar(
                select(func.count()).select_from(Run).where(Run.status == "queued", Run.created_at < prog)
            )
            najstarsze = await session.scalar(
                select(func.min(Run.created_at)).where(Run.status == "queued", Run.created_at < prog)
            )
    except Exception as error:  # noqa: BLE001 - wynik diagnostyki
        return Check("kolejka zadań", False, f"{error.__class__.__name__}: {error}"[:300])
    finally:
        await database.close()
    if not zalegle:
        return Check("kolejka zadań", True, "brak zaległości")
    wiek = utcnow() - najstarsze if najstarsze else timedelta()
    minuty = int(wiek.total_seconds() // 60)
    return Check(
        "kolejka zadań",
        False,
        f"{zalegle} zadań czeka ponad {KOLEJKA_ALARM_MIN} min (najstarsze: {minuty} min)"
        " — sprawdź proces roboczy tej bazy",
    )


def check_claude_cli(settings: Settings) -> list[Check]:
    """Claude Code CLI: program, profil projektu i plik tokenu OAuth."""
    from nexus.agent.runner import read_oauth_token

    executable = shutil.which(settings.claude_bin)
    if not executable:
        return [Check("claude cli", False, f"brak programu {settings.claude_bin}")]
    version = _run([executable, "--version"], timeout=30).stdout.strip()
    profile = settings.claude_profile_dir
    token = read_oauth_token(profile)
    if not token:
        token_check = Check("token claude", False, f"{profile / 'oauth-token'} – brak (claude setup-token)")
    elif not TOKEN_PATTERN.fullmatch(token):
        token_check = Check(
            "token claude",
            False,
            f"{profile / 'oauth-token'} – nieprawidłowy format (oczekiwano sk-ant-oat01-…); "
            "zapisz token ponownie: deploy/zapisz-token.sh",
        )
    else:
        token_check = Check("token claude", True, f"{profile / 'oauth-token'} ({len(token)} znaków)")
    return [Check("claude cli", bool(version), f"{executable} ({version or 'brak wersji'})"), token_check]


async def _list_mcp_tools() -> list[str]:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nexus.mcp_server"],
        env={**os.environ, "NEXUS_RUN_ID": str(uuid.uuid4()), "NEXUS_CONVERSATION_ID": ""},
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
    return [tool.name for tool in result.tools]


def check_mcp_server() -> Check:
    """Serwer MCP narzędzi: uruchomienie i lista narzędzi."""
    from nexus.tools import registry

    try:
        names = asyncio.run(asyncio.wait_for(_list_mcp_tools(), 120))
    except Exception as error:  # noqa: BLE001 - wynik diagnostyki
        return Check("serwer MCP", False, f"{error.__class__.__name__}: {error}"[:300])
    expected = set(registry.names())
    missing = sorted(expected - set(names))
    return Check(
        "serwer MCP",
        not missing,
        f"{len(names)} narzędzi" + (f"; brak: {missing}" if missing else ""),
    )


def check_claude_online(settings: Settings) -> Check:
    """Krótkie zapytanie testowe przez CLI (weryfikuje token i dostęp do modelu)."""
    from nexus.agent.runner import cli_environment, friendly_error

    with tempfile.TemporaryDirectory() as directory:
        completed = _run(
            [
                settings.claude_bin,
                "-p",
                "Odpowiedz jednym słowem: OK",
                "--model",
                settings.claude_model,
                "--output-format",
                "json",
                "--no-session-persistence",
                "--strict-mcp-config",
                "--allowed-tools",
                "ToolSearch",
            ],
            timeout=180,
            env=cli_environment(settings, Path(directory)),
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    if completed.returncode == 0 and not payload.get("is_error"):
        return Check("claude online", True, f"model {settings.claude_model} odpowiada")
    return Check("claude online", False, friendly_error(completed.stdout + completed.stderr))


def run_checks(settings: Settings, online: bool = False) -> list[Check]:
    """Wykonuje wszystkie kontrole."""
    steps: list[Callable[[], Check | list[Check]]] = [
        lambda: asyncio.run(check_database(settings)),
        lambda: asyncio.run(check_kolejka(settings)),
        lambda: check_data_dir(settings),
        check_font,
        check_programs,
        check_programy_narzedzi,
        lambda: check_licencje_narzedzi(settings),
        lambda: check_miejsce(settings),
        lambda: check_kopia_zapasowa(settings),
        lambda: asyncio.run(check_poczta_portalu(settings)),
        lambda: check_realesrgan(settings),
        lambda: check_http("qdrant", f"{settings.qdrant_url}/readyz"),
        lambda: (
            check_http("tika", f"{settings.tika_url}/version")
            if settings.tika_url
            else check_tika_app(settings)
        ),
        lambda: check_http("languagetool", f"{settings.languagetool_url}/v2/languages"),
        lambda: check_redis(settings),
        lambda: check_whisper(settings),
        lambda: check_google_speech(settings),
        lambda: check_chmura(settings),
        lambda: check_claude_cli(settings),
        check_mcp_server,
    ]
    if online:
        steps.append(lambda: check_claude_online(settings))
    results: list[Check] = []
    for step in steps:
        try:
            outcome = step()
        except Exception as error:  # noqa: BLE001 - diagnostyka ma dojść do końca
            # Kontrola, która się wysypie, nie może zabrać ze sobą pozostałych: po to się
            # uruchamia diagnostykę, żeby zobaczyć **wszystko**, co nie działa, a nie
            # pierwszą rzecz, która nie działa. Wyjątek jest tu wynikiem, nie awarią.
            outcome = Check("kontrola przerwana", False, f"{error.__class__.__name__}: {error}"[:300])
        results.extend(outcome if isinstance(outcome, list) else [outcome])
    return results
