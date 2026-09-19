#!/usr/bin/env bash
# Budowa rozszerzenia przeglądarki Danaco Nexus (Chrome, Edge, Danaco Lynx).
#
#   extension/buduj.sh [katalog-wyjściowy]
#
# Wynik (domyślnie): .tmp/rozszerzenie/out/nexus-rozszerzenie/ (do „Załaduj rozpakowane”)
# oraz .tmp/rozszerzenie/out/nexus-rozszerzenie.zip. Wersja z extension/manifest.json.
set -euo pipefail

KATALOG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KATALOG"

if [[ -d /danaco/programy/node/bin ]]; then
  export PATH="/danaco/programy/node/bin:$PATH"
fi
if [[ -d /danaco/projekty/danaco-nexus/.cache ]]; then
  export npm_config_cache="${npm_config_cache:-/danaco/projekty/danaco-nexus/.cache/npm}"
fi

if [[ ! -d node_modules/esbuild ]]; then
  npm ci --no-audit --no-fund
fi

npx tsc --noEmit
node buduj.mjs "$@"
