#!/usr/bin/env bash
# Przesuwa wydanie o jeden etap: strefa robocza → przedsionek → produkcja.
#
#   deploy/wydania/wypchnij.sh przedsionek [znacznik]   — wystawia wydanie na test.danaco-nexus.pl
#   deploy/wydania/wypchnij.sh produkcja               — promuje to, co stoi w przedsionku
#   deploy/wydania/wypchnij.sh produkcja <znacznik>    — promuje wskazane wydanie
#
# Produkcja nigdy nie bierze wydania, którego nie było w przedsionku: tam się je ogląda
# i sprawdza. Poprzednia wersja produkcji zostaje zapamiętana, żeby dało się cofnąć
# jednym poleceniem (deploy/wydania/cofnij.sh).

set -euo pipefail

KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WYDANIA="$KORZEN/wydania"
WERSJE="$WYDANIA/wersje"
ETAP="${1:-}"
ZNACZNIK="${2:-}"

[ -n "$ETAP" ] || { echo "Podaj etap: przedsionek albo produkcja." >&2; exit 2; }

biezace() { [ -L "$WYDANIA/$1" ] && basename "$(readlink -f "$WYDANIA/$1")" || true; }

# Etap to dwie jednostki: API i proces roboczy. Obie biorą kod z tego samego wydania,
# więc obie muszą wstać na nowe — inaczej agent zostałby na poprzednim kodzie.
przeladuj() {
  # Jednostki systemd są dowiązaniami do plików w repozytorium, więc mogły się zmienić
  # razem z kodem; bez przeładowania systemd trzymałby się poprzedniej wersji opisu.
  systemctl daemon-reload 2>/dev/null || sudo systemctl daemon-reload
  for jednostka in "$@"; do
    # Instalacja bez przedsionka nie ma jego jednostek — brak jednostki nie jest błędem
    # wypchnięcia, ale musi być widoczny, żeby nie wyglądało, że coś wstało.
    if ! systemctl list-unit-files "$jednostka" >/dev/null 2>&1 \
        || [ -z "$(systemctl list-unit-files --no-legend "$jednostka" 2>/dev/null)" ]; then
      echo "pominięto: nie ma jednostki $jednostka" >&2
      continue
    fi
    systemctl restart "$jednostka" 2>/dev/null || sudo systemctl restart "$jednostka"
  done
}

case "$ETAP" in
  przedsionek)
    if [ -z "$ZNACZNIK" ]; then
      ZNACZNIK="$(ls -1 "$WERSJE" 2>/dev/null | sort | tail -1)"
    fi
    [ -n "$ZNACZNIK" ] && [ -d "$WERSJE/$ZNACZNIK" ] || { echo "Nie ma wydania $ZNACZNIK." >&2; exit 1; }
    ln -sfn "$WERSJE/$ZNACZNIK" "$WYDANIA/przedsionek"
    przeladuj danaco-nexus-przedsionek.service danaco-nexus-worker-przedsionek.service
    echo "przedsionek: $ZNACZNIK → https://test.danaco-nexus.pl"
    ;;
  produkcja)
    if [ -z "$ZNACZNIK" ]; then
      ZNACZNIK="$(biezace przedsionek)"
      [ -n "$ZNACZNIK" ] || { echo "Przedsionek jest pusty — najpierw wypchnij tam wydanie." >&2; exit 1; }
    fi
    [ -d "$WERSJE/$ZNACZNIK" ] || { echo "Nie ma wydania $ZNACZNIK." >&2; exit 1; }
    POPRZEDNIE="$(biezace produkcja)"
    if [ -n "$POPRZEDNIE" ] && [ "$POPRZEDNIE" != "$ZNACZNIK" ]; then
      printf '%s\n' "$POPRZEDNIE" > "$WYDANIA/POPRZEDNIA-PRODUKCJA"
    fi
    ln -sfn "$WERSJE/$ZNACZNIK" "$WYDANIA/produkcja"
    przeladuj danaco-nexus-api.service danaco-nexus-worker.service
    echo "produkcja: $ZNACZNIK → https://danaco-nexus.pl (cofnięcie do: ${POPRZEDNIE:-brak})"
    ;;
  *)
    echo "Nieznany etap: $ETAP (przedsionek albo produkcja)." >&2
    exit 2
    ;;
esac
