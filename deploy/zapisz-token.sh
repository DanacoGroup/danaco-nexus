#!/usr/bin/env bash
# Zapisuje token OAuth Claude Code CLI w profilu projektu (dane/claude-profil/oauth-token).
#
# Token tworzy właściciel konta poleceniem:  claude setup-token
# Następnie:  sudo -u danaco-serwis deploy/zapisz-token.sh
# Token można wkleić w całości, także zawinięty w kilka linii (tak wyświetla go
# setup-token); wklejanie kończy pusta linia (Enter). Znaki nie są wyświetlane.
# Zapisywany jest wyłącznie poprawny token (sk-ant-oat01-…) z prawami 600.
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFIL="$PROJEKT/dane/claude-profil"
WZOR='^sk-ant-oat01-[A-Za-z0-9_-]{60,}$'

if [ "$(id -un)" != "danaco-serwis" ]; then
    echo "Uruchom jako danaco-serwis: sudo -u danaco-serwis $0" >&2
    exit 1
fi

echo "Wklej token OAuth (wynik claude setup-token), a potem naciśnij Enter jeszcze raz:"
wklejone=""
while IFS= read -r -s linia; do
    [ -z "${linia//[[:space:]]/}" ] && [ -n "$wklejone" ] && break
    wklejone+="$linia"
done
echo
# Usunięcie odstępów z zawijania linii i znaczników wklejania terminala.
token="$(printf '%s' "$wklejone" | tr -d '[:space:]' | sed -e 's/\x1b\[20[01]~//g')"
if ! [[ "$token" =~ $WZOR ]]; then
    echo "To nie jest token Claude Code (oczekiwano: sk-ant-oat01-…, otrzymano ${#token} znaków). Nic nie zapisano." >&2
    exit 1
fi
umask 077
mkdir -p "$PROFIL"
printf '%s\n' "$token" > "$PROFIL/oauth-token.nowy"
mv -f "$PROFIL/oauth-token.nowy" "$PROFIL/oauth-token"
echo "Zapisano token (${#token} znaków) w $PROFIL/oauth-token. Sprawdzenie: deploy/nexus-cli.sh doctor --online"
