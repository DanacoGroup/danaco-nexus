"""Testy modułu Research: ochrona SSRF, pobieranie stron, bazy prac naukowych, narzędzia i API."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpcore
import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nexus.api.app import create_app
from nexus.api.auth import set_admin_credentials
from nexus.config import Settings
from nexus.db import Conversation, Database, Message, Run
from nexus.models.research import ResearchReport
from nexus.research import scholar, web
from nexus.research.web import BlockedAddressError, FetchError, check_url, fetch_page
from nexus.tools import registry
from nexus.tools.base import ToolError

PUBLIC_IP = "93.184.215.14"
PASSWORD = "bardzo-tajne-haslo-2026"
HEADERS = {"X-Nexus-Request": "1"}

ARTICLE_HTML = """<!doctype html>
<html lang="pl"><head>
<meta charset="utf-8">
<title>Pompy ciepła w 2026 roku – Poradnik</title>
<meta name="description" content="Jak wybrać pompę ciepła do domu jednorodzinnego.">
<meta property="og:site_name" content="Energia Dziś">
<meta name="author" content="Anna Kowalska">
<meta property="article:published_time" content="2026-03-01">
<link rel="canonical" href="https://example.com/pompy">
<script>alert("nie czytaj mnie")</script>
<style>body { color: red }</style>
</head><body>
<nav><a href="/menu">Menu główne</a></nav>
<article>
<h1>Pompy ciepła w 2026 roku</h1>
<p>Pompa ciepła powietrze–woda to najczęściej wybierane urządzenie w nowych domach.
Współczynnik COP dobrych modeli przekracza 4,5 przy temperaturze zewnętrznej 7°C.</p>
<p>Koszt instalacji wynosi zwykle od 35 do 60 tys. zł brutto, zależnie od mocy i producenta.
Dofinansowanie z programu Czyste Powietrze może pokryć znaczną część kosztów.</p>
<p>W starszych budynkach przed montażem warto ocenić izolację ścian i dachu, szczelność okien
oraz możliwość obniżenia temperatury zasilania instalacji grzewczej. Dobrze dobrana pompa pracuje
wtedy z wysoką sprawnością przez cały sezon, a rachunki za ogrzewanie spadają nawet o połowę.</p>
<ul><li>Moc dobiera się do zapotrzebowania budynku.</li><li>Ważna jest temperatura zasilania.</li></ul>
<p>Więcej: <a href="https://example.org/raport">raport instytutu</a>.</p>
</article>
<footer>Stopka serwisu – prawa zastrzeżone</footer>
</body></html>"""


def fake_resolver(mapping: dict[str, list[str]] | None = None) -> Callable[[str, int], list[str]]:
    """Resolver DNS bez sieci: domyślnie każdy host ma publiczny adres."""

    def resolve(host: str, _port: int) -> list[str]:
        return (mapping or {}).get(host, [PUBLIC_IP])

    return resolve


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


# --- Ochrona SSRF ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost:8930/api",
        "http://intranet.local/",
        "http://10.1.2.3/",
        "http://192.168.0.10/admin",
        "http://172.16.5.5/",
        "http://100.64.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fd00::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
        "http://2130706433/",
        "http://0x7f.0.0.1/",
        "ftp://example.com/plik",
        "file:///etc/passwd",
        "gopher://example.com/",
        "http://uzytkownik:haslo@example.com/",
        "http:///bez-hosta",
    ],
)
def test_check_url_blocks_private_and_invalid(url: str) -> None:
    with pytest.raises(BlockedAddressError):
        check_url(url, fake_resolver())


def test_check_url_blocks_hosts_resolving_to_private_addresses() -> None:
    resolver = fake_resolver({"wewnetrzny.example.com": [PUBLIC_IP, "10.0.0.7"]})
    with pytest.raises(BlockedAddressError, match="10.0.0.7"):
        check_url("https://wewnetrzny.example.com/", resolver)


def test_check_url_allows_public_addresses() -> None:
    assert check_url("https://example.com/strona?x=1", fake_resolver()) == "https://example.com/strona?x=1"
    assert check_url(f"http://{PUBLIC_IP}:8080/", fake_resolver())


def test_safe_backend_rejects_private_address_at_connect_time() -> None:
    # DNS rebinding: sprawdzenie adresu przy nawiązywaniu połączenia, nie tylko przed żądaniem.
    backend = web._SafeBackend(fake_resolver({"example.com": ["127.0.0.1"]}))
    with pytest.raises(BlockedAddressError):
        backend.connect_tcp("example.com", 80, timeout=1)
    with web.safe_client(5, fake_resolver({"example.com": ["192.168.1.1"]})) as client:
        with pytest.raises(BlockedAddressError):
            client.get("http://example.com/")


def test_safe_backend_connects_only_to_checked_address(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def connect(self: Any, host: str, port: int, *args: Any, **kwargs: Any) -> Any:
        calls.append(host)
        raise httpcore.ConnectError("brak sieci w teście")

    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    backend = web._SafeBackend(fake_resolver({"example.com": [PUBLIC_IP]}))
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("example.com", 443, timeout=1)
    assert calls == [PUBLIC_IP]


def test_is_public_ip() -> None:
    assert web.is_public_ip("8.8.8.8")
    assert web.is_public_ip("2a00:1450:4001:82a::200e")
    for address in ("127.0.0.1", "10.0.0.1", "::1", "fe80::1", "224.0.0.1", "::ffff:10.0.0.1", "nie-ip"):
        assert not web.is_public_ip(address)


# --- Pobieranie stron -----------------------------------------------------------------------------


def test_fetch_page_extracts_article_and_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("Mozilla/5.0 (compatible; DanacoNexus")
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=ARTICLE_HTML)

    page = fetch_page("https://example.com/pompy", client=mock_client(handler), resolve=fake_resolver())
    assert page.title == "Pompy ciepła w 2026 roku – Poradnik"
    assert page.description.startswith("Jak wybrać pompę")
    assert page.site_name == "Energia Dziś"
    assert page.author == "Anna Kowalska"
    assert page.published == "2026-03-01"
    assert page.language == "pl"
    assert page.canonical == "https://example.com/pompy"
    assert "# Pompy ciepła w 2026 roku" in page.text
    assert "COP dobrych modeli przekracza 4,5" in page.text
    assert "- Moc dobiera się" in page.text
    assert "alert" not in page.text and "color: red" not in page.text
    assert "Menu główne" not in page.text and "Stopka serwisu" not in page.text
    assert {"text": "raport instytutu", "url": "https://example.org/raport"} in page.links
    assert not page.truncated


def test_fetch_page_blocks_redirect_to_private_address() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    with pytest.raises(BlockedAddressError):
        fetch_page("https://example.com/przekierowanie", client=mock_client(handler), resolve=fake_resolver())


def test_fetch_page_follows_public_redirect_and_limits_size() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/stary":
            return httpx.Response(301, headers={"location": "/nowy"})
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"a" * 50_000)

    page = fetch_page(
        "https://example.com/stary", client=mock_client(handler), resolve=fake_resolver(), max_bytes=10_000
    )
    assert page.final_url == "https://example.com/nowy"
    assert page.truncated and len(page.text) <= 10_000


def test_fetch_page_reads_pdf_and_rejects_binary() -> None:
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Raport roczny instytutu 2025")
        document.set_metadata({"title": "Raport roczny"})
        pdf = document.tobytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".pdf"):
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=pdf)
        if request.url.path == "/brak":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "application/zip"}, content=b"PK\x03\x04")

    result = fetch_page(
        "https://example.com/raport.pdf", client=mock_client(handler), resolve=fake_resolver()
    )
    assert result.content_type == "application/pdf"
    assert result.title == "Raport roczny"
    assert "Raport roczny instytutu 2025" in result.text
    with pytest.raises(FetchError, match="Nieobsługiwany"):
        fetch_page("https://example.com/plik.zip", client=mock_client(handler), resolve=fake_resolver())
    with pytest.raises(FetchError, match="404"):
        fetch_page("https://example.com/brak", client=mock_client(handler), resolve=fake_resolver())


def test_extract_html_skips_boilerplate_with_unclosed_tags() -> None:
    html = (
        "<html><body><div class='vector-dropdown mw-portlet-lang'><ul><li>Deutsch<li>Polski</ul></div>"
        "<div role='navigation'><p>Menu boczne</div>"
        "<div id='cookie-banner' hidden>Akceptuj ciasteczka</div>"
        "<p>Pierwszy akapit bez zamknięcia<p>Drugi akapit<ul><li>Punkt A<li>Punkt B</ul>"
        "<span aria-hidden='true'>ukryte</span><p>Koniec treści</body></html>"
    )
    data = web.extract_html(html, "https://example.com/")
    text = data["text"]
    assert "Deutsch" not in text and "Menu boczne" not in text and "ciasteczka" not in text
    assert "ukryte" not in text
    assert "Pierwszy akapit bez zamknięcia" in text and "Koniec treści" in text
    assert "- Punkt A\n- Punkt B" in text


def test_excerpt_strips_markdown() -> None:
    from nexus.research.store import excerpt

    assert (
        excerpt("## Wnioski\n- Pompa **opłaca** się.\n1. Punkt `kod`", 80)
        == "Wnioski Pompa opłaca się. Punkt kod"
    )
    assert excerpt("a " * 200, 20).endswith("…")


def test_decode_uses_meta_charset() -> None:
    body = '<html><head><meta charset="iso-8859-2"><title>Łódź</title></head></html>'.encode("iso-8859-2")
    assert "Łódź" in web.decode_body(body, "text/html")


def test_web_search_parses_duckduckgo_results() -> None:
    html = """<div class="result"><a class="result__a"
      href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x">Pierwszy <b>wynik</b></a>
      <a class="result__snippet" href="#">Opis pierwszego wyniku</a></div>
      <div class="result"><a class="result__a" href="https://example.org/b">Drugi</a>
      <div class="result__snippet">Opis drugiego</div></div>
      <div class="result"><a class="result__a" href="https://example.org/b">Duplikat</a></div>"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and b"q=pompy+ciep" in request.content
        return httpx.Response(200, text=html)

    results = web.web_search("pompy ciepła", 5, client=mock_client(handler))
    assert results == [
        {"title": "Pierwszy wynik", "url": "https://example.com/a", "snippet": "Opis pierwszego wyniku"},
        {"title": "Drugi", "url": "https://example.org/b", "snippet": "Opis drugiego"},
    ]


