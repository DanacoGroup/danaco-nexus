#!/usr/bin/env bash
# Przenosi magazyn obrazów containerd z partycji systemowej na /danaco.
#
# Docker 29 korzysta z magazynu obrazów containerd (/var/lib/containerd), którego nie
# obejmuje ustawienie "data-root" w /etc/docker/daemon.json. Na serwerze partycja "/"
# ma 9,6 GB, więc obrazy stosu Danaco Nexus (ok. 5 GB) muszą leżeć na /danaco.
#
# Skrypt wymaga uprawnień root i zatrzymuje na chwilę Dockera i containerd: działające
# kontenery (np. qdrant) zostaną uruchomione ponownie zgodnie z ich polityką restartu.
# Uruchamiać świadomie, poza godzinami pracy: sudo ./deploy/przeniesienie-containerd.sh
set -euo pipefail

TARGET=/danaco/containerd
CONFIG=/etc/containerd/config.toml

if [[ $EUID -ne 0 ]]; then
    echo "Uruchom jako root (sudo)." >&2
    exit 1
fi
if [[ -e "$TARGET" && -n "$(ls -A "$TARGET" 2>/dev/null)" ]]; then
    echo "Katalog $TARGET istnieje i nie jest pusty – przerwano." >&2
    exit 1
fi

echo "Kontenery przed zmianą:"
docker ps --format '  {{.Names}} ({{.Image}}) {{.Status}}'

systemctl stop docker.socket docker
systemctl stop containerd

mkdir -p "$TARGET"
rsync -aHAX --numeric-ids /var/lib/containerd/ "$TARGET"/
mv /var/lib/containerd /var/lib/containerd.przed-przeniesieniem

if [[ ! -f "$CONFIG" ]]; then
    containerd config default > "$CONFIG"
fi
cp "$CONFIG" "$CONFIG.przed-przeniesieniem"
if grep -qE '^root *=' "$CONFIG"; then
    sed -i -E "s#^root *=.*#root = \"$TARGET\"#" "$CONFIG"
else
    sed -i "1i root = \"$TARGET\"" "$CONFIG"
fi

systemctl start containerd
systemctl start docker

echo "Kontenery po zmianie:"
docker ps --format '  {{.Names}} ({{.Image}}) {{.Status}}'
echo "Gotowe. Po sprawdzeniu działania usług można usunąć /var/lib/containerd.przed-przeniesieniem."
