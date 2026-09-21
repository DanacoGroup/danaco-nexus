# Moduł Demo: piaskownica „Wypróbuj teraz”

Gość bez konta uruchamia w przeglądarce gotowe sprawy Danaco Nexusa: widzi kolejne kroki
agenta, ich czasy i pobiera plik wynikowy. Pokaz działa na tym samym rejestrze narzędzi,
z którego korzysta produkt — nie ma w nim atrap funkcji, a nagrany przebieg jest zawsze
oznaczony jako pokaz.

## Spis treści

1. [Architektura](#architektura)
2. [Limity](#limity)
3. [Tryb pracy: na żywo albo odtworzenie](#tryb-pracy-na-żywo-albo-odtworzenie)
4. [Scenariusze](#scenariusze)
5. [Wykaz tras](#wykaz-tras)
6. [Pliki przykładowe i nagrania](#pliki-przykładowe-i-nagrania)
7. [Frontend i podpięcie trasy](#frontend-i-podpięcie-trasy)
8. [Zagrożenia i zabezpieczenia](#zagrożenia-i-zabezpieczenia)
9. [Testy i kontrole](#testy-i-kontrole)
10. [Ograniczenia](#ograniczenia)

## Architektura

| Plik | Rola |
|---|---|
| `backend/nexus/demo/sesje.py` | sesje gościa w pamięci procesu API, limity, katalog roboczy, walidacja plików, tempo zapytań |
| `backend/nexus/demo/scenariusze.py` | definicje pięciu scenariuszy: kroki, narzędzia, parametry, wymagania środowiska |
| `backend/nexus/demo/gotowosc.py` | sprawdzenie modelu, programów zewnętrznych i bazy wiedzy; rozstrzyga tryb pracy |
| `backend/nexus/demo/przebieg.py` | wykonanie kroków (narzędzie albo model) oraz odtworzenie nagrania, rozgłaszanie stanu |
| ~~`backend/nexus/demo/model.py`~~ | **nie istnieje**. Pokaz nie woła modelu wcale: `przebieg.py` wykonuje kroki narzędziami albo odtwarza nagranie, a `gotowosc.py` sprawdza tylko, czy `claude` i token są na miejscu |
| `backend/nexus/demo/przyklady/` | pliki wejściowe, generator `generuj.py`, nagrania przebiegów |
| `backend/nexus/api/modules/demo.py` | router `/api/demo` (bez `require_session`) |
| `frontend/src/demo/` | **tylko** `WejscieGoscia.tsx` — ekranu pokazu nie ma, patrz „Frontend i podpięcie trasy” |

Sesja gościa żyje **wyłącznie w pamięci procesu API** — nie ma jej w bazie danych, nie
zakłada rozmowy ani wpisu w magazynie plików użytkownika. Pliki gościa i wyniki leżą
w `<NEXUS_DATA_DIR>/work/demo/<sesja>/pliki`; katalog znika razem z sesją. Narzędzie
pracuje w zwykłym katalogu roboczym przebiegu (`tempfile.mkdtemp` w `work_dir`), który
jest kasowany zaraz po kroku — tak samo jak przy zadaniach zalogowanego użytkownika.

Sprzątanie jest leniwe: każde założenie sesji i każde jej pobranie usuwa sesje, którym
upłynął czas życia, razem z katalogami. Zakończenie pokazu przez gościa (`DELETE /api/demo/sesja`)
kasuje katalog od razu i usuwa fragmenty dokumentów z pokazowej kolekcji bazy wiedzy.

## Limity

Wartości z `Limity` w `backend/nexus/demo/sesje.py` (stałe w kodzie, wspólne dla wszystkich gości):

| Limit | Wartość | Skutek przekroczenia |
|---|---|---|
| Wiadomości na sesję (przebieg albo pytanie) | 6 | `429` i wezwanie do założenia konta |
| Rozmiar jednego pliku | 8 MB | `413` |
| Liczba plików gościa | 4 | `429` |
| Długość własnej wiadomości | 500 znaków | odrzucenie przez walidację (`422`), pole też ogranicza wpis |
| Czas życia sesji | 30 minut | `401` i skasowanie danych |
| Sesje z jednego adresu | 3 | `429` |
| Zapytania z jednego adresu | 30 na minutę | `429` |
| Równoległe przebiegi w sesji | 1 | `429` |
| Czas jednego przebiegu | 420 s | przebieg kończy się błędem, narzędzie dostaje sygnał anulowania |

## Tryb pracy: na żywo albo odtworzenie

Scenariusz deklaruje wymagania: programy zewnętrzne (`tesseract`, `realesrgan`, `whisper`),
model (token OAuth konta Claude i program CLI) oraz bazę wiedzy (Qdrant). `Gotowosc`
sprawdza je przy każdym odczycie stanu; wynik Qdranta jest zapamiętywany na minutę.

- **wszystko dostępne → `na-zywo`**: kroki wywołują prawdziwe narzędzia agenta, czasy są
  mierzone zegarem, pliki wynikowe powstają teraz;
- **czegoś brakuje → `odtworzenie`**: serwer odtwarza nagrany przebieg z
  `przyklady/nagrania/<id>.json` — kroki z zapisanymi czasami i gotowe pliki wynikowe.

Odtworzenie nigdy nie udaje pracy na żywo: tryb jest polem odpowiedzi API, a interfejs
pokazuje przy krokach i przy karcie scenariusza znacznik **„Pokaz odtwarzany”** z powodem
(`opisBrakow`). Czas kroku pochodzi z nagrania, natomiast pauza w interfejsie to ułamek
tego czasu (0,12 ×, najwyżej 1,4 s) — pokaz nie czeka 48 sekund na powiększenie AI.

## Scenariusze

| Id | Tytuł | Kroki (narzędzia) | Wymaga |
|---|---|---|---|
| `faktura` | Faktura ze skanu | `enhance_document_scan` → `ocr_documents` → krok modelu (kwota i termin) | tesseract, model |
| `zdjecie` | Stare zdjęcie od nowa | `enhance_photo` → `upscale_image` | realesrgan |
| `skany` | Przeszukiwalny PDF ze skanów | `convert_images` (jeden PDF) → `ocr_documents` | tesseract |
| `notatka` | Notatka z nagrania | `transcribe_audio` → krok modelu (ustalenia) → `write_document` | whisper, model |
| `wyszukiwanie` | Szukanie po znaczeniu | `index_documents` → `search_documents` | Qdrant |

Wszystkie użyte narzędzia są w rejestrze `backend/nexus/tools/` i mieszczą się w wykazie
funkcji dostępnych dziś (LANDING_PAGE_SPEC rozdz. 8). Gość przekazuje wyłącznie
identyfikator scenariusza i opcjonalnie własne pliki — nazwy narzędzi i ich parametry
buduje serwer, więc z piaskownicy nie da się wywołać dowolnego narzędzia.

## Wykaz tras

Prefiks `/api/demo`, bez logowania. Metody zmieniające stan wymagają nagłówka `X-Nexus-Request: 1`.

| Metoda i ścieżka | Działanie |
|---|---|
| `GET /stan` | zakłada sesję (ciasteczko `nexus_demo`), zwraca limity, gotowość serwera i scenariusze z trybem |
| `POST /pliki` | przyjmuje własny plik gościa (`multipart/form-data`, pole `plik`) |
| `POST /scenariusze/{id}/uruchom` | startuje przebieg; zużywa jedną wiadomość; zwraca stan przebiegu i sesji |
| `GET /przebiegi/{id}` | stan przebiegu (dla klientów bez strumienia) |
| `GET /przebiegi/{id}/zdarzenia` | strumień SSE: zdarzenie `stan` z pełnym stanem przebiegu, zakończone stanem końcowym |
| `POST /przebiegi/{id}/przerwij` | przerywa trwający przebieg |
| `POST /pytanie` | własne pytanie gościa; jedno wywołanie modelu bez narzędzi; `503`, gdy serwer nie ma modelu |
| `GET /pliki/{id}` | pobranie pliku z sesji pokazu |
| `GET /przyklady/{scenariusz}/{nazwa}` | podgląd pliku przykładowego (tylko nazwy z listy scenariusza) |
| `DELETE /sesja` | kończy pokaz, kasuje katalog i indeks gościa |

Ciasteczko `nexus_demo`: `HttpOnly`, `SameSite=Lax`, `Secure` zgodnie z `NEXUS_COOKIE_SECURE`,
ścieżka `/api/demo` (nie trafia do reszty aplikacji), czas życia równy czasowi życia sesji.

## Pliki przykładowe i nagrania

Pliki powstają skryptem `backend/nexus/demo/przyklady/generuj.py`:

```bash
cd backend && PYTHONPATH=$PWD ../.venv/bin/python -m nexus.demo.przyklady.generuj
```

Skrypt tworzy skan faktury (zdjęcie kartki z przekrzywieniem, cieniem i szumem), dwie
strony umowy, wyblakłe zdjęcie, trzy dokumenty tekstowe oraz nagranie narady syntezowane
głosami Piper (16 kHz; bez głosów na dysku plik jest pomijany i scenariusz działa wyłącznie
z nagrania). Do tego zapisuje nagrania przebiegów (`nagrania/*.json`) i ich pliki wynikowe
(`nagrania/pliki/**`). Razem około 4,6 MB.

Przy instalacji nieedytowalnej pakietu trzeba dołączyć dane — do `backend/pyproject.toml`,
sekcja `[tool.setuptools.package-data]`, dopisać:

```toml
"nexus.demo" = ["przyklady/*", "przyklady/nagrania/*.json", "przyklady/nagrania/pliki/**/*"]
```

## Frontend i podpięcie trasy

Poniższa tabela opisuje ekran, **którego nie zbudowano**. Zostawiamy ją jako zapis
pierwotnego zamysłu; żaden z tych plików nie istnieje w repozytorium.

| Plik (nieistniejący) | Zamierzona rola |
|---|---|
| ~~`frontend/src/demo/api.ts`~~ | klient `/api/demo`, strumień SSE (`fetchEventStream`), formaty czasu i rozmiaru |
| ~~`frontend/src/demo/elementy.tsx`~~ | karta scenariusza, znacznik trybu, lista kroków, wynik, wezwanie do konta |
| ~~`frontend/src/demo/Piaskownica.tsx`~~ | ekran „Wypróbuj teraz” |

**Stan na 21.09.2026: tego ekranu nie ma.** Produkt poszedł inną drogą — `/wyprobuj`
nie otwiera pokazu obok aplikacji, tylko zakłada **konto próbne** i wpuszcza do pełnego
okna (`frontend/src/demo/WejscieGoscia.tsx`, gałąź `screen === "demo"` w `App.tsx`).
Pliki `Piaskownica.tsx`, `demo/api.ts` i `demo/elementy.tsx` nie istnieją; w katalogu
`frontend/src/demo/` został sam `WejscieGoscia.tsx`.

Zaplecze pokazu żyje dalej: `/api/demo/*` odpowiada, `scenariusze.py` ma pięć scenariuszy,
a `/api/demo/stan` melduje gotowość modelu i programów. Nic z interfejsu do tego nie sięga,
więc to albo materiał na osobny ekran, albo kod do usunięcia — decyzja należy do właściciela.
Rozdziały niżej (dostępność, zagrożenia, limity) opisują zaplecze i są nadal aktualne.

Interfejs używa wyłącznie ról semantycznych z `frontend/src/styles.css` (`bg-app`, `bg-raised`,
`bg-side`, `text-fg`, `text-muted`, `text-subtle`, `border-line`, `border-line-strong`,
`bg-accent-fill`, `text-on-accent`, `text-accent`, `bg-accent-soft`, `font-heading`,
`.aurora-obrys`, `.spinner`) — bez wartości szesnastkowych.

Dostępność: scenariusze to przyciski z `aria-pressed`, lista kroków jest listą
uporządkowaną ze stanem każdego kroku czytanym przez czytnik ekranu (`sr-only`) oraz
obszarem `role="status" aria-live="polite"` zapowiadającym bieżący krok; pole wiadomości ma
etykietę i licznik znaków powiązany przez `aria-describedby`; błędy trafiają do `role="alert"`;
pliki wynikowe to odsyłacze z opisem „Pobierz plik …”. Wszystko działa z klawiatury —
nie ma elementów klikalnych bez roli.

## Zagrożenia i zabezpieczenia

| Zagrożenie | Zabezpieczenie |
|---|---|
| Uruchomienie dowolnego narzędzia przez gościa | gość podaje wyłącznie identyfikator scenariusza; nazwy narzędzi i parametry buduje serwer (`scenariusze.py`), wejście przechodzi przez `Tool.parse` |
| Dostęp do powłoki | żaden scenariusz nie udostępnia narzędzi `pc_*` ani poleceń powłoki; krok modelu biegnie z `--tools ""`, `--strict-mcp-config` i `--no-session-persistence`, więc model nie ma żadnego narzędzia |
| Dostęp do sieci z poziomu pokazu | scenariusze nie zawierają `web_search`, `web_fetch_page` ani narzędzi chmury; model nie ma narzędzi sieciowych |
| Wyjście poza katalog roboczy | nazwa pliku od gościa nigdy nie trafia do ścieżki — plik zapisujemy jako `<uuid><rozszerzenie>` w katalogu sesji; pliki nagrań kopiujemy po sprawdzeniu `is_relative_to`; podgląd przykładu tylko dla nazw z listy scenariusza |
| Podejrzenie cudzych plików | `ToolContext.resolve_file` widzi wyłącznie pliki tej sesji; nieznany identyfikator kończy się błędem narzędzia, a trasa pobierania zwraca `404` |
| Złośliwy plik (podszywanie się pod obraz) | lista dozwolonych rozszerzeń, sprawdzenie sygnatury treści, dla plików tekstowych wymóg UTF-8, limit rozmiaru czytany przy odczycie strumienia |
| Wstrzyknięcie polecenia treścią pliku | tekst z OCR i transkrypcji jest opisywany modelowi jako dane (`STRAZ_POLECENIA`), a instrukcja systemowa zabrania wykonywania poleceń z treści; model i tak nie ma narzędzi |
| Zajęcie zasobów serwera | limit wiadomości, jeden przebieg naraz, limit czasu przebiegu, limit sesji z adresu, tempo 30 zapytań na minutę |
| Trwały ślad danych gościa | brak zapisu w bazie i w magazynie plików; katalog sesji kasowany po wygaśnięciu albo na żądanie; fragmenty z bazy wiedzy usuwane przy zakończeniu sesji |
| Zmieszanie danych gościa z bazą wiedzy użytkownika | pokaz używa osobnej kolekcji Qdranta `<kolekcja>_demo` (`ustawienia_demo`) |
| Żądanie z obcej witryny (CSRF) | każda metoda zmieniająca stan wymaga nagłówka `X-Nexus-Request: 1`, niedostępnego dla formularzy innych witryn; ciasteczko ma `SameSite=Lax` i wąską ścieżkę |
| Przejęcie ciasteczka skryptem | ciasteczko `HttpOnly`, `Secure` w produkcji; polityka CSP aplikacji obowiązuje także tę trasę |
| Udawanie prawdziwego przebiegu | tryb jest polem odpowiedzi API, interfejs oznacza odtworzenie znacznikiem i powodem; nagranie nie może podmienić trybu |

## Testy i kontrole

`backend/tests/test_demo.py` (22 testy) obejmuje: założenie sesji bez logowania, zgodność
scenariuszy z rejestrem narzędzi, wymóg nagłówka aplikacji, odtworzenie nagrania z pobraniem
pliku, wyczerpanie limitu wiadomości, odrzucenie pytania bez modelu, walidację plików
(rozszerzenie, sygnatura, rozmiar, UTF-8), izolację plików między sesjami, kasowanie danych
po wygaśnięciu, limit sesji z adresu, tempo zapytań, podgląd przykładów tylko z listy,
przebieg na żywo z krokiem narzędzia i krokiem modelu (podmieniony uruchamiacz CLI) oraz
zgłaszanie błędu narzędzia.

`frontend/src/demo/demo.test.tsx` (9 testów) obejmuje formaty czasu i rozmiaru, opis braków,
licznik wiadomości, oznaczenie odtworzenia, listę kroków z czasami, wynik z odsyłaczem do
pobrania, wezwanie do konta oraz ekran przy braku modelu i przy wygasłym pokazie.

Wyniki kontroli po wdrożeniu modułu (repozytorium zawierało wtedy także równolegle
rozwijane moduły `portal` i `platnosci`):

| Kontrola | Wynik |
|---|---|
| `.venv/bin/python -m pytest backend/tests -q` | 372 passed, 14 skipped |
| `.venv/bin/ruff check backend/nexus/demo backend/nexus/api/modules/demo.py backend/tests/test_demo.py` | All checks passed |
| `cd frontend && npx tsc --noEmit` | bez błędów |
| `cd frontend && npx vitest run` | 16 plików, 153 testy, wszystkie zielone |

## Ograniczenia

- Sesje i przebiegi żyją w pamięci jednego procesu API — przy kilku procesach gość musi
  trafiać do tego samego (trzymanie sesji po adresie w odwrotnym proxy) albo pokaz zacznie
  się od nowa. Restart API kończy trwające pokazy.
- Limity tempa i liczby sesji liczą się per proces; za proxy liczy się adres z `X-Forwarded-For`.
- Scenariusz `wyszukiwanie` wymaga działającego Qdranta; pierwsze indeksowanie pobiera model
  osadzeń (fastembed) do wspólnej pamięci podręcznej.
- Krok modelu to jedno wywołanie `claude -p` — pokaz nie prowadzi rozmowy i nie pamięta
  poprzednich wiadomości gościa.
- Własne pytanie działa tylko przy podłączonym modelu; bez niego pole jest wyłączone
  z wyjaśnieniem, a nie zastępowane nagraną odpowiedzią.
- Gość wgrywa własne pliki, ale scenariusz zawsze wykonuje ten sam ciąg kroków — piaskownica
  nie prowadzi swobodnej pracy agenta.
- Ekran nie jest podpięty do tras aplikacji (patrz [Frontend i podpięcie trasy](#frontend-i-podpięcie-trasy)).
