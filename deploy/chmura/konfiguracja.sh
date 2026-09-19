#!/usr/bin/env bash
# Instalacja i konfiguracja Nextcloud (chmura osobista Danaco Nexus).
# Uruchamiana przez deploy/instalacja.sh jako danaco-serwis; idempotentna.
#
# Tworzy (tylko raz):
#   rolę i bazę PostgreSQL „nextcloud” (hasło losowe w dane/nextcloud/db-haslo, prawa 600),
#   instalację Nextcloud z kontem „admin” (hasło początkowe losowe w
#   dane/nextcloud/admin-haslo-poczatkowe – do zmiany przez właściciela),
#   hasło aplikacji dla Nexusa (dane/app/chmura-token) do WebDAV.
# Za każdym razem ustawia konfigurację systemową (domeny, proxy, pamięć podręczna, język).
set -euo pipefail

PROJEKT=/danaco/projekty/danaco-nexus
NC_KATALOG="$PROJEKT/dane/nextcloud"
NC="$NC_KATALOG/nextcloud"
FRANKENPHP="$PROJEKT/programy/frankenphp/frankenphp"
PG_BIN=/danaco/programy/postgresql-18/usr/lib/postgresql/18/bin
PG_GNIAZDO="$PROJEKT/dane/run"
PG_PORT=5433
DOMENA_CHMURY="${NEXUS_CHMURA_DOMENA:-cloud.danaco-nexus.pl}"
ADMIN=admin

export LD_LIBRARY_PATH=/danaco/programy/postgresql-18/usr/lib/x86_64-linux-gnu
export PHP_INI_SCAN_DIR="$PROJEKT/deploy/chmura/php" TMPDIR="$PROJEKT/dane/tmp" HOME="$NC_KATALOG"

if [ "$(id -un)" != "danaco-serwis" ]; then
    echo "Uruchom jako danaco-serwis: sudo -u danaco-serwis $0" >&2
    exit 1
fi
umask 077

occ() { (cd "$NC" && "$FRANKENPHP" php-cli occ --no-interaction "$@"); }
losowe_haslo() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40; }
psql_nexus() { "$PG_BIN/psql" -h "$PG_GNIAZDO" -p "$PG_PORT" -d postgres -v ON_ERROR_STOP=1 -qtA "$@"; }

echo "== Baza danych nextcloud"
[ -s "$NC_KATALOG/db-haslo" ] || losowe_haslo > "$NC_KATALOG/db-haslo"
psql_nexus -v haslo="$(cat "$NC_KATALOG/db-haslo")" <<'SQL'
SELECT 'CREATE ROLE nextcloud LOGIN' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nextcloud') \gexec
ALTER ROLE nextcloud PASSWORD :'haslo';
SELECT 'CREATE DATABASE nextcloud OWNER nextcloud ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'nextcloud') \gexec
SQL

echo "== Instalacja Nextcloud"
mkdir -p "$NC_KATALOG/dane"
if ! occ status --output=json 2>/dev/null | grep -q '"installed":true'; then
    [ -s "$NC_KATALOG/admin-haslo-poczatkowe" ] || losowe_haslo > "$NC_KATALOG/admin-haslo-poczatkowe"
    occ maintenance:install \
        --database pgsql --database-name nextcloud --database-user nextcloud \
        --database-host "$PG_GNIAZDO:$PG_PORT" --database-pass "$(cat "$NC_KATALOG/db-haslo")" \
        --admin-user "$ADMIN" --admin-pass "$(cat "$NC_KATALOG/admin-haslo-poczatkowe")" \
        --data-dir "$NC_KATALOG/dane"
fi

echo "== Konfiguracja systemowa"
occ config:system:set trusted_domains 0 --value=localhost
occ config:system:set trusted_domains 1 --value=127.0.0.1
occ config:system:set trusted_domains 2 --value="$DOMENA_CHMURY"
occ config:system:set trusted_proxies 0 --value=127.0.0.1
occ config:system:set overwrite.cli.url --value="https://$DOMENA_CHMURY"
occ config:system:set overwriteprotocol --value=https
occ config:system:set overwritecondaddr --value='^127\.0\.0\.1$'
occ config:system:set memcache.local --value='\OC\Memcache\APCu'
occ config:system:set default_language --value=pl
occ config:system:set default_locale --value=pl_PL
occ config:system:set default_phone_region --value=PL
occ config:system:set default_timezone --value=Europe/Warsaw
occ config:system:set maintenance_window_start --type=integer --value=1
occ config:system:set log_type --value=file
occ config:system:set logfile --value="$NC_KATALOG/nextcloud.log"
occ config:system:set loglevel --type=integer --value=2
occ config:system:set tempdirectory --value="$PROJEKT/dane/tmp"
occ config:system:set htaccess.RewriteBase --value=/
occ config:system:set updatechecker --type=boolean --value=true
occ background:cron
occ maintenance:repair --include-expensive >/dev/null
occ db:add-missing-indices >/dev/null
occ maintenance:update:htaccess >/dev/null || true

echo "== Logowanie jednokrotne z Nexusa (user_saml, zmienna środowiskowa)"
# Caddy hosta pyta Nexusa (forward_auth /api/auth/sso) o sesję i przy ważnej sesji
# dodaje nagłówek X-Nexus-User; Nextcloud loguje wskazane, istniejące konto.
# Awaryjne logowanie hasłem Nextcloud: https://$DOMENA_CHMURY/login?direct=1
occ app:list --output=json | grep -q '"user_saml"' || occ app:install user_saml
occ app:enable user_saml >/dev/null
occ config:app:set user_saml type --value=environment-variable
occ config:app:set user_saml general-require_provisioned_account --value=1
occ config:app:set user_saml general-allow_multiple_user_back_ends --value=1
if ! occ saml:config:get --output=json 2>/dev/null | grep -q '"1"'; then
    occ saml:config:create >/dev/null
fi
occ saml:config:set --general-uid_mapping=HTTP_X_NEXUS_USER 1
occ saml:config:set --general-idp0_display_name="Danaco Nexus" 1

echo "== Hasło aplikacji dla Nexusa (WebDAV)"
TOKEN="$PROJEKT/dane/app/chmura-token"
if [ ! -s "$TOKEN" ]; then
    # Bez hasła logowania (tryb nieinteraktywny) – hasło aplikacji wyłącznie dla WebDAV Nexusa.
    wynik="$(occ user:auth-tokens:add --name="Danaco Nexus" "$ADMIN" 2>&1 || true)"
    haslo_aplikacji="$(printf '%s\n' "$wynik" | grep -E '^[A-Za-z0-9-]{20,}$' | tail -1 || true)"
    if [ -n "$haslo_aplikacji" ]; then
        printf '%s\n' "$haslo_aplikacji" > "$TOKEN"
        echo "Zapisano $TOKEN"
    else
        echo "Nie udało się utworzyć hasła aplikacji: $(printf '%s' "$wynik" | tail -1)" >&2
    fi
fi

occ status
