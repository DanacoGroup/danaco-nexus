#!/usr/bin/env bash
# Kopia zapasowa Danaco Nexus: bazy klastra projektu, pliki użytkownika, wektory bazy wiedzy
# i sekrety. Uruchamiana z timera systemd (deploy/systemd/danaco-nexus-kopia.timer) albo ręcznie:
#
#   deploy/kopia-zapasowa.sh [katalog-docelowy]
#
# Z innego konta niż danaco-serwis skrypt podnosi się sam przez sudo.
#
# Domyślny katalog: dane/kopie. Kopia jest spójna w obrębie bazy (pg_dump w jednej transakcji),
# pliki i wektory kopiowane są po zrzucie bazy — odtworzenie opisuje rozdz. „Odtworzenie” niżej.
set -Eeuo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CEL="${1:-$PROJEKT/dane/kopie}"
POSTGRES="/danaco/programy/postgresql-18/usr/lib/postgresql/18/bin"
# Biblioteki klienta bazy leżą obok programów klastra — bez tego psql i pg_dump nie startują.
export LD_LIBRARY_PATH="/danaco/programy/postgresql-18/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
GNIAZDO="$PROJEKT/dane/run"
ZNACZNIK="$(date -u +%Y%m%dT%H%M%SZ)"
KATALOG="$CEL/$ZNACZNIK"
DZIENNIK="$CEL/kopia.log"
TRZYMAJ_DNI="${NEXUS_KOPIE_DNI:-14}"

mkdir -p "$KATALOG"
exec > >(tee -a "$DZIENNIK") 2>&1
echo "== Kopia zapasowa $ZNACZNIK → $KATALOG"

if [[ ! -S "$GNIAZDO/.s.PGSQL.5433" ]]; then
  echo "BŁĄD: klaster PostgreSQL nie działa (brak gniazda w $GNIAZDO)." >&2
  exit 1
fi
# Klaster wpuszcza wyłącznie danaco-serwis (peer, deploy/postgres/pg_hba.conf), więc
# z innego konta skrypt podnosi się sam — tak samo jak deploy/nexus-cli.sh.
if [[ "$(id -un)" != "danaco-serwis" ]]; then
  # sudo czyści środowisko, więc ustawienie liczby dni przekazujemy wprost.
  exec sudo -u danaco-serwis env "NEXUS_KOPIE_DNI=${NEXUS_KOPIE_DNI:-14}" "${BASH_SOURCE[0]}" "$@"
fi

echo "-- bazy danych"
# Rozróżnienie jest tu istotne: „baza nie istnieje” wolno pominąć, „psql nie działa” nie —
# cicha kopia bez zrzutu bazy jest gorsza niż brak kopii.
if ! LISTA="$("$POSTGRES/psql" -h "$GNIAZDO" -p 5433 -d postgres -tAc \
    "SELECT datname FROM pg_database WHERE datistemplate = false")"; then
  echo "BŁĄD: nie udało się odpytać klastra (psql)." >&2
  exit 1
fi
for baza in nexus nextcloud; do
  if grep -qx "$baza" <<<"$LISTA"; then
    "$POSTGRES/pg_dump" -h "$GNIAZDO" -p 5433 -d "$baza" --format=custom --compress=9 \
      --file "$KATALOG/$baza.dump"
    echo "   $baza: $(du -h "$KATALOG/$baza.dump" | cut -f1)"
  else
    echo "   $baza: brak w klastrze, pomijam"
  fi
done
"$POSTGRES/pg_dumpall" -h "$GNIAZDO" -p 5433 --globals-only > "$KATALOG/role-i-uprawnienia.sql"

echo "-- pliki użytkownika"
if [[ -d "$PROJEKT/dane/app/files" ]]; then
  tar --create --zstd --file "$KATALOG/pliki.tar.zst" -C "$PROJEKT/dane/app" files
  echo "   pliki: $(du -h "$KATALOG/pliki.tar.zst" | cut -f1)"
fi

echo "-- wektory bazy wiedzy"
if [[ -d "$PROJEKT/dane/qdrant/storage" ]]; then
  tar --create --zstd --file "$KATALOG/qdrant.tar.zst" -C "$PROJEKT/dane/qdrant" storage
  echo "   qdrant: $(du -h "$KATALOG/qdrant.tar.zst" | cut -f1)"
fi

