#!/usr/bin/env bash
# Pokazuje, co gdzie stoi: wydania na dysku oraz wskazania przedsionka i produkcji.
set -euo pipefail
KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WYDANIA="$KORZEN/wydania"
wskazanie() { [ -L "$WYDANIA/$1" ] && basename "$(readlink -f "$WYDANIA/$1")" || echo "—"; }
echo "przedsionek: $(wskazanie przedsionek)"
echo "produkcja:   $(wskazanie produkcja)"
echo "cofnięcie:   $( [ -f "$WYDANIA/POPRZEDNIA-PRODUKCJA" ] && cat "$WYDANIA/POPRZEDNIA-PRODUKCJA" || echo '—')"
echo
echo "wydania na dysku (najnowsze na dole):"
ls -1 "$WYDANIA/wersje" 2>/dev/null | sort | sed 's/^/  /'
