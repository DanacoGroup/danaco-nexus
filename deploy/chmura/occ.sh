#!/usr/bin/env bash
# Polecenie administracyjne Nextcloud (occ) z uprawnieniami usługi, np.:
#   deploy/chmura/occ.sh status
#   deploy/chmura/occ.sh user:resetpassword admin      # nowe hasło logowania do chmury
#   deploy/chmura/occ.sh files:scan --all              # po ręcznym dodaniu plików na dysku
set -euo pipefail

PROJEKT=/danaco/projekty/danaco-nexus
if [ "$(id -un)" != "danaco-serwis" ]; then
    exec sudo -u danaco-serwis "$PROJEKT/deploy/chmura/occ.sh" "$@"
fi
export PHP_INI_SCAN_DIR="$PROJEKT/deploy/chmura/php" TMPDIR="$PROJEKT/dane/tmp" HOME="$PROJEKT/dane/nextcloud"
cd "$PROJEKT/dane/nextcloud/nextcloud"
exec "/danaco/programy/frankenphp/frankenphp" php-cli occ "$@"
