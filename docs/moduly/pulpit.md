# Moduł „pulpit” – Nexus Desktop dla Windows

Nexus Desktop to aplikacja Windows (Electron 44 + electron-builder, instalator NSIS), która:

1. otwiera Nexusa (`https://danaco-nexus.pl`) we własnym oknie z ikoną, zapamiętanym rozmiarem
   i położeniem, ikoną w zasobniku i opcjonalnym autostartem (`--ukryty`, tylko zasobnik);
2. ma **wysuwany panel** przy prawej krawędzi ekranu – zawsze na wierzchu, otwierany najechaniem
   na cienki języczek, kliknięciem albo skrótem (domyślnie `Ctrl+Spacja`, konfigurowalny);
   drugi skrót (`Ctrl+Shift+Spacja`) otwiera panel i od razu dołącza zrzut okna;
3. uruchamia **lokalnego agenta komputera**: narzędzia `pc_*`, z których asystent Claude na serwerze
   korzysta, aby diagnozować i naprawiać komputer, szukać i czytać pliki, robić zrzuty ekranu.

## Architektura

```
Claude Code CLI ─ MCP (nexus.mcp_server) ─ narzędzie pc_* ──┐ Redis (Valkey)
                                                            │  nexus:pc:<urządzenie>:req
API FastAPI  /api/pulpit/ws  ◄──────────────────────────────┘  nexus:pc:resp:<id żądania>
      │ WebSocket (klucz urządzenia kind="desktop")             nexus:pc:online (hasz)
Nexus Desktop (Windows) ─ PcTools: pc_info, pc_find_files, pc_read_file, pc_powershell, pc_screenshot
```

| Plik | Rola |
|---|---|
| `backend/nexus/pulpit.py` | Przekaźnik: pośrednik Redis (asynchroniczny dla API, synchroniczny dla narzędzi) i pośrednik w pamięci (testy / brak Redisa), wybór komputera, oczekiwanie na odpowiedź z limitem czasu, anulowanie. |
| `backend/nexus/api/modules/pulpit.py` | `WS /api/pulpit/ws` (uwierzytelnienie kluczem w pierwszym komunikacie albo nagłówku), rejestr podłączonych komputerów, `GET /api/pulpit/komputery`. |
| `backend/nexus/tools/pc.py` | Narzędzia agenta `pc_*` (opisy i schematy dla Claude). |
| `desktop/src/main.js` | Proces główny: okno, zasobnik, skróty, IPC, ustawienia, klucz urządzenia z sesji okna. |
| `desktop/src/panel.js` | Języczek i panel (pasek narzędzi + `/?widok=panel`), umowa postMessage, „Zobacz ekran”, „Wstaw”. |
| `desktop/src/agent/*` | Połączenie WebSocket, narzędzia, klasyfikacja poleceń PowerShell, ścieżki poufne. |
| `desktop/src/powershell.js` | Uruchamianie PowerShell (limit czasu, anulowanie, UAC) i stały proces pomocniczy user32. |
| `desktop/src/confirm.js`, `src/ui/confirm.*` | Okno zgody na polecenia zmieniające system. |
| `desktop/src/smoke.js` | Test uruchomienia bez udziału użytkownika. |

### Protokół WebSocket

* komputer → serwer: `{"type":"auth","token":"nxd_…","host","version","platform"}` (pierwszy komunikat,
  zamiast niego można wysłać nagłówek `Authorization: Bearer nxd_…`), `{"type":"ping"}` co 25 s,
  `{"type":"response","id","ok","result"|"error"}`;
* serwer → komputer: `ready`, `pong`, `request {id, tool, args}`, `cancel {id}`, `error {message}`.
* Kody zamknięcia: `4401` – klucz nieprawidłowy, cofnięty albo nie jest kluczem rodzaju `desktop`
  (sprawdzany ponownie co 60 s przy pingu), `4409` – ten sam komputer połączył się ponownie
  (starsze połączenie jest zamykane, żeby żądanie nie wykonało się dwa razy).
* Wynik narzędzia: `{text?, data?, images?: [base64 JPEG/PNG], file?: {name, path, data}}`; `file` trafia do
  rozmowy jako plik wynikowy (dostaje `file_id`) i nie jest pokazywany modelowi.
* Brak podłączonego komputera → narzędzie zwraca czytelny błąd („Żaden komputer z Nexus Desktop nie jest
  teraz podłączony…”); brak odpowiedzi → błąd po `NEXUS_PULPIT_TIMEOUT_S` (+ czas na zgodę dla PowerShell).

### Narzędzia agenta

