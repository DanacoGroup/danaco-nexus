# Moduł „start”: strona startowa, powłoka aplikacji, panel osadzony, powiadomienia

Gałąź `modul/start`. Obejmuje publiczną stronę startową, powłokę aplikacji z nawigacją
modułów, tryb osadzony `?widok=panel`, panel „Zadania w toku”, powiadomienia Web Push,
moduł „Urządzenia” i publiczne pobieranie instalatorów.

## Trasy interfejsu

| Adres | Niezalogowany | Zalogowany |
|---|---|---|
| `/` | strona startowa (sprzedażowa) | czat (nowa rozmowa) |
| `/start` | strona startowa | strona startowa |
| `/zaloguj?next=/ścieżka` | logowanie | powrót pod `next` (tylko ścieżki tej witryny) albo `/` |
| `/?next=cloud` | logowanie | powrót do chmury (jak dotąd) |
| `/c/<uuid>` | logowanie, potem rozmowa | rozmowa |
| `/m/<id>` | logowanie, potem moduł | moduł z `frontend/src/modules/<id>` albo moduł, który ma `<id>` w polu `aliasy` |
| `/?widok=panel` | panel osadzony (sam obsługuje logowanie) | panel osadzony |

Cztery moduły mają w pasku nawigacji inną nazwę niż identyfikator w adresie, więc przyjmują
też adres spod tej nazwy (pole `aliasy` w `NexusModule`): `cloud` ← `chmura`,
`research` ← `badania`, `urzadzenia` ← `sprzet`, `mozliwosci` ← `narzedzia`. Powłoka
sprowadza alias do identyfikatora, więc podświetlenie paska i przejście widoku działają
tak samo jak pod adresem właściwym.

Dwie pozycje paska nie są modułami rejestru, a mimo to mają adres pod `/m/`: `/m/glos`
otwiera nakładkę rozmowy głosowej (`shell/Workspace.tsx`), a `/m/czat` (oraz `/m/chat`
i `/m/rozmowa`) prowadzi do rozmowy — rozpoznaje je `parseRoute`, zanim adres trafi do
rejestru modułów.

Zainstalowana aplikacja (PWA) bez sesji otwiera się od razu na logowaniu, nie na stronie startowej.

## Powłoka aplikacji

- Komputer: pionowy pasek modułów po lewej (`shell/ModuleNav.tsx`): **Czat**, **Głos**
  (otwiera istniejący tryb rozmowy głosowej), potem moduły z `MODULES` (rejestr
  `modules/registry.ts`, kolejność `order`), na dole przycisk „Zadania”.
- Telefon: dolny pasek (najwyżej 5 miejsc; nadmiar w arkuszu „Więcej”); chowa się,
  gdy pole tekstowe ma fokus (klawiatura ekranowa).
- Moduły innych strumieni pojawiają się same – wystarczy `modules/<id>/index.tsx`.
- Stan czatu jest wydzielony do `shell/useChat.ts` (wspólny dla aplikacji i panelu).

## Tryb osadzony (`?widok=panel`)

Kompaktowy czat do ramki (`iframe`) rozszerzenia lub Nexus Desktop albo do WebView.
Implementacja: `shell/PanelApp.tsx`, protokół: `shell/embed.ts`.

Rodzic → panel (`postMessage`):

| Komunikat | Działanie |
|---|---|
| `{type:"nexus:auth", token:"nxd_…"}` | tryb klucza urządzenia: `Authorization: Bearer` zamiast ciasteczka, strumień zdarzeń czytany fetch-em |
| `{type:"nexus:context", context:{kind:"page"\|"screen", title, url, text, image?}}` | kontekst do następnej wiadomości; `context:null` usuwa kontekst; `image` (data URL PNG/JPEG/WebP/GIF) trafia jako załącznik |
| `{type:"nexus:prompt", text, send?}` | wstawia tekst do pola; z `send:true` od razu wysyła (z kontekstem) |

Panel → rodzic: `{type:"nexus:ready"}` po starcie, `{type:"nexus:insert", text}` (przycisk
„Wstaw”), `{type:"nexus:copy", text}` (przycisk „Kopiuj”; panel próbuje też sam skopiować).
Tekst do wstawienia/kopiowania to odpowiedź bez formatowania Markdown.

- Kontekst dołączany jest raz, do najbliższej wysłanej wiadomości, jako blok
  `[Kontekst: <kind> „<title>” <url>]\n<text>` przed pytaniem użytkownika
  (tekst strony obcinany do 60 000 znaków). W historii rozmowy widać tylko nagłówek bloku i pytanie.
- Panel przyjmuje komunikaty wyłącznie od `window.parent` (albo z `source === null`, gdy jest
  oknem głównym WebView). Bez klucza przez 1,2 s próbuje sesji z ciasteczka; bez obu pokazuje
  instrukcję połączenia urządzenia.
