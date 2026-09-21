#!/usr/bin/env bash
# Buduje wydanie ze strefy roboczej: gotowy, niezmienny artefakt w wydania/wersje/<znacznik>.
#
# Strefa robocza (to repozytorium) nie jest tym, co widzi użytkownik. Każda zmiana musi
# najpierw przejść bramkę (ruff, pytest, testy i budowa frontendu), a dopiero potem staje
# się wydaniem. Wydanie jest kopiowane w całości, żeby dalsza praca w repozytorium nie
# zmieniała tego, co już gdzieś działa.
#
#   deploy/wydania/zbuduj.sh [--bez-bramki]
#
# Wypisuje znacznik wydania na standardowe wyjście (ostatni wiersz).

set -euo pipefail

KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WYDANIA="$KORZEN/wydania"
WERSJE="$WYDANIA/wersje"
PYTHON="$KORZEN/.venv/bin/python"
BEZ_BRAMKI="${1:-}"
# Pełny przebieg testów mieści się w kilku minutach; powyżej tego to zakleszczenie.
LIMIT_PYTEST_S="${LIMIT_PYTEST_S:-900}"

cd "$KORZEN"
mkdir -p "$WERSJE"

# Bramka nie może pracować równolegle z innym przebiegiem testów: scenariusz `agents`
# uruchamia atrapę CLI i serwer MCP jako procesy potomne, a dwa przebiegi naraz
# zakleszczają się na tych samych zasobach (sprawdzone 20.09.2026).
# Blokadę wolno wskazać osobno (``BRAMKA_LOCK``). Potrzebne, gdy poprzednia budowa
# zakleszczyła się na testach i trzyma blokadę mimo że nic już nie liczy: wtedy uruchamia
# się poprawioną budowę obok, zamiast czekać na proces, który nigdy nie skończy.
# Nazwa bez ukośnika to plik w `wydania/`, nie w katalogu, z którego uruchomiono skrypt —
# inaczej `BRAMKA_LOCK=gate7` zostawia śmieć w korzeniu repozytorium.
BLOKADA="${BRAMKA_LOCK:-.bramka.lock}"
case "$BLOKADA" in
  */*) ;;
  *) BLOKADA="$WYDANIA/$BLOKADA" ;;
esac
exec 9>"$BLOKADA"
if ! flock -n 9; then
  echo "Inna budowa wydania już trwa — poczekaj na jej koniec." >&2
  echo "Jeżeli poprzednia budowa wisi, wskaż inną blokadę: BRAMKA_LOCK=... $0" >&2
  exit 1
fi

ZNACZNIK="$(date +%Y%m%d-%H%M%S)-$(git rev-parse --short HEAD 2>/dev/null || echo brak)"
DOCELOWY="$WERSJE/$ZNACZNIK"
DZIENNIK="$KORZEN/.logs/wydanie-$ZNACZNIK.log"
mkdir -p "$KORZEN/.logs"

KROK="przygotowanie"
powiedz() { KROK="$*"; printf '%s\n' "$*" | tee -a "$DZIENNIK" >&2; }

# Bez tego bramka kończyła się w pół zdania: ostatnim wierszem logu był nagłówek kroku,
# a powód przerwania (limit czasu pytest, błąd ruff, nieudana budowa) leżał w osobnym
# dzienniku wydania, o którym trzeba było wiedzieć. Teraz przerwanie samo mówi, gdzie stanęło.
na_bledzie() {
  kod=$?
  printf 'przerwano na kroku: %s (kod %d)\n' "$KROK" "$kod" >&2
  printf 'dziennik wydania: %s\n' "$DZIENNIK" >&2
  tail -n 15 "$DZIENNIK" >&2
}
trap na_bledzie ERR

# Odcisk źródeł na starcie biegu.
#
# Bramka liczy kilkanaście minut i czyta drzewo robocze **w kilku różnych momentach**:
# pytest na początku, testy interfejsu w środku, `npm run build` na końcu. Jeżeli w tym
# czasie zmienią się źródła, wydanie powstaje z innego kodu niż ten, który przeszedł testy —
# a znacznik wydania niesie tylko skrót commita, więc po artefakcie tego nie widać.
# Zdarzyło się to 21 września 2026 trzy razy w ciągu godziny i za każdym razem po cichu.
#
# Liczymy sumę kontrolną **treści** plików źródłowych — razem z konfiguracją budowy
# interfejsu (`vite.config.ts` niesie cały manifest PWA i reguły service workera,
# `index.html` wpięcie ekranu ładowania, `package.json` haki `pretest`/`prebuild`).
# Bez nich zmiana wpływająca na wynik budowy przechodziła niezauważona, czyli działo się
# dokładnie to, przed czym ten krok ma chronić. Pomijamy to, co bramka sama
# wytwarza: `frontend/src/tokens.css` i `frontend/src/dane/narzedzia.ts` odtwarza hak
# `pretest`/`prebuild` przy każdym uruchomieniu, więc ich czas modyfikacji zmienia się
# zawsze — treść zwykle nie, ale nie ma powodu na tym polegać.
odcisk_zrodel() {
  find backend/nexus backend/tests frontend/src frontend/scripts deploy desktop/src extension/src \
    frontend/vite.config.ts frontend/index.html frontend/package.json frontend/tsconfig.json \
    -type f \
    ! -path 'frontend/src/tokens.css' \
    ! -path 'frontend/src/dane/narzedzia.ts' \
    ! -name '*.pyc' \
    -print0 2>/dev/null | sort -z | xargs -0 cat 2>/dev/null | cksum
}
ODCISK_START="$(odcisk_zrodel)"

powiedz "=== wydanie $ZNACZNIK ==="

if [ "$BEZ_BRAMKI" != "--bez-bramki" ]; then
  powiedz "--- sekrety ---"
  # Klucz wpisany „na chwilę” do repozytorium zostaje w historii na zawsze, a zauważa się
  # go dopiero po wycieku. Skan trwa ćwierć sekundy na całej historii (115 commitów,
  # 5,5 MB), więc nie ma powodu, żeby go tu nie było. Zawężenia fałszywych trafień —
  # hasła kont testowych — stoją w `.gitleaks.toml` i dotyczą wyłącznie reguły ogólnej;
  # prawdziwy klucz w pliku testu nadal zapala czerwone światło.
  if command -v gitleaks >/dev/null 2>&1; then
    gitleaks detect --no-banner --redact >>"$DZIENNIK" 2>&1
  else
    powiedz "--- sekrety: pominięte (brak gitleaks) ---"
  fi
  powiedz "--- ruff ---"
  "$KORZEN/.venv/bin/ruff" check backend >>"$DZIENNIK" 2>&1
  powiedz "--- pytest ---"
  # Limit czasu i zrzut stosów: przy dwóch przebiegach naraz zdarza się zakleszczenie
  # w okolicy `test_agent.py::test_subagents_become_nested_events` (atrapa CLI uruchamia
  # prawdziwy serwer MCP jako proces wnuka). Bez limitu budowa wisiała godzinami i trzymała
  # blokadę bramki; z limitem kończy się błędem i zostawia w dzienniku ślad, gdzie stanęła.
  ( cd backend && timeout "$LIMIT_PYTEST_S" "$PYTHON" -m pytest -q -o faulthandler_timeout=600 \
      --deselect tests/test_research.py::test_openalex_real_network ) >>"$DZIENNIK" 2>&1
  powiedz "--- testy interfejsu ---"
  # `npm test`, nie `npx vitest run`: hak `pretest` przegenerowuje `frontend/public`
  # i katalog narzędzi ze źródeł. Część testów czyta te pliki (ekran ładowania jest
  # kopią z `landing/`), a ten krok idzie **przed** budową interfejsu — bez haka testy
  # sprawdzałyby to, co zostało po poprzedniej budowie, a nie bieżące źródła.
  ( cd frontend && npx tsc --noEmit && npm test ) >>"$DZIENNIK" 2>&1
  powiedz "--- programy narzędzi ---"
  # Testy tego nie złapią: przy braku programu pomijają przypadek zamiast zgłosić błąd.
  # Tak zniknął cały skład dokumentów — `typst` leżał poza PATH usług, a `typeset_document`
  # odmawiał pracy dopiero przy użytkowniku. Sprawdzamy **ścieżką usługi** z `.env`, bo to
  # ona obowiązuje po wdrożeniu, a nie ścieżka powłoki, w której stoi bramka.
  # Bez `.env` (świeże repozytorium przed instalacją) sprawdzamy ścieżką powłoki.
  SCIEZKA_USLUGI=""
  if [ -f "$KORZEN/.env" ]; then
    SCIEZKA_USLUGI="$(sed -n 's/^PATH=//p' "$KORZEN/.env" | tail -1 | tr -d '"')"
  fi
  ( cd backend && PATH="${SCIEZKA_USLUGI:-$PATH}" "$PYTHON" -c "
import sys
from nexus.doctor import check_programy_narzedzi

wynik = check_programy_narzedzi()
print(wynik.detail)
sys.exit(0 if wynik.ok else 1)
" ) >>"$DZIENNIK" 2>&1
fi

powiedz "--- budowa interfejsu ---"
( cd frontend && npm run build ) >>"$DZIENNIK" 2>&1

# Zanim skopiujemy artefakt: czy to wciąż ten sam kod, który przeszedł bramkę?
powiedz "--- odcisk źródeł ---"
ODCISK_KONIEC="$(odcisk_zrodel)"
if [ "$ODCISK_START" != "$ODCISK_KONIEC" ]; then
  powiedz "PRZERWANE: źródła zmieniły się w trakcie bramki"
  {
    echo "Źródła zmieniły się między startem bramki a budową artefaktu."
    echo "Testy przeszły na innym kodzie niż ten, który trafiłby do wydania."
    echo "Powtórz budowę, gdy nikt nie pisze po drzewie roboczym."
  } | tee -a "$DZIENNIK" >&2
  exit 1
fi

powiedz "--- kopiowanie artefaktu ---"
rm -rf "$DOCELOWY.tmp"
mkdir -p "$DOCELOWY.tmp"
# Do wydania idzie to, co serwer uruchamia: kod, gotowy interfejs i pliki wdrożeniowe —
# **oraz źródła klientów**, z których ten interfejs powstał.
#
# Źródeł nie było tu do 21 września 2026 i wydanie nie dawało się z niczego odtworzyć: artefakt
# miał `frontend/dist` (kod zbudowany, bez map źródeł), ale nie `frontend/src`. Kopia zapasowa
# serwera obejmuje dane użytkowników, nie repozytorium, więc jedynym miejscem, gdzie żyły
# źródła, było drzewo robocze na tym dysku — z 266 zmienionymi plikami poza commitami.
# Tego samego dnia jedno nieostrożne `git checkout --` skasowało z niego ~180 wierszy pracy
# (odzyskane wyłącznie z zapisu rozmowy, który nikomu nie służy za kopię zapasową).
#
# Koszt: `frontend/src` 2,4 MB, `desktop/src` 208 kB, `extension` 380 kB, reszta poniżej
# 100 kB — przy wydaniu ważącym ok. 7 MB to niecała połowa wzrostu. `landing/` (395 MB)
# i `motion/` (114 MB) zostają poza wydaniem: to materiały źródłowe, a ich wynik jest już
# w `frontend/dist`. Wyjątkiem jest ekran ładowania marki: `landing/ladowanie/ladowanie.js`
# i `.css` to **kod**, nie materiał — to z nich `frontend/scripts/zasoby.py` robi kopię
# w `frontend/public`. Dochodzi `frontend/public/ladowanie/opcje.js`, który jest źródłem
# i leży tam na stałe: cały ten katalog jest w `.gitignore` z wyjątkiem tego pliku, więc
# bez niego ekranu ładowania nie da się odtworzyć. `.gitignore` i `.gitleaks.toml` też
# wchodzą — bez nich odtworzone repozytorium zachowuje się inaczej niż oryginał.
tar -cf - \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  --exclude='node_modules' --exclude='dist' \
  backend/nexus deploy README.md CHANGELOG.md | tar -xf - -C "$DOCELOWY.tmp"
mkdir -p "$DOCELOWY.tmp/zrodla"
tar -cf - \
  --exclude='node_modules' --exclude='dist' --exclude='__pycache__' --exclude='*.pyc' \
  frontend/src frontend/scripts frontend/package.json frontend/index.html \
  frontend/vite.config.ts frontend/tsconfig.json \
  desktop/src desktop/package.json desktop/test desktop/assets \
  extension android/scripts \
  landing/ladowanie/ladowanie.js landing/ladowanie/ladowanie.css \
  frontend/public/ladowanie/opcje.js \
  .gitignore .gitleaks.toml \
  | tar -xf - -C "$DOCELOWY.tmp/zrodla"
mkdir -p "$DOCELOWY.tmp/frontend"
# Gotowy interfejs waży 645 MB, z czego 589 MB to nagrania (galeria filmów i kampania);
# właściwy kod strony to 1,4 MB. Nagrania są w każdym wydaniu identyczne, a kopiowane od
# nowa urosły do 48 GB w jeden dzień. `--link-dest` zakłada twarde dowiązanie wszędzie
# tam, gdzie plik jest taki sam jak w poprzednim wydaniu; zmieniony kopiuje się normalnie.
# Jest to bezpieczne: wydania są tylko do odczytu (serwuje je uvicorn), `sprzataj.sh`
# usuwa całe katalogi — czyli odpina dowiązania — a kopia zapasowa obejmuje `frontend/public`
# (źródło nagrań), nie `wydania`. Bez rsynca albo bez poprzedniego wydania kopiujemy po staremu.
POPRZEDNI_DIST=""
for katalog in "$WERSJE"/*/frontend/dist; do
  [ -d "$katalog" ] && POPRZEDNI_DIST="$katalog"