| Narzędzie | Działanie |
|---|---|
| `pc_info` | System, procesor i obciążenie, RAM (zajęty/wolny, pamięć zadeklarowana), dyski (wolne miejsce), czas pracy, procesy wg pamięci, programy autostartu. |
| `pc_find_files` | Szukanie po nazwie (fragment lub `*`/`?`), rozszerzeniach, dacie zmiany i treści. Treść: indeks wyszukiwania Windows (także DOCX/PDF), bez indeksu – pliki tekstowe. Domyślnie Pulpit, Dokumenty, Pobrane, Obrazy, Wideo, Muzyka, OneDrive; pomija `AppData`, `node_modules`, katalogi systemowe i ukryte; limit 25 s. |
| `pc_read_file` | Tekst (UTF-8/UTF-16/Windows-1250), podgląd obrazu, zawartość katalogu, metadane; `upload=true` przesyła plik do 10 MB do rozmowy (dalej OCR, konwersje, `extract_text`). |
| `pc_powershell` | Polecenie Windows PowerShell 5.1: tylko-odczyt z białej listy od razu, każde inne po zgodzie w oknie na komputerze; `as_admin=true` – zawsze zgoda + monit UAC Windows. |
| `pc_screenshot` | Zrzut ekranu (`screen`, numer ekranu) albo okna aktywnego przed Nexusem (`active_window`); użytkownik dostaje powiadomienie. |

## Bezpieczeństwo

* **Zgoda na zmiany.** `desktop/src/agent/powershellPolicy.js` klasyfikuje polecenie; domyślnie wymagana jest
  zgoda. Bez zgody wykonuje się tylko polecenie, w którym każde wywołanie jest na białej liście
  (`Get-Process`, `Get-CimInstance`, `Get-ChildItem`, `Select-Object`, `ipconfig /all`…), a składnia nie pozwala
  uruchomić niczego innego: blokowane są m.in. wywołania metod (`.Kill()`), operator `&`, dot-sourcing,
  przekierowania `>`, podwyrażenia `$( )` w napisach, znak `` ` ``, here-stringi, `ForEach-Object -MemberName`,
  statyczne wywołania .NET spoza listy, przypisania do właściwości, definicje funkcji, nazwy poleceń
  zmieniających stan nawet w argumentach i odwołania do danych poufnych (`.ssh`, `Login Data`, `.kdbx`…).
* **Okno zgody** pokazuje pełne polecenie, opis od asystenta, powody i ostrzeżenia (usuwanie rekurencyjne,
  dyski, rejestr, zabezpieczenia, pobieranie z internetu). Domyślny przycisk to „Odrzuć”, „Wykonaj” jest
  aktywny po 1,2 s, brak decyzji w 240 s = odmowa. Treść jest wstawiana wyłącznie przez `textContent`.
* **Dziennik audytowy**: `%APPDATA%\Nexus Desktop\logi\nexus-desktop.log` (polecenia, decyzje, kody wyjścia).
* **Pliki poufne** są zawsze zablokowane (klucze SSH/GPG, `.env`, `.pfx/.pem/.key`, menedżery haseł,
  profile przeglądarek, magazyny poświadczeń Windows, klucz samej aplikacji).
* **Ustawienia** pozwalają wyłączyć cały agent, dostęp do plików, zrzuty i PowerShell.
* **Klucz urządzenia** jest tworzony przyciskiem „Połącz komputer” z sesji zalogowanego okna
  (`POST /api/urzadzenia`, `kind: "desktop"`) albo wklejany ręcznie; zapisywany przez `safeStorage` (DPAPI)
  i nigdy nie wyświetlany. Cofnięcie klucza na stronie Urządzenia rozłącza komputer najpóźniej po ~85 s.
* **Treści zdalne**: `contextIsolation` + `sandbox`, nawigacja tylko w obrębie witryny Nexusa (inne adresy
  w przeglądarce systemowej), uprawnienia (mikrofon, powiadomienia) tylko dla witryny Nexusa. Preload panelu
  nie udostępnia stronie żadnego API. Lokalne strony mają CSP `script-src 'self'`, a IPC przyjmuje żądania
  tylko od stron `file://`.

## Panel i umowa postMessage

Panel to okno z dwoma widokami: lokalny pasek narzędzi (Zobacz ekran, Cały ekran, Przypnij, Pełne okno,
Odśwież, Ustawienia, Schowaj) i strona `https://danaco-nexus.pl/?widok=panel` we wspólnej sesji
(`persist:nexus`) z oknem głównym – logowanie w oknie działa też w panelu. Strona jest oknem najwyższego
poziomu (nie iframe), więc `window.parent === window`:

* rodzic → panel: preload publikuje `nexus:context`, `nexus:prompt`, `nexus:auth` przez
  `window.postMessage(msg, location.origin)` – po `nexus:ready` (albo 4 s po załadowaniu strony);
  `nexus:auth` wysyłany tylko przy włączonej opcji „Panel loguje się kluczem urządzenia”;
* panel → rodzic: `nexus:ready`, `nexus:insert`, `nexus:copy` wysłane przez stronę do `window.parent`
  (czyli do siebie) odbiera preload i przekazuje do procesu głównego.
