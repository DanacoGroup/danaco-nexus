"""Własne konta Nextcloud dla planów z synchronizacją (atrapa Nextclouda w pamięci)."""

from __future__ import annotations

import asyncio
import base64
import uuid
from pathlib import Path
from urllib.parse import parse_qs, unquote

import httpx
import pytest

from nexus.chmura_konta import BladKontaChmury, konto_chmury, uid_konta, zapewnij_konto
from nexus.config import Settings
from nexus.db import ADMIN_OWNER

MULTISTATUS_CALDAV = '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'


class AtrapaNextcloud:
    """Minimalny Nextcloud: OCS użytkowników i WebDAV plików, wszystko w słownikach."""

    def __init__(self) -> None:
        self.hasla: dict[str, str] = {"admin": "token-techniczny"}
        self.limity: dict[str, str] = {}
        self.pliki: dict[str, bytes] = {}
        self.katalogi: set[str] = set()
        self.usuniete: list[str] = []
        # Kalendarze: ścieżka kolekcji → {nazwa pliku .ics: treść}.
        self.kalendarze: dict[str, dict[str, str]] = {}

    def _ocs(self, kod: int) -> httpx.Response:
        return httpx.Response(200, json={"ocs": {"meta": {"statuscode": kod}, "data": {}}})

    def _multistatus(self, sciezka: str) -> httpx.Response:
        prefiks = sciezka.rstrip("/") + "/"
        wpisy = [
            f"<d:response><d:href>{prefiks}</d:href><d:propstat><d:prop><d:resourcetype><d:collection/>"
            "</d:resourcetype></d:prop></d:propstat></d:response>"
        ]
        for katalog in sorted(self.katalogi):
            if katalog.startswith(prefiks) and "/" not in katalog[len(prefiks) :].rstrip("/"):
                wpisy.append(
                    f"<d:response><d:href>{katalog}/</d:href><d:propstat><d:prop><d:resourcetype>"
                    "<d:collection/></d:resourcetype></d:prop></d:propstat></d:response>"
                )
        for plik in sorted(self.pliki):
            if plik.startswith(prefiks) and "/" not in plik[len(prefiks) :]:
                wpisy.append(
                    f"<d:response><d:href>{plik}</d:href><d:propstat><d:prop><d:resourcetype/>"
                    "</d:prop></d:propstat></d:response>"
                )
        tresc = '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">' + "".join(wpisy) + "</d:multistatus>"
        return httpx.Response(207, content=tresc.encode())

    def _caldav(self, request: httpx.Request, sciezka: str, login: str) -> httpx.Response:
        korzen = f"/remote.php/dav/calendars/{login}/"
        kolekcja = korzen + sciezka.removeprefix(korzen).split("/")[0] if sciezka != korzen else ""
        if request.method == "PROPFIND" and sciezka == korzen:
            wpisy = "".join(
                f"<d:response><d:href>{k}/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/>"
                "<c:calendar/></d:resourcetype><d:displayname>Kalendarz</d:displayname></d:prop></d:propstat>"
                "</d:response>"
                for k in self.kalendarze
                if k.startswith(korzen)
            )
            tresc = f"{MULTISTATUS_CALDAV}{wpisy}</d:multistatus>"
            return httpx.Response(207, content=tresc.encode())
        if request.method == "MKCALENDAR":
            if kolekcja in self.kalendarze:
                return httpx.Response(405)
            self.kalendarze[kolekcja] = {}
            return httpx.Response(201)
        if request.method == "REPORT":
            wpisy = "".join(
                f"<d:response><d:href>{kolekcja}/{plik}</d:href><d:propstat><d:prop>"
                f"<c:calendar-data>{dane}</c:calendar-data></d:prop></d:propstat></d:response>"
                for plik, dane in self.kalendarze.get(kolekcja, {}).items()
            )
            tresc = f"{MULTISTATUS_CALDAV}{wpisy}</d:multistatus>"
            return httpx.Response(207, content=tresc.encode())
        if request.method == "PUT":
            self.kalendarze.setdefault(kolekcja, {})[sciezka.rsplit("/", 1)[-1]] = request.read().decode()
            return httpx.Response(201)
        if request.method == "DELETE":
            self.kalendarze.pop(kolekcja, None)
            return httpx.Response(204)
        return httpx.Response(405)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        naglowek = request.headers.get("authorization", "")
        login, _, haslo = base64.b64decode(naglowek.split()[-1]).decode().partition(":")
        if self.hasla.get(login) != haslo:
            return httpx.Response(401)
        sciezka = unquote(request.url.path)
        if sciezka == "/ocs/v1.php/cloud/users" and request.method == "POST":
            dane = parse_qs(request.content.decode())
            uid = dane["userid"][0]
            if uid in self.hasla:
                return self._ocs(102)
            self.hasla[uid] = dane["password"][0]
            self.katalogi.add(f"/remote.php/dav/files/{uid}")
            return self._ocs(100)
        if sciezka.startswith("/ocs/v1.php/cloud/users/") and request.method == "PUT":
            uid = sciezka.rsplit("/", 1)[-1]
            dane = parse_qs(request.content.decode())
            if dane["key"][0] == "password":
                self.hasla[uid] = dane["value"][0]
            else:
                self.limity[uid] = dane["value"][0]
            return self._ocs(100)
        if sciezka.startswith(f"/remote.php/dav/calendars/{login}/"):
            return self._caldav(request, sciezka, login)
        wlasny = f"/remote.php/dav/files/{login}"
        if not sciezka.startswith(wlasny):
            return httpx.Response(403)
        if request.method == "PROPFIND":
            if sciezka.rstrip("/") not in self.katalogi:
                return httpx.Response(404)
            return self._multistatus(sciezka)
        if request.method == "MKCOL":
            if sciezka.rstrip("/") in self.katalogi:
                return httpx.Response(405)
            self.katalogi.add(sciezka.rstrip("/"))
            return httpx.Response(201)
        if request.method == "GET":
            if sciezka not in self.pliki:
                return httpx.Response(404)
            return httpx.Response(200, content=self.pliki[sciezka])
        if request.method == "PUT":
            self.pliki[sciezka] = request.read()
            return httpx.Response(201)
        if request.method == "DELETE":
            self.usuniete.append(sciezka)
            self.katalogi = {k for k in self.katalogi if not k.startswith(sciezka)}
            self.pliki = {k: v for k, v in self.pliki.items() if not k.startswith(sciezka)}
            return httpx.Response(204)
        return httpx.Response(405)


