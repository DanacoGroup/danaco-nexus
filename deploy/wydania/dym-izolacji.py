"""Test dymny izolacji kont na produkcji: dwa tymczasowe konta, A tworzy, B nie widzi; oba usuwane."""

import asyncio
import io
import secrets
import sys

import httpx

API = "https://danaco-nexus.pl"
H = {"X-Nexus-Request": "1"}


async def konto(nazwa: str) -> tuple[httpx.AsyncClient, httpx.AsyncClient, str, str]:
    email = f"dym-{nazwa}-{secrets.token_hex(3)}@example.com"
    haslo = "Dym-Izolacji-" + secrets.token_hex(6)
    portal = httpx.AsyncClient(base_url=API, timeout=60)
    r = await portal.post(
        "/api/portal/konto/rejestracja", json={"email": email, "password": haslo, "name": nazwa}, headers=H
    )
    assert r.status_code == 201, r.text
    okno = httpx.AsyncClient(base_url=API, timeout=60)
    r = await okno.post("/api/auth/login", json={"username": email, "password": haslo}, headers=H)
    assert r.status_code == 200, r.text
    return portal, okno, email, haslo


async def main() -> int:
    wyniki: list[tuple[str, bool]] = []
    pa, a, _, haslo_a = await konto("a")
    pb, b, _, haslo_b = await konto("b")
    try:
        rozmowa = (await a.post("/api/conversations", json={"title": "Poufne A"}, headers=H)).json()["id"]
        plik = (
            await a.post(
                "/api/files", files={"file": ("tajne.txt", io.BytesIO(b"tajne A"), "text/plain")}, headers=H
            )
        ).json()["id"]
        wyniki.append(("B nie widzi rozmów A", (await b.get("/api/conversations")).json() == []))
        wyniki.append(
            ("B nie otworzy rozmowy A", (await b.get(f"/api/conversations/{rozmowa}")).status_code == 404)
        )
        wyniki.append(
            ("B nie pobierze pliku A", (await b.get(f"/api/files/{plik}/download")).status_code == 404)
        )
        szkice = await b.get("/api/poczta/oczekujace")
        wyniki.append(("lista szkiców poczty B pusta", szkice.status_code == 200 and szkice.json() == []))
        wyniki.append(
            ("B nie dostaje loginu chmury", "admin" not in (await b.get("/api/cloud/synchronizacja")).text)
        )
        wyniki.append(
            ("B nie dostaje CalDAV", (await b.get("/api/kalendarz/synchronizacja")).status_code == 403)
        )
        kosz = await b.get("/api/cloud/kosz")
        wyniki.append(("kosz B pusty albo niedostępny", kosz.status_code != 200 or kosz.json() == []))
        wyniki.append(
            ("A widzi swoją rozmowę", (await a.get(f"/api/conversations/{rozmowa}")).status_code == 200)
        )
    finally:
        for portal, okno, haslo in ((pa, a, haslo_a), (pb, b, haslo_b)):
            r = await portal.post(
                "/api/portal/konto/usuniecie", json={"password": haslo, "confirmation": "USUWAM"}, headers=H
            )
            wyniki.append((f"usunięcie konta ({r.status_code})", r.status_code == 200))
            wyniki.append(("sesja okna wygasła", (await okno.get("/api/conversations")).status_code == 401))
            await portal.aclose()
            await okno.aclose()
    for opis, ok in wyniki:
        print(("OK   " if ok else "BŁĄD ") + opis)
    return 0 if all(ok for _, ok in wyniki) else 1


sys.exit(asyncio.run(main()))
