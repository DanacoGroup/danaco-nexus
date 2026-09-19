"""Polecenia administracyjne: ``python -m nexus.cli set-password``."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from nexus.api.auth import DEFAULT_USERNAME, set_admin_credentials
from nexus.config import get_settings
from nexus.db import Database


async def _set_password(username: str, password: str) -> None:
    database = Database(get_settings().database_url)
    try:
        await database.create_schema()
        await set_admin_credentials(database, username, password)
    finally:
        await database.close()


def main(argv: list[str] | None = None) -> int:
    """Punkt wejścia poleceń administracyjnych."""
    parser = argparse.ArgumentParser(prog="nexus.cli", description="Administracja Danaco Nexus")
    commands = parser.add_subparsers(dest="command", required=True)
    set_password = commands.add_parser("set-password", help="Ustaw login i hasło administratora")
    set_password.add_argument("--username", default=DEFAULT_USERNAME)
    arguments = parser.parse_args(argv)

    if arguments.command == "set-password":
        password = getpass.getpass("Nowe hasło (min. 12 znaków): ")
        if password != getpass.getpass("Powtórz hasło: "):
            print("Hasła nie są identyczne.", file=sys.stderr)
            return 1
        try:
            asyncio.run(_set_password(arguments.username.strip(), password))
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"Ustawiono hasło administratora „{arguments.username}”. Wszystkie sesje wylogowano.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
