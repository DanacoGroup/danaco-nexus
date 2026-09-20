"""Narzędzia komputera użytkownika (Nexus Desktop dla Windows): pc_info, pc_find_files,
pc_read_file, pc_powershell, pc_screenshot.

Narzędzia nie działają na serwerze – żądanie trafia przez Redis do API, a stamtąd
WebSocketem do aplikacji Nexus Desktop (``nexus.pulpit``). Polecenia PowerShell
zmieniające system wykonują się dopiero po zatwierdzeniu przez użytkownika na komputerze.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Literal

from pydantic import Field

from nexus.pulpit import (
    MAX_FILE_BYTES,
    MemoryBroker,
    PcCancelled,
    PcError,
    call_computer,
    decode_images,
    sync_broker,
)
from nexus.storage import safe_filename
from nexus.tools.base import (
    OutputFile,
    ToolCancelled,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    registry,
    truncate_text,
)

COMPUTER_FIELD = Field(
    "",
    max_length=100,
    description="Nazwa komputera (gdy podłączonych jest kilka); pusto = ostatnio podłączony.",
)


class PcInput(ToolInput):
    computer: str = COMPUTER_FIELD


class PcInfoInput(PcInput):
    top_processes: int = Field(15, ge=1, le=60, description="Liczba procesów o największym zużyciu pamięci.")


class PcFindFilesInput(PcInput):
    name: str = Field(
        "",
        max_length=200,
        description="Fragment nazwy albo wzorzec z * i ?, np. 'faktura*2026*.pdf'. Pusto = dowolna nazwa.",
    )
    content: str = Field(
        "",
        max_length=200,
        description=(
            "Szukany tekst w treści (indeks wyszukiwania Windows – także DOCX/PDF/XLSX; "
            "bez indeksu tylko pliki tekstowe)."
        ),
    )
    folders: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Katalogi do przeszukania (ścieżki bezwzględne albo 'Pulpit', 'Dokumenty', 'Pobrane', 'Obrazy', "
            "'Wideo', 'Muzyka', 'OneDrive'). Pusto = wszystkie katalogi użytkownika."
        ),
    )
    extensions: list[str] = Field(
        default_factory=list, max_length=20, description="Rozszerzenia, np. ['pdf', 'docx']."
    )
    modified_after: str = Field("", max_length=10, description="Tylko pliki zmienione od daty RRRR-MM-DD.")
    limit: int = Field(50, ge=1, le=500, description="Najwięcej wyników.")


class PcReadFileInput(PcInput):
    path: str = Field(
        min_length=1, max_length=1000, description="Pełna ścieżka pliku albo katalogu na komputerze."
    )
    max_chars: int = Field(20000, ge=500, le=100000, description="Najwięcej znaków podglądu tekstu.")
    upload: bool = Field(
        False,
        description=(
            "Prześlij cały plik (do 10 MB) do rozmowy – dostanie file_id do dalszej obróbki "
            "narzędziami serwera (OCR, konwersje, extract_text)."
        ),
    )


class PcPowershellInput(PcInput):
    command: str = Field(min_length=1, max_length=8000, description="Polecenie Windows PowerShell 5.1.")
    description: str = Field(
        min_length=3,
        max_length=500,
        description="Po polsku: co polecenie robi i po co (widzi to użytkownik w oknie zgody).",
    )
    timeout_s: int = Field(60, ge=5, le=600, description="Limit czasu wykonania polecenia w sekundach.")
    as_admin: bool = Field(
        False,
        description=(
            "Uruchom jako administrator (np. sfc, DISM, czyszczenie C:\\Windows\\Temp, usługi). "
            "Zawsze wymaga zgody w oknie Nexusa i w monicie UAC Windows."
        ),
    )


class PcScreenshotInput(PcInput):
    target: Literal["screen", "active_window"] = Field(
        "screen", description="'screen' – cały ekran, 'active_window' – okno aktywne przed Nexusem."
    )
    display: int = Field(0, ge=0, le=8, description="Numer ekranu (0 = główny).")


def _call(
    ctx: ToolContext, tool: str, args: PcInput, extra_timeout: int = 0
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = args.model_dump(exclude={"computer"})
    try:
        broker = sync_broker(ctx.settings)
    except Exception as error:  # noqa: BLE001 - brak Redisa opisany dla modelu
        raise ToolError(f"Przekaźnik komputera jest niedostępny: {error}") from error
    try:
        return call_computer(
            broker,
            tool,
            payload,
            # Narzędzie sięga wyłącznie do komputerów konta, które prowadzi ten przebieg.
            owner=str(ctx.owner_id),
            computer=args.computer,
            timeout=ctx.settings.pulpit_timeout_s + extra_timeout,
            cancelled=ctx.cancel.is_set,
            progress=ctx.progress,
        )
    except PcCancelled as error:
        raise ToolCancelled from error
    except PcError as error:
        raise ToolError(str(error)) from error
    except OSError as error:
        raise ToolError(f"Przekaźnik komputera jest niedostępny: {error}") from error
    finally:
        if not isinstance(broker, MemoryBroker):
            broker.close()


def _result(result: dict[str, Any], computer: dict[str, Any], summary: str) -> ToolResult:
    data = result.get("data")
    text = result.get("text")
    payload: dict[str, Any] = {"computer": computer.get("name"), "host": computer.get("host")}
    if data is not None:
        payload["data"] = data
    if isinstance(text, str) and text:
        payload["text"], cut = truncate_text(text)
        if cut:
            payload["note"] = "Wynik skrócono."
    try:
        images = decode_images(result.get("images"))
    except PcError as error:
        raise ToolError(str(error)) from error
    return ToolResult(payload, summary, images=images)


@registry.register(
    "pc_info",
    """Stan komputera użytkownika z Nexus Desktop (Windows): system, procesor, pamięć RAM
