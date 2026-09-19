#!/usr/bin/env bash
# Instalacja i aktualizacja Danaco Nexus na serwerze (bez Dockera).
#
# Wszystko, co należy wyłącznie do projektu, trafia do katalogu projektu:
#   .venv/               środowisko Pythona (backend)
#   programy/qdrant/     program Qdrant
#   dane/postgres/       klaster PostgreSQL 18 (port 5433, gniazdo w dane/run)
#   dane/qdrant/         magazyn Qdrant (porty 6335/6336)
#   dane/app/            pliki, pamięć podręczna, logi aplikacji
#   dane/claude-profil/  profil Claude Code CLI (token OAuth w pliku oauth-token)
#   .cache/              pamięć podręczna pip/uv/npm (poza partycją systemową)
# Współdzielone programy serwera (PostgreSQL 18, Java, LanguageTool, Tika,
# Tesseract, LibreOffice, FFmpeg, Real-ESRGAN, Node, Claude CLI) są tylko używane.
#
# Użycie (jako danaco-root, z katalogu projektu):  deploy/instalacja.sh
# Skrypt jest idempotentny: ponowne uruchomienie aktualizuje zależności i interfejs.
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USLUGA_UZYTKOWNIK=danaco-serwis
PYTHON=/danaco/programy/uv-pythony/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12
UV=/danaco/programy/bin/uv
NODE_BIN=/danaco/programy/node/bin
PG_BIN=/danaco/programy/postgresql-18/usr/lib/postgresql/18/bin
PG_LIB=/danaco/programy/postgresql-18/usr/lib/x86_64-linux-gnu
QDRANT_WERSJA=v1.19.1
FRANKENPHP_WERSJA=v1.12.7
NEXTCLOUD_WERSJA=34.0.4
PG_PORT=5433

cd "$PROJEKT"
export UV_CACHE_DIR="$PROJEKT/.cache/uv" PIP_CACHE_DIR="$PROJEKT/.cache/pip" npm_config_cache="$PROJEKT/.cache/npm"
krok() { printf '\n== %s\n' "$*"; }

krok "Katalogi projektu"
umask 002
mkdir -p dane/app dane/run dane/qdrant dane/tmp dane/.cache programy .cache
if [ ! -d dane/claude-profil ]; then
    sudo -u "$USLUGA_UZYTKOWNIK" mkdir -m 700 dane/claude-profil
fi
[ -f .env ] || { cp .env.example .env; chmod 640 .env; echo "Utworzono .env z .env.example"; }

krok "Środowisko Pythona (.venv)"
[ -x .venv/bin/python ] || "$UV" venv --python "$PYTHON" .venv
"$UV" pip install --python .venv/bin/python -e "backend[test]"

krok "Interfejs WWW (frontend/dist)"
(cd frontend && PATH="$NODE_BIN:$PATH" npm ci --no-audit --no-fund && PATH="$NODE_BIN:$PATH" npm run build)

krok "Qdrant $QDRANT_WERSJA (programy/qdrant)"
if [ ! -x programy/qdrant/qdrant ] || [ "$(cat programy/qdrant/WERSJA 2>/dev/null)" != "$QDRANT_WERSJA" ]; then
    mkdir -p programy/qdrant
    archiwum="$PROJEKT/.cache/qdrant-$QDRANT_WERSJA.tar.gz"
    curl -fsSL --retry 3 -o "$archiwum" \
        "https://github.com/qdrant/qdrant/releases/download/$QDRANT_WERSJA/qdrant-x86_64-unknown-linux-gnu.tar.gz"
    tar -xzf "$archiwum" -C programy/qdrant qdrant
    echo "$QDRANT_WERSJA" > programy/qdrant/WERSJA
fi
programy/qdrant/qdrant --version

krok "FrankenPHP $FRANKENPHP_WERSJA (programy/frankenphp) – serwer PHP chmury"
if [ ! -x programy/frankenphp/frankenphp ] || [ "$(cat programy/frankenphp/WERSJA 2>/dev/null)" != "$FRANKENPHP_WERSJA" ]; then
    mkdir -p programy/frankenphp
    curl -fsSL --retry 3 -o programy/frankenphp/frankenphp.nowy \
        "https://github.com/php/frankenphp/releases/download/$FRANKENPHP_WERSJA/frankenphp-linux-x86_64"
    chmod 755 programy/frankenphp/frankenphp.nowy
    mv -f programy/frankenphp/frankenphp.nowy programy/frankenphp/frankenphp
    echo "$FRANKENPHP_WERSJA" > programy/frankenphp/WERSJA
