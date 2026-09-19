#!/usr/bin/env bash
# Dodaje (albo zastępuje) konto pocztowe modułu Poczta w dane/app/poczta.json – pozostałe konta
# i ich podpisy zostają bez zmian. Zapisuje login, hasło, nadawcę i serwery.
#
# Serwer mail.danaco-group.pl: IMAP 993 (TLS), SMTP 465 (TLS) albo 587 (STARTTLS).
# Użycie:  sudo -u danaco-serwis deploy/zapisz-poczte.sh
# Hasło jest wczytywane bez echa i zapisywane w pliku z prawami 600 (tylko danaco-serwis).
# Na końcu skrypt sprawdza logowanie IMAP i SMTP (bez wysyłania wiadomości).
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIK="$PROJEKT/dane/app/poczta.json"
PYTHON="$PROJEKT/.venv/bin/python"
WZOR_ADRESU='^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'

if [ "$(id -un)" != "danaco-serwis" ]; then
    echo "Uruchom jako danaco-serwis: sudo -u danaco-serwis $0" >&2
    exit 1
fi
if [ ! -x "$PYTHON" ]; then
    echo "Brak środowiska $PYTHON – najpierw uruchom deploy/instalacja.sh." >&2
    exit 1
fi

read -r -p "Adres e-mail (login), np. biuro@danaco-group.pl: " login
login="$(printf '%s' "$login" | tr -d '[:space:]')"
if ! [[ "$login" =~ $WZOR_ADRESU ]]; then
    echo "To nie wygląda na adres e-mail. Nic nie zapisano." >&2
    exit 1
fi
read -r -p "Nazwa nadawcy (np. Danaco Group; Enter = bez nazwy): " nazwa
read -r -s -p "Hasło do skrzynki: " haslo
echo
if [ -z "$haslo" ]; then
    echo "Puste hasło. Nic nie zapisano." >&2
    exit 1
fi
read -r -p "Serwer poczty [mail.danaco-group.pl]: " serwer
serwer="${serwer:-mail.danaco-group.pl}"
read -r -p "Wysyłanie: 465 (TLS) czy 587 (STARTTLS) [465]: " port
port="${port:-465}"
case "$port" in
    465) bezpieczenstwo=ssl ;;
    587) bezpieczenstwo=starttls ;;
    *) echo "Dozwolone porty: 465 albo 587. Nic nie zapisano." >&2; exit 1 ;;
esac

umask 077
# Dane trafiają do Pythona przez standardowe wejście (hasło nie pojawia się w argumentach procesu).
printf '%s\n%s\n%s\n%s\n%s\n%s\n' "$login" "$nazwa" "$serwer" "$port" "$bezpieczenstwo" "$haslo" \
    | "$PYTHON" -c '
import json, os, sys
login, name, host, port, security, password = sys.stdin.read().split("\n")[:6]
account = {
    "id": login.lower(), "login": login, "address": login, "name": name.strip(), "password": password,
    "imap_host": host, "imap_port": 993, "smtp_host": host, "smtp_port": int(port), "smtp_security": security,
}
data = {"default": account["id"], "accounts": []}
if os.path.exists(sys.argv[2]):
    with open(sys.argv[2], encoding="utf-8") as handle:
        old = json.load(handle)
    if isinstance(old.get("accounts"), list):
        data = old
    elif old.get("login"):
        data = {"default": old["login"].lower(), "accounts": [old]}
key = lambda a: (a.get("id") or a.get("address") or a.get("login") or "").lower()
same = [a for a in data["accounts"] if key(a) == account["id"]]
if same:
    account["signature_html"] = same[0].get("signature_html", "")
    account["label"] = same[0].get("label", "")
data["accounts"] = [a for a in data["accounts"] if key(a) != account["id"]] + [account]
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
' "$PLIK.nowy" "$PLIK"
mv -f "$PLIK.nowy" "$PLIK"
unset haslo
echo "Zapisano konto w $PLIK. Sprawdzanie logowania wszystkich kont…"

cd "$PROJEKT"
if NEXUS_POCZTA_CONFIG_FILE="$PLIK" "$PYTHON" -m nexus.mail sprawdz; then
    echo "Poczta gotowa. Moduł Poczta i narzędzia asystenta działają bez restartu usług."
else
    echo "Logowanie nie powiodło się – sprawdź adres i hasło i uruchom skrypt ponownie." >&2
    exit 1
fi
