"""Testy poczty: parsowanie wiadomości, klient IMAP/SMTP (atrapy), narzędzia agenta i API modułu."""

from __future__ import annotations

import email
import json
import uuid
from email.policy import default as default_policy
from pathlib import Path

import httpx
import pytest
from biuro_pomoc import HEADERS, MailServer, api, biuro_settings, mail_server, raw_message  # noqa: F401
from conftest import ToolHarness
from fastapi.testclient import TestClient

from nexus.api.modules import poczta as poczta_api
from nexus.config import Settings
from nexus.mail import (
    MailClient,
    MailError,
    MailNotConfigured,
    build_message,
    html_to_text,
    load_config,
    parse_message,
    reply_headers,
    utf7_decode,
    utf7_encode,
)
from nexus.tools import registry
from nexus.tools.base import ToolError


def call(harness: ToolHarness, name: str, /, **arguments: object):  # type: ignore[no-untyped-def]
    tool = registry.get(name)
    return tool.handler(harness.context(), tool.parse(arguments))


@pytest.fixture
def tool_harness(harness: ToolHarness, biuro_settings: Settings) -> ToolHarness:  # noqa: F811
    harness.settings = biuro_settings
    return harness


# --- funkcje pomocnicze ---


@pytest.mark.parametrize("name", ["Wysłane", "Kosz & spam", "Zażółć/gęślą", "INBOX", "Ðá"])
def test_utf7_roundtrip(name: str) -> None:
    encoded = utf7_encode(name)
    assert encoded.isascii()
    assert utf7_decode(encoded) == name


def test_utf7_known_value() -> None:
    assert utf7_encode("Wysłane") == "Wys&AUI-ane"
    assert utf7_decode("Elementy wys&AUI-ane") == "Elementy wysłane"


def test_parse_message_text_html_and_attachments() -> None:
    raw = raw_message(
        "Oferta – zażółć",
        body="Dzień dobry,\nw załączniku oferta.",
        html="<p>Dzień <b>dobry</b></p><script>alert(1)</script>",
        attachment=("oferta.pdf", b"%PDF-1.4 test"),
    )
    parsed = parse_message(raw)
    assert parsed["subject"] == "Oferta – zażółć"
    assert parsed["from"] == [{"name": "Jan Kowalski", "email": "jan@example.pl"}]
    assert parsed["text"].startswith("Dzień dobry")
    assert "<b>dobry</b>" in parsed["html"]
    assert [(a["name"], a["mime"], a["size"]) for a in parsed["attachments"]] == [
        ("oferta.pdf", "application/pdf", 13)
    ]
    assert parsed["date"].startswith("2026-09-18")


def test_html_to_text_skips_scripts() -> None:
    text = html_to_text("<html><head><style>p{}</style></head><p>Raz</p><script>x()</script><p>Dwa</p>")
    assert text == "Raz\n\nDwa"


def test_reply_headers_and_build_message() -> None:
    original = parse_message(raw_message("Pytanie o termin", message_id="<abc@example.pl>"))
    headers = reply_headers(original)
    assert headers["subject"] == "Re: Pytanie o termin"
    assert headers["to"] == "Jan Kowalski <jan@example.pl>"
    assert reply_headers({**original, "subject": "RE: x"})["subject"] == "RE: x"
    settings_file = {"login": "biuro@danaco-group.pl", "password": "x", "name": "Biuro"}
    config = load_config_from(settings_file)
    message = build_message(
        config, [headers["to"]], headers["subject"], "Odpowiedź", in_reply_to=headers["in_reply_to"]
    )
    assert message["In-Reply-To"] == "<abc@example.pl>"
    assert message["From"] == "Biuro <biuro@danaco-group.pl>"
    assert message["Message-ID"].endswith("@danaco-group.pl>")
    with pytest.raises(MailError, match="Nieprawidłowy adres"):
        build_message(config, ["to nie adres"], "x", "y")


def load_config_from(data: dict[str, object], tmp: Path | None = None) -> object:
    import tempfile

    directory = Path(tmp or tempfile.mkdtemp())
    path = directory / "poczta.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_config(Settings(poczta_config_file=path, database_url="sqlite+aiosqlite:///:memory:"))