# --- Bazy prac naukowych --------------------------------------------------------------------------

OPENALEX_WORK = {
    "id": "https://openalex.org/W123",
    "doi": "https://doi.org/10.1000/HEAT.2024.1",
    "display_name": "Heat pumps in cold climates",
    "publication_year": 2024,
    "publication_date": "2024-05-01",
    "authorships": [
        {"author": {"display_name": "Anna Maria Kowalska"}},
        {"author": {"display_name": "John Smith"}},
    ],
    "primary_location": {
        "source": {"display_name": "Energy and Buildings"},
        "landing_page_url": "https://journal.example/heat",
    },
    "best_oa_location": {"pdf_url": "https://journal.example/heat.pdf"},
    "open_access": {"is_oa": True},
    "cited_by_count": 42,
    "abstract_inverted_index": {"Heat": [0], "pumps": [1], "work": [2]},
    "primary_topic": {"display_name": "Building Energy"},
    "keywords": [{"display_name": "heat pump"}],
    "type": "article",
}
S2_PAPER = {
    "paperId": "a" * 40,
    "title": "Heat Pumps in Cold Climates",
    "authors": [{"name": "Anna Maria Kowalska"}, {"name": "John Smith"}],
    "year": 2024,
    "venue": "Energy and Buildings",
    "abstract": "Heat pumps work even at minus twenty degrees.",
    "citationCount": 50,
    "externalIds": {"DOI": "10.1000/heat.2024.1"},
    "openAccessPdf": None,
    "url": "https://www.semanticscholar.org/paper/aaa",
    "referenceCount": 31,
    "influentialCitationCount": 4,
    "tldr": {"text": "Heat pumps are efficient in cold climates."},
    "fieldsOfStudy": ["Engineering"],
}
ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <published>2024-01-03T10:00:00Z</published>
    <title>Modelling  heat pump
      performance</title>
    <summary>We model heat pumps.</summary>
    <author><name>Piotr Nowak</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/2401.01234v2" rel="related" type="application/pdf"/>
  </entry>
