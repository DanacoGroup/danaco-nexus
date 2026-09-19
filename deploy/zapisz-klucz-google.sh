#!/usr/bin/env bash
# Zapisuje klucz API Google Cloud dla rozmowy głosowej (dane/app/google-api-key).
#
# Klucz tworzy właściciel projektu w konsoli Google Cloud: Interfejsy API i usługi →
# Dane logowania → Utwórz dane logowania → Klucz interfejsu API. W projekcie muszą być
# włączone: Cloud Text-to-Speech API i Cloud Speech-to-Text API (klucz warto ograniczyć
# do tych dwóch interfejsów).
# Użycie:  sudo -u danaco-serwis deploy/zapisz-klucz-google.sh
# Klucz jest wczytywany bez echa i zapisywany z prawami 600 (tylko danaco-serwis).
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIK="$PROJEKT/dane/app/google-api-key"
WZOR='^AIza[A-Za-z0-9_-]{35}$'

if [ "$(id -un)" != "danaco-serwis" ]; then
    echo "Uruchom jako danaco-serwis: sudo -u danaco-serwis $0" >&2
    exit 1
fi

read -r -s -p "Klucz API Google Cloud (AIza…): " klucz
echo
klucz="$(printf '%s' "$klucz" | tr -d '[:space:]')"
if ! [[ "$klucz" =~ $WZOR ]]; then
    echo "To nie wygląda na klucz API Google (oczekiwano: AIza… – 39 znaków). Nic nie zapisano." >&2
    exit 1
fi
umask 077
printf '%s\n' "$klucz" > "$PLIK.nowy"
mv -f "$PLIK.nowy" "$PLIK"
echo "Zapisano klucz w $PLIK. Sprawdzenie: deploy/nexus-cli.sh doctor"
