"""Bezpieczne pobieranie stron WWW i wyszukiwanie w sieci.

Ochrona przed SSRF: dozwolone są tylko adresy http/https wskazujące publiczne
adresy IP. Sprawdzenie odbywa się przed każdym żądaniem (także po przekierowaniu),
a w produkcyjnym kliencie dodatkowo w chwili nawiązywania połączenia TCP – połączenie
idzie na już sprawdzony adres IP, więc podmiana DNS (DNS rebinding) nie pomaga.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

import httpcore
import httpx

USER_AGENT = "Mozilla/5.0 (compatible; DanacoNexus/0.1; +https://danaco-nexus.pl)"
ACCEPT = "text/html,application/xhtml+xml,application/pdf;q=0.9,text/plain;q=0.8,*/*;q=0.5"
MAX_REDIRECTS = 5
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".intranet")
TEXT_TYPES = ("text/plain", "text/markdown", "text/csv", "application/json", "text/xml", "application/xml")
HTML_TYPES = ("text/html", "application/xhtml+xml")
MAX_LINKS = 40

Resolver = Callable[[str, int], list[str]]


class FetchError(Exception):
    """Nie udało się pobrać strony (komunikat dla użytkownika / modelu)."""


class BlockedAddressError(FetchError):
    """Adres niedozwolony: inny protokół, adres prywatny, lokalny albo zarezerwowany."""


def system_resolve(host: str, port: int) -> list[str]:
    """Adresy IP nazwy hosta (systemowy resolver)."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise FetchError(f"Nie można odnaleźć serwera {host}.") from error
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def is_public_ip(value: str) -> bool:
    """Czy adres IP jest publiczny (nie prywatny, lokalny, zarezerwowany ani grupowy)."""
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped or address.sixtofour
        if mapped is not None:
            address = mapped
        elif address in ipaddress.ip_network("64:ff9b::/96"):
            address = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return address.is_global and not address.is_multicast


def _public_addresses(host: str, port: int, resolve: Resolver) -> list[str]:
    host = host.strip("[]").rstrip(".").lower()
    if not host or host == "localhost" or host.endswith(BLOCKED_SUFFIXES):
        raise BlockedAddressError(f"Adres {host or '(pusty)'} jest niedozwolony (sieć lokalna).")
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        # Zapisy liczbowe w rodzaju „2130706433” czy „0x7f.1” system zamienia na adresy IP.
        if re.fullmatch(r"(0x[0-9a-f]*|\d+)(\.(0x[0-9a-f]*|\d+))*", host):
            raise BlockedAddressError(f"Adres {host} jest niedozwolony.") from None
        addresses = resolve(host, port)
    if not addresses:
        raise FetchError(f"Nie można odnaleźć serwera {host}.")
    blocked = [address for address in addresses if not is_public_ip(address)]
    if blocked:
        raise BlockedAddressError(
            f"Adres {host} wskazuje sieć prywatną lub lokalną ({blocked[0]}) – pobieranie zablokowane."
        )
    return addresses


def check_url(url: str, resolve: Resolver = system_resolve) -> str:
    """Sprawdza adres (protokół, host, publiczny adres IP); zwraca adres znormalizowany."""
    url = url.strip()
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise BlockedAddressError(f"Nieprawidłowy adres: {url[:200]}") from error
    if parts.scheme.lower() not in {"http", "https"}:
        raise BlockedAddressError("Dozwolone są tylko adresy http:// i https://.")
    if parts.username or parts.password:
        raise BlockedAddressError("Adresy z danymi logowania są niedozwolone.")
    if not parts.hostname:
        raise BlockedAddressError("Adres nie zawiera nazwy serwera.")
    _public_addresses(parts.hostname, port or (443 if parts.scheme.lower() == "https" else 80), resolve)
    return url


