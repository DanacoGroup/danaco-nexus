#!/usr/bin/env bash
# Testy e2e rozszerzenia na serwerze: budowa, serwer testowy Nexusa (SQLite, 127.0.0.1),
# Chromium z rozpakowanym rozszerzeniem (Playwright).
#
#   extension/e2e/uruchom.sh <katalog-testowy> [port]
#
# Katalog testowy musi zawierać venv/ z zainstalowanym backendem (pip install -e backend[test]).
set -euo pipefail

TEST="$(cd "$1" && pwd)"
PORT="${2:-18913}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PATH="/danaco/programy/node/bin:$PATH"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/danaco/programy/playwright}"
export NEXUS_E2E_TMP="$TEST"
export npm_config_cache="${npm_config_cache:-/danaco/projekty/danaco-nexus/.cache/npm}"

"$REPO/extension/buduj.sh" "$TEST/out"

DANE="$TEST/dane-e2e"
rm -rf "$DANE"
mkdir -p "$DANE"
BAZA="sqlite+aiosqlite:///$DANE/nexus.db"
(cd "$REPO/backend" && "$TEST/venv/bin/python" "$REPO/extension/e2e/klucz_testowy.py" "$BAZA" "$DANE/klucz")

NEXUS_DATABASE_URL="$BAZA" NEXUS_DATA_DIR="$DANE/app" NEXUS_STATIC_DIR="$DANE/brak" NEXUS_REDIS_URL="" \
NEXUS_VOICE_WARM_UP=false NEXUS_COOKIE_SECURE=false NEXUS_QDRANT_URL="http://127.0.0.1:1" \
  "$TEST/venv/bin/python" -m uvicorn nexus.api.app:app --app-dir "$REPO/backend" --host 127.0.0.1 --port "$PORT" \
  >"$DANE/uvicorn.log" 2>&1 &
SERWER_PID=$!
trap 'kill $SERWER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -fsS "http://127.0.0.1:$PORT/api/health"
echo
KOD=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/rozszerzenie/konfiguracja")
echo "Bez klucza: HTTP $KOD (oczekiwane 401)"

NEXUS_TEST_SERWER="http://127.0.0.1:$PORT" NEXUS_TEST_KLUCZ="$(cat "$DANE/klucz")" \
  node "$REPO/extension/e2e/panel.e2e.mjs" "$TEST/out/nexus-rozszerzenie"
