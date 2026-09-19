#!/usr/bin/env python3
"""Ustawia rekordy DNS Danaco Nexus w strefie OVH (idempotentnie).

Rekordy: danaco-nexus.pl, www i chmura → adres IPv4/IPv6 serwera.
Poświadczenia API OVH: /etc/danaco/ovh.env (OVH_ENDPOINT, OVH_AK, OVH_AS, OVH_CK).

Użycie:  deploy/dns/ustaw-dns.py [--sprawdz]
  --sprawdz  tylko pokazuje stan strefy i planowane zmiany, niczego nie zmienia.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request

STREFA = "danaco-nexus.pl"
IPV4 = "193.70.46.37"
IPV6 = "2001:41d0:303:c25::"
NAZWY = ("", "www", "chmura")
TTL = 3600
PLIK_POSWIADCZEN = "/etc/danaco/ovh.env"
ENDPOINTY = {"ovh-eu": "https://eu.api.ovh.com/1.0"}


def poswiadczenia() -> dict[str, str]:
    wartosci = {}
    with open(PLIK_POSWIADCZEN, encoding="utf-8") as plik:
        for wiersz in plik:
            wiersz = wiersz.strip()
            if wiersz and not wiersz.startswith("#") and "=" in wiersz:
                klucz, wartosc = wiersz.split("=", 1)
                wartosci[klucz.strip()] = wartosc.strip().strip('"')
    return wartosci


class Ovh:
    def __init__(self) -> None:
        dane = poswiadczenia()
        self.url = ENDPOINTY.get(dane["OVH_ENDPOINT"], dane["OVH_ENDPOINT"])
        self.ak, self.as_, self.ck = dane["OVH_AK"], dane["OVH_AS"], dane["OVH_CK"]

    def __call__(self, metoda: str, sciezka: str, tresc: object | None = None) -> object:
        adres = self.url + sciezka
        cialo = json.dumps(tresc) if tresc is not None else ""
        czas = urllib.request.urlopen(self.url + "/auth/time", timeout=20).read().decode().strip()
        podpis = "+".join([self.as_, self.ck, metoda, adres, cialo, czas])
        naglowki = {
            "X-Ovh-Application": self.ak,
            "X-Ovh-Consumer": self.ck,
            "X-Ovh-Timestamp": czas,
            "X-Ovh-Signature": "$1$" + hashlib.sha1(podpis.encode()).hexdigest(),
            "Content-Type": "application/json",
        }
        zadanie = urllib.request.Request(adres, data=cialo.encode() or None, method=metoda, headers=naglowki)
        with urllib.request.urlopen(zadanie, timeout=30) as odpowiedz:
            surowe = odpowiedz.read()
        return json.loads(surowe) if surowe else None


def main() -> int:
    tylko_sprawdz = "--sprawdz" in sys.argv[1:]
    api = Ovh()
    if STREFA not in api("GET", "/domain/zone"):
        print(f"Strefy {STREFA} nie ma jeszcze na koncie OVH (domena nie jest zarejestrowana lub nie używa DNS OVH).")
        return 2
    zmiany = 0
    for nazwa in NAZWY:
        for typ, adres in (("A", IPV4), ("AAAA", IPV6)):
            identyfikatory = api("GET", f"/domain/zone/{STREFA}/record?fieldType={typ}&subDomain={nazwa}")
            rekordy = [api("GET", f"/domain/zone/{STREFA}/record/{i}") for i in identyfikatory]
            etykieta = f"{nazwa or '@'} {typ}"
            if [r["target"] for r in rekordy] == [adres]:
                print(f"OK      {etykieta} → {adres}")
                continue
            print(f"ZMIANA  {etykieta}: {[r['target'] for r in rekordy]} → {adres}")
            zmiany += 1
            if tylko_sprawdz:
                continue
            for rekord in rekordy:
                api("DELETE", f"/domain/zone/{STREFA}/record/{rekord['id']}")
            api(
                "POST",
                f"/domain/zone/{STREFA}/record",
                {"fieldType": typ, "subDomain": nazwa, "target": adres, "ttl": TTL},
            )
    if zmiany and not tylko_sprawdz:
        api("POST", f"/domain/zone/{STREFA}/refresh")
        print(f"Odświeżono strefę {STREFA} ({zmiany} zmian).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as blad:
        print(f"Błąd API OVH {blad.code}: {blad.read().decode()[:300]}", file=sys.stderr)
        raise SystemExit(1) from None
