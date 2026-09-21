#!/usr/bin/env bash
# Cofa produkcję do poprzedniego sprawnego wydania (jedno polecenie, bez budowania).
#
#   deploy/wydania/cofnij.sh            — wraca do wydania sprzed ostatniej promocji
#   deploy/wydania/cofnij.sh <znacznik> — wraca do wskazanego wydania z wydania/wersje

set -euo pipefail

KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WYDANIA="$KORZEN/wydania"
ZNACZNIK="${1:-}"

if [ -z "$ZNACZNIK" ]; then
  [ -f "$WYDANIA/POPRZEDNIA-PRODUKCJA" ] || { echo "Nie ma zapisanej poprzedniej wersji." >&2; exit 1; }
  ZNACZNIK="$(cat "$WYDANIA/POPRZEDNIA-PRODUKCJA")"
fi
[ -d "$WYDANIA/wersje/$ZNACZNIK" ] || { echo "Nie ma wydania $ZNACZNIK." >&2; exit 1; }

BIEZACE="$(basename "$(readlink -f "$WYDANIA/produkcja")" 2>/dev/null || true)"
printf '%s\n' "$BIEZACE" > "$WYDANIA/POPRZEDNIA-PRODUKCJA"
ln -sfn "$WYDANIA/wersje/$ZNACZNIK" "$WYDANIA/produkcja"
# Cofnięcie dotyczy obu jednostek produkcji: API i procesu roboczego (agenta).
for jednostka in danaco-nexus-api.service danaco-nexus-worker.service; do
  systemctl restart "$jednostka" 2>/dev/null || sudo systemctl restart "$jednostka"
done
echo "produkcja cofnięta: $BIEZACE → $ZNACZNIK"
