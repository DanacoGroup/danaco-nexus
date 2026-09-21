#!/usr/bin/env bash
# Sprząta stare wydania z wydania/wersje.
#
#   deploy/wydania/sprzataj.sh              — pokazuje, co poszłoby do usunięcia (nic nie kasuje)
#   deploy/wydania/sprzataj.sh --ile 10     — zostawia dziesięć najnowszych zamiast pięciu
#   deploy/wydania/sprzataj.sh --wykonaj    — dopiero to usuwa
#
# Każde wydanie to pełna kopia artefaktu (z nagraniami kampanii ma ponad pół gigabajta),
# a buduje się je kilka razy dziennie — bez sprzątania katalog rośnie bez końca. Skrypt
# nigdy nie rusza wydania wskazanego przez przedsionek, produkcję ani zapamiętanego do
# cofnięcia (wydania/POPRZEDNIA-PRODUKCJA), nawet jeśli wypadły poza N najnowszych.

set -euo pipefail

KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WYDANIA="$KORZEN/wydania"
WERSJE="$WYDANIA/wersje"
ILE=5
WYKONAJ=0

while [ $# -gt 0 ]; do
  case "$1" in
    --wykonaj) WYKONAJ=1; shift ;;
    --ile) ILE="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Nieznany argument: $1" >&2; exit 2 ;;
  esac
done

case "$ILE" in
  ''|*[!0-9]*) echo "--ile wymaga liczby." >&2; exit 2 ;;
esac
[ "$ILE" -ge 1 ] || { echo "--ile musi być co najmniej 1." >&2; exit 2; }
[ -d "$WERSJE" ] || { echo "Brak katalogu $WERSJE." >&2; exit 1; }

wskazanie() { [ -L "$WYDANIA/$1" ] && basename "$(readlink -f "$WYDANIA/$1")" || true; }

CHRONIONE=$(
  {
    wskazanie przedsionek
    wskazanie produkcja
    [ -f "$WYDANIA/POPRZEDNIA-PRODUKCJA" ] && cat "$WYDANIA/POPRZEDNIA-PRODUKCJA"
    ls -1 "$WERSJE" | sort | tail -n "$ILE"
  } | sed '/^$/d' | sort -u
)

DO_USUNIECIA=$(ls -1 "$WERSJE" | sort | grep -vxF "$CHRONIONE" || true)

if [ -z "$DO_USUNIECIA" ]; then
  echo "Nie ma czego sprzątać: $(ls -1 "$WERSJE" | wc -l) wydań, wszystkie chronione."
  exit 0
fi

echo "zostają (najnowsze $ILE oraz wskazania przedsionka, produkcji i cofnięcia):"
echo "$CHRONIONE" | sed 's/^/  /'
echo
echo "do usunięcia:"
while IFS= read -r znacznik; do
  printf '  %s  %s\n' "$(du -sh "$WERSJE/$znacznik" | cut -f1)" "$znacznik"
done <<< "$DO_USUNIECIA"

if [ "$WYKONAJ" -eq 0 ]; then
  echo
  echo "To był podgląd. Usuwa dopiero: $0 --wykonaj"
  exit 0
fi

while IFS= read -r znacznik; do
  rm -rf "${WERSJE:?}/${znacznik:?}"
  # Dziennik budowy jest już tylko śladem po katalogu, którego nie ma — idzie razem z nim.
  rm -f "$KORZEN/.logs/wydanie-${znacznik:?}.log"
  echo "usunięte: $znacznik"
done <<< "$DO_USUNIECIA"
