"""Kanały portalu dla wyszukiwarek i czytników: Atom 1.0, ``sitemap.xml`` i ``robots.txt``.

Adresy budowane są z adresu publicznego (``NEXUS_PORTAL_PUBLIC_URL`` albo ``NEXUS_PUBLIC_URL``)
i ścieżek portalu opisanych w ``docs/portal/README.md``.
"""

from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape

from nexus.db import utcnow
from nexus.models.portal import PortalContent

# Ścieżki stron portalu bez własnego wpisu w bazie (sekcje stałe interfejsu). Kolejność i zestaw
# odpowiadają trasowaniu w ``frontend/src/portal/trasy.ts``; adres strony produktu to korzeń witryny,
# bo „/start” pokazuje tę samą treść i wskazuje „/” jako kanoniczny. Trzy strony zgodności są
# publiczne i indeksowalne, więc mają wpis w mapie — rzadko się zmieniają, stąd niski priorytet.
STRONY_STALE = (
    ("/", "1.0", "daily"),
    ("/wyprobuj", "0.7", "monthly"),
    ("/portal", "0.9", "daily"),
    ("/portal/oferta", "0.9", "weekly"),
    ("/portal/funkcje", "0.9", "weekly"),
    ("/portal/zastosowania", "0.9", "weekly"),
    ("/portal/narzedzia", "0.9", "weekly"),
    ("/portal/cennik", "0.9", "weekly"),
    ("/portal/dokumentacja", "0.8", "weekly"),
    ("/portal/blog", "0.8", "daily"),
    ("/portal/wiedza", "0.8", "weekly"),
    ("/portal/kontakt", "0.5", "monthly"),
    ("/portal/prywatnosc", "0.4", "yearly"),
    ("/portal/regulamin", "0.4", "yearly"),
    ("/portal/cookies", "0.4", "yearly"),
)
# Ścieżka listy dla każdego rodzaju treści; pozycje trafiają pod ``<lista>/<slug>``.
SCIEZKI = {
    "blog": "/portal/blog",
    "wiedza": "/portal/wiedza",
    "dokumentacja": "/portal/dokumentacja",
    "strona": "/portal/s",
}
# Adresy zamknięte dla robotów: API, aplikacja użytkownika, panele po zalogowaniu i punkty
# techniczne. Ten sam wykaz odsiewa mapę witryny, więc żaden z nich nie może do niej trafić.
ZAMKNIETE = (
    "/api/",
    "/c/",
    "/m/",
    "/pobierz/",
    "/share-target",
    "/zaloguj",
    "/portal/konto",
    "/portal/panel",
    "/portal/admin",
    "/portal/szukaj",
    "/s/",
)
# Adres wariantowy tej samej treści; kanoniczny wskazuje korzeń witryny (``frontend/src/seo.ts``).
ZAMKNIETE_WZORCE = ("/*?widok=panel",)
# Adresy zamknięte dokładnie, bez podrzędnych: ``/portal/s`` to sam przedrostek stron Twórcy (nie ma
# go w trasowaniu), ale ``/portal/s/<adres>`` zostaje otwarty. W ``robots.txt`` stąd znak „$”.
ZAMKNIETE_DOKLADNE = ("/portal/s",)


def adres_pozycji(baza: str, record: PortalContent) -> str:
    """Pełny adres pozycji treści."""
    return f"{baza}{SCIEZKI.get(record.kind, '/portal')}/{record.slug}"


def czy_zamkniety(sciezka: str) -> bool:
    """Czy ścieżka należy do części zamkniętej dla robotów."""
    if sciezka in ZAMKNIETE_DOKLADNE:
        return True
    return any(sciezka == zamknieta.rstrip("/") or sciezka.startswith(zamknieta) for zamknieta in ZAMKNIETE)


def _czas(wartosc: datetime | None) -> str:
    return (wartosc or utcnow()).isoformat()


def atom(baza: str, pozycje: list[PortalContent], tytul: str = "Danaco Nexus – blog") -> str:
    """Kanał Atom 1.0 z podanymi pozycjami (najnowsza pierwsza)."""
    zaktualizowano = _czas(max((p.published_at for p in pozycje if p.published_at), default=None))
    wiersze = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="pl">',
        f"<title>{escape(tytul)}</title>",
        f"<id>{escape(baza)}/portal/blog</id>",
        f'<link rel="alternate" type="text/html" href="{escape(baza)}/portal/blog"/>',
        f'<link rel="self" type="application/atom+xml" href="{escape(baza)}/portal/atom.xml"/>',
        f"<updated>{zaktualizowano}</updated>",
    ]
    for record in pozycje:
        adres = adres_pozycji(baza, record)
        wiersze += [
            "<entry>",
            f"<title>{escape(record.title)}</title>",
            f"<id>{escape(adres)}</id>",
            f'<link rel="alternate" type="text/html" href="{escape(adres)}"/>',
            f"<updated>{_czas(record.updated_at)}</updated>",
            f"<published>{_czas(record.published_at)}</published>",
            f"<summary type=\"text\">{escape(record.excerpt)}</summary>",
        ]
        if record.author:
            wiersze.append(f"<author><name>{escape(record.author)}</name></author>")
        for znacznik in record.tags or []:
            wiersze.append(f'<category term="{escape(znacznik)}"/>')
        wiersze.append("</entry>")
    wiersze.append("</feed>")
    return "\n".join(wiersze)


def sitemap(baza: str, pozycje: list[PortalContent]) -> str:
    """Mapa witryny: stałe strony portalu i opublikowane treści."""
    wiersze = ['<?xml version="1.0" encoding="utf-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for sciezka, priorytet, czestotliwosc in STRONY_STALE:
        if czy_zamkniety(sciezka):
            continue
        wiersze += [
            "<url>",
            f"<loc>{escape(baza)}{sciezka}</loc>",
            f"<changefreq>{czestotliwosc}</changefreq>",
            f"<priority>{priorytet}</priority>",
            "</url>",
        ]
    for record in pozycje:
        if (record.seo or {}).get("noindex"):
            continue
        adres = adres_pozycji(baza, record)
        if czy_zamkniety(adres[len(baza) :]):
            continue
        wiersze += [
            "<url>",
            f"<loc>{escape(adres)}</loc>",
            f"<lastmod>{_czas(record.updated_at)}</lastmod>",
            "<changefreq>monthly</changefreq>",
            "<priority>0.7</priority>",
            "</url>",
        ]
    wiersze.append("</urlset>")
    return "\n".join(wiersze)


def robots(baza: str) -> str:
    """Treść ``robots.txt``: część publiczna otwarta, aplikacja i API zamknięte."""
    wiersze = ["User-agent: *", "Allow: /portal"]
    wiersze += [f"Disallow: {sciezka}" for sciezka in (*ZAMKNIETE, *ZAMKNIETE_WZORCE)]
    wiersze += [f"Disallow: {sciezka}$" for sciezka in ZAMKNIETE_DOKLADNE]
    wiersze += ["", f"Sitemap: {baza}/sitemap.xml"]
    return "\n".join(wiersze) + "\n"
