#!/usr/bin/env bash
# Buduje obrazy Danaco Nexus. Budowa korzysta z sieci hosta, ponieważ zapora serwera
# blokuje ruch wychodzący kontenerów w sieci mostkowej (pobieranie pakietów npm i pip).
set -euo pipefail
cd "$(dirname "$0")/.."
export DOCKER_BUILDKIT=0
docker build --network host --target worker -t danaco-nexus-worker:latest .
docker build --network host --target api -t danaco-nexus-api:latest .
echo "Obrazy zbudowane: danaco-nexus-api:latest, danaco-nexus-worker:latest"