def test_load_config_errors(tmp_path: Path) -> None:
    settings = Settings(
        poczta_config_file=tmp_path / "brak.json", database_url="sqlite+aiosqlite:///:memory:"
    )
    with pytest.raises(MailNotConfigured, match="zapisz-poczte"):
        load_config(settings)
    with pytest.raises(MailNotConfigured, match="loginu i hasła"):
        load_config_from({"login": "a@b.pl"}, tmp_path)
    with pytest.raises(MailNotConfigured, match="smtp_security"):
        load_config_from({"login": "a@b.pl", "password": "x", "smtp_security": "brak"}, tmp_path)
    config = load_config_from({"login": "a@b.pl", "password": "x", "smtp_security": "starttls"}, tmp_path)
    assert (config.smtp_port, config.address, config.imap_port) == (587, "a@b.pl", 993)  # type: ignore[attr-defined]
    assert "x" not in repr(config)


# --- klient IMAP na atrapie ---


def test_client_folders_list_read_search(mail_server: MailServer, biuro_settings: Settings) -> None:  # noqa: F811
    mail_server.add("INBOX", raw_message("Pierwsza"), {"\\Seen"})
    second = mail_server.add("INBOX", raw_message("Faktura żółta", body="Kwota 100 zł"))
    with MailClient(load_config(biuro_settings)) as client:
        folders = client.folders(with_counts=True)
        assert [(f["name"], f["role"], f["label"]) for f in folders] == [
            ("INBOX", "INBOX", "Odebrane"),
            ("Drafts", "\\Drafts", "Szkice"),
            ("Wysłane", "\\Sent", "Wysłane"),
        ]
        assert folders[0]["messages"] == 2 and folders[0]["unseen"] == 1
        listing = client.list_messages("INBOX", limit=1)
        assert listing["total"] == 2 and listing["more"] is True
        assert [m["subject"] for m in listing["messages"]] == ["Faktura żółta"]
        older = client.list_messages("INBOX", before_uid=second)
        assert [m["subject"] for m in older["messages"]] == ["Pierwsza"]
        found = client.search("INBOX", text="żółta")
        assert [m["uid"] for m in found["messages"]] == [second]
        assert client.list_messages("INBOX", unread_only=True)["total"] == 1
        message = client.read("INBOX", second, mark_seen=True)
        assert message["text"].strip() == "Kwota 100 zł"
    assert "\\Seen" in mail_server.boxes["INBOX"][1].flags
    with pytest.raises(MailError, match="Nie ma folderu"), MailClient(load_config(biuro_settings)) as client:
        client.list_messages("Brak")


def test_client_rejects_wrong_password(mail_server: MailServer, biuro_settings: Settings) -> None:  # noqa: F811
    mail_server.password = "inne"
    with pytest.raises(MailError, match="odrzucił login"), MailClient(load_config(biuro_settings)):
        pass


# --- narzędzia agenta ---


def test_mail_tools(mail_server: MailServer, tool_harness: ToolHarness, tmp_path: Path) -> None:  # noqa: F811
    uid = mail_server.add(
        "INBOX", raw_message("Zapytanie", body="Proszę o ofertę.", attachment=("plan.pdf", b"%PDF-1.4"))
    )
    listing = call(tool_harness, "mail_list")
    assert listing.data["messages"][0]["subject"] == "Zapytanie"
    assert {"name": "Drafts", "role": "\\Drafts"} in listing.data["folders"]
    read = call(tool_harness, "mail_read", uid=uid, import_attachments=True)
    assert read.data["text"].strip() == "Proszę o ofertę."
    assert [output.name for output in read.files] == ["plan.pdf"]
    assert read.files[0].path.read_bytes() == b"%PDF-1.4"
    assert mail_server.boxes["INBOX"][0].flags == set(), "agent czyta bez oznaczania jako przeczytane"

    draft = call(tool_harness, "mail_draft", reply_to_uid=uid, body="Dziękujemy, oferta w załączeniu.")
    assert draft.data["saved_in"] == "Drafts"
    saved = email.message_from_bytes(mail_server.boxes["Drafts"][0].raw, policy=default_policy)
    assert saved["Subject"] == "Re: Zapytanie" and saved["In-Reply-To"] == "<m1@example.pl>"
    assert "> Proszę o ofertę." in saved.get_body().get_content()
    assert mail_server.boxes["Drafts"][0].flags == {"\\Draft", "\\Seen"}

    attachment = tmp_path / "oferta.txt"
    attachment.write_text("Oferta", encoding="utf-8")
    file_id = tool_harness.add(attachment)
    pending = call(tool_harness, "mail_send", reply_to_uid=uid, body="Odpowiedź", file_ids=[file_id])
    assert mail_server.sent == [], "agent nie wysyła poczty"
    assert "Oczekujące" in pending.data["status"]
    uuid.UUID(pending.data["pending_id"])
    with pytest.raises(ToolError, match="adresata"):
        call(tool_harness, "mail_send", subject="Bez adresata", body="x")


