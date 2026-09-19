#!/usr/bin/env bash
# Zapisuje klucz API Semantic Scholar dla modułu Research (dane/app/semantic-scholar-key).
#
# Klucz jest opcjonalny: bez niego wyszukiwanie prac działa, ale Semantic Scholar ma wtedy
# wspólny, niski limit zapytań (częste odpowiedzi „limit zapytań”). Klucz przyznaje
# Semantic Scholar po wypełnieniu formularza: https://www.semanticscholar.org/product/api
# Użycie:  sudo -u danaco-serwis deploy/zapisz-klucz-semantic-scholar.sh
# Klucz jest wczytywany bez echa i zapisywany z prawami 600 (tylko danaco-serwis).
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIK="$PROJEKT/dane/app/semantic-scholar-key"
WZOR='^[A-Za-z0-9]{20,64}$'

if [ "$(id -un)" != "danaco-serwis" ]; then
    echo "Uruchom jako danaco-serwis: sudo -u danaco-serwis $0" >&2
    exit 1
fi

read -r -s -p "Klucz API Semantic Scholar: " klucz
echo
klucz="$(printf '%s' "$klucz" | tr -d '[:space:]')"
if ! [[ "$klucz" =~ $WZOR ]]; then
    echo "To nie wygląda na klucz API Semantic Scholar (litery i cyfry, 20–64 znaki). Nic nie zapisano." >&2
    exit 1
fi
umask 077
printf '%s\n' "$klucz" > "$PLIK.nowy"
mv -f "$PLIK.nowy" "$PLIK"
echo "Zapisano klucz w $PLIK. Narzędzia scholar_search i scholar_paper użyją go przy kolejnym zadaniu."