class _SafeBackend(httpcore.SyncBackend):
    """Połączenia TCP wyłącznie na sprawdzone, publiczne adresy IP."""

    def __init__(self, resolve: Resolver) -> None:
        self._resolve = resolve

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.NetworkStream:
        addresses = _public_addresses(host, port, self._resolve)
        last_error: Exception | None = None
        for address in addresses:
            try:
                return super().connect_tcp(address, port, timeout, local_address, socket_options)
            except httpcore.ConnectError as error:
                last_error = error
        raise httpcore.ConnectError(str(last_error or f"Brak połączenia z {host}"))


class _SafeTransport(httpx.HTTPTransport):
    def __init__(self, resolve: Resolver) -> None:
        super().__init__(retries=1)
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(),
            max_connections=20,
            network_backend=_SafeBackend(resolve),
        )


def safe_client(timeout: float = 30, resolve: Resolver = system_resolve) -> httpx.Client:
    """Klient HTTP z blokadą adresów prywatnych na poziomie połączenia (bez proxy z otoczenia)."""
    return httpx.Client(
        transport=_SafeTransport(resolve),
        timeout=httpx.Timeout(timeout, connect=min(timeout, 15)),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": ACCEPT, "Accept-Language": "pl,en;q=0.8"},
    )


@dataclass(slots=True)
class PageContent:
    """Treść pobranej strony (tekst i metadane)."""

    url: str
    final_url: str
    status: int
    content_type: str
    title: str = ""
    description: str = ""
    site_name: str = ""
    author: str = ""
    published: str = ""
    language: str = ""
    canonical: str = ""
    text: str = ""
    truncated: bool = False
    size_bytes: int = 0
    links: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Słownik do wyniku narzędzia / odpowiedzi API."""
        return asdict(self)


# --- Wydobywanie tekstu z HTML -------------------------------------------------------------

SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "svg", "template", "iframe", "nav", "footer", "aside", "form", "button"}
    | {"select", "canvas", "object", "dialog", "math", "head"}
)
SKIP_ROLES = frozenset({"navigation", "banner", "contentinfo", "complementary", "search", "menu", "dialog"})
# Klasy i identyfikatory elementów pomocniczych (menu, stopki, listy języków, spisy treści, reklamy).
BOILERPLATE = re.compile(
    r"^(nav|navbar|navigation|menu|menubar|sidebar|breadcrumbs?|cookies?|cookie[-_].*|consent.*|footer|"
    r"site-header|lang|languages?|interlanguage.*|share|sharing|social.*|related|advert.*|ads?|banner|"
    r"popup|modal|newsletter|subscribe|comments?|toc|noprint|navbox|catlinks|printfooter|mw-editsection|"
    r"mw-jump-link|mw-portlet.*|vector-dropdown|vector-toc|vector-menu.*|vector-header.*|"
    r"vector-page-toolbar|vector-sticky-header|sr-only|visually-hidden|screen-reader-text|skip-link)$",
    re.IGNORECASE,
)
BLOCK_TAGS = frozenset(
    {"p", "div", "section", "article", "main", "header", "tr", "table", "ul", "ol", "dl", "dt", "dd"}
    | {"blockquote", "pre", "figure", "figcaption", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"}
)
VOID_TAGS = frozenset(
    {"br", "hr", "img", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "track"}
)
META_KEYS = {
    "description": "description",
    "og:description": "description",
    "twitter:description": "description",
    "og:title": "og_title",
    "og:site_name": "site_name",
    "author": "author",
    "article:author": "author",
    "citation_author": "author",
    "article:published_time": "published",
    "citation_publication_date": "published",
    "date": "published",
    "dc.date": "published",
    "citation_title": "og_title",
}


def _is_boilerplate(tag: str, attributes: dict[str, str]) -> bool:
    if tag in SKIP_TAGS or attributes.get("aria-hidden") == "true" or "hidden" in attributes:
        return True
    if attributes.get("role", "").lower() in SKIP_ROLES:
        return True
    tokens = attributes.get("class", "").split() + attributes.get("id", "").split()
    return any(BOILERPLATE.match(token) for token in tokens)


class _HtmlExtractor(HTMLParser):
    """Parser HTML zbierający tekst głównej treści, metadane i odnośniki.

    Otwarte elementy są na stosie, więc brakujące znaczniki zamykające (częste w HTML)
    nie psują pomijania menu, stopek i innych elementów pomocniczych.
    """

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.stack: list[tuple[str, bool]] = []
        self.skip_depth = 0
        self.in_title = False
        self.title = ""
        self.meta: dict[str, str] = {}
        self.language = ""
        self.canonical = ""
        self.links: list[dict[str, str]] = []
        self._link_href: str | None = None
        self._link_text: list[str] = []
        # Osobne bufory: cała strona, <article> i <main> – wybierany jest najlepszy.
        self.parts: dict[str, list[str]] = {"body": [], "article": [], "main": []}
        self.depth = {"article": 0, "main": 0}

    def _emit(self, text: str) -> None:
        self.parts["body"].append(text)
        for zone in ("article", "main"):
            if self.depth[zone]:
                self.parts[zone].append(text)

    def _head_element(self, tag: str, attributes: dict[str, str]) -> bool:
        if tag == "html" and attributes.get("lang"):
            self.language = attributes["lang"][:20]
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            target = META_KEYS.get(key)
            content = " ".join(attributes.get("content", "").split())
            if target and content and target not in self.meta:
                self.meta[target] = content[:1000]
            return True
        if tag == "link":
            if "canonical" in attributes.get("rel", "").lower().split():
                self.canonical = urljoin(self.base_url, attributes.get("href", ""))
            return True
        if tag == "title":
            self.in_title = not self.title
            return True
        return False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if self._head_element(tag, attributes):
            return
        if tag in VOID_TAGS:
            if tag in {"br", "hr"} and not self.skip_depth:
                self._emit("\n")
            return
        skip = _is_boilerplate(tag, attributes)
        self.stack.append((tag, skip))
        if skip:
            self.skip_depth += 1
        if self.skip_depth:
            return
        if tag in self.depth:
            self.depth[tag] += 1
        if tag == "a":
            href = attributes.get("href", "")
            self._link_href = urljoin(self.base_url, href) if href else None
            self._link_text = []
        if tag in BLOCK_TAGS:
            self._emit("\n")
        if tag in {"h1", "h2", "h3", "h4"}:
            self._emit("#" * int(tag[1]) + " ")
        elif tag == "li":
            self._emit("- ")
        elif tag in {"td", "th"}:
            self._emit(" | ")

    def _close(self, tag: str, skip: bool) -> None:
        if skip:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "a" and self._link_href is not None:
            text = " ".join("".join(self._link_text).split())
            href = self._link_href.split("#", 1)[0]
            if text and href.startswith(("http://", "https://")) and len(self.links) < MAX_LINKS:
                if all(link["url"] != href for link in self.links):
                    self.links.append({"text": text[:150], "url": href[:1000]})
            self._link_href = None
        if tag in self.depth and self.depth[tag]:
            self.depth[tag] -= 1
        if tag in BLOCK_TAGS:
            self._emit("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
            return
        if tag in VOID_TAGS or all(name != tag for name, _skip in self.stack):
            return
        while self.stack:
            name, skip = self.stack.pop()
            self._close(name, skip)
            if name == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data
            return
        if self.skip_depth:
            return
        if self._link_href is not None:
            self._link_text.append(data)
        self._emit(data)


LIST_LINE = re.compile(r"^(- |\| )")


def normalize_text(text: str) -> str:
    """Porządkuje białe znaki: pojedyncze spacje w wierszach, najwyżej jeden pusty wiersz,
    bez pustych wierszy między kolejnymi punktami listy."""
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line not in {"#", "##", "###", "####", "-", "|"}]
    cleaned: list[str] = []
    for index, line in enumerate(lines):
        if not line:
            if not cleaned or not cleaned[-1]:
                continue
            following = next((item for item in lines[index + 1 :] if item), "")
            if LIST_LINE.match(cleaned[-1]) and LIST_LINE.match(following):
                continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def extract_html(html: str, base_url: str) -> dict[str, Any]:
    """Tytuł, metadane, główny tekst i odnośniki strony HTML."""
    parser = _HtmlExtractor(base_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - uszkodzony HTML: zostaje to, co odczytano
        pass
    texts = {zone: normalize_text("".join(parts)) for zone, parts in parser.parts.items()}
    text = texts["body"]
    for zone in ("article", "main"):
        if len(texts[zone]) >= 400:
            text = texts[zone]
            break
    title = " ".join(unescape(parser.title).split()) or parser.meta.get("og_title", "")
    return {
        "title": title[:500],
        "description": parser.meta.get("description", ""),
        "site_name": parser.meta.get("site_name", ""),
        "author": parser.meta.get("author", ""),
        "published": parser.meta.get("published", ""),
        "language": parser.language,
        "canonical": parser.canonical,
        "text": text,
        "links": parser.links,
    }


def _charset(content_type: str, head: bytes) -> str:
    match = re.search(r"charset=[\"']?([\w.:-]+)", content_type, re.IGNORECASE)
    if match:
        return match.group(1)
    meta = re.search(rb"<meta[^>]+charset=[\"']?([\w.:-]+)", head[:4096], re.IGNORECASE)
    return meta.group(1).decode("ascii", "ignore") if meta else "utf-8"


def decode_body(body: bytes, content_type: str) -> str:
    """Dekoduje treść według nagłówka lub znacznika <meta charset> (domyślnie UTF-8)."""
    charset = _charset(content_type, body)
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def pdf_text(body: bytes, max_pages: int = 300) -> tuple[str, str]:
    """Tekst i tytuł dokumentu PDF pobranego z sieci."""
    import pymupdf

    try:
        with pymupdf.open(stream=body, filetype="pdf") as document:
            title = (document.metadata or {}).get("title", "") or ""
            pages = [page.get_text("text") for page in list(document)[:max_pages]]
    except Exception as error:  # noqa: BLE001 - uszkodzony lub zaszyfrowany PDF
        raise FetchError(f"Nie udało się odczytać pliku PDF: {error}") from error
    return normalize_text("\n\n".join(pages)), title.strip()


def fetch_page(
    url: str,
    *,
    client: httpx.Client | None = None,
    resolve: Resolver = system_resolve,
    max_bytes: int = 8 * 1024 * 1024,
    max_chars: int = 200_000,
    timeout: float = 30,
) -> PageContent:
    """Pobiera stronę (HTML, PDF, tekst) z ochroną przed SSRF i limitem rozmiaru."""
    own_client = client is None
    client = client or safe_client(timeout, resolve)
    current = url.strip()
    try:
        for _hop in range(MAX_REDIRECTS + 1):
            check_url(current, resolve)
            try:
                with client.stream(
                    "GET", current, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT}
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location", "")
                        if not location:
                            raise FetchError("Przekierowanie bez adresu docelowego.")
                        current = urljoin(str(response.url), location)
                        continue
                    if response.status_code >= 400:
                        raise FetchError(f"Serwer odpowiedział błędem HTTP {response.status_code}.")
                    chunks: list[bytes] = []
                    size = 0
                    truncated = False
                    for chunk in response.iter_bytes():
                        chunks.append(chunk)
                        size += len(chunk)
                        if size >= max_bytes:
                            truncated = True
                            break
                    body = b"".join(chunks)[:max_bytes]
                    content_type = response.headers.get("content-type", "").lower()
                    status = response.status_code
                    final_url = str(response.url)
            except httpx.TimeoutException as error:
                raise FetchError("Przekroczono czas oczekiwania na odpowiedź serwera.") from error
            except httpx.HTTPError as error:
                raise FetchError(f"Błąd połączenia: {error}") from error
            return _page(url, final_url, status, content_type, body, truncated, max_chars)
        raise FetchError("Zbyt wiele przekierowań.")
    finally:
        if own_client:
            client.close()


def _page(
    url: str, final_url: str, status: int, content_type: str, body: bytes, truncated: bool, max_chars: int
) -> PageContent:
    page = PageContent(url=url, final_url=final_url, status=status, content_type=content_type.split(";")[0])
    page.size_bytes = len(body)
    sniff = body[:1024].lstrip().lower()
    if "application/pdf" in content_type or body[:5] == b"%PDF-":
        if truncated:
            raise FetchError("Plik PDF przekracza limit rozmiaru.")
        page.text, page.title = pdf_text(body)
        page.content_type = "application/pdf"
    elif content_type.startswith(HTML_TYPES) or sniff.startswith((b"<!doctype html", b"<html")):
        data = extract_html(decode_body(body, content_type), final_url)
        for key in ("title", "description", "site_name", "author", "published", "language", "canonical"):
            setattr(page, key, data[key])
        page.text = data["text"]
        page.links = data["links"]
    elif content_type.startswith(TEXT_TYPES) or content_type.startswith("text/"):
        page.text = normalize_text(decode_body(body, content_type))
    else:
        raise FetchError(f"Nieobsługiwany rodzaj treści: {content_type or 'nieznany'}.")
    if not page.title:
        page.title = urlsplit(final_url).hostname or final_url
    if len(page.text) > max_chars:
        page.text = page.text[:max_chars]
        truncated = True
    page.truncated = truncated
    return page


# --- Wyszukiwanie w sieci (zapas, gdy wbudowane WebSearch jest niedostępne) ----------------


class _DuckDuckGoParser(HTMLParser):
    """Wyniki strony html.duckduckgo.com: tytuł, adres, fragment."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: (value or "") for key, value in attrs}
        classes = attributes.get("class", "").split()
        if tag == "a" and "result__a" in classes:
            self.results.append({"title": "", "url": _unwrap_ddg(attributes.get("href", "")), "snippet": ""})
            self._field = "title"
        elif tag in {"a", "div", "td"} and "result__snippet" in classes and self.results:
            self._field = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"a", "div", "td"}:
            self._field = None

    def handle_data(self, data: str) -> None:
        if self._field and self.results:
            self.results[-1][self._field] += data


