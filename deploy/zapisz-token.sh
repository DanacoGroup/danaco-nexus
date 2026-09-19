#!/usr/bin/env bash
# Zapisuje token OAuth Claude Code CLI w profilu projektu (dane/claude-profil/oauth-token).
#
# Token tworzy właściciel konta poleceniem:  claude setup-token
# Następnie:  sudo -u danaco-serwis deploy/zapisz-token.sh
# Token jest wczytywany bez echa i zapisywany z prawami 600 (tylko danaco-serwis).
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFIL="$PROJEKT/dane/claude-profil"

if [ "$(id -un)" != "danaco-serwis" ]; then
    echo "Uruchom jako danaco-serwis: sudo -u danaco-serwis $0" >&2
    exit 1
fi

read -r -s -p "Token OAuth (wynik claude setup-token): " token
echo
if [ -z "$token" ]; then
    echo "Pusty token – nic nie zapisano." >&2
    exit 1
fi
umask 077
mkdir -p "$PROFIL"
printf '%s\n' "$token" > "$PROFIL/oauth-token.nowy"
mv -f "$PROFIL/oauth-token.nowy" "$PROFIL/oauth-token"
echo "Zapisano $PROFIL/oauth-token. Sprawdzenie: deploy/nexus-cli.sh doctor --online"
