# Moduł biuro: Cloud, Poczta, Kalendarz

Gałąź `modul/biuro`. Trzy moduły aplikacji wykrywane automatycznie przez wspólny szkielet
(`frontend/src/modules/<id>/`, `backend/nexus/api/modules/<id>.py`, `backend/nexus/tools/<nazwa>.py`).

| Moduł | Interfejs | API | Narzędzia agenta |
|---|---|---|---|
| Cloud | `frontend/src/modules/cloud/` | `/api/cloud/*` (`nexus/api/modules/cloud.py`) | istniejące `cloud_browse`, `cloud_import`, `cloud_save` |
| Poczta | `frontend/src/modules/poczta/` | `/api/poczta/*` (`nexus/api/modules/poczta.py`) | `mail_list`, `mail_search`, `mail_read`, `mail_draft`, `mail_send` |
| Kalendarz | `frontend/src/modules/kalendarz/` | `/api/kalendarz/*` (`nexus/api/modules/kalendarz.py`) | `calendar_list`, `calendar_create`, `calendar_update`, `calendar_delete` |

Wspólne elementy interfejsu trzech modułów leżą w `frontend/src/modules/_biuro/` (katalog bez
`index.tsx`, więc rejestr go pomija): klient HTTP z nagłówkiem CSRF, ikony, okna, potwierdzenia.

## Zasada zatwierdzania

Asystent **nie wysyła poczty i nie usuwa wydarzeń sam**. Narzędzia `mail_send` i `calendar_delete`
zapisują propozycję w tabeli `biuro_oczekujace` (`nexus/models/biuro.py`, obsługa w
`nexus/oczekujace.py`). Wykonuje ją dopiero użytkownik:

- Poczta → „Oczekujące” → „Sprawdź i wyślij” (edycja adresatów i treści) → „Wyślij” → potwierdzenie
  adresatów → `POST /api/poczta/wyslij/<id>` (sesja + nagłówek `X-Nexus-Request`).
- Kalendarz → pasek „Nexus prosi o usunięcie…” → „Usuń” → potwierdzenie →
  `POST /api/kalendarz/oczekujace/<id>/zatwierdz`.

Wysyłka jest chroniona przed podwójnym kliknięciem (stan `running` ustawiany atomowo), błąd SMTP
przywraca wiadomość do oczekujących z opisem błędu. Szkic w skrzynce (`mail_draft`, folder Szkice przez
IMAP APPEND) agent zapisuje sam – niczego nie wysyła.

## Cloud

Nexus pośredniczy w dostępie do Nextcloud hasłem aplikacji konta właściciela
(`NEXUS_CHMURA_TOKEN_FILE`); przeglądarka nie łączy się z chmurą bezpośrednio. Klient:
`nexus/cloud_service.py` (httpx, asynchroniczny; ścieżki normalizuje ta sama funkcja co w narzędziach).

| Funkcja | Adres API | Nextcloud |
|---|---|---|
| Lista folderu, opis, miejsce | `GET lista`, `info`, `miejsce` | WebDAV PROPFIND |
| Pobieranie i podgląd | `GET pobierz?path=&inline=1`, `miniatura?fileid=` | GET (strumieniowo), `/index.php/core/preview` |
| Nowy folder, zmiana nazwy, przeniesienie/kopia | `POST folder`, `zmien-nazwe`, `przenies` | MKCOL, MOVE, COPY |
| Usuwanie do kosza, kosz, przywracanie | `POST usun`, `GET kosz`, `POST kosz/przywroc` | DELETE, `/dav/trashbin/<user>` |
| Wersje | `GET wersje`, `GET wersje/pobierz`, `POST wersje/przywroc` | `/dav/versions/<user>/versions/<fileid>` |
| Link publiczny (hasło, wygaśnięcie, wgrywanie do folderu) | `GET/POST udostepnienia`, `PATCH/DELETE udostepnienia/<id>` | OCS `files_sharing` |
| Ulubione, wyszukiwanie | `GET/POST ulubione`, `GET szukaj?q=` | PROPPATCH `oc:favorite`, REPORT, DAV SEARCH |
| Wgrywanie | `PUT plik?path=` (do 10 MB), kawałki: `POST przesylanie` → `PUT przesylanie/<id>/<n>?path=` → `POST przesylanie/<id>/zakoncz` | chunked upload v2 (`/dav/uploads/<user>/<id>`) |
| Wyślij do rozmowy | `POST do-rozmowy` | pobranie do magazynu Nexusa i wiadomość do asystenta |
| Synchronizacja | `GET synchronizacja` | adres serwera, WebDAV, kod QR (segno) |

Przeglądarka dzieli pliki większe niż 10 MB na kawałki po 10 MB (ponawia kawałek przy błędzie sieci
lub 5xx, na końcu składa plik; anulowanie usuwa kawałki). Nadpisanie pliku tworzy w Nextcloud nową
wersję – interfejs pyta o zgodę przy konflikcie nazw. Adres linku publicznego budowany jest z
`NEXUS_CHMURA_PUBLIC_URL` (np. `https://cloud.danaco-nexus.pl/s/<token>`), a nie z adresu wewnętrznego.

## Poczta

