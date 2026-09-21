#!/usr/bin/env bash
# Wpina sprzedaż: zapisuje klucze Stripe i identyfikatory cen, sprawdza je i restartuje API.
#
# Sprzedaż jest w produkcie gotowa — plany, kredyty, pakiety, faktury, kupony, portal
# rozliczeniowy i webhooki. Nie działa, dopóki serwer nie ma poświadczeń konta Stripe:
# `sprzedaz_aktywna` jest wtedy fałszem i interfejs pokazuje „powiadom mnie” zamiast
# przycisku zakupu. Ten skrypt zamyka tę lukę bez ręcznej edycji plików.
#
# Skrypt przyjmuje klucze prawdziwe (`sk_live_…`) i testowe (`sk_test_…`) — decyduje
# właściciel. Prawdziwe znaczy prawdziwe płatności od pierwszego zakupu; testowe pozwalają
# przeklikać ścieżkę kartami testowymi, ale nie sprawdzają, czy ktoś naprawdę zapłaci.
#
#   deploy/zapisz-stripe.sh
#
# Skrypt pyta o wartości i niczego nie wypisuje na ekran ani do historii powłoki.

set -euo pipefail

KORZEN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DANE="$KORZEN/dane/app"
ENV_PLIK="$KORZEN/.env"

czytaj_tajne() {
  local zmienna="$1" pytanie="$2" wartosc=""
  printf '%s: ' "$pytanie" >&2
  read -rs wartosc
  printf '\n' >&2
  printf -v "$zmienna" '%s' "$wartosc"
}

echo "=== Wpięcie sprzedaży Stripe ==="
echo "Klucze i ceny bierzesz z panelu Stripe — z tego trybu, w którym chcesz sprzedawać." >&2
echo >&2

czytaj_tajne KLUCZ "Klucz tajny (sk_live_… do sprzedaży, sk_test_… do przeklikania)"
[ -n "$KLUCZ" ] || { echo "Bez klucza tajnego sprzedaż się nie włączy." >&2; exit 1; }
case "$KLUCZ" in
  sk_test_*|sk_live_*|rk_test_*|rk_live_*) ;;
  *) echo "To nie wygląda na klucz tajny Stripe (oczekiwane sk_test_… albo sk_live_…)." >&2; exit 1 ;;
esac

czytaj_tajne WEBHOOK "Sekret webhooka (whsec_…, można pominąć na start)"

echo >&2
echo "Identyfikatory cen — zapis: plan:okres=price_… oddzielone średnikiem." >&2
echo "Przykład: osobisty:miesiac=price_A;osobisty:rok=price_B;pro:miesiac=price_C" >&2
printf 'Ceny: ' >&2
read -r CENY

echo >&2
echo "Kwoty w groszach, tym samym zapisem — muszą zgadzać się z cenami w Stripe." >&2
echo "Przykład: osobisty:miesiac=2900;osobisty:rok=29000" >&2
printf 'Kwoty: ' >&2
read -r KWOTY

mkdir -p "$DANE"
zapisz_sekret() {
  local plik="$1" tresc="$2"
  [ -n "$tresc" ] || return 0
  printf '%s' "$tresc" > "$plik"
  chmod 600 "$plik"
  echo "  zapisano $(basename "$plik")" >&2
}
zapisz_sekret "$DANE/stripe-klucz" "$KLUCZ"
zapisz_sekret "$DANE/stripe-webhook" "$WEBHOOK"

# Wpisy w `.env` idą przez plik tymczasowy: przerwany zapis nie zostawia okrojonego
# środowiska, na którym usługa nie wstanie.
ustaw_env() {
  local nazwa="$1" wartosc="$2" tmp
  tmp="$(mktemp "$ENV_PLIK.XXXX")"
  grep -v "^${nazwa}=" "$ENV_PLIK" > "$tmp" || true
  # Wartość idzie w cudzysłowach: cennik ma postać `kod:okres=price_…;kod:okres=price_…`,
  # a średnik bez cudzysłowu rozcina wiersz przy `source` — tak przestały działać wszystkie
  # polecenia `deploy/nexus-cli.sh`. systemd czyta cudzysłowy poprawnie i je zdejmuje.
  printf '%s="%s"\n' "$nazwa" "$wartosc" >> "$tmp"
  chmod --reference="$ENV_PLIK" "$tmp"
  mv "$tmp" "$ENV_PLIK"
}
ustaw_env NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK "$DANE/stripe-klucz"
[ -n "$WEBHOOK" ] && ustaw_env NEXUS_PLATNOSCI_WEBHOOK_SEKRET_PLIK "$DANE/stripe-webhook"
[ -n "$CENY" ] && ustaw_env NEXUS_PLATNOSCI_CENY "$CENY"
[ -n "$KWOTY" ] && ustaw_env NEXUS_PLATNOSCI_KWOTY "$KWOTY"

echo >&2
echo "-- restart API" >&2
systemctl restart danaco-nexus-api.service 2>/dev/null || sudo systemctl restart danaco-nexus-api.service
sleep 4

echo "-- sprawdzenie" >&2
ADRES="${NEXUS_PUBLIC_URL:-https://danaco-nexus.pl}"
STAN="$(curl -sf "$ADRES/api/platnosci/cennik" | grep -o '"sprzedaz_aktywna":[a-z]*' || true)"
if [ "$STAN" = '"sprzedaz_aktywna":true' ]; then
  echo "Sprzedaż włączona — cennik pokazuje przyciski zakupu." >&2
else
  echo "Sprzedaż nadal wyłączona. Sprawdź dziennik: journalctl -u danaco-nexus-api -n 50" >&2
  exit 1
fi