* „Zobacz ekran”: zrzut okna aktywnego przed otwarciem panelu (`desktopCapturer`, dopasowanie po uchwycie
  okna) → `nexus:context {kind:"screen", title, text:"Okno programu …", image: data:image/jpeg}`.

### „Wstaw” – wybór techniki

Tekst trafia do schowka Electron, panel się chowa, a stały proces pomocniczy PowerShell (skompilowany
raz przez `Add-Type`, bez modułów natywnych) aktywuje poprzednie okno (`AttachThreadInput` +
`SetForegroundWindow`) i wysyła `Ctrl+V` przez `System.Windows.Forms.SendKeys`. Wybrane zamiast `robotjs` /
`@nut-tree/nut-js`, bo te wymagają kompilacji natywnej albo płatnych paczek binarnych. Ograniczenia: do
okien uruchomionych jako administrator Windows nie pozwala wkleić z aplikacji bez uprawnień (UIPI) – wtedy
tekst zostaje w schowku i pojawia się powiadomienie. Tekst zostaje w schowku także po wklejeniu.

## Budowa instalatora (Windows)

```powershell
cd desktop
npm install
npm test                     # node:test – klasyfikacja PowerShell, ścieżki, narzędzia
npm run smoke                # test uruchomienia (raport JSON + zrzuty w %TEMP%\nexus-desktop-test\raport)
npx electron-builder --win nsis
# wynik: desktop\dist\Nexus-Desktop-Setup-<wersja>.exe (~110 MB)
```

### Test uruchomienia na serwerze bez ekranu (Linux)

Pulpit jest programem dla Windows, ale test uruchomienia da się przeprowadzić na serwerze
budującym — pod wirtualnym ekranem:

```bash
cd desktop
xvfb-run -a npx electron . --smoke-test --disable-gpu --smoke-out=/tmp/nexus-smoke
```

Dwie rzeczy, o które łatwo się potknąć:

* **limit czasu musi być większy niż 150 s** — tyle wynosi wewnętrzny bezpiecznik testu
  (`src/smoke.js`), po którym zapisuje raport; krótszy `timeout` ubija go, zanim cokolwiek
  powstanie;
* raport kończy się `"ok": false` **z powodów, których na Linuksie nie da się uniknąć**:
  brak `powershell.exe` i ścieżek `C:\…`. Miarą powodzenia jest sekcja `windows` — wszystkie
  pięć okien ma mieć `"state": "zaladowano"`.

Instalator jest **niepodpisany**. Przy pierwszym uruchomieniu Windows SmartScreen pokaże „System Windows
ochronił ten komputer” – trzeba kliknąć „Więcej informacji” → „Uruchom mimo to”. Ostrzeżenie zniknie po
podpisaniu certyfikatem Authenticode (najlepiej EV) – `electron-builder` podpisze automatycznie po ustawieniu
`CSC_LINK`/`CSC_KEY_PASSWORD` (albo `win.signtoolOptions`). Instalacja jest per-użytkownik (bez uprawnień
administratora), z wyborem katalogu i skrótami.

## Konfiguracja serwera

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `NEXUS_PULPIT_TIMEOUT_S` | 90 | Limit odpowiedzi komputera na narzędzie (wyszukiwanie/przesyłanie plików +60 s). |
| `NEXUS_PULPIT_CONFIRM_TIMEOUT_S` | 300 | Dodatkowy czas na zgodę użytkownika (PowerShell). |
| `NEXUS_REDIS_URL` | – | **Wymagany** w produkcji: API i serwer MCP to osobne procesy. |

Caddy przekazuje WebSocket bez dodatkowej konfiguracji (`reverse_proxy`); połączenie jest podtrzymywane
pingiem co 25 s.

## Testy

* `backend/tests/test_pulpit.py` – fałszywy komputer przez `TestClient.websocket_connect`: pełny obieg
  żądanie/odpowiedź z obrazem, błąd komputera, przesłanie pliku, anulowanie, limit czasu, odrzucenie złych
  kluczy (4401), cofnięcie klucza przy pingu, zastąpienie połączenia (4409), rejestr komputerów. Każdy test
  działa na pośredniku w pamięci i – z `NEXUS_TEST_REDIS_URL` – na prawdziwym Valkey.
* `desktop/test/*.test.js` – klasyfikacja poleceń PowerShell (tylko odczyt / zgoda, ostrzeżenia), ścieżki
  poufne i katalogi, wyszukiwanie, podgląd i przesyłanie plików, dekodowanie tekstu, brak wykonania bez zgody.
* `npm run smoke` (`electron . --smoke-test`) – tworzy okno główne, języczek, panel, ustawienia i okno zgody,
  sprawdza proces pomocniczy, `pc_info`, zrzut ekranu, wyszukiwanie, odczyt pliku, PowerShell tylko-odczyt,
  rejestrację skrótów i stan agenta; kończy się kodem 0/1.
