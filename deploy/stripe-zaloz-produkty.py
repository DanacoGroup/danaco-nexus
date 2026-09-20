#!/usr/bin/env python3
"""Zakłada w Stripe produkty i ceny Danaco Nexus; wypisuje gotowe wpisy do `.env`.

Skrypt jest idempotentny: produkt i cenę rozpoznaje po znaczniku `metadata.nexus`,
więc powtórne uruchomienie niczego nie dubluje. Cen w Stripe nie da się zmienić —
zmiana kwoty znaczy nową cenę, a stara zostaje przy tych, którzy już płacą. Dlatego
przy innej kwocie skrypt zakłada nową cenę i to jej identyfikator wypisuje.

  deploy/stripe-zaloz-produkty.py [--na-sucho]

Klucz bierze z pliku wskazanego przez `NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK`, a gdy go nie
ma — z `/etc/danaco/ekancelaria.env` (to samo konto Stripe obsługuje projekty Danaco).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.stripe.com/v1"
ZNACZNIK = "danaco-nexus"

#: Plany: kod, nazwa, opis, kwota miesięczna w groszach. Cena roczna to dziesięciokrotność
#: miesięcznej — dwa miesiące w prezencie za zobowiązanie na rok.
PLANY: list[tuple[str, str, str, int]] = [
    ("osobisty", "Danaco Nexus — Osobisty", "Dla jednej osoby, do pracy i do życia.", 8_900),
    ("pro", "Danaco Nexus — Pro", "Dla tych, którzy używają Nexusa codziennie i dużo.", 19_900),
    ("zespol", "Danaco Nexus — Grupa", "Cena za każdego użytkownika w grupie.", 4_900),
]

#: Pakiety kredytów: kod, nazwa, liczba kredytów, kwota w groszach. Im większy pakiet,
#: tym niższa stawka za kredyt — przy dużym schodzi do poziomu planu Pro.
PAKIETY: list[tuple[str, str, int, int]] = [
    ("maly", "Danaco Nexus — 5 000 kredytów", 5_000, 7_900),
    ("sredni", "Danaco Nexus — 20 000 kredytów", 20_000, 24_900),
    ("duzy", "Danaco Nexus — 60 000 kredytów", 60_000, 59_900),
]


def klucz_stripe() -> str:
    plik = os.environ.get("NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK", "")
    if plik and pathlib.Path(plik).is_file():
        return pathlib.Path(plik).read_text(encoding="utf-8").strip()
    zapas = pathlib.Path("/etc/danaco/ekancelaria.env")
    if zapas.is_file():
        trafienie = re.search(r'^STRIPE_SECRET_KEY=["\']?([^"\'\n]*)', zapas.read_text(), re.M)
        if trafienie and trafienie.group(1).strip():
            return trafienie.group(1).strip()
    raise SystemExit("Nie znalazłem klucza Stripe. Ustaw NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK.")


def wywolaj(klucz: str, sciezka: str, dane: dict[str, str] | None = None, **zapytanie: str):  # type: ignore[no-untyped-def]
    adres = f"{API}/{sciezka}"
    if zapytanie:
        adres += "?" + urllib.parse.urlencode(zapytanie)
    ciało = urllib.parse.urlencode(dane).encode() if dane else None
    zad = urllib.request.Request(adres, data=ciało, headers={"Authorization": f"Bearer {klucz}"})
    try:
        with urllib.request.urlopen(zad, timeout=30) as odp:
            return json.load(odp)
    except urllib.error.HTTPError as blad:
        tresc = blad.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"Stripe odmówił ({blad.code}) przy {sciezka}: {tresc}") from blad


def znajdz_produkt(klucz: str, kod: str):  # type: ignore[no-untyped-def]
    """Produkt Nexusa o danym kodzie albo None — rozpoznawany po znaczniku, nie po nazwie."""
    for produkt in wywolaj(klucz, "products", limit="100", active="true")["data"]:
        meta = produkt.get("metadata", {})
        if meta.get("nexus") == ZNACZNIK and meta.get("kod") == kod:
            return produkt
    return None


def znajdz_cene(klucz: str, produkt_id: str, kwota: int, okres: str | None):  # type: ignore[no-untyped-def]
    """Aktywna cena o tej samej kwocie i tym samym okresie albo None."""
    for cena in wywolaj(klucz, "prices", product=produkt_id, limit="100", active="true")["data"]:
        if cena["unit_amount"] != kwota or cena["currency"] != "pln":
            continue
        cykl = (cena.get("recurring") or {}).get("interval")
        if okres is None and cykl is None:
            return cena
        if okres == "miesiac" and cykl == "month":
            return cena
        if okres == "rok" and cykl == "year":
            return cena
    return None


def zapewnij_produkt(klucz: str, kod: str, nazwa: str, opis: str, na_sucho: bool):  # type: ignore[no-untyped-def]
    istniejacy = znajdz_produkt(klucz, kod)
    if istniejacy:
        print(f"  produkt {kod}: jest ({istniejacy['id']})", file=sys.stderr)
        return istniejacy
    if na_sucho:
        print(f"  produkt {kod}: DO ZAŁOŻENIA — {nazwa}", file=sys.stderr)
        return {"id": f"(nowy:{kod})"}
    produkt = wywolaj(
        klucz,
        "products",
        {"name": nazwa, "description": opis, "metadata[nexus]": ZNACZNIK, "metadata[kod]": kod},
    )
    print(f"  produkt {kod}: założony ({produkt['id']})", file=sys.stderr)
    return produkt


def zapewnij_cene(klucz: str, produkt, kwota: int, okres: str | None, opis: str, na_sucho: bool) -> str:  # type: ignore[no-untyped-def]
    if not produkt["id"].startswith("prod_"):
        return f"(nowa:{opis})"
    istniejaca = znajdz_cene(klucz, produkt["id"], kwota, okres)
    if istniejaca:
        print(f"    cena {opis}: jest ({istniejaca['id']})", file=sys.stderr)
        return istniejaca["id"]
    if na_sucho:
        print(f"    cena {opis}: DO ZAŁOŻENIA — {kwota / 100:.2f} zł", file=sys.stderr)
        return f"(nowa:{opis})"
    dane = {
        "product": produkt["id"],
        "currency": "pln",
        "unit_amount": str(kwota),
        "metadata[nexus]": ZNACZNIK,
    }
    if okres:
        dane["recurring[interval]"] = "month" if okres == "miesiac" else "year"
    cena = wywolaj(klucz, "prices", dane)
    print(f"    cena {opis}: założona ({cena['id']}, {kwota / 100:.2f} zł)", file=sys.stderr)
    return cena["id"]


def main() -> int:
    na_sucho = "--na-sucho" in sys.argv
    klucz = klucz_stripe()
    tryb = "TESTOWY" if klucz.startswith(("sk_test_", "rk_test_")) else "PRAWDZIWY"
    print(f"Konto Stripe: tryb {tryb}{' — nic nie zakładam' if na_sucho else ''}", file=sys.stderr)

    ceny: list[str] = []
    kwoty: list[str] = []

    print("Plany:", file=sys.stderr)
    for kod, nazwa, opis, miesiac in PLANY:
        produkt = zapewnij_produkt(klucz, kod, nazwa, opis, na_sucho)
        rok = miesiac * 10
        ceny.append(f"{kod}:miesiac={zapewnij_cene(klucz, produkt, miesiac, 'miesiac', f'{kod} mies.', na_sucho)}")
        ceny.append(f"{kod}:rok={zapewnij_cene(klucz, produkt, rok, 'rok', f'{kod} rok', na_sucho)}")
        kwoty.append(f"{kod}:miesiac={miesiac}")
        kwoty.append(f"{kod}:rok={rok}")

    print("Pakiety kredytów:", file=sys.stderr)
    for kod, nazwa, kredyty, kwota in PAKIETY:
        produkt = zapewnij_produkt(klucz, f"pakiet-{kod}", nazwa, f"{kredyty:,} kredytów".replace(",", " "), na_sucho)
        ceny.append(f"pakiet:{kod}={zapewnij_cene(klucz, produkt, kwota, None, f'pakiet {kod}', na_sucho)}")
        kwoty.append(f"pakiet:{kod}={kwota}")

    print("\n# Wpisy do .env:", file=sys.stderr)
    print(f"NEXUS_PLATNOSCI_CENY={';'.join(ceny)}")
    print(f"NEXUS_PLATNOSCI_KWOTY={';'.join(kwoty)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