def test_mail_tools_without_configuration(harness: ToolHarness, tmp_path: Path) -> None:
    harness.settings.poczta_config_file = tmp_path / "brak.json"
    with pytest.raises(ToolError, match="nie jest skonfigurowana"):
        call(harness, "mail_list")


# --- API modułu ---


def test_api_state_without_configuration(api: TestClient) -> None:  # noqa: F811
    assert api.get("/api/poczta/stan").json()["configured"] is False
    assert api.get("/api/poczta/foldery").status_code == 503


def test_api_read_and_attachment(api: TestClient, mail_server: MailServer) -> None:  # noqa: F811
    uid = mail_server.add(
        "INBOX",
        raw_message("Z obrazem", html='<p>Hej</p><img src="cid:logo">', attachment=("umowa.pdf", b"%PDF")),
    )
    state = api.get("/api/poczta/stan").json()
    assert state == {"configured": True, "address": "biuro@danaco-group.pl", "name": "Biuro Danaco"}
    folders = api.get("/api/poczta/foldery").json()
    assert folders[0]["unseen"] == 1
    listing = api.get("/api/poczta/wiadomosci", params={"folder": "INBOX"}).json()
    assert listing["messages"][0]["has_attachments"] is True
    message = api.get("/api/poczta/wiadomosc", params={"folder": "INBOX", "uid": uid}).json()
    assert message["html"].startswith("<p>Hej</p>")
    assert "\\Seen" in mail_server.boxes["INBOX"][0].flags
    index = message["attachments"][0]["index"]
    download = api.get("/api/poczta/zalacznik", params={"folder": "INBOX", "uid": uid, "index": index})
    assert download.content == b"%PDF"
    assert download.headers["content-type"] == "application/octet-stream"
    assert "umowa.pdf" in download.headers["content-disposition"]
    inline = api.get(
        "/api/poczta/zalacznik", params={"folder": "INBOX", "uid": uid, "index": index, "inline": 1}
    )
    assert inline.headers["content-type"] == "application/pdf"
    flag = api.post("/api/poczta/flaga", json={"folder": "INBOX", "uid": uid, "flag": "seen", "value": False})
    assert flag.status_code == 403, "zmiana stanu wymaga nagłówka CSRF"
    flag = api.post(
        "/api/poczta/flaga",
        json={"folder": "INBOX", "uid": uid, "flag": "seen", "value": False},
        headers=HEADERS,
    )
    assert flag.status_code == 200 and "\\Seen" not in mail_server.boxes["INBOX"][0].flags


def test_api_pending_send_flow(api: TestClient, mail_server: MailServer) -> None:  # noqa: F811
    uid = mail_server.add("INBOX", raw_message("Pytanie", message_id="<q@example.pl>"))
    created = api.post(
        "/api/poczta/oczekujace",
        json={
            "to": ["Jan <jan@example.pl>"],
            "subject": "Re: Pytanie",
            "body": "Szkic",
            "reply": {"folder": "INBOX", "uid": uid},
            "in_reply_to": "<q@example.pl>",
        },
        headers=HEADERS,
    )
    assert created.status_code == 201, created.text
    pending = created.json()
    assert pending["status"] == "pending" and pending["summary"].startswith("Do: Jan <jan@example.pl>")
    invalid = api.patch(f"/api/poczta/oczekujace/{pending['id']}", json={"to": ["zly"]}, headers=HEADERS)
    assert invalid.status_code == 422
    edited = api.patch(
        f"/api/poczta/oczekujace/{pending['id']}", json={"body": "Poprawiona treść"}, headers=HEADERS
    )
    assert edited.json()["payload"]["body"] == "Poprawiona treść"
    assert [item["id"] for item in api.get("/api/poczta/oczekujace").json()] == [pending["id"]]

    assert api.post(f"/api/poczta/wyslij/{pending['id']}").status_code == 403, "wysyłka wymaga CSRF"
    assert mail_server.sent == []
    mail_server.smtp_fail = True
    failed = api.post(f"/api/poczta/wyslij/{pending['id']}", headers=HEADERS)
    assert failed.status_code == 502
    assert api.get("/api/poczta/oczekujace").json()[0]["error"].startswith("Wysłanie nie powiodło się")
    mail_server.smtp_fail = False
    sent = api.post(f"/api/poczta/wyslij/{pending['id']}", headers=HEADERS)
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "done"
    assert len(mail_server.sent) == 1
    recipients, data = mail_server.sent[0]
    assert recipients == ["jan@example.pl"]
    message = email.message_from_bytes(data, policy=default_policy)
    assert message.get_body().get_content().strip() == "Poprawiona treść"
    assert message["In-Reply-To"] == "<q@example.pl>"
    assert len(mail_server.boxes["Wysłane"]) == 1, "kopia w folderze Wysłane"
    assert "\\Answered" in mail_server.boxes["INBOX"][0].flags
    again = api.post(f"/api/poczta/wyslij/{pending['id']}", headers=HEADERS)
    assert again.status_code == 409 and len(mail_server.sent) == 1
    assert api.get("/api/poczta/oczekujace").json() == []
    history = api.get("/api/poczta/oczekujace", params={"all": 1}).json()
    assert history[0]["status"] == "done"