def occ_atrapy(chmura: AtrapaNextcloud):  # type: ignore[no-untyped-def]
    """``occ`` działający na stanie atrapy: zakładanie kont, hasła i limity."""

    async def occ(argumenty: list[str], srodowisko: dict[str, str]) -> tuple[int, str]:
        polecenie, uid = argumenty[0], argumenty[-1]
        if polecenie == "user:add":
            if uid in chmura.hasla:
                return 1, f'The user "{uid}" already exists.'
            chmura.hasla[uid] = srodowisko["OC_PASS"]
            chmura.katalogi.add(f"/remote.php/dav/files/{uid}")
            return 0, f'The user "{uid}" was created successfully'
        if polecenie == "user:resetpassword":
            chmura.hasla[uid] = srodowisko["OC_PASS"]
            return 0, "Successfully reset password"
        if polecenie == "user:setting":
            chmura.limity[argumenty[1]] = argumenty[-1]
            return 0, ""
        return 1, "nieznane polecenie"

    return occ


@pytest.fixture
def ustawienia(tmp_path: Path) -> Settings:
    token = tmp_path / "app" / "chmura-token"
    token.parent.mkdir()
    token.write_text("token-techniczny\n", encoding="utf-8")
    return Settings(
        chmura_url="http://chmura.test",
        chmura_user="admin",
        chmura_token_file=token,
        database_url="sqlite+aiosqlite:///:memory:",
    )