echo "-- pakiety marki i materiałów"
# Rendery, nagrania i pliki robocze marki (ok. 1,9 GB) nie leżą w repozytorium — są za
# ciężkie na historię git. Skoro git ich nie chroni, musi je chronić kopia zapasowa:
# bez nich nie da się odtworzyć ani `frontend/public`, ani materiałów promocyjnych.
# Kopia jest przyrostowa przez zstd i robiona raz — kolejne biegi zastępują plik.
MATERIALY=(branding design-system landing logo motion prezentacja product promocja ui-kit frontend/public)
ISTNIEJACE=()
for katalog in "${MATERIALY[@]}"; do
  [[ -d "$PROJEKT/$katalog" ]] && ISTNIEJACE+=("$katalog")
done
if (( ${#ISTNIEJACE[@]} )); then
  tar --create --zstd --file "$KATALOG/materialy.tar.zst" \
    -C "$PROJEKT" --ignore-failed-read "${ISTNIEJACE[@]}" 2>/dev/null || true
  echo "   materiały: $(du -h "$KATALOG/materialy.tar.zst" | cut -f1)"
fi

echo "-- kod źródłowy"
# Do 21 września 2026 kopia obejmowała bazy, pliki użytkowników, wektory, materiały marki
# i sekrety — **wszystko oprócz kodu**. Założenie było takie, że kod chroni git. Nie chronił:
# drzewo robocze miało tego dnia ponad 260 zmienionych plików poza commitami, a jedno
# nieostrożne `git checkout --` skasowało z niego kilkaset wierszy pracy.
# Kod waży tyle co nic przy 1,9 GB materiałów, więc nie ma powodu go pomijać.
# `node_modules`, `dist`, `build`, `.gradle` i wtyczki generowane przez Capacitora
# zostają poza kopią — odtwarza je instalacja i budowa (same ważą ponad 110 MB).
tar --create --zstd --file "$KATALOG/zrodla.tar.zst" \
  -C "$PROJEKT" --ignore-failed-read \
  --exclude='node_modules' --exclude='dist' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.pytest_cache' --exclude='.venv' \
  --exclude='build' --exclude='.gradle' --exclude='capacitor-cordova-android-plugins' \
  --exclude='.mypy_cache' --exclude='.ruff_cache' --exclude='backend/dane' \
  backend frontend/src frontend/scripts frontend/package.json frontend/index.html \
  frontend/vite.config.ts frontend/tsconfig.json \
  desktop/src desktop/package.json extension android/scripts android/android \
  deploy docs motion/MOTION_GUIDELINES.md README.md CHANGELOG.md .env.example \
  .gitignore .gitleaks.toml landing/ladowanie frontend/public/ladowanie/opcje.js \
  2>/dev/null || true
echo "   kod: $(du -h "$KATALOG/zrodla.tar.zst" | cut -f1)"

echo "-- sekrety i konfiguracja"
# Plik .env i klucze mają prawa 600; kopia dziedziczy je przez --preserve-permissions.
# Wykaz jest wyliczony, nie zgadywany: każdy plik z sekretem w dane/app ma prawa 600.
# Klucz podpisu Androida jest tu najważniejszy: bez niego nowej wersji aplikacji nie da się
# zainstalować jako aktualizacji na telefonach, które mają już poprzednią.
tar --create --zstd --preserve-permissions --file "$KATALOG/sekrety.tar.zst" \
  -C "$PROJEKT" --ignore-failed-read \
  .env \
  dane/app/google-api-key \
  dane/app/chmura-token \
  dane/app/poczta.json \
  dane/app/vapid \
  dane/app/android-keystore \
  dane/claude-profil 2>/dev/null || true
chmod 600 "$KATALOG/sekrety.tar.zst" 2>/dev/null || true

echo "-- suma kontrolna"
( cd "$KATALOG" && sha256sum ./* > SUMY.sha256 )

echo "-- sprzątanie kopii starszych niż $TRZYMAJ_DNI dni"
find "$CEL" -mindepth 1 -maxdepth 1 -type d -mtime "+$TRZYMAJ_DNI" -exec rm -rf {} + 2>/dev/null || true

echo "== Gotowe: $(du -sh "$KATALOG" | cut -f1) w $KATALOG"

# Odtworzenie (ręczne, przy zatrzymanych usługach danaco-nexus.target):
#   systemctl --user stop danaco-nexus.target
#   systemctl --user start danaco-nexus-postgres.service
#   pg_restore -h dane/run -p 5433 -d nexus --clean --if-exists dane/kopie/<znacznik>/nexus.dump
#   tar --extract --zstd --file dane/kopie/<znacznik>/pliki.tar.zst -C dane/app
#   tar --extract --zstd --file dane/kopie/<znacznik>/qdrant.tar.zst -C dane/qdrant
#   systemctl --user start danaco-nexus.target