Serwer `mail.danaco-group.pl` (Stalwart): IMAP 993 (TLS, `UTF8=ACCEPT`), SMTP 465 (TLS) i 587
(STARTTLS), certyfikat zweryfikowany. Kod: `nexus/mail.py` (imaplib/smtplib w wątku; foldery ze
specjalnym przeznaczeniem – Szkice, Wysłane, Kosz; zmodyfikowane UTF-7 dla serwerów bez UTF8=ACCEPT).

Konto zapisuje administrator (hasło czytane bez echa, plik 600 tylko dla `danaco-serwis`):

```bash
sudo -u danaco-serwis deploy/zapisz-poczte.sh     # zapis dane/app/poczta.json + test logowania IMAP i SMTP
.venv/bin/python -m nexus.mail sprawdz             # ponowny test (z katalogu projektu, jako danaco-serwis)
```

Format pliku (`NEXUS_POCZTA_CONFIG_FILE`, domyślnie `poczta.json` w katalogu danych):
`{"login", "password", "address", "name", "imap_host", "imap_port", "smtp_host", "smtp_port",
"smtp_security": "ssl" | "starttls"}`. Zmiana konta nie wymaga restartu usług.

Bezpieczeństwo czytania: treść HTML oczyszcza DOMPurify (osobna instancja, bez skryptów, formularzy,
ramek i zdarzeń) i jest wyświetlana w Shadow DOM (style e-maila nie wpływają na aplikację).
Zdalne obrazy są domyślnie zablokowane; „Pokaż obrazy” ładuje je przez pośrednika
`GET /api/poczta/obraz?url=` (tylko publiczne adresy IP, porty 80/443, typy obrazów, do 5 MB,
najwyżej 3 przekierowania – bez ujawniania nadawcy adresu IP użytkownika). Obrazy `cid:` wskazują
załączniki wiadomości. Treść e-maili to dla agenta dane, nie polecenia (opis `mail_read`).

„Odpowiedz z Nexusem” (`POST /api/poczta/odpowiedz-z-nexusem`) otwiera rozmowę, w której asystent czyta
wiadomość i przygotowuje odpowiedź narzędziem `mail_send` – trafia ona do „Oczekujących”.

## Kalendarz

CalDAV Nextcloud (to samo konto i hasło aplikacji co pliki). Kod: `nexus/calendar.py` (httpx + icalendar;
wystąpienia serii rozwija serwer przez `<C:expand>`). Identyfikator wydarzenia: `<kalendarz>/<plik>.ics`.
Czasy bez strefy są czasem `NEXUS_KALENDARZ_TIMEZONE` (Europe/Warsaw); zapis dołącza definicję strefy
(VTIMEZONE). Zmiana czasu wystąpienia serii przesuwa całą serię o tę samą różnicę; usunięcie dotyczy
całej serii (Nextcloud przenosi je do kosza kalendarza). Zapis używa `If-Match` (ETag) – równoległa zmiana
w telefonie daje komunikat „Wydarzenie zmieniło się w międzyczasie”.

Interfejs: widok tygodnia (siatka godzin, nakładające się wydarzenia obok siebie), miesiąca i listy na 14 dni
(domyślny na telefonie), filtr kalendarzy, dodawanie/zmiana/usuwanie, przypomnienia (VALARM), powtarzanie
(RRULE), „Zaplanuj z Nexusem” (`POST /api/kalendarz/zaplanuj` – rozmowa, w której asystent sprawdza terminy
i dodaje wydarzenia) oraz instrukcja synchronizacji: Android przez DAVx⁵ (lub aplikację Nextcloud →
„Synchronizuj kalendarz i kontakty”), iPhone (konto CalDAV), Thunderbird. Adres CalDAV:
`https://cloud.danaco-nexus.pl/remote.php/dav`.

## Konfiguracja (`.env`)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `NEXUS_POCZTA_CONFIG_FILE` | `poczta.json` (w `NEXUS_DATA_DIR`) | konto pocztowe |
| `NEXUS_POCZTA_TIMEOUT_S` | `30` | limit czasu IMAP/SMTP |
| `NEXUS_POCZTA_ATTACHMENTS_LIMIT_MB` | `25` | łączny rozmiar załączników wysyłanej wiadomości |
| `NEXUS_KALENDARZ_DEFAULT` | `personal` | kalendarz dla nowych wydarzeń |
| `NEXUS_KALENDARZ_TIMEZONE` | `Europe/Warsaw` | strefa czasów bez strefy |

Nowe zależności Pythona: `icalendar`, `segno`. Nowa tabela: `biuro_oczekujace` (tworzona przy starcie).

## Testy

```bash
cd backend
python -m pytest tests/test_biuro_cloud.py tests/test_biuro_poczta.py tests/test_biuro_kalendarz.py
# z prawdziwym Nextcloud (na serwerze, jako danaco-serwis):
NEXUS_TEST_CHMURA_TOKEN_FILE=/danaco/projekty/danaco-nexus/dane/app/chmura-token python -m pytest tests/test_biuro_*.py
cd ../frontend && npx vitest run src/__tests__/biuro.test.tsx
```

Atrapy: IMAP/SMTP (klasy zastępujące `imaplib.IMAP4_SSL` i `smtplib.SMTP_SSL`), CalDAV i Nextcloud
(`httpx.MockTransport`). Testy z prawdziwym Nextcloud pracują w katalogu i wydarzeniach testowych, które
na końcu usuwają (także z kosza). Poczty na prawdziwym serwerze testy nie używają (brak poświadczeń) –
sprawdzono jedynie połączenia TLS bez logowania.