def _unwrap_ddg(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parts = urlsplit(href)
    if parts.hostname and parts.hostname.endswith("duckduckgo.com") and parts.path.startswith("/l/"):
        target = parse_qs(parts.query).get("uddg", [""])[0]
        return target or href
    return href


def web_search(
    query: str,
    limit: int = 10,
    *,
    client: httpx.Client | None = None,
    searxng_url: str = "",
    timeout: float = 20,
) -> list[dict[str, str]]:
    """Wyszukiwanie w sieci: SearXNG (jeśli skonfigurowany) albo DuckDuckGo w wersji HTML."""
    own_client = client is None
    client = client or httpx.Client(
        timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )
    try:
        if searxng_url:
            response = client.get(
                f"{searxng_url.rstrip('/')}/search", params={"q": query, "format": "json", "language": "all"}
            )
            response.raise_for_status()
            items = response.json().get("results", [])
            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                }
                for item in items
            ]
        else:
            response = client.post("https://html.duckduckgo.com/html/", data={"q": query, "kl": "pl-pl"})
            response.raise_for_status()
            parser = _DuckDuckGoParser()
            parser.feed(response.text)
            results = parser.results
    except (httpx.HTTPError, ValueError) as error:
        raise FetchError(f"Wyszukiwarka jest niedostępna: {error}") from error
    finally:
        if own_client:
            client.close()
    cleaned = []
    for item in results:
        url = item["url"].strip()
        if not url.startswith(("http://", "https://")) or any(entry["url"] == url for entry in cleaned):
            continue
        cleaned.append(
            {
                "title": " ".join(item["title"].split())[:300],
                "url": url[:1000],
                "snippet": " ".join(item["snippet"].split())[:500],
            }
        )
        if len(cleaned) >= limit:
            break
    return cleaned