fi

krok "Nextcloud $NEXTCLOUD_WERSJA (dane/nextcloud/nextcloud) – chmura osobista"
if [ ! -f dane/nextcloud/nextcloud/version.php ]; then
    archiwum="$PROJEKT/.cache/nextcloud-$NEXTCLOUD_WERSJA.tar.bz2"
    if [ ! -f "$archiwum" ]; then
        curl -fsSL --retry 3 -o "$archiwum" "https://download.nextcloud.com/server/releases/nextcloud-$NEXTCLOUD_WERSJA.tar.bz2"
    fi
    oczekiwana="$(curl -fsSL "https://download.nextcloud.com/server/releases/nextcloud-$NEXTCLOUD_WERSJA.tar.bz2.sha256" | head -1 | cut -d' ' -f1)"
    [ "$(sha256sum "$archiwum" | cut -d' ' -f1)" = "$oczekiwana" ] || { echo "Błędna suma kontrolna Nextcloud" >&2; exit 1; }
    sudo -u "$USLUGA_UZYTKOWNIK" mkdir -p dane/nextcloud
    sudo -u "$USLUGA_UZYTKOWNIK" tar -xjf "$archiwum" -C dane/nextcloud
fi
# Aktualizacje Nextcloud wykonuje jego własny mechanizm (occ upgrade / aktualizator).

krok "Klaster PostgreSQL (dane/postgres, port $PG_PORT)"
if ! sudo -u "$USLUGA_UZYTKOWNIK" test -f dane/postgres/PG_VERSION; then
    sudo -u "$USLUGA_UZYTKOWNIK" env LD_LIBRARY_PATH="$PG_LIB" "$PG_BIN/initdb" \
        -D "$PROJEKT/dane/postgres" --encoding=UTF8 --locale=C.UTF-8 \
        --auth-local=peer --auth-host=reject --username="$USLUGA_UZYTKOWNIK"
fi

krok "Usługi systemd"
for jednostka in deploy/systemd/*.service deploy/systemd/*.target deploy/systemd/*.timer; do
    nazwa="$(basename "$jednostka")"
    if [ ! -e "/etc/systemd/system/$nazwa" ]; then
        sudo systemctl link "$PROJEKT/$jednostka"
    fi
done
sudo systemctl daemon-reload
sudo systemctl enable --now danaco-nexus-postgres.service danaco-nexus-qdrant.service danaco-nexus-languagetool.service

krok "Baza danych nexus"
for _ in $(seq 1 30); do
    LD_LIBRARY_PATH="$PG_LIB" "$PG_BIN/pg_isready" -q -h "$PROJEKT/dane/run" -p "$PG_PORT" && break
    sleep 1
done
if ! sudo -u "$USLUGA_UZYTKOWNIK" env LD_LIBRARY_PATH="$PG_LIB" "$PG_BIN/psql" -h "$PROJEKT/dane/run" -p "$PG_PORT" \
        -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'nexus'" | grep -q 1; then
    sudo -u "$USLUGA_UZYTKOWNIK" env LD_LIBRARY_PATH="$PG_LIB" "$PG_BIN/createdb" -h "$PROJEKT/dane/run" -p "$PG_PORT" nexus
fi

krok "Chmura osobista (Nextcloud)"
sudo -u "$USLUGA_UZYTKOWNIK" "$PROJEKT/deploy/chmura/konfiguracja.sh"
sudo systemctl enable danaco-nexus-chmura.service danaco-nexus-chmura-cron.timer
sudo systemctl restart danaco-nexus-chmura.service
sudo systemctl start danaco-nexus-chmura-cron.timer

krok "Aplikacja"
sudo systemctl enable danaco-nexus.target danaco-nexus-api.service danaco-nexus-worker.service
sudo systemctl restart danaco-nexus-api.service danaco-nexus-worker.service

krok "Diagnostyka"
deploy/nexus-cli.sh doctor || true

cat <<'KONIEC'

Instalacja zakończona. Pozostałe kroki wykonuje administrator:
  1. token Claude Code CLI:   claude setup-token  →  sudo -u danaco-serwis deploy/zapisz-token.sh
  2. hasło administratora:    deploy/nexus-cli.sh set-password
  3. domena (Caddy):          patrz README, sekcja „Publikacja pod domeną”
KONIEC
