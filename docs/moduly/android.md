# Moduł `android` – aplikacja Nexus dla Androida

Natywna aplikacja Android (Capacitor 8 + moduły Kotlin) w katalogu `android/`. Główne okno to ta sama
aplikacja co w przeglądarce (`https://danaco-nexus.pl`), a moduły natywne dodają to, czego przeglądarka
nie potrafi: rozmowę głosową w tle, Nexusa jako asystenta systemowego, języczek przy krawędzi ekranu,
szkice odpowiedzi na SMS i lokalne powiadomienia.

## Spis treści

1. [Funkcje](#funkcje)
2. [Architektura](#architektura)
3. [Umowy z innymi strumieniami](#umowy-z-innymi-strumieniami)
4. [Uprawnienia i zgody](#uprawnienia-i-zgody)
5. [Budowa APK](#budowa-apk)
6. [Instalacja na telefonie](#instalacja-na-telefonie)
7. [Testy](#testy)
8. [Ograniczenia i znane ryzyka](#ograniczenia-i-znane-ryzyka)

## Funkcje

| Funkcja | Jak działa | Wejście |
|---|---|---|
| Okno aplikacji | WebView Capacitor ładuje `https://danaco-nexus.pl`; ekran startowy `#171717`, ciemne paski systemowe, ikona z logo Nexusa (`frontend/public/icons`). `cloud.danaco-nexus.pl` i `api.` zostają w oknie, inne adresy otwiera przeglądarka systemowa, pliki pobiera DownloadManager (folder Pobrane). | ikona aplikacji, odnośniki `https://danaco-nexus.pl/c/<id>` |
| Połączenie z Nexusem | Po zalogowaniu w oknie mostek JS tworzy klucz urządzenia `POST /api/urzadzenia {kind: "android"}` i przekazuje go do magazynu natywnego (EncryptedSharedPreferences). Moduły natywne używają `Authorization: Bearer nxd_…`. Klucz cofnięty na serwerze jest usuwany i tworzony ponownie po wejściu do aplikacji. | automatycznie |
| Rozmowa głosowa w tle | Usługa pierwszoplanowa `microphone|mediaPlayback` z powiadomieniem „Nexus słucha” (Wstrzymaj/Wznów, Zakończ). Natywna pętla jak w `VoiceMode.tsx`: VAD energetyczny (te same progi), `/api/voice/transcribe` (WAV 16 kHz), wiadomość `voice=true`, strumień `/api/runs/<id>/events`, `/api/voice/speak` zdanie po zdaniu (2 zdania naprzód), przerywanie głosem, audio focus, wstrzymanie przy rozmowie telefonicznej, auto-koniec po 10 min ciszy. | kafelek szybkich ustawień, skrót ikony, panel, ustawienia, `window.nexusAndroid.startVoice()` |
| Asystent systemowy | `VoiceInteractionService` + sesja z małym panelem (72% wysokości) zamiast pełnego okna. Tekst ekranu (`AssistStructure`, bez pól haseł) i zrzut ekranu trafiają do panelu jako `nexus:context` (`kind: "screen"`). | przytrzymanie przycisku zasilania / gest asystenta |
| Języczek przy krawędzi | Nakładka (SYSTEM_ALERT_WINDOW): dotknięcie lub przeciągnięcie w lewo otwiera panel nad dowolną aplikacją, przeciąganie w pionie przesuwa uchwyt. Przycisk ekranu w panelu: zrzut przez MediaProjection (zgoda za każdym razem, jedna klatka) i/lub tekst z usługi dostępności. | stały uchwyt przy prawej krawędzi |
| Wstaw / Kopiuj | `nexus:insert` z panelu: panel się chowa, usługa dostępności wpisuje tekst w aktywne pole aplikacji pod spodem (dopisuje do istniejącej treści). Bez usługi – schowek. `nexus:copy` – schowek. | przyciski odpowiedzi w panelu |
| SMS | Na żądanie: lista wątków (READ_SMS), szkic odpowiedzi od Nexusa (rozmowa „SMS: <numer>” w historii), edycja, „Wstaw”, „Kopiuj”, „Otwórz w Wiadomościach” (`SENDTO smsto:` z treścią). Nexus nigdy nie wysyła SMS-ów. | panel, skrót ikony, ustawienia |
| Powiadomienia | WebView nie obsługuje Web Push, więc mostek zgłasza rozpoczęte zadania (`run.started`), a po zejściu aplikacji w tło WorkManager co 30 s sprawdza `/api/runs/<id>` (najdłużej 3 h) i pokazuje lokalne powiadomienie „Gotowe” z przejściem do rozmowy. | automatycznie |
| Ustawienia | Natywny ekran z wyjaśnieniem każdej zgody przed prośbą systemową; wszystkie moduły wymagające uprawnień są domyślnie wyłączone. | skrót ikony, powiadomienie języczka, panel asystenta |

## Architektura

```
android/
├── package.json, capacitor.config.json, www/       projekt Capacitor (server.url = https://danaco-nexus.pl)
├── scripts/ikony.py                                ikony mipmap z frontend/public/icons
├── scripts/test-mostek.mjs                         testy skryptów wstrzykiwanych do WebView (Node)
└── android/app/src/main/
    ├── assets/nexus/most.js                        mostek okna głównego (klucz, zadania, window.nexusAndroid)
    ├── assets/nexus/panel.js                       mostek panelu (nexus:ready/insert/copy → aplikacja)
    └── java/pl/danaco/nexus/
        ├── MainActivity.kt                         BridgeActivity, wstecz, odnośniki /c/<id>
        ├── web/                                    NexusAndroidPlugin (mostek), NexusWebViewClient, Downloads
        ├── api/                                    NexusApi (OkHttp, Bearer), parser SSE
        ├── voice/                                  VoiceService, MicRecorder, Vad, Sentences, SpeechPlayer, kafelek
        ├── assist/                                 VoiceInteractionService, sesja, RecognitionService, tekst ekranu
        ├── panel/                                  PanelView (pasek + WebView ?widok=panel), PanelProtocol
        ├── overlay/                                EdgeTabService (języczek), MediaProjection
        ├── access/                                 usługa dostępności (odczyt, wstawianie)
        ├── sms/                                    odczyt SMS, wątki, polecenie szkicu, ekran
        ├── notify/                                 kanały powiadomień, RunWatch (WorkManager)
        ├── settings/                               ekran ustawień i zgód
        └── config/                                 adresy, ustawienia, magazyn klucza urządzenia
```

Decyzje:

- **Mostek bez pośrednika Capacitor.** Capacitor w trybie `server.url` pobiera HTML strony sam i podmienia
  nagłówki odpowiedzi (m.in. CSP), a strony z service workera w ogóle nie dostają jego skryptu.
  Dlatego żądania do Nexusa idą prosto do sieci (`NexusWebViewClient`), a mostek jest wstrzykiwany
  przez `WebViewCompat.addDocumentStartJavaScript` i odbierany przez `addWebMessageListener`
  – oba ograniczone do originu `https://danaco-nexus.pl` i ramki głównej.
- **Pętla głosowa natywna, nie w WebView.** Przeglądarka zatrzymuje mikrofon i audio przy wygaszonym
  ekranie; usługa pierwszoplanowa działa dalej. Logika (progi VAD, podział na zdania, synteza z
  wyprzedzeniem, wypełniacz „Chwileczkę…” po 4,5 s) jest przeniesiona 1:1 z `VoiceMode.tsx`
  i `sentences.ts`, a testy Kotlin powtarzają przypadki z `sentences.test.ts`.
- **Uruchamianie mikrofonu przez przezroczyste okno** (`VoiceStartActivity`): Android 14+ pozwala
  uruchomić usługę z mikrofonem tylko z widocznego okna; to samo okno prosi o zgody.

## Umowy z innymi strumieniami

### Tryb osadzony (strumień `start`)

Panel asystenta i języczka ładuje `https://danaco-nexus.pl/?widok=panel` i realizuje umowę:

| Kierunek | Wiadomość | Zachowanie aplikacji |
|---|---|---|
| aplikacja → panel | `{type: "nexus:auth", token: "nxd_…"}` | wysyłana po `nexus:ready` (ciasteczko sesji i tak jest wspólne z oknem głównym) |
| aplikacja → panel | `{type: "nexus:context", context: {kind: "screen", title, url, text, image?}}` | tytuł = nazwa aplikacji na ekranie, `image` = JPEG `data:` (dłuższy bok ≤ 1280 px), `text` ≤ 20 000 znaków |
| aplikacja → panel | `{type: "nexus:prompt", text, send}` | dostępne w `PanelView.sendPrompt` |
| panel → aplikacja | `nexus:ready`, `nexus:insert {text}`, `nexus:copy {text}` | kolejka wiadomości do panelu jest wysyłana dopiero po `nexus:ready` |

**Ważne dla implementacji panelu:** w WebView panel jest oknem najwyższego poziomu, więc
`window.parent === window`. Aplikacja wysyła wiadomości przez `window.postMessage(msg, location.origin)`
(`event.source === window`), a odbiera wiadomości, które panel wysyła do `window.parent`
(`event.source === window`, `event.origin === location.origin`). Panel nie powinien więc wymagać
`window.parent !== window` ani odrzucać wiadomości od samego siebie dla tych typów.

### Okno główne (strumień `start`, opcjonalnie)

Na Androidzie strona ma obiekt `window.nexusAndroid` (tylko w aplikacji):

| Metoda | Działanie |
|---|---|
| `startVoice(conversationId?)` | rozmowa głosowa w tle w podanej rozmowie (albo nowej) |
| `openSettings()` | ustawienia modułów Androida |
| `openSms()` | szkice odpowiedzi SMS |

Aplikacja dopisuje do User-Agent `NexusAndroid/1` (panel: `NexusAndroid/1 NexusPanel/1`) – interfejs
może po tym ukryć np. instalację PWA i pokazać przycisk rozmowy w tle.

### Klucze urządzeń (szkielet)

Nazwa klucza: `Android – <producent> <model>`, `kind: "android"`. Klucz tworzy wyłącznie zalogowana
przeglądarka w oknie aplikacji (wymóg `_require_browser_login`).

## Uprawnienia i zgody

| Uprawnienie | Po co | Kiedy prośba |
|---|---|---|
| `RECORD_AUDIO`, `FOREGROUND_SERVICE_MICROPHONE`, `FOREGROUND_SERVICE_MEDIA_PLAYBACK`, `WAKE_LOCK` | rozmowa głosowa w tle | przy pierwszym uruchomieniu rozmowy |
| `POST_NOTIFICATIONS` | powiadomienie rozmowy i zakończonych zadań | razem z mikrofonem albo w ustawieniach |
| `SYSTEM_ALERT_WINDOW`, `FOREGROUND_SERVICE_SPECIAL_USE`, `RECEIVE_BOOT_COMPLETED` | języczek (przywracany po restarcie telefonu) | po włączeniu języczka – ekran systemowy |
| `FOREGROUND_SERVICE_MEDIA_PROJECTION` + zgoda MediaProjection | zrzut ekranu z języczka | przy każdym zrzucie (dialog systemowy) |
| usługa dostępności | odczyt tekstu aplikacji pod panelem, „Wstaw” | ręcznie w Ustawienia → Dostępność |
| `READ_SMS` | szkice odpowiedzi na SMS | po włączeniu modułu SMS |
| rola asystenta | przytrzymanie przycisku zasilania | ręcznie w Ustawienia → Aplikacje domyślne → Asystent cyfrowy |

Zasady: nic nie jest wysyłane w imieniu użytkownika (SMS tylko jako szkic, „Wstaw” wpisuje tekst,
nie naciska „Wyślij”); zawartość ekranu trafia do Nexusa wyłącznie po działaniu użytkownika; treść
SMS-ów i ekranu jest w poleceniu oznaczona jako dane, a nie polecenia; kopie zapasowe aplikacji są
wyłączone (klucz urządzenia nie opuszcza telefonu).

## Budowa APK

Odtwarzalna budowa na serwerze (instaluje JDK 21 i Android SDK w katalogu projektu przy pierwszym
uruchomieniu, potem: `npm ci`, `cap sync`, testy, lint, `assembleRelease`, weryfikacja podpisu):

```bash
cd /danaco/projekty/danaco-nexus
deploy/android/buduj-apk.sh            # wynik: .tmp/android/out/nexus-android.apk
deploy/android/buduj-apk.sh --bez-testow
```

| Element | Położenie |
|---|---|
| JDK 21 (Temurin) | `programy/jdk-21` |
| Android SDK (platforma 36, build-tools 36.0.0) | `programy/android-sdk` |
| Gradle, npm, dane narzędzi Android | `.cache/gradle`, `.cache/npm`, `.cache/android-user` |
| Klucz podpisu wydania | `.tmp/android/keystore/nexus-release.jks` + `keystore.properties` (prawa 600) |
| APK i raport lint | `.tmp/android/out/nexus-android.apk`, `.tmp/android/out/lint-results.html` |

Klucz podpisu powstaje raz (RSA 4096, PKCS12, alias `nexus`, hasło losowe zapisane tylko w
`keystore.properties`). **Należy zrobić jego kopię** (np. do sejfu haseł i chmury prywatnej) i przy
wdrożeniu przenieść go z `.tmp/` do `dane/app/android-keystore/` (zmienna `KLUCZE`), bo katalog `.tmp`
jest tymczasowy. Utrata klucza oznacza, że nowej wersji nie da się zainstalować jako aktualizacji.

Wersje: Capacitor 8.5.2, AGP 8.13.0, Gradle 8.14.3, Kotlin 2.2.21, compileSdk/targetSdk 36, minSdk 29.

## Instalacja na telefonie

1. Pobierz `nexus-android.apk` na telefon i zezwól przeglądarce/menedżerowi plików na instalację aplikacji.
2. Otwórz Nexusa i zaloguj się – aplikacja połączy się sama (komunikat „Aplikacja połączona z Nexusem”).
3. Asystent: Ustawienia → Aplikacje → Aplikacje domyślne → Asystent cyfrowy → Nexus; włącz „Użyj tekstu
   z ekranu” i „Użyj zrzutu ekranu”, jeśli panel ma widzieć ekran.
4. Pozostałe moduły włącz w ustawieniach Nexusa (przytrzymaj ikonę → Ustawienia).
5. Kafelek „Nexus – rozmowa” dodaj w edycji szybkich ustawień.

## Testy

| Zakres | Narzędzie | Liczba |
|---|---|---|
| VAD, zdania (przypadki z `sentences.test.ts`), odpowiedź strumieniowana, WAV | JUnit | 18 |
| Klient API (Bearer bez CSRF, multipart, błędy FastAPI, SSE z wznowieniem `after`) | JUnit + MockWebServer | 11 |
| Parser SSE, mostek, umowa panelu, tekst ekranu, SMS | JUnit | 8 |
| Okno główne (Capacitor + wtyczka + klient WebView), ustawienia, SMS, start rozmowy bez klucza, języczek, panel, WorkManager | Robolectric | 9 |
| Skrypty `most.js` i `panel.js` (klucz, `run.started`, ponowne zgłoszenie po logowaniu, filtr źródeł) | Node | 1 plik |

Uruchamiane przez `deploy/android/buduj-apk.sh` (Gradle `testReleaseUnitTest lintRelease`).

## Ograniczenia i znane ryzyka

- Emulatora nie da się uruchomić na serwerze (brak dostępu do `/dev/kvm`), więc zachowanie na urządzeniu
  – mikrofon, echo przy przerywaniu, usługa przy wygaszonym ekranie, sesja asystenta, nakładka,
  MediaProjection, wstawianie przez dostępność, odczyt SMS – wymaga sprawdzenia na telefonie.
- Tryb `?widok=panel` realizuje strumień `start`; do czasu scalenia panel pokazuje zwykłą aplikację,
  a wiadomości `nexus:*` czekają na `nexus:ready`.
- Producenci (Xiaomi, Huawei, Samsung) mogą dodatkowo usypiać usługi w tle – wtedy trzeba wyłączyć
  optymalizację baterii dla Nexusa.
- Wybór pliku (`<input type=file>`) działa w oknie głównym; w panelu nakładki i asystenta nie (brak
  aktywności do obsługi wyboru).
- `androidx.security:security-crypto` 1.1.0 jest oznaczona jako przestarzała – działa, ale przy
  kolejnej aktualizacji warto przejść na własne szyfrowanie kluczem z Android Keystore.
