#!/usr/bin/env bash
# Polecenia administracyjne Danaco Nexus z uprawnieniami usługi (danaco-serwis)
# i konfiguracją z pliku .env, np.:
#   deploy/nexus-cli.sh doctor [--online]
#   deploy/nexus-cli.sh set-password
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USLUGA_UZYTKOWNIK=danaco-serwis

if [ "$(id -un)" != "$USLUGA_UZYTKOWNIK" ]; then
    exec sudo -u "$USLUGA_UZYTKOWNIK" "$PROJEKT/deploy/nexus-cli.sh" "$@"
fi

cd "$PROJEKT/backend"
set -a
# shellcheck source=/dev/null
. "$PROJEKT/.env"
set +a
export HOME="$PROJEKT/dane"
exec "$PROJEKT/.venv/bin/python" -m nexus.cli "$@"
