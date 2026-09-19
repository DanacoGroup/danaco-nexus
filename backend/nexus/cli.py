"""Polecenia administracyjne: ``python -m nexus.cli set-password`` oraz ``doctor``."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from nexus.api.auth import DEFAULT_USERNAME, set_admin_credentials
from nexus.config import get_settings
from nexus.db import Database
from nexus.doctor import run_checks


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
    doctor = commands.add_parser("doctor", help="Sprawdź bazę, usługi, narzędzia i klucz API")
    doctor.add_argument(
        "--online",
        action="store_true",
        help="Sprawdź klucz API odczytem metadanych modelu (bez generowania tokenów)",
    )
    arguments = parser.parse_args(argv)

    if arguments.command == "doctor":
        results = run_checks(get_settings(), online=arguments.online)
        width = max(len(check.name) for check in results)
        for check in results:
            print(f"{'OK ' if check.ok else 'BŁĄD'}  {check.name.ljust(width)}  {check.detail}")
        failed = sum(not check.ok for check in results)
        print(f"\nKontrole: {len(results) - failed} poprawnych, {failed} z błędem.")
        return 1 if failed else 0

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