- Nagłówki: `GET /?widok=panel` (`backend/nexus/api/modules/osadzanie.py`) zwraca CSP z
  `frame-ancestors` z ustawienia `NEXUS_PANEL_FRAME_ANCESTORS` (domyślnie
  `* chrome-extension: moz-extension: safari-web-extension: file:`); pozostałe adresy mają
  nadal `frame-ancestors 'none'` i `X-Frame-Options: DENY`. Service worker nie obsługuje
  nawigacji `?widok=panel` ani `/pobierz/…` (zawsze z sieci).
- W ramce na obcej stronie przeglądarka nie wysyła ciasteczka sesji (`SameSite=Lax`) –
  panel działa tam tylko z kluczem urządzenia.
- `api.ts` eksportuje `apiFetch`/`apiRequest`/`authHeaders` – moduły powinny ich używać,
  żeby działały także w trybie klucza.

## Zadania w toku (wiele sesji)

- `GET /api/w-toku` – wszystkie zadania `queued`/`running` z tytułem rozmowy, trybem
  (`Conversation.meta.mode`) i ostatnio użytym narzędziem.
- Interfejs odpytuje listę co 3 s (gdy coś trwa) lub 15 s; panel pozwala przejść do rozmowy
  i anulować zadanie. Zadanie zakończone w innej rozmowie daje powiadomienie w aplikacji.
- Przy pozycji czekającej w kolejce stoi czas czekania („W kolejce · 12 min”), a sama tura
  rozmowy po czterdziestu pięciu sekundach mówi wprost, że zadanie czeka dłużej niż zwykle.
  Bez tego zadanie, którego nikt nie podjął, wyglądało dokładnie jak liczone.

## Powiadomienia Web Push

- Klucz VAPID (P-256, PEM) powstaje przy pierwszym starcie API w `dane/app/vapid`
  (prawa 600; ścieżka: `NEXUS_PUSH_VAPID_FILE`). Wyłączenie: `NEXUS_PUSH_ENABLED=false`.
  Kontakt w VAPID: `NEXUS_PUSH_CONTACT` (domyślnie `NEXUS_PUBLIC_URL`).
- API: `GET /api/push/klucz`, `POST /api/push/subskrypcje` (`PushSubscription.toJSON()` + `name`),
  `POST /api/push/wypisz` (`{endpoint}`), `POST /api/push/test`. Tabela `push_subscriptions`.
- API nasłuchuje kanału Redis `nexus:run-finished` (JSON `{run_id, conversation_id, status, title}`,
  publikuje strumień „agenci”) i wysyła powiadomienie o statusie `done`/`failed`
  (`cancelled` – bez powiadomienia). Subskrypcje z odpowiedzią 404/410 są usuwane, po 5
  kolejnych błędach również.
- Service worker (`public/share-target.js`): `push` pokazuje powiadomienie (pomija je, gdy
  ta rozmowa jest właśnie otwarta i widoczna), `notificationclick` przełącza otwarte okno na
  rozmowę albo otwiera nowe.
- Włączanie na urządzeniu: moduł „Urządzenia” → „Powiadomienia na tym urządzeniu”.
  Na iPhonie tylko w aplikacji dodanej do ekranu początkowego.

## Urządzenia

Moduł `modules/urzadzenia`: tworzenie klucza (`POST /api/urzadzenia`), jednorazowe pokazanie
klucza z kodem QR, lista i cofanie kluczy, powiadomienia push, instalatory do pobrania.
Kod QR zawiera adres parowania:

```
danaconexus://sparuj?serwer=<adres serwera, URL-encoded>&klucz=<nxd_…>
```

**Stan na 21.09.2026**: tego schematu nie obsługuje dziś żaden klient. Aplikacja Android
zakłada klucz sama przy pierwszym zalogowaniu w oknie Nexusa (`AndroidManifest.xml` nie ma
filtra dla `danaconexus://`, a w kodzie nie ma czytnika kodów), Nexus Desktop i rozszerzenie
przyjmują **wklejony** adres serwera i klucz. Kod QR zostaje jako wygodny nośnik dla
urządzeń własnych („inne”: `Authorization: Bearer <klucz>`) i na przyszłość — podpowiedź
w module mówi teraz to, co robi telefon naprawdę.

## Pobieranie instalatorów

`GET /pobierz` – lista (`name`, `label`, `available`, `size`, `updated_at`, `sha256`);
`GET|HEAD /pobierz/<plik>` – plik jako załącznik. Publiczne (bez logowania). Serwowane są
wyłącznie nazwy z białej listy z katalogu `dane/app/pobieranie/`:

| Plik | Źródło |
|---|---|
| `nexus-android.apk` | strumień „android” |
| `nexus-desktop-setup.exe` | strumień „pulpit” |
| `nexus-rozszerzenie.zip` | strumień „rozszerzenie” |

Brakujący plik strona startowa pokazuje jako „Wkrótce do pobrania”.

## Testy

- `backend/tests/test_start.py` – pobieranie (biała lista, publiczność), klucz VAPID,
  subskrypcje i wysyłka (atrapa usługi push), zadania w toku, nagłówki panelu.
- `frontend/src/__tests__/{route,sse,embed,shell,panel}.test.*` – trasy, parser SSE i
  strumień fetch, protokół postMessage, tryb klucza w `api.ts`, pełny przebieg panelu.