def test_api_pending_cancel_and_drafts(api: TestClient, mail_server: MailServer) -> None:  # noqa: F811
    pending = api.post(
        "/api/poczta/oczekujace", json={"to": ["a@example.pl"], "subject": "S", "body": "B"}, headers=HEADERS
    ).json()
    draft = api.post(f"/api/poczta/oczekujace/{pending['id']}/szkic", headers=HEADERS)
    assert draft.json() == {"ok": True, "folder": "Drafts"}
    assert len(mail_server.boxes["Drafts"]) == 1
    assert (
        api.delete(f"/api/poczta/oczekujace/{pending['id']}", headers=HEADERS).json()["status"] == "cancelled"
    )
    assert api.post(f"/api/poczta/wyslij/{pending['id']}", headers=HEADERS).status_code == 409
    assert api.post(f"/api/poczta/wyslij/{uuid.uuid4()}", headers=HEADERS).status_code == 404
    assert mail_server.sent == []


def test_api_reply_with_nexus_creates_conversation(api: TestClient, mail_server: MailServer) -> None:  # noqa: F811
    uid = mail_server.add("INBOX", raw_message("Rezerwacja pokoju"))
    response = api.post(
        "/api/poczta/odpowiedz-z-nexusem",
        json={"folder": "INBOX", "uid": uid, "instruction": "Potwierdź termin"},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    conversation = api.get(f"/api/conversations/{response.json()['conversation_id']}").json()
    assert conversation["title"] == "Odpowiedź: Rezerwacja pokoju"
    text = conversation["turns"][0]["text"]
    assert f"UID {uid}" in text and "mail_send" in text and "Potwierdź termin" in text


def test_remote_image_proxy(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/przekierowanie":
            return httpx.Response(302, headers={"location": "/logo.png"})
        if request.url.path == "/logo.png":
            return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})
        return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})

    api.app.state.mail_image_transport = httpx.MockTransport(handler)
    assert api.get("/api/poczta/obraz", params={"url": "http://127.0.0.1/logo.png"}).status_code == 400
    assert api.get("/api/poczta/obraz", params={"url": "file:///etc/passwd"}).status_code == 400
    monkeypatch.setattr(poczta_api, "_public_host", lambda host, port: host == "obrazy.example.pl")
    assert (
        api.get("/api/poczta/obraz", params={"url": "https://obrazy.example.pl:8443/x.png"}).status_code
        == 400
    )
    image = api.get("/api/poczta/obraz", params={"url": "https://obrazy.example.pl/przekierowanie"})
    assert image.status_code == 200 and image.content == b"\x89PNG"
    assert image.headers["content-type"] == "image/png"
    page = api.get("/api/poczta/obraz", params={"url": "https://obrazy.example.pl/strona"})
    assert page.status_code == 404


def test_public_host_blocks_private_addresses() -> None:
    assert poczta_api._public_host("127.0.0.1", 80) is False
    assert poczta_api._public_host("10.1.2.3", 443) is False
    assert poczta_api._public_host("169.254.169.254", 80) is False
    assert poczta_api._public_host("nie-istnieje.invalid", 80) is False
