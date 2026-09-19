"""Wyszukiwanie prac naukowych w otwartych bazach bez kluczy API.

Źródła: OpenAlex, Semantic Scholar, arXiv i Crossref. Wyniki są scalane po DOI
(lub znormalizowanym tytule), a pola uzupełniane z kolejnych baz. Każda baza może
być chwilowo niedostępna (np. limit zapytań Semantic Scholar) – wtedy jej błąd
trafia do listy ``errors``, a pozostałe wyniki są zwracane normalnie.
"""

from __future__ import annotations

import math
import re
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from nexus.research.web import USER_AGENT

OPENALEX = "https://api.openalex.org"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1"
ARXIV = "https://export.arxiv.org/api/query"
CROSSREF = "https://api.crossref.org/works"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
SOURCES = ("openalex", "semantic_scholar", "arxiv", "crossref")
# Semantic Scholar bez klucza ma wspólny limit zapytań – jedna ponowna próba po przerwie.
S2_RETRY_SECONDS = 1.5
S2_FIELDS = "title,authors,year,venue,abstract,citationCount,externalIds,openAccessPdf,url,publicationDate"
S2_DETAIL_FIELDS = (
    S2_FIELDS + ",referenceCount,influentialCitationCount,tldr,fieldsOfStudy,publicationTypes,journal"
)
OPENALEX_SELECT = (
    "id,doi,display_name,publication_year,publication_date,authorships,primary_location,open_access,"
    "best_oa_location,cited_by_count,abstract_inverted_index,type"
)
# Dziedziny Semantic Scholar (fieldsOfStudy) i ich polskie nazwy.
FIELDS_OF_STUDY = {
    "informatyka": "Computer Science",
    "medycyna": "Medicine",
    "chemia": "Chemistry",
    "biologia": "Biology",
    "materiałoznawstwo": "Materials Science",
    "fizyka": "Physics",
    "geologia": "Geology",
    "psychologia": "Psychology",
    "sztuka": "Art",
    "historia": "History",
    "geografia": "Geography",
    "socjologia": "Sociology",
    "biznes": "Business",
    "zarządzanie": "Business",
    "nauki polityczne": "Political Science",
    "politologia": "Political Science",
    "ekonomia": "Economics",
    "filozofia": "Philosophy",
    "matematyka": "Mathematics",
    "inżynieria": "Engineering",
    "nauki o środowisku": "Environmental Science",
    "ochrona środowiska": "Environmental Science",
    "rolnictwo": "Agricultural and Food Sciences",
    "edukacja": "Education",
    "prawo": "Law",
    "językoznawstwo": "Linguistics",
    "lingwistyka": "Linguistics",
}


class ScholarError(Exception):
    """Błąd bazy prac naukowych."""


