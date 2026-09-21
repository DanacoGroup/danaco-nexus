"""Most do serwera MCP dla procesu CLI zamkniętego w piaskownicy.

Serwer MCP (``nexus.mcp_server``) potrzebuje kodu Nexusa, środowiska Pythona i bazy
danych — czyli dokładnie tego, czego agent widzieć nie może. Dlatego nie uruchamia go CLI
wewnątrz piaskownicy, tylko serwer na zewnątrz: w katalogu roboczym zadania powstaje
gniazdo uniksowe, a w piaskownicy stoi kilkunastowierszowa przelotka w Node, która łączy
standardowe wejście/wyjście z tym gniazdem.

Z punktu widzenia CLI nic się nie zmienia — to nadal serwer MCP „stdio”. Z punktu widzenia
agenta kod Nexusa nie istnieje: w jego przestrzeni montowań nie ma ani źródeł, ani
środowiska Pythona, którym dałoby się je uruchomić.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

NAZWA_GNIAZDA = "mcp.sock"
NAZWA_PRZELOTKI = "most-mcp.mjs"
# Ścieżka gniazda uniksowego mieści się w ~108 bajtach (``sun_path``), a katalog zadania
# leży głęboko — w testach i przy dłuższym katalogu danych limit pękał („AF_UNIX path too
# long”). Gniazdo dostaje więc własny, krótki katalog; do piaskownicy wchodzi jako osobne
# montowanie pod tą samą ścieżką.
KATALOG_GNIAZD = Path(tempfile.gettempdir()) / "nexus-mcp"

# Przelotka: stdin → gniazdo, gniazdo → stdout. Nic więcej; żadnego dostępu do plików.
PRZELOTKA = """\
import net from "node:net";

const gniazdo = process.argv[2];
const polaczenie = net.connect(gniazdo);
polaczenie.on("error", (blad) => {
  process.stderr.write(`most MCP: ${blad.message}\\n`);
  process.exit(1);
});
process.stdin.pipe(polaczenie);
polaczenie.pipe(process.stdout);
process.stdin.on("end", () => polaczenie.end());
polaczenie.on("close", () => process.exit(0));
"""


class MostMcp:
    """Nasłuch gniazda, który każde połączenie obsługuje osobnym procesem serwera MCP."""

    def __init__(self, run_dir: Path, env: dict[str, str]) -> None:
        KATALOG_GNIAZD.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._katalog = Path(tempfile.mkdtemp(dir=KATALOG_GNIAZD))
        self._gniazdo = self._katalog / NAZWA_GNIAZDA
        self._przelotka = run_dir / NAZWA_PRZELOTKI
        self._env = env
        self._server: asyncio.AbstractServer | None = None
        self._procesy: set[asyncio.subprocess.Process] = set()

    @property
    def katalog_gniazda(self) -> Path:
        """Katalog gniazda — do wpuszczenia w piaskownicę (poza katalogiem zadania)."""
        return self._katalog

    @property
    def gniazdo(self) -> Path:
        """Ścieżka gniazda (widoczna także w piaskownicy — katalog zadania jest montowany)."""
        return self._gniazdo

    @property
    def przelotka(self) -> Path:
        """Ścieżka skryptu przelotki uruchamianego przez CLI w piaskownicy."""
        return self._przelotka

    async def start(self) -> None:
        """Zapisuje przelotkę i otwiera nasłuch gniazda."""
        self._przelotka.write_text(PRZELOTKA, encoding="utf-8")
        with contextlib.suppress(FileNotFoundError):
            self._gniazdo.unlink()
        self._server = await asyncio.start_unix_server(self._obsluz, path=str(self._gniazdo))
        # Gniazdo należy do procesu serwera; nikt poza piaskownicą zadania go nie potrzebuje.
        with contextlib.suppress(OSError):
            os.chmod(self._gniazdo, 0o600)

    async def _obsluz(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Jedno połączenie CLI = jeden proces serwera MCP poza piaskownicą."""
        proces = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "nexus.mcp_server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,
            env=self._env,
        )
        self._procesy.add(proces)
        try:
            await asyncio.gather(
                self._przepisz(reader, proces.stdin),
                self._przepisz(proces.stdout, writer),
            )
        finally:
            self._procesy.discard(proces)
            if proces.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proces.terminate()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(proces.wait(), timeout=5)
            with contextlib.suppress(Exception):
                writer.close()

    @staticmethod
    async def _przepisz(zrodlo: asyncio.StreamReader | None, cel: asyncio.StreamWriter | None) -> None:
        """Przepisuje strumień bajtów do końca; zamknięcie po jednej stronie kończy przepływ."""
        if zrodlo is None or cel is None:
            return
        try:
            while True:
                porcja = await zrodlo.read(65536)
                if not porcja:
                    break
                cel.write(porcja)
                await cel.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            with contextlib.suppress(Exception):
                cel.close()

    async def zamknij(self) -> None:
        """Zamyka nasłuch i kończy procesy serwera MCP, które jeszcze działają."""
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None
        for proces in list(self._procesy):
            if proces.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proces.kill()
        self._procesy.clear()
        shutil.rmtree(self._katalog, ignore_errors=True)


def konfiguracja_przez_most(most: MostMcp, node: str, nazwa_serwera: str) -> dict[str, object]:
    """Konfiguracja ``--mcp-config`` wskazująca przelotkę zamiast serwera MCP wprost."""
    return {
        "mcpServers": {
            nazwa_serwera: {
                "type": "stdio",
                "command": node,
                "args": [str(most.przelotka), str(most.gniazdo)],
                "env": {},
            }
        }
    }
