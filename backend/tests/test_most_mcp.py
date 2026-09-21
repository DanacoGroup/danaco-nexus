"""Most do serwera MCP: przelotka w piaskownicy ↔ gniazdo ↔ serwer narzędzi na zewnątrz.

Ten moduł jest jedynym wejściem agenta do narzędzi, kiedy działa piaskownica — i był
jedynym plikiem w `nexus/agent/`, którego żaden test nie dotykał. Testy w `test_agent.py`
pracują z `agent_piaskownica=False`, więc idą serwerem MCP wprost i mostu nie widzą.

Sprawdzamy całą drogę naprawdę: klient MCP uruchamia przelotkę w Node dokładnie tym
poleceniem, które trafia do `--mcp-config`, przelotka łączy się z gniazdem, most stawia
po drugiej stronie proces serwera narzędzi. Dodatkowo — granice: gniazdo poza katalogiem
zadania, prawa 0600, sprzątanie po zamknięciu.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest

from nexus.agent import most_mcp

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="gniazda uniksowe")

NODE = shutil.which("node")


def _srodowisko(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "NEXUS_DATABASE_URL": f"sqlite+aiosqlite:///{(tmp_path / 'most.db').as_posix()}",
        "NEXUS_DATA_DIR": str(tmp_path / "dane"),
        "NEXUS_RUN_ID": str(uuid.uuid4()),
        "NEXUS_CONVERSATION_ID": str(uuid.uuid4()),
        "NEXUS_OWNER_ID": str(uuid.uuid4()),
    }


@pytest.mark.asyncio
async def test_most_stawia_gniazdo_poza_katalogiem_zadania(tmp_path: Path) -> None:
    run_dir = tmp_path / "bieg"
    run_dir.mkdir()
    most = most_mcp.MostMcp(run_dir, _srodowisko(tmp_path))
    await most.start()
    try:
        assert most.przelotka == run_dir / most_mcp.NAZWA_PRZELOTKI
        assert most.przelotka.read_text(encoding="utf-8") == most_mcp.PRZELOTKA
        assert most.gniazdo.exists()
        # Gniazdo leży poza katalogiem zadania: ścieżka `sun_path` ma ~108 bajtów, a katalog
        # zadania bywa głęboki. Do piaskownicy wchodzi jako osobne montowanie.
        assert run_dir not in most.gniazdo.parents
        assert most.katalog_gniazda.parent == most_mcp.KATALOG_GNIAZD
        assert oct(most.gniazdo.stat().st_mode)[-3:] == "600"
    finally:
        await most.zamknij()
    assert not most.katalog_gniazda.exists()


def test_konfiguracja_wskazuje_przelotke_a_nie_serwer(tmp_path: Path) -> None:
    run_dir = tmp_path / "bieg"
    run_dir.mkdir()
    most = most_mcp.MostMcp(run_dir, {})
    config = most_mcp.konfiguracja_przez_most(most, "/usr/bin/node", "nexus")
    serwer = config["mcpServers"]["nexus"]  # type: ignore[index]
    assert serwer["command"] == "/usr/bin/node"
    assert serwer["args"] == [str(most.przelotka), str(most.gniazdo)]
    # Przelotka nie dostaje żadnej zmiennej: konfiguracja Nexusa zostaje po stronie serwera.
    assert serwer["env"] == {}
    assert serwer["type"] == "stdio"
    shutil.rmtree(most.katalog_gniazda, ignore_errors=True)


@pytest.mark.skipif(NODE is None, reason="przelotka wymaga Node")
@pytest.mark.asyncio
async def test_narzedzia_dochodza_przez_most(tmp_path: Path) -> None:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    run_dir = tmp_path / "bieg"
    run_dir.mkdir()
    most = most_mcp.MostMcp(run_dir, _srodowisko(tmp_path))
    await most.start()
    try:
        serwer = most_mcp.konfiguracja_przez_most(most, NODE, "nexus")["mcpServers"]["nexus"]  # type: ignore[index]
        parametry = StdioServerParameters(
            command=serwer["command"], args=serwer["args"], env=dict(os.environ)
        )
        async with stdio_client(parametry) as (czytaj, pisz):
            async with ClientSession(czytaj, pisz) as sesja:
                await sesja.initialize()
                narzedzia = await sesja.list_tools()
        nazwy = {narzedzie.name for narzedzie in narzedzia.tools}
        assert nazwy, "most nie przepuścił wykazu narzędzi"
        assert "write_document" in nazwy
    finally:
        await most.zamknij()
    assert not most.katalog_gniazda.exists()