done
if [ -n "$POPRZEDNI_DIST" ] && command -v rsync >/dev/null 2>&1; then
  # Dwie opcje, obie konieczne — sprawdzone pomiarem, nie z pamięci:
  # `--checksum`, bo budowa przepisuje cały katalog `dist` i każdy plik ma nowy czas
  #   modyfikacji; zwykłe porównanie (rozmiar + czas) uznałoby wszystko za zmienione,
  # `--no-times`, bo rsync dowiązuje tylko pliki zgodne **i treścią, i atrybutami** —
  #   a czas modyfikacji zawsze się różni, więc bez tego nie powstaje ani jedno dowiązanie.
  # Skutek uboczny jest na plus: dowiązany plik zachowuje czas z poprzedniego wydania,
  # więc ETag nagrania przestaje się zmieniać przy każdym wdrożeniu i przeglądarka
  # użytkownika nie ściąga go od nowa.
  rsync -a --checksum --no-times --link-dest="$POPRZEDNI_DIST" \
    frontend/dist/ "$DOCELOWY.tmp/frontend/dist/"
else
  cp -a frontend/dist "$DOCELOWY.tmp/frontend/dist"
fi
git rev-parse HEAD > "$DOCELOWY.tmp/WYDANIE-COMMIT" 2>/dev/null || echo brak > "$DOCELOWY.tmp/WYDANIE-COMMIT"
date -Is > "$DOCELOWY.tmp/WYDANIE-DATA"
mv "$DOCELOWY.tmp" "$DOCELOWY"

powiedz "gotowe: $DOCELOWY"
printf '%s\n' "$ZNACZNIK"
