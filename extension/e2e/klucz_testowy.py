"""Klucz urządzenia dla testowej bazy SQLite (testy e2e rozszerzenia).

    python klucz_testowy.py <adres-bazy> <plik-na-klucz>

Tworzy schemat bazy, dodaje urządzenie „Rozszerzenie – test e2e” i zapisuje jego klucz
do pliku (uprawnienia 600). Używać wyłącznie z bazą testową.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import sys
from pathlib import Path

from nexus.api.auth import DEVICE_TOKEN_PREFIX, token_hash
from nexus.db import Database, DeviceToken


async def main(url: str, target: Path) -> None:
    if not url.startswith("sqlite"):
        raise SystemExit("Tylko baza testowa SQLite.")
    token = DEVICE_TOKEN_PREFIX + secrets.token_urlsafe(32)
    database = Database(url)
    await database.create_schema()
    async with database.session() as session:
        session.add(DeviceToken(token_hash=token_hash(token), name="Rozszerzenie – test e2e", kind="rozszerzenie"))
    await database.close()
    target.write_text(token, encoding="utf-8")
    os.chmod(target, 0o600)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], Path(sys.argv[2])))