</feed>"""
CROSSREF_RESPONSE = {
    "message": {
        "items": [
            {
                "DOI": "10.1000/heat.2024.1",
                "title": ["Heat pumps in cold climates"],
                "author": [{"given": "Anna Maria", "family": "Kowalska"}],
                "issued": {"date-parts": [[2024, 5]]},
                "abstract": "<jats:p>Heat pumps <jats:italic>work</jats:italic>.</jats:p>",
                "is-referenced-by-count": 40,
                "container-title": ["Energy and Buildings"],
                "URL": "https://doi.org/10.1000/heat.2024.1",
            },
            {
                "DOI": "10.1000/other",
                "title": ["Ground source systems"],
                "author": [{"name": "Zespół Badawczy"}],
                "issued": {"date-parts": [[2021]]},
                "is-referenced-by-count": 3,
            },
        ]
    }
}


def scholar_handler(s2_status: int = 200) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "api.openalex.org" and path == "/works":
            assert (
                request.url.params["filter"]
                == "from_publication_date:2020-01-01,to_publication_date:2025-12-31"
            )
            return httpx.Response(200, json={"results": [OPENALEX_WORK]})
        if host == "api.openalex.org":
            return httpx.Response(200, json=OPENALEX_WORK)
        if host == "api.semanticscholar.org":
            if s2_status != 200:
                return httpx.Response(s2_status)
            if path.endswith("/search"):
                assert request.url.params["year"] == "2020-2025"
                assert request.url.params["fieldsOfStudy"] == "Engineering"
                return httpx.Response(200, json={"data": [S2_PAPER]})
            return httpx.Response(200, json=S2_PAPER)
        if host == "export.arxiv.org":
            return httpx.Response(200, text=ARXIV_FEED)
        if host == "api.crossref.org":
            return httpx.Response(200, json=CROSSREF_RESPONSE)
        return httpx.Response(404)

    return handler


def test_scholar_search_merges_sources_by_doi() -> None:
    query = scholar.Query("heat pumps", 2020, 2025, "inżynieria", 5)
    found = scholar.search(query, client=mock_client(scholar_handler()))
    papers = found["papers"]
    assert found["errors"] == {}
    assert found["counts"] == {"openalex": 1, "semantic_scholar": 1, "arxiv": 1, "crossref": 2}
    assert len(papers) == 3
    top = papers[0]
    assert top.doi == "10.1000/heat.2024.1"
    assert sorted(top.sources) == ["crossref", "openalex", "semantic_scholar"]
    assert top.citations == 50
    assert top.pdf_url == "https://journal.example/heat.pdf"
    assert top.abstract == "Heat pumps work"
    arxiv = next(paper for paper in papers if "arxiv" in paper.sources)
    assert arxiv.title == "Modelling heat pump performance"
    assert arxiv.ids["arxiv"] == "2401.01234"
    assert arxiv.doi == "10.48550/arxiv.2401.01234"


def test_scholar_search_reports_unavailable_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scholar, "S2_RETRY_SECONDS", 0.01)
    s2_calls: list[httpx.Request] = []
    handler = scholar_handler(429)

    def counting(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.semanticscholar.org":
            s2_calls.append(request)
        return handler(request)

    found = scholar.search(
        scholar.Query("heat pumps", 2020, 2025, "inżynieria", s2_api_key="klucz-testowy"),
        client=mock_client(counting),
    )
    assert "limit" in found["errors"]["semantic_scholar"]
    assert found["papers"]
    assert len(s2_calls) == 2  # jedna ponowna próba po odpowiedzi 429
    assert s2_calls[0].headers["x-api-key"] == "klucz-testowy"


def test_scholar_search_without_key_sends_no_key_header() -> None:
    seen: list[httpx.Request] = []
    handler = scholar_handler()

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    scholar.search(scholar.Query("heat pumps", 2020, 2025, "inżynieria"), client=mock_client(recording))
    assert all("x-api-key" not in request.headers for request in seen)


def test_apa_citation() -> None:
    paper = scholar.Paper(
        title="Heat pumps in cold climates",
        authors=["Anna Maria Kowalska", "John Smith", "Jan Nowak-Jeziorański"],
        year=2024,
        venue="Energy and Buildings",
        doi="10.1000/heat.2024.1",
    )
    assert scholar.apa_citation(paper) == (
        "Kowalska, A. M., Smith, J., & Nowak-Jeziorański, J. (2024). Heat pumps in cold climates. "
        "*Energy and Buildings*. https://doi.org/10.1000/heat.2024.1"
    )
    assert scholar.apa_citation(scholar.Paper(title="Bez autora")) == "Bez autora. (b.d.)."


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("https://doi.org/10.1000/ABC.1", ("doi", "10.1000/abc.1")),
        ("10.48550/arXiv.2401.01234", ("doi", "10.48550/arxiv.2401.01234")),
        ("arXiv:2401.01234v3", ("arxiv", "2401.01234")),
        ("https://arxiv.org/pdf/2401.01234v1.pdf", ("arxiv", "2401.01234")),
        ("https://openalex.org/W123", ("openalex", "W123")),
        ("a" * 40, ("semantic_scholar", "a" * 40)),
        ("Heat pumps in cold climates", ("title", "Heat pumps in cold climates")),
    ],
)
def test_classify_identifier(identifier: str, expected: tuple[str, str]) -> None:
    assert scholar.classify_identifier(identifier) == expected


def test_paper_details_combines_openalex_and_semantic_scholar() -> None:
    paper = scholar.paper_details("10.1000/heat.2024.1", client=mock_client(scholar_handler()))
    assert paper["title"] == "Heat pumps in cold climates"
    assert paper["references_count"] == 31
    assert paper["tldr"].startswith("Heat pumps are efficient")
    assert paper["topic"] == "Building Energy"
    assert paper["apa"].startswith("Kowalska, A. M., & Smith, J. (2024).")
    assert paper["errors"] == {}


def _online(host: str = "api.openalex.org") -> bool:
    try:
        socket.create_connection((host, 443), timeout=3).close()
        return True
    except OSError:
        return False


# Samo otwarte gniazdo nie znaczy, że OpenAlex odpowie: serwer bywa niedostępny, odrzuca
# ruch z serwerowni albo zwraca błąd. Zestaw testów ma być zielony bez sieci, więc test
# sięgający do obcej usługi uruchamia się wyłącznie na żądanie: NEXUS_TESTY_SIEC=1.
TESTY_SIEC = os.environ.get("NEXUS_TESTY_SIEC", "") == "1"


@pytest.mark.skipif(
    not (TESTY_SIEC and _online()), reason="Test sieciowy — uruchom z NEXUS_TESTY_SIEC=1"
)
def test_openalex_real_network() -> None:
    with scholar.scholar_client() as client:
        papers = scholar.search_openalex(
            client, scholar.Query("heat pump efficiency cold climate", 2018, 2025, limit=5)
        )
    assert papers
    assert all(paper.title and paper.year and 2018 <= paper.year <= 2025 for paper in papers)
    assert any(paper.doi for paper in papers)


# --- Narzędzia agenta -----------------------------------------------------------------------------


class FakeKnowledge:
    """Atrapa bazy wektorowej (Qdrant) zapamiętująca zaindeksowane teksty."""

    def __init__(self) -> None:
        self.entries: dict[str, tuple[str, str]] = {}
        self.wlasciciele: dict[str, str | None] = {}
        self.deleted: list[str] = []

    def index(
        self,
        file_id: uuid.UUID,
        name: str,
        _conversation: Any,
        pages: list[tuple[int | None, str]],
        owner_id: uuid.UUID | None = None,
    ) -> int:
        # Właściciel trafia do ładunku fragmentu — bez tego wspólna kolekcja Qdranta
        # nie rozdzielałaby kont.
        self.entries[str(file_id)] = (name, "\n".join(text for _page, text in pages))
        self.wlasciciele[str(file_id)] = str(owner_id) if owner_id else None
        return 1

    def delete(self, file_id: uuid.UUID) -> None:
        self.deleted.append(str(file_id))
        self.entries.pop(str(file_id), None)

    def search(
        self,
        query: str,
        limit: int = 8,
        file_ids: list[str] | None = None,
        owner_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        hits = [
            {"file_id": key, "name": name, "text": text[:200], "score": 0.9, "page": None}
            for key, (name, text) in self.entries.items()
            if owner_id is None or self.wlasciciele.get(key) in (None, str(owner_id))
            if (file_ids is None or key in file_ids) and query.lower() in text.lower()
        ]
        return hits[:limit]


def _prepare_database(url: str) -> None:
    async def run() -> None:
        database = Database(url)
        await database.create_schema()
        await database.close()

    asyncio.run(run())


@pytest.fixture
def tool_env(harness: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, FakeKnowledge]:
    harness.settings.database_url = f"sqlite+aiosqlite:///{(tmp_path / 'narzedzia.db').as_posix()}"
    _prepare_database(harness.settings.database_url)
    knowledge = FakeKnowledge()
    monkeypatch.setattr("nexus.tools.research.knowledge_base", lambda _ctx: knowledge)

    def fake_fetch(url: str, **_kwargs: Any) -> web.PageContent:
        return fetch_page(
            url,
            client=mock_client(
                lambda request: httpx.Response(200, headers={"content-type": "text/html"}, text=ARTICLE_HTML)
            ),
            resolve=fake_resolver(),
        )

    monkeypatch.setattr("nexus.tools.research.fetch_page", fake_fetch)
    return harness, knowledge


def call(harness: Any, name: str, arguments: dict[str, Any]) -> Any:
    tool = registry.get(name)
    context = harness.context()
    try:
        return tool.handler(context, tool.parse(arguments))
    finally:
        context.cleanup()


def test_web_fetch_page_tool_pages_through_text(tool_env: tuple[Any, FakeKnowledge]) -> None:
    harness, _knowledge = tool_env
    first = call(harness, "web_fetch_page", {"url": "https://example.com/pompy", "max_chars": 500})
    assert first.data["title"].startswith("Pompy ciepła")
    assert len(first.data["text"]) == 500
    assert first.data["next_offset"] == 500
    rest = call(
        harness,
        "web_fetch_page",
        {"url": "https://example.com/pompy", "offset": 500, "max_chars": 60000, "include_links": True},
    )
    assert rest.data["next_offset"] is None
    assert rest.data["links"]


def test_web_fetch_page_tool_blocks_local_address(harness: Any) -> None:
    with pytest.raises(ToolError, match="niedozwolony|zablokowane"):
        call(harness, "web_fetch_page", {"url": "http://127.0.0.1:8930/api/health"})


def test_knowledge_tools_save_read_and_notes(tool_env: tuple[Any, FakeKnowledge]) -> None:
    harness, knowledge = tool_env
    saved = call(
        harness,
        "knowledge_save",
        {"url": "https://example.com/pompy", "collection": "Pompy ciepła", "note": "Ważne: COP > 4,5."},
    )
    assert saved.data["created"] and saved.data["indexed"]
    assert saved.data["collection"] == "Pompy ciepła"
    assert "COP dobrych modeli" in knowledge.entries[saved.data["source_id"]][1]
    assert saved.data["note_id"] in knowledge.entries

    again = call(
        harness, "knowledge_save", {"url": "https://example.com/pompy", "collection": "pompy ciepła"}
    )
    assert not again.data["created"] and again.data["source_id"] == saved.data["source_id"]

    paper = call(
        harness,
        "knowledge_save",
        {
            "kind": "praca",
            "title": "Heat pumps in cold climates",
            "content": "Abstrakt pracy o pompach ciepła.",
            "authors": ["Anna Kowalska"],
            "doi": "https://doi.org/10.1000/HEAT",
            "collection": saved.data["collection_id"],
        },
    )
    assert paper.data["collection_id"] == saved.data["collection_id"]

    listing = call(harness, "knowledge_read", {"collection": "Pompy ciepła"})
    assert listing.data["sources"] == 2 and listing.data["notes"] == 1
    kinds = {item["kind"] for item in listing.data["source_list"]}
    assert kinds == {"strona", "praca"}

    source = call(harness, "knowledge_read", {"source_id": saved.data["source_id"], "max_chars": 500})
    assert source.data["content"].startswith("# Pompy ciepła")
    assert source.data["next_offset"] == 500
    assert source.data["meta"]["site_name"] == "Energia Dziś"

    note = call(
        harness,
        "knowledge_notes",
        {"action": "add", "collection": "Pompy ciepła", "title": "Wnioski", "content": "Pompa się opłaca."},
    )
    assert note.data["indexed"]
    notes = call(
        harness, "knowledge_notes", {"action": "list", "collection": "Pompy ciepła", "query": "opłaca"}
    )
    assert [item["title"] for item in notes.data["notes"]] == ["Wnioski"]

    collections = call(harness, "knowledge_read", {})
    assert [item["name"] for item in collections.data["collections"]] == ["Pompy ciepła"]
    with pytest.raises(ToolError, match="Nie znaleziono kolekcji"):
        call(harness, "knowledge_read", {"collection": "Nieistniejąca"})


def test_knowledge_save_requires_content_or_url(tool_env: tuple[Any, FakeKnowledge]) -> None:
    harness, _knowledge = tool_env
    with pytest.raises(ToolError, match="Podaj adres"):
        call(harness, "knowledge_save", {"title": "Pusty"})


def test_scholar_search_tool(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    original = scholar.search
    monkeypatch.setattr(
        "nexus.research.scholar.search",
        lambda query, sources=None: original(query, sources, client=mock_client(scholar_handler())),
    )
    result = call(
        harness,
        "scholar_search",
        {"query": "heat pumps", "year_from": 2020, "year_to": 2025, "field": "inżynieria", "limit": 5},
    )
    assert result.data["results"][0]["apa"].startswith("Kowalska, A. M.")
    assert result.summary == "Prace naukowe: 3"


# --- API ------------------------------------------------------------------------------------------


@pytest.fixture
def api_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, FakeKnowledge, Settings]]:
    settings = Settings(
        data_dir=tmp_path / "data",
        static_dir=tmp_path / "static",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'nexus.db').as_posix()}",
        cookie_secure=False,
        cookie_domain="",
        public_url="",
        chmura_public_url="",
        redis_url="",
        voice_warm_up=False,
        voice_stt_model_dir=tmp_path / "brak-modelu",
        voice_tts_dir=tmp_path / "brak-glosow",
        voice_google_key_file=tmp_path / "brak-klucza-google",
        qdrant_url="http://127.0.0.1:1",
    )

    async def prepare() -> None:
        database = Database(settings.database_url)
        await database.create_schema()
        await set_admin_credentials(database, "admin", PASSWORD)
        await database.close()

    asyncio.run(prepare())

    def fake_fetch(url: str, **_kwargs: Any) -> web.PageContent:
        return fetch_page(
            url,
            client=mock_client(
                lambda request: httpx.Response(200, headers={"content-type": "text/html"}, text=ARTICLE_HTML)
            ),
            resolve=fake_resolver({"wewnetrzny.example.com": ["10.0.0.5"]}),
        )

    monkeypatch.setattr("nexus.api.modules.research.fetch_page", fake_fetch)
    knowledge = FakeKnowledge()
    with TestClient(create_app(settings)) as client:
        client.app.state.knowledge = knowledge  # type: ignore[attr-defined]
        response = client.post(
            "/api/auth/login", json={"username": "admin", "password": PASSWORD}, headers=HEADERS
        )
        assert response.status_code == 200, response.text
        yield client, knowledge, settings


def test_api_requires_session(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "d", database_url=f"sqlite+aiosqlite:///{(tmp_path / 'a.db').as_posix()}"
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/research/kolekcje").status_code == 401


def test_api_collections_sources_notes(api_client: tuple[TestClient, FakeKnowledge, Settings]) -> None:
    client, knowledge, _settings = api_client
    assert client.post("/api/research/kolekcje", json={"name": "Bez CSRF"}).status_code == 403
    created = client.post(
        "/api/research/kolekcje",
        json={"name": "  Pompy   ciepła ", "description": "Temat domu"},
        headers=HEADERS,
    )
    assert created.status_code == 201
    collection = created.json()
    assert collection["name"] == "Pompy ciepła"
    cid = collection["id"]

    page = client.post(
        f"/api/research/kolekcje/{cid}/zrodla", json={"url": "https://example.com/pompy"}, headers=HEADERS
    )
    assert page.status_code == 201, page.text
    source = page.json()
    assert source["kind"] == "strona" and source["title"].startswith("Pompy ciepła")
    assert source["excerpt"].startswith("Jak wybrać pompę")
    assert source["id"] in knowledge.entries  # indeksowanie w tle po odpowiedzi

    text = client.post(
        f"/api/research/kolekcje/{cid}/zrodla",
        json={"title": "Oferta instalatora", "content": "Cena montażu pompy 42 000 zł."},
        headers=HEADERS,
    ).json()
    assert text["kind"] == "tekst"

    blocked = client.post(
        f"/api/research/kolekcje/{cid}/zrodla",
        json={"url": "http://wewnetrzny.example.com/"},
        headers=HEADERS,
    )
    assert blocked.status_code == 422 and "zablokowane" in blocked.json()["detail"]
    assert client.post(f"/api/research/kolekcje/{cid}/zrodla", json={}, headers=HEADERS).status_code == 422

    listing = client.get(f"/api/research/kolekcje/{cid}/zrodla").json()
    assert {item["id"] for item in listing} == {source["id"], text["id"]}
    assert all(item["indexed"] for item in client.get(f"/api/research/kolekcje/{cid}/zrodla").json())
    full = client.get(f"/api/research/zrodla/{source['id']}").json()
    assert "COP dobrych modeli" in full["content"]

    note = client.post(
        f"/api/research/kolekcje/{cid}/notatki",
        json={"title": "Wniosek", "content": "Montaż pompy się opłaca.", "source_id": source["id"]},
        headers=HEADERS,
    )
    assert note.status_code == 201
    note_id = note.json()["id"]
    edited = client.patch(
        f"/api/research/notatki/{note_id}", json={"content": "Zmieniona treść"}, headers=HEADERS
    )
    assert edited.json()["content"] == "Zmieniona treść"
    assert knowledge.entries[note_id][1].endswith("Zmieniona treść")

    collections = client.get("/api/research/kolekcje").json()
    assert collections[0]["sources"] == 2 and collections[0]["notes"] == 1

    odpowiedz = client.get("/api/research/szukaj", params={"q": "montażu", "collection_id": cid})
    assert odpowiedz.status_code == 200, odpowiedz.text
    found = odpowiedz.json()
    assert [hit["id"] for hit in found["results"]] == [text["id"]]
    assert found["results"][0]["type"] == "source"

    renamed = client.patch(f"/api/research/zrodla/{text['id']}", json={"title": "Oferta A"}, headers=HEADERS)
    assert renamed.json()["title"] == "Oferta A"
    assert client.delete(f"/api/research/zrodla/{text['id']}", headers=HEADERS).json() == {"ok": True}
    assert text["id"] in knowledge.deleted
    assert client.get(f"/api/research/zrodla/{text['id']}").status_code == 404

    assert client.delete(f"/api/research/kolekcje/{cid}", headers=HEADERS).json() == {"ok": True}
    assert source["id"] in knowledge.deleted and note_id in knowledge.deleted
    assert client.get("/api/research/kolekcje").json() == []


def test_api_file_source(api_client: tuple[TestClient, FakeKnowledge, Settings], tmp_path: Path) -> None:
    client, knowledge, _settings = api_client
    cid = client.post("/api/research/kolekcje", json={"name": "Pliki"}, headers=HEADERS).json()["id"]
    uploaded = client.post(
        "/api/files",
        files={
            "file": ("notatka.md", "# Spotkanie\nUstalenia dotyczące pomp ciepła.".encode(), "text/markdown")
        },
        headers=HEADERS,
    ).json()
    response = client.post(
        f"/api/research/kolekcje/{cid}/zrodla", json={"file_id": uploaded["id"]}, headers=HEADERS
    )
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["kind"] == "plik" and source["file_id"] == uploaded["id"]
    assert "Ustalenia" in knowledge.entries[source["id"]][1]
    image = client.post(
        "/api/files", files={"file": ("zdjecie.png", b"\x89PNG\r\n\x1a\n", "image/png")}, headers=HEADERS
    ).json()
    refused = client.post(
        f"/api/research/kolekcje/{cid}/zrodla", json={"file_id": image["id"]}, headers=HEADERS
    )
    assert refused.status_code == 422


def test_api_preview_blocks_private_address(api_client: tuple[TestClient, FakeKnowledge, Settings]) -> None:
    client, _knowledge, _settings = api_client
    response = client.post(
        "/api/research/podglad", json={"url": "http://wewnetrzny.example.com/"}, headers=HEADERS
    )
    assert response.status_code == 422
    preview = client.post("/api/research/podglad", json={"url": "https://example.com/pompy"}, headers=HEADERS)
    assert preview.json()["site_name"] == "Energia Dziś"


def _database_call(settings: Settings, action: Callable[[Database], Any]) -> Any:
    async def run() -> Any:
        database = Database(settings.database_url)
        try:
            return await action(database)
        finally:
            await database.close()

    return asyncio.run(run())


def test_api_research_flow(api_client: tuple[TestClient, FakeKnowledge, Settings]) -> None:
    client, _knowledge, settings = api_client
    started = client.post(
        "/api/research/badania",
        json={"question": "Czy pompa ciepła opłaca się w starym domu?", "kind": "deep", "depth": "quick"},
        headers=HEADERS,
    )
    assert started.status_code == 201, started.text
    report = started.json()
    assert report["status"] == "queued" and report["run_id"]
    # Tytuł raportu widzi użytkownik, a produkt jest po polsku.
    assert report["title"].startswith("Badanie sieci: Czy pompa")

    conversation_id = uuid.UUID(report["conversation_id"])
    run_id = uuid.UUID(report["run_id"])

    async def inspect(database: Database) -> tuple[dict[str, Any], str]:
        async with database.session() as session:
            conversation = await session.get(Conversation, conversation_id)
            message = await session.scalar(
                select(Message).where(Message.run_id == run_id, Message.kind == "user")
            )
            assert conversation is not None and message is not None
        return conversation.meta, message.content[0]["text"]

    meta, prompt = _database_call(settings, inspect)
    assert meta["mode"] == "research" and meta["depth"] == "quick" and meta["collection_id"]
    assert "Deep Research" in prompt and "knowledge_save" in prompt
    assert prompt.endswith("Czy pompa ciepła opłaca się w starym domu?")

    listing = client.get("/api/research/badania").json()
    assert [item["id"] for item in listing] == [report["id"]]
    assert listing[0]["status"] == "queued"
    collections = client.get("/api/research/kolekcje").json()
    assert [item["name"] for item in collections] == ["Research"]

    async def finish(database: Database) -> None:
        async with database.session() as session:
            run = await session.get(Run, run_id)
            assert run is not None
            run.status = "done"
            session.add(
                Message(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    role="assistant",
                    kind="assistant",
                    content=[
                        {"type": "text", "text": "# Raport\nOpłaca się [1]."},
                        {"type": "tool_use", "id": "t1", "name": "web_search", "input": {}},
                    ],
                )
            )
            session.add(
                Message(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    role="assistant",
                    kind="assistant",
                    content=[
                        {"type": "text", "text": "## Źródła\n- [1] Poradnik – https://example.com/pompy"}
                    ],
                )
            )

    _database_call(settings, finish)
    detail = client.get(f"/api/research/badania/{report['id']}").json()
    assert detail["status"] == "done" and not detail["active"]
    assert (
        detail["report"]
        == "# Raport\nOpłaca się [1].\n\n## Źródła\n- [1] Poradnik – https://example.com/pompy"
    )

    scholar_run = client.post(
        "/api/research/badania",
        json={"question": "heat pump efficiency", "kind": "scholar", "save_sources": False},
        headers=HEADERS,
    ).json()
    assert scholar_run["collection_id"] is None
    assert scholar_run["title"].startswith("Prace naukowe: ")
    assert client.delete(f"/api/research/badania/{report['id']}", headers=HEADERS).json() == {"ok": True}
    assert [item["id"] for item in client.get("/api/research/badania").json()] == [scholar_run["id"]]

    async def reports(database: Database) -> int:
        async with database.session() as session:
            return len((await session.scalars(select(ResearchReport))).all())

    assert _database_call(settings, reports) == 1


def test_api_chat_with_documents(api_client: tuple[TestClient, FakeKnowledge, Settings]) -> None:
    client, _knowledge, settings = api_client
    cid = client.post("/api/research/kolekcje", json={"name": "Dom"}, headers=HEADERS).json()["id"]
    source = client.post(
        f"/api/research/kolekcje/{cid}/zrodla",
        json={"title": "Umowa", "content": "Termin: 30 dni."},
        headers=HEADERS,
    ).json()
    note = client.post(
        f"/api/research/kolekcje/{cid}/notatki", json={"content": "Zapytać o gwarancję."}, headers=HEADERS
    ).json()

    assert client.post("/api/research/rozmowa", json={}, headers=HEADERS).status_code == 422
    missing = client.post("/api/research/rozmowa", json={"source_ids": [str(uuid.uuid4())]}, headers=HEADERS)
    assert missing.status_code == 404

    chosen = client.post(
        "/api/research/rozmowa",
        json={"source_ids": [source["id"]], "note_ids": [note["id"]], "question": "Jaki jest termin?"},
        headers=HEADERS,
    )
    assert chosen.status_code == 201, chosen.text
    data = chosen.json()
    assert data["title"] == "Dokumenty: Umowa i inne (2)"
    detail = client.get(f"/api/conversations/{data['conversation_id']}").json()
    text = detail["turns"][0]["text"]
    assert f"source_id: {source['id']}" in text and f"note_id: {note['id']}" in text
    assert text.endswith("Jaki jest termin?")

    async def meta(database: Database) -> dict[str, Any]:
        async with database.session() as session:
            conversation = await session.get(Conversation, uuid.UUID(data["conversation_id"]))
            assert conversation is not None
            return conversation.meta

    stored = _database_call(settings, meta)
    assert stored["mode"] == "chat"
    assert stored["knowledge"]["source_ids"] == [source["id"]]

    # Plan wejściowy pozwala na jedno zadanie naraz, a pierwsza rozmowa zostawiła zadanie
    # w kolejce: druga musi poczekać, aż poprzednia się skończy albo zostanie anulowana.
    zajete = client.post("/api/research/rozmowa", json={"collection_id": cid}, headers=HEADERS)
    assert zajete.status_code == 409, zajete.text
    anulowane = client.post(f"/api/runs/{data['run_id']}/cancel", headers=HEADERS)
    assert anulowane.status_code == 200, anulowane.text

    whole = client.post("/api/research/rozmowa", json={"collection_id": cid}, headers=HEADERS).json()
    assert whole["title"] == "Dokumenty: Dom"
    assert json.dumps(whole)
