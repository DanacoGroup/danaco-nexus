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


async def _konto_testowe(email: str, haslo: str, plan: str, kredyty_dodatkowe: int) -> str:
    """Zakłada konto klienta z kredytami, z pominięciem płatności.

    Do wydania testerom i na własne konto właściciela: pełna przestrzeń i pełne możliwości,
    bez przechodzenia przez Stripe. Konto jest zwykłym kontem portalu — testerzy pracują
    dokładnie tak, jak będą pracować klienci.
    """
    from nexus.platnosci import kredyty
    from nexus.portal.konta import BladKonta, utworz_konto, znajdz_konto

    settings = get_settings()
    database = Database(settings.database_url)
    try:
        await database.create_schema()
        async with database.session() as session:
            istniejace = await znajdz_konto(session, email.strip().lower())
            if istniejace is not None:
                user = istniejace
                utworzone = False
            else:
                try:
                    user = await utworz_konto(session, email=email, haslo=haslo, name="Konto testowe")
                except BladKonta as error:
                    raise ValueError(str(error)) from error
                utworzone = True
        await kredyty.przydziel_z_planu(database, user.id, plan, "konto-testowe")
        if kredyty_dodatkowe > 0:
            await kredyty.przydziel(database, user.id, kredyty_dodatkowe, "konto-testowe", "Przydział ręczny")
        saldo = (await kredyty.stan(database, user.id)).saldo
    finally:
        await database.close()
    stan_konta = "założone" if utworzone else "już istniało"
    return f"Konto {email} ({stan_konta}). Plan {plan}, saldo kredytów: {saldo}."


def main(argv: list[str] | None = None) -> int:
    """Punkt wejścia poleceń administracyjnych."""
    parser = argparse.ArgumentParser(prog="nexus.cli", description="Administracja Danaco Nexus")
    commands = parser.add_subparsers(dest="command", required=True)
    set_password = commands.add_parser("set-password", help="Ustaw login i hasło administratora")
    set_password.add_argument("--username", default=DEFAULT_USERNAME)
    doctor = commands.add_parser("doctor", help="Sprawdź bazę, usługi, narzędzia i Claude Code CLI")
    doctor.add_argument(
        "--online",
        action="store_true",
        help="Wykonaj krótkie zapytanie testowe przez Claude Code CLI",
    )
    konto = commands.add_parser(
        "konto-testowe", help="Załóż konto z kredytami bez przechodzenia przez płatność"
    )
    konto.add_argument("--email", required=True)
    konto.add_argument("--plan", default="pro", help="Kod planu z katalogu (domyślnie pro)")
    konto.add_argument(
        "--kredyty", type=int, default=0, help="Kredyty ponad przydział planu (domyślnie 0)"
    )
    arguments = parser.parse_args(argv)

    if arguments.command == "doctor":
        results = run_checks(get_settings(), online=arguments.online)
        width = max(len(check.name) for check in results)
        for check in results:
            print(f"{'OK  ' if check.ok else 'BŁĄD'}  {check.name.ljust(width)}  {check.detail}")
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

    if arguments.command == "konto-testowe":
        haslo = getpass.getpass("Hasło konta (min. 12 znaków): ")
        if haslo != getpass.getpass("Powtórz hasło: "):
            print("Hasła nie są identyczne.", file=sys.stderr)
            return 1
        try:
            print(
                asyncio.run(
                    _konto_testowe(arguments.email, haslo, arguments.plan, max(arguments.kredyty, 0))
                )
            )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