@dataclass(slots=True)
class Paper:
    """Praca naukowa w ujednoliconej postaci."""

    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
    abstract: str = ""
    citations: int | None = None
    url: str = ""
    pdf_url: str = ""
    open_access: bool = False
    published: str = ""
    ids: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    rank: float = 0.0

    def as_dict(self, abstract_chars: int = 1500) -> dict[str, Any]:
        """Słownik wyniku (skrócony abstrakt, cytowanie APA)."""
        data = asdict(self)
        data.pop("rank")
        if abstract_chars and len(self.abstract) > abstract_chars:
            data["abstract"] = self.abstract[:abstract_chars].rstrip() + "…"
        data["apa"] = apa_citation(self)
        return data


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _strip_tags(text: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", text or ""))


def normalize_doi(value: str) -> str:
    """DOI bez prefiksu adresu, małymi literami."""
    value = (value or "").strip()
    value = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    return value.lower()


def _title_key(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title.lower())
    return re.sub(r"[^a-z0-9]+", "", folded)[:120]


def _author_apa(name: str) -> str:
    name = _clean(name)
    if not name:
        return ""
    if "," in name:
        family, _, given = name.partition(",")
    else:
        parts = name.split(" ")
        if len(parts) == 1:
            return name
        family, given = parts[-1], " ".join(parts[:-1])
    initials = " ".join(f"{part[0]}." for part in re.split(r"[\s-]+", given.strip()) if part)
    return f"{family.strip()}, {initials}".strip().rstrip(",")


def apa_citation(paper: Paper) -> str:
    """Cytowanie w stylu APA 7 (do listy źródeł raportu)."""
    authors = [_author_apa(name) for name in paper.authors if _clean(name)]
    if len(authors) > 20:
        author_text = ", ".join(authors[:19]) + ", … " + authors[-1]
    elif len(authors) > 1:
        author_text = ", ".join(authors[:-1]) + ", & " + authors[-1]
    else:
        author_text = authors[0] if authors else ""
    year = f"({paper.year})" if paper.year else "(b.d.)"
    title = paper.title.rstrip(".")
    parts = [f"{author_text} {year}. {title}." if author_text else f"{title}. {year}."]
    if paper.venue:
        parts.append(f"*{paper.venue}*.")
    if paper.doi:
        parts.append(f"https://doi.org/{paper.doi}")
    elif paper.url:
        parts.append(paper.url)
    return " ".join(part for part in parts if part)


def _abstract_from_index(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positions: dict[int, str] = {}
    for word, places in index.items():
        for place in places:
            positions[place] = word
    return " ".join(positions[key] for key in sorted(positions))


# --- Parsowanie odpowiedzi poszczególnych baz ---------------------------------------------


def parse_openalex(item: dict[str, Any]) -> Paper:
    """Praca z OpenAlex (``/works``)."""
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    best = item.get("best_oa_location") or {}
    open_access = item.get("open_access") or {}
    openalex_id = str(item.get("id") or "").rsplit("/", 1)[-1]
    return Paper(
        title=_clean(item.get("display_name") or item.get("title")),
        authors=[
            _clean((entry.get("author") or {}).get("display_name"))
            for entry in item.get("authorships") or []
            if (entry.get("author") or {}).get("display_name")
        ],
        year=item.get("publication_year"),
        venue=_clean(source.get("display_name")),
        doi=normalize_doi(item.get("doi") or ""),
        abstract=_abstract_from_index(item.get("abstract_inverted_index")),
        citations=item.get("cited_by_count"),
        url=location.get("landing_page_url") or item.get("doi") or item.get("id") or "",
        pdf_url=best.get("pdf_url") or location.get("pdf_url") or "",
        open_access=bool(open_access.get("is_oa")),
        published=item.get("publication_date") or "",
        ids={"openalex": openalex_id} if openalex_id else {},
        sources=["openalex"],
    )


def parse_semantic_scholar(item: dict[str, Any]) -> Paper:
    """Praca z Semantic Scholar (Graph API)."""
    external = item.get("externalIds") or {}
    pdf = item.get("openAccessPdf") or {}
    ids = {"semantic_scholar": item.get("paperId", "")}
    if external.get("ArXiv"):
        ids["arxiv"] = external["ArXiv"]
    return Paper(
        title=_clean(item.get("title")),
        authors=[_clean(author.get("name")) for author in item.get("authors") or [] if author.get("name")],
        year=item.get("year"),
        venue=_clean(item.get("venue") or (item.get("journal") or {}).get("name")),
        doi=normalize_doi(external.get("DOI") or ""),
        abstract=_clean(item.get("abstract")),
        citations=item.get("citationCount"),
        url=item.get("url") or "",
        pdf_url=pdf.get("url") or "",
        open_access=bool(pdf.get("url")),
        published=item.get("publicationDate") or "",
        ids={key: value for key, value in ids.items() if value},
        sources=["semantic_scholar"],
    )


def parse_crossref(item: dict[str, Any]) -> Paper:
    """Praca z Crossref (``/works``)."""
    authors = []
    for author in item.get("author") or []:
        if author.get("family"):
            authors.append(_clean(f"{author.get('given', '')} {author['family']}"))
        elif author.get("name"):
            authors.append(_clean(author["name"]))
    date_parts = ((item.get("issued") or {}).get("date-parts") or [[None]])[0]
    year = date_parts[0] if date_parts and isinstance(date_parts[0], int) else None
    pdf = next(
        (link.get("URL", "") for link in item.get("link") or [] if "pdf" in link.get("content-type", "")), ""
    )
    title = item.get("title") or [""]
    venue = item.get("container-title") or [""]
    return Paper(
        title=_clean(title[0] if title else ""),
        authors=authors,
        year=year,
        venue=_clean(venue[0] if venue else ""),
        doi=normalize_doi(item.get("DOI") or ""),
        abstract=_strip_tags(item.get("abstract") or ""),
        citations=item.get("is-referenced-by-count"),
        url=item.get("URL") or "",
        pdf_url=pdf,
        published="-".join(str(part) for part in date_parts if part) if year else "",
        sources=["crossref"],
    )


def parse_arxiv(xml_text: str) -> list[Paper]:
    """Prace z odpowiedzi Atom API arXiv."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        raise ScholarError(f"Nieprawidłowa odpowiedź arXiv: {error}") from error
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        entry_id = entry.findtext(f"{ATOM}id") or ""
        arxiv_id = re.sub(r"v\d+$", "", entry_id.rsplit("/abs/", 1)[-1])
        if not arxiv_id or "api/errors" in entry_id:
            continue
        published = entry.findtext(f"{ATOM}published") or ""
        pdf = next(
            (
                link.get("href", "")
                for link in entry.findall(f"{ATOM}link")
                if link.get("title") == "pdf" or link.get("type") == "application/pdf"
            ),
            f"https://arxiv.org/pdf/{arxiv_id}",
        )
        papers.append(
            Paper(
                title=_clean(entry.findtext(f"{ATOM}title")),
                authors=[_clean(author.findtext(f"{ATOM}name")) for author in entry.findall(f"{ATOM}author")],
                year=int(published[:4]) if published[:4].isdigit() else None,
                venue=_clean(entry.findtext(f"{ARXIV_NS}journal_ref")) or "arXiv",
                doi=normalize_doi(entry.findtext(f"{ARXIV_NS}doi") or f"10.48550/arXiv.{arxiv_id}"),
                abstract=_clean(entry.findtext(f"{ATOM}summary")),
                url=f"https://arxiv.org/abs/{arxiv_id}",
                pdf_url=pdf,
                open_access=True,
                published=published[:10],
                ids={"arxiv": arxiv_id},
                sources=["arxiv"],
            )
        )
    return papers


# --- Zapytania ------------------------------------------------------------------------------


@dataclass(slots=True)
class Query:
    """Parametry wyszukiwania prac."""

    text: str
    year_from: int | None = None
    year_to: int | None = None
    field: str = ""
    limit: int = 10
    contact_email: str = ""
    s2_api_key: str = ""

    @property
    def s2_field(self) -> str:
        """Dziedzina w nazewnictwie Semantic Scholar (pusta, gdy nieznana)."""
        name = self.field.strip().lower()
        if not name:
            return ""
        if name in FIELDS_OF_STUDY:
            return FIELDS_OF_STUDY[name]
        english = {value.lower(): value for value in FIELDS_OF_STUDY.values()}
        return english.get(name, "")

    @property
    def text_with_field(self) -> str:
        """Zapytanie uzupełnione o dziedzinę, gdy baza nie filtruje dziedzin."""
        return f"{self.text} {self.field}".strip() if self.field and not self.s2_field else self.text


def _get(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retry_after_limit: float = 0,
) -> httpx.Response:
    try:
        response = client.get(url, params=params, headers=headers)
        if response.status_code == 429 and retry_after_limit:
            time.sleep(retry_after_limit)
            response = client.get(url, params=params, headers=headers)
    except httpx.HTTPError as error:
        raise ScholarError(f"brak połączenia ({error.__class__.__name__})") from error
    if response.status_code == 429:
        raise ScholarError("limit zapytań – spróbuj za chwilę")
    if response.status_code == 404:
        raise ScholarError("nie znaleziono")
    if response.status_code >= 400:
        raise ScholarError(f"błąd HTTP {response.status_code}")
    return response


def search_openalex(client: httpx.Client, query: Query) -> list[Paper]:
    """Wyszukiwanie w OpenAlex."""
    filters = []
    if query.year_from:
        filters.append(f"from_publication_date:{query.year_from}-01-01")
    if query.year_to:
        filters.append(f"to_publication_date:{query.year_to}-12-31")
    params: dict[str, Any] = {
        "search": query.text_with_field,
        "per-page": query.limit,
        "select": OPENALEX_SELECT,
    }
    if filters:
        params["filter"] = ",".join(filters)
    if query.contact_email:
        params["mailto"] = query.contact_email
    data = _get(client, f"{OPENALEX}/works", params).json()
    return [parse_openalex(item) for item in data.get("results", [])]


def _year_range(query: Query) -> str:
    if query.year_from and query.year_to:
        return f"{query.year_from}-{query.year_to}"
    if query.year_from:
        return f"{query.year_from}-"
    if query.year_to:
        return f"-{query.year_to}"
    return ""


def _s2_headers(api_key: str) -> dict[str, str] | None:
    return {"x-api-key": api_key} if api_key else None


def _arxiv_text(client: httpx.Client, params: dict[str, Any]) -> str:
    try:
        return _get(client, ARXIV, params).text
    except ScholarError as error:
        if "406" not in str(error):
            raise
    # Brama arXiv odrzuca kodem 406 część zapytań wyszukiwania wysłanych przez httpx (te same
    # zapytania z urllib i curl przechodzą) – zapasowo biblioteka standardowa.
    request = urllib.request.Request(
        f"{ARXIV}?{urlencode(params, safe=':[]')}", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as error:
        raise ScholarError(f"błąd połączenia z arXiv ({error})") from error


def search_semantic_scholar(client: httpx.Client, query: Query) -> list[Paper]:
    """Wyszukiwanie w Semantic Scholar (bez klucza – wspólny limit zapytań)."""
    params: dict[str, Any] = {"query": query.text, "limit": query.limit, "fields": S2_FIELDS}
    if _year_range(query):
        params["year"] = _year_range(query)
    if query.s2_field:
        params["fieldsOfStudy"] = query.s2_field
    data = _get(
        client,
        f"{SEMANTIC_SCHOLAR}/paper/search",
        params,
        headers=_s2_headers(query.s2_api_key),
        retry_after_limit=S2_RETRY_SECONDS,
    ).json()
    return [parse_semantic_scholar(item) for item in data.get("data") or []]


def arxiv_query(query: Query) -> str:
    """Wyrażenie wyszukiwania arXiv (wszystkie słowa w dowolnym polu, opcjonalnie lata)."""
    words = [word for word in re.findall(r"[\w-]+", query.text_with_field) if len(word) > 1][:12]
    expression = " AND ".join(f"all:{word}" for word in words) or "all:*"
    if query.year_from or query.year_to:
        start = f"{query.year_from or 1991}01010000"
        end = f"{query.year_to or 2100}12312359"
        expression += f" AND submittedDate:[{start} TO {end}]"
    return expression


def search_arxiv(client: httpx.Client, query: Query) -> list[Paper]:
    """Wyszukiwanie w arXiv (preprinty: fizyka, matematyka, informatyka, biologia ilościowa…)."""
    params = {
        "search_query": arxiv_query(query),
        "start": 0,
        "max_results": query.limit,
        "sortBy": "relevance",
    }
    return parse_arxiv(_arxiv_text(client, params))


def search_crossref(client: httpx.Client, query: Query) -> list[Paper]:
    """Wyszukiwanie w Crossref (metadane publikacji z DOI)."""
    filters = []
    if query.year_from:
        filters.append(f"from-pub-date:{query.year_from}")
    if query.year_to:
        filters.append(f"until-pub-date:{query.year_to}")
    params: dict[str, Any] = {
        "query.bibliographic": query.text_with_field,
        "rows": query.limit,
        "select": "DOI,title,author,issued,abstract,is-referenced-by-count,link,container-title,URL,type",
    }
    if filters:
        params["filter"] = ",".join(filters)
    if query.contact_email:
        params["mailto"] = query.contact_email
    data = _get(client, CROSSREF, params).json()
    return [
        parse_crossref(item) for item in (data.get("message") or {}).get("items", []) if item.get("title")
    ]


SEARCHERS: dict[str, Callable[[httpx.Client, Query], list[Paper]]] = {
    "openalex": search_openalex,
    "semantic_scholar": search_semantic_scholar,
    "arxiv": search_arxiv,
    "crossref": search_crossref,
}


def merge_papers(groups: dict[str, list[Paper]]) -> list[Paper]:
    """Scala wyniki baz (DOI lub tytuł), uzupełnia brakujące pola i porządkuje wg trafności."""
    merged: dict[str, Paper] = {}
    for _source, papers in groups.items():
        for position, paper in enumerate(papers):
            if not paper.title:
                continue
            key = f"doi:{paper.doi}" if paper.doi else f"t:{_title_key(paper.title)}"
            title_key = f"t:{_title_key(paper.title)}"
            existing = merged.get(key) or merged.get(title_key)
            score = 1.0 / (position + 1)
            if existing is None:
                paper.rank = score
                merged[key] = paper
                merged.setdefault(title_key, paper)
                continue
            existing.rank += score
            for name in ("abstract", "venue", "url", "pdf_url", "published", "doi"):
                if not getattr(existing, name) and getattr(paper, name):
                    setattr(existing, name, getattr(paper, name))
            if not existing.authors:
                existing.authors = paper.authors
            existing.year = existing.year or paper.year
            if paper.citations is not None:
                existing.citations = max(existing.citations or 0, paper.citations)
            existing.open_access = existing.open_access or paper.open_access
            existing.ids.update({k: v for k, v in paper.ids.items() if k not in existing.ids})
            existing.sources.extend(source for source in paper.sources if source not in existing.sources)
            if existing.doi:
                merged.setdefault(f"doi:{existing.doi}", existing)
    unique = list({id(paper): paper for paper in merged.values()}.values())
    for paper in unique:
        paper.rank += 0.08 * math.log10((paper.citations or 0) + 1)
    return sorted(unique, key=lambda paper: paper.rank, reverse=True)


def scholar_client(timeout: float = 25) -> httpx.Client:
    """Klient HTTP dla baz prac naukowych."""
    return httpx.Client(
        timeout=httpx.Timeout(timeout, connect=10),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml;q=0.9"},
        follow_redirects=True,
    )


def search(
    query: Query, sources: list[str] | None = None, client: httpx.Client | None = None
) -> dict[str, Any]:
    """Wyszukuje równolegle we wskazanych bazach; zwraca scalone wyniki i błędy baz."""
    chosen = [source for source in (sources or list(SOURCES)) if source in SEARCHERS]
    own_client = client is None
    client = client or scholar_client()
    groups: dict[str, list[Paper]] = {}
    errors: dict[str, str] = {}
    counts: dict[str, int] = {}
    try:
        with ThreadPoolExecutor(max_workers=len(chosen) or 1) as pool:
            futures = {source: pool.submit(SEARCHERS[source], client, query) for source in chosen}
            for source, future in futures.items():
                try:
                    groups[source] = future.result()
                    counts[source] = len(groups[source])
                except (ScholarError, ValueError, KeyError, TypeError) as error:
                    errors[source] = str(error) or error.__class__.__name__
    finally:
        if own_client:
            client.close()
    papers = merge_papers(groups)[: max(query.limit, 1) * 2]
    return {"papers": papers, "errors": errors, "counts": counts}


# --- Szczegóły jednej pracy -----------------------------------------------------------------


def classify_identifier(identifier: str) -> tuple[str, str]:
    """Rodzaj identyfikatora pracy: doi, arxiv, openalex, semantic_scholar albo title."""
    value = identifier.strip()
    arxiv = re.search(r"arxiv\.org/(?:abs|pdf)/([\w.-]+?)(?:v\d+)?(?:\.pdf)?$", value, re.IGNORECASE)
    if arxiv:
        return "arxiv", arxiv.group(1)
    if re.fullmatch(r"(arxiv:)?\d{4}\.\d{4,5}(v\d+)?", value, re.IGNORECASE):
        return "arxiv", re.sub(r"(?i)^arxiv:|v\d+$", "", value)
    doi = normalize_doi(value)
    if re.match(r"^10\.\d{4,9}/\S+$", doi):
        return "doi", doi
    openalex = re.fullmatch(r"(?:https?://openalex\.org/)?(W\d+)", value, re.IGNORECASE)
    if openalex:
        return "openalex", openalex.group(1).upper()
    if re.fullmatch(r"[0-9a-f]{40}", value.lower()):
        return "semantic_scholar", value.lower()
    return "title", value


def paper_details(
    identifier: str, client: httpx.Client | None = None, contact_email: str = "", s2_api_key: str = ""
) -> dict[str, Any]:
    """Szczegóły pracy (OpenAlex + Semantic Scholar, dla arXiv także arXiv)."""
    kind, value = classify_identifier(identifier)
    own_client = client is None
    client = client or scholar_client()
    extra: dict[str, Any] = {}
    errors: dict[str, str] = {}
    groups: dict[str, list[Paper]] = {}
    params = {"mailto": contact_email} if contact_email else None
    try:
        if kind == "title":
            found = search(
                Query(value, limit=3, contact_email=contact_email), ["openalex", "crossref"], client
            )
            if not found["papers"]:
                raise ScholarError("Nie znaleziono pracy o podanym tytule.")
            best = found["papers"][0]
            kind, value = ("doi", best.doi) if best.doi else ("openalex", best.ids.get("openalex", ""))
        openalex_path = {
            "doi": f"doi:{value}",
            "openalex": value,
            "arxiv": f"doi:10.48550/arXiv.{value}",
        }.get(kind)
        if openalex_path:
            try:
                item = _get(client, f"{OPENALEX}/works/{quote(openalex_path, safe=':/')}", params).json()
                groups["openalex"] = [parse_openalex(item)]
                topic = (item.get("primary_topic") or {}).get("display_name")
                keywords = [entry.get("display_name") for entry in item.get("keywords") or []]
                extra.update({"topic": topic or "", "keywords": [k for k in keywords if k][:10]})
                extra["type"] = item.get("type", "")
            except ScholarError as error:
                errors["openalex"] = str(error)
        s2_id = {"doi": f"DOI:{value}", "arxiv": f"ARXIV:{value}", "semantic_scholar": value}.get(kind)
        if s2_id:
            try:
                item = _get(
                    client,
                    f"{SEMANTIC_SCHOLAR}/paper/{quote(s2_id, safe=':/')}",
                    {"fields": S2_DETAIL_FIELDS},
                    headers=_s2_headers(s2_api_key),
                    retry_after_limit=S2_RETRY_SECONDS,
                ).json()
                groups["semantic_scholar"] = [parse_semantic_scholar(item)]
                extra.update(
                    {
                        "references_count": item.get("referenceCount"),
                        "influential_citations": item.get("influentialCitationCount"),
                        "tldr": (item.get("tldr") or {}).get("text", ""),
                        "fields_of_study": item.get("fieldsOfStudy") or [],
                        "publication_types": item.get("publicationTypes") or [],
                    }
                )
            except ScholarError as error:
                errors["semantic_scholar"] = str(error)
        if kind == "arxiv":
            try:
                papers = parse_arxiv(_arxiv_text(client, {"id_list": value}))
                if papers:
                    groups["arxiv"] = papers
            except ScholarError as error:
                errors["arxiv"] = str(error)
    finally:
        if own_client:
            client.close()
    merged = merge_papers(groups)
    if not merged:
        raise ScholarError(
            "Nie udało się pobrać danych pracy: " + "; ".join(f"{k}: {v}" for k, v in errors.items())
        )
    paper = merged[0].as_dict(abstract_chars=0)
    paper.update({key: value for key, value in extra.items() if value not in (None, "", [])})
    paper["errors"] = errors
    return paper