def test_konto_powstaje_z_limitem_planu_i_przejmuje_pliki(ustawienia: Settings) -> None:
    chmura = AtrapaNextcloud()
    klient = uuid.uuid4()
    stary = f"/remote.php/dav/files/admin/Konta/{klient}"
    techniczny = "/remote.php/dav/files/admin"
    chmura.katalogi |= {techniczny, f"{techniczny}/Konta", stary, f"{stary}/Umowy"}
    chmura.pliki[f"{stary}/notatka.txt"] = b"pierwsza"
    chmura.kalendarze[f"/remote.php/dav/calendars/admin/konto-{klient}-personal"] = {
        "spotkanie.ics": "BEGIN:VCALENDAR"
    }
    chmura.pliki[f"{stary}/Umowy/umowa.pdf"] = b"%PDF druga"
    transport = httpx.MockTransport(chmura)

    konto = asyncio.run(zapewnij_konto(ustawienia, klient, 2048, transport, occ_atrapy(chmura)))

    assert konto.uid == uid_konta(klient) and chmura.hasla[konto.uid] == konto.haslo
    assert chmura.limity[konto.uid] == "2048 MB"
    nowy = f"/remote.php/dav/files/{konto.uid}"
    assert chmura.pliki[f"{nowy}/notatka.txt"] == b"pierwsza"
    assert chmura.pliki[f"{nowy}/Umowy/umowa.pdf"] == b"%PDF druga"
    assert stary in chmura.usuniete and not any(k.startswith(stary) for k in chmura.pliki)
    # Kalendarz konta przechodzi razem z plikami: z przedrostkiem w koncie technicznym, bez niego u klienta.
    assert chmura.kalendarze == {
        f"/remote.php/dav/calendars/{konto.uid}/personal": {"spotkanie.ics": "BEGIN:VCALENDAR"}
    }
    # Hasło zna tylko Nexus: plik z prawami wyłącznie dla właściciela procesu.
    zapisane = konto_chmury(ustawienia, klient)
    assert zapisane == konto
    plik = ustawienia.chmura_token_file.parent / "chmura-konta" / konto.uid
    assert plik.stat().st_mode & 0o077 == 0

    # Drugie wywołanie nie zakłada konta od nowa, tylko odświeża limit (np. po zmianie planu).
    ponownie = asyncio.run(zapewnij_konto(ustawienia, klient, 10240, transport, occ_atrapy(chmura)))
    assert ponownie == konto and chmura.limity[konto.uid] == "10240 MB"


def test_konto_bez_zapisanego_hasla_dostaje_nowe_zamiast_drugiego_konta(ustawienia: Settings) -> None:
    chmura = AtrapaNextcloud()
    klient = uuid.uuid4()
    chmura.hasla[uid_konta(klient)] = "zgubione"
    transport = httpx.MockTransport(chmura)
    konto = asyncio.run(zapewnij_konto(ustawienia, klient, 1024, transport, occ_atrapy(chmura)))
    assert chmura.hasla[konto.uid] == konto.haslo != "zgubione"


def test_wlasciciel_instalacji_nie_dostaje_osobnego_konta(ustawienia: Settings) -> None:
    assert konto_chmury(ustawienia, ADMIN_OWNER) is None
    with pytest.raises(BladKontaChmury):
        asyncio.run(zapewnij_konto(ustawienia, ADMIN_OWNER, 1024))


def test_zawieszony_occ_jest_zabijany(
    ustawienia: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """occ, który nie odpowiada, nie może zostać w tle z hasłem konta w środowisku."""
    import nexus.chmura_konta as modul

    skrypt = tmp_path / "occ"
    skrypt.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    skrypt.chmod(0o755)
    ustawienia.chmura_occ = skrypt
    oryginal = asyncio.wait_for

    async def szybko(zadanie, timeout):  # type: ignore[no-untyped-def]
        return await oryginal(zadanie, timeout=0.2)

    monkeypatch.setattr(modul.asyncio, "wait_for", szybko)
    kod, wyjscie = asyncio.run(modul.occ_uslugi(ustawienia)(["status"], {}))
    assert kod == 124 and "120 s" in wyjscie
