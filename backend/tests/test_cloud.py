"""Testy narzędzi chmury osobistej (Nextcloud przez WebDAV).

Test integracyjny wymaga działającego Nextcloud i zmiennej
``NEXUS_TEST_CHMURA_TOKEN_FILE`` (plik z hasłem aplikacji); pracuje
w katalogu tymczasowym, który na końcu usuwa.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from conftest import ToolHarness

from nexus.tools import registry
from nexus.tools.base import ToolError
from nexus.tools.cloud import CloudClient, normalize_cloud_path

TOKEN_FILE = os.environ.get("NEXUS_TEST_CHMURA_TOKEN_FILE", "")
CHMURA_URL = os.environ.get("NEXUS_TEST_CHMURA_URL", "http://127.0.0.1:8940")


def call(harness: ToolHarness, name: str, /, **arguments: object):  # type: ignore[no-untyped-def]
    tool = registry.get(name)
    context = harness.context()
    try:
        return tool.handler(context, tool.parse(arguments))
    finally:
        context.cleanup()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", "/"),
        ("/", "/"),
        ("Dokumenty//Faktury 2026/", "/Dokumenty/Faktury 2026"),
        ("./a/./b", "/a/b"),
        ("\\Skany\\2026", "/Skany/2026"),
    ],
)
def test_normalize_cloud_path(raw: str, expected: str) -> None:
    assert normalize_cloud_path(raw) == expected


@pytest.mark.parametrize("raw", ["../etc", "/a/../../b", "a/\x00b"])
def test_normalize_cloud_path_rejects_escape(raw: str) -> None:
    with pytest.raises(ToolError):
        normalize_cloud_path(raw)


def test_cloud_tools_require_configuration(harness: ToolHarness, tmp_path: Path) -> None:
    harness.settings.chmura_token_file = tmp_path / "brak-tokenu"
    with pytest.raises(ToolError, match="nie jest skonfigurowana"):
        call(harness, "cloud_browse", path="/")


@pytest.mark.skipif(
    not TOKEN_FILE or not Path(TOKEN_FILE).is_file(), reason="Brak NEXUS_TEST_CHMURA_TOKEN_FILE"
)
def test_cloud_save_browse_import_roundtrip(harness: ToolHarness, tmp_path: Path) -> None:
    harness.settings.chmura_url = CHMURA_URL
    harness.settings.chmura_token_file = Path(TOKEN_FILE)
    harness.settings.chmura_public_url = "https://chmura.example.pl"
    folder = f"/Nexus-testy-{uuid.uuid4().hex[:8]}/Faktury 2026"
    source = tmp_path / "faktura.txt"
    source.write_text("Faktura nr 1/2026 – zażółć gęślą jaźń\n", encoding="utf-8")
    file_id = harness.add(source, "Faktura żółta 1_2026.txt")
    client = CloudClient(harness.settings)
    try:
        saved = call(harness, "cloud_save", file_ids=[file_id], folder=folder)
        assert saved.data["saved"] == [f"{folder}/Faktura żółta 1_2026.txt"]
        assert saved.data["folder_link"].startswith("https://chmura.example.pl/apps/files/?dir=")
        again = call(harness, "cloud_save", file_ids=[file_id], folder=folder)
        assert again.data["saved"] == [f"{folder}/Faktura żółta 1_2026 (2).txt"]

        listing = call(harness, "cloud_browse", path=folder)
        names = [entry["name"] for entry in listing.data["entries"]]
        assert names == ["Faktura żółta 1_2026 (2).txt", "Faktura żółta 1_2026.txt"]
        assert all(entry["type"] == "file" and entry["size_bytes"] > 0 for entry in listing.data["entries"])
        parent = call(harness, "cloud_browse", path=folder.rsplit("/", 1)[0])
        assert parent.data["entries"][0]["type"] == "folder"

        imported = call(harness, "cloud_import", paths=[folder])
        assert sorted(output.name for output in imported.files) == names
        assert imported.files[0].path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
        single = call(harness, "cloud_import", paths=[f"{folder}/Faktura żółta 1_2026.txt"])
        assert [output.name for output in single.files] == ["Faktura żółta 1_2026.txt"]
        with pytest.raises(ToolError, match="W chmurze nie ma"):
            call(harness, "cloud_import", paths=[f"{folder}/brak.pdf"])
    finally:
        client.http.request("DELETE", client.url(folder.split("/")[1]))
        client.close()