(zajęta/wolna), dyski (wolne miejsce), czas pracy i procesy zużywające najwięcej pamięci.
Pierwszy krok diagnozy „komputer zwalnia / brakuje miejsca / przycina RAM”.""",
    PcInfoInput,
)
def pc_info(ctx: ToolContext, args: PcInfoInput) -> ToolResult:
    result, computer = _call(ctx, "pc_info", args)
    return _result(result, computer, f"Stan komputera {computer.get('name')}")


@registry.register(
    "pc_find_files",
    """Wyszukuje pliki na komputerze użytkownika (Nexus Desktop) po nazwie i/lub treści
w katalogach użytkownika (Pulpit, Dokumenty, Pobrane, OneDrive…) albo wskazanych katalogach.
Zwraca ścieżki, rozmiary i daty zmiany. Podgląd lub pobranie pliku: pc_read_file.""",
    PcFindFilesInput,
)
def pc_find_files(ctx: ToolContext, args: PcFindFilesInput) -> ToolResult:
    if not args.name.strip() and not args.content.strip() and not args.extensions:
        raise ToolError("Podaj nazwę, treść albo rozszerzenia szukanych plików.")
    result, computer = _call(ctx, "pc_find_files", args, extra_timeout=60)
    found = result.get("data", {}).get("files", []) if isinstance(result.get("data"), dict) else []
    return _result(result, computer, f"Znalezione pliki na komputerze: {len(found)}")


@registry.register(
    "pc_read_file",
    """Podgląd pliku lub katalogu na komputerze użytkownika (Nexus Desktop): tekst pliku,
obraz jako podgląd, zawartość katalogu, metadane. Z upload=true przesyła cały plik (do 10 MB)
do rozmowy – wynik ma file_id do dalszej obróbki narzędziami serwera. Pliki z danymi
logowania (klucze, hasła, profile przeglądarek) są zablokowane.""",
    PcReadFileInput,
)
def pc_read_file(ctx: ToolContext, args: PcReadFileInput) -> ToolResult:
    result, computer = _call(ctx, "pc_read_file", args, extra_timeout=60 if args.upload else 0)
    tool_result = _result(result, computer, f"Plik z komputera: {args.path}")
    upload = result.get("file")
    if args.upload and isinstance(upload, dict):
        tool_result.files.append(_store_upload(ctx, upload))
        tool_result.summary = f"Przesłano z komputera: {upload.get('name')}"
    return tool_result


def _store_upload(ctx: ToolContext, upload: dict[str, Any]) -> OutputFile:
    try:
        data = base64.b64decode(str(upload.get("data", "")), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ToolError("Komputer przesłał uszkodzony plik.") from error
    if len(data) > MAX_FILE_BYTES:
        raise ToolError("Plik z komputera przekracza 10 MB.")
    name = safe_filename(str(upload.get("name") or "plik-z-komputera"))
    target = ctx.output_path(name)
    target.write_bytes(data)
    return OutputFile(target, name, f"Z komputera: {str(upload.get('path', ''))[:300]}")


@registry.register(
    "pc_powershell",
    """Wykonuje polecenie Windows PowerShell na komputerze użytkownika (Nexus Desktop):
diagnoza i naprawy (miejsce na dysku, pamięć, usługi, sieć, dziennik zdarzeń, pliki tymczasowe).
Polecenia tylko do odczytu z białej listy (Get-Process, Get-CimInstance, Get-ChildItem…)
wykonują się od razu; każde inne wymaga zatwierdzenia przez użytkownika w oknie na komputerze
(pokazuje pełne polecenie i opis) – odmowa lub brak odpowiedzi kończy się błędem. Opisz uczciwie,
co polecenie zmienia. Polecenia wymagające uprawnień administratora uruchamiaj z as_admin=true.
Wynik: tekst wyjścia i kod zakończenia.""",
    PcPowershellInput,
)
def pc_powershell(ctx: ToolContext, args: PcPowershellInput) -> ToolResult:
    result, computer = _call(
        ctx, "pc_powershell", args, extra_timeout=ctx.settings.pulpit_confirm_timeout_s + args.timeout_s
    )
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    mode = "za zgodą" if data.get("confirmed") else "tylko odczyt"
    return _result(result, computer, f"PowerShell ({mode}), kod {data.get('exit_code', '?')}")


@registry.register(
    "pc_screenshot",
    """Zrzut ekranu komputera użytkownika (Nexus Desktop): cały ekran albo okno aktywne
przed otwarciem Nexusa. Użyj, gdy użytkownik pyta o to, co widzi, albo przy diagnozie
komunikatu błędu na ekranie.""",
    PcScreenshotInput,
)
def pc_screenshot(ctx: ToolContext, args: PcScreenshotInput) -> ToolResult:
    result, computer = _call(ctx, "pc_screenshot", args)
    tool_result = _result(result, computer, f"Zrzut ekranu komputera {computer.get('name')}")
    if not tool_result.images:
        raise ToolError("Komputer nie zwrócił zrzutu ekranu.")
    return tool_result
