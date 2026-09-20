# Danaco Nexus — Specyfikacje dziedzinowe orkiestracji par

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | etap 1B |
| **Status** | Deweloperski |
| **Data** | 2026-09-20 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Specyfikacje dziesięciu dziedzin i zasady pracy w parach specjalista — weryfikator |
| **Klasa dokumentu** | Specyfikacja wykonawcza |
| **Odbiorcy** | specjaliści dziedzinowi · weryfikatorzy · właściciel produktu |
| **Przeznaczenie** | Wyznacza zakres, własność plików, zadania i kryteria odbioru każdej dziedziny, tak aby dziesięć par mogło pracować równolegle bez kolizji. |
| **Zasada nadrzędna** | Specjalista pracuje wyłącznie w swoich plikach. Weryfikator nie poprawia — zwraca usterki. Najwyżej trzy tury na parę. |

## Spis treści

1. [Zasady pracy w parze](#1-zasady-pracy-w-parze)
2. [Własność plików](#2-własność-plików)
3. [Fala 1 — treść, sprzedaż, konta, zgodność](#3-fala-1--treść-sprzedaż-konta-zgodność)
4. [Fala 2 — ruch, widoczność, nawigacja](#4-fala-2--ruch-widoczność-nawigacja)
5. [Fala 3 — dostępność, wydajność, bezpieczeństwo](#5-fala-3--dostępność-wydajność-bezpieczeństwo)
6. [Kontrole wspólne](#6-kontrole-wspólne)

---

## 1. Zasady pracy w parze

| Reguła | Treść |
|---|---|
| Podział ról | Specjalista projektuje i wdraża. Weryfikator wyłącznie sprawdza i opisuje usterki — nie poprawia kodu. |
| Zawracanie | Usterki wracają do specjalisty w zakresie **samych usterek**, nie całego zadania. |
| Liczba tur | Najwyżej trzy. Po trzeciej turze nierozwiązane usterki trafiają do raportu jako sprawy otwarte. |
| Raport | Składa weryfikator: co powstało, co sprawdzono, czym to potwierdzono, co zostaje otwarte. |
| Dowód | Każde twierdzenie o stanie kodu ma ścieżkę pliku; każde o poprawności — wynik uruchomionej kontroli. |
| Język | Polski, rzeczowy. Nazwy plików i symboli po angielsku tam, gdzie tak jest w repozytorium. |

## 2. Własność plików

Specjalista zmienia **wyłącznie** pliki swojej dziedziny. Gdy zmiana wymaga cudzego pliku,
opisuje ją w raporcie jako patch do wykonania — nie robi jej sam.

| Para | Pliki własne |
|---|---|
| P1 Treść | `frontend/src/landing/**`, `frontend/src/portal/tresc.ts`, `frontend/src/portal/strony/**` (bez `Cennik.tsx`, `Konto.tsx`), etykiety w `frontend/src/modules/*/index.tsx`, `SUGGESTIONS` w `frontend/src/shell/Workspace.tsx`, etykiety w `frontend/src/shell/ModuleNav.tsx` |
| P2 Sprzedaż | `backend/nexus/platnosci/**`, `backend/nexus/api/modules/platnosci.py`, `frontend/src/platnosci/**`, `frontend/src/portal/strony/Cennik.tsx`, `backend/tests/test_platnosci.py`, `docs/platnosci/README.md` |
| P3 Konta | `backend/nexus/portal/konta.py`, `backend/nexus/portal/poczta_portalu.py`, `backend/nexus/api/modules/portal.py`, `frontend/src/portal/strony/Konto.tsx`, `frontend/src/portal/api.ts`, `backend/tests/test_portal.py`, `docs/portal/README.md` |
| P4 Zgodność | nowe `frontend/src/portal/strony/{Prywatnosc,Regulamin,Cookies}.tsx`, nowy `frontend/src/portal/tresc-prawna.ts`, `docs/zgodnosc/**` |
| P5 Ruch | `frontend/src/styles.css`, `frontend/src/ui/ruch.css`, nowe `frontend/src/ruch/**`, `frontend/scripts/zasoby.py`, wpięcie w `frontend/src/landing/**` i `frontend/src/portal/ui.tsx` |
| P6 Widoczność | `frontend/index.html`, `frontend/src/seo.ts`, `frontend/src/portal/seo.ts`, `backend/nexus/portal/kanaly.py`, `frontend/vite.config.ts` |
| P7 Nawigacja | `frontend/src/portal/trasy.ts`, nawigacja i stopka w `frontend/src/portal/Portal.tsx`, `frontend/src/shell/route.ts` |
| P8 Dostępność | dowolny plik interfejsu — po wcześniejszych falach; zmiany wyłącznie usuwające bariery |
| P9 Wydajność | `frontend/vite.config.ts`, `frontend/src/App.tsx`, `frontend/scripts/zasoby.py`, `backend/nexus/api/app.py` |
| P10 Bezpieczeństwo | `backend/nexus/**` — wyłącznie poprawki usuwające podatności |

## 3. Fala 1 — treść, sprzedaż, konta, zgodność

### P1 — Treść i język marketingowy

Przedmiotem jest **cała witryna**, nie sama strona główna: strona produktu, portal
(oferta, funkcjonalności, cennik, dokumentacja, blog, centrum wiedzy, kontakt), nazwy zakładek
i pozycji nawigacji, nazwy sekcji, nagłówki, hasła, podtytuły, wezwania do działania, teksty
pustych stanów, podpowiedzi pól, etykiety modułów aplikacji.

Zadania: ocenić każdy istniejący tekst pod kątem nośności i trafiania w potrzebę użytkownika;
przepisać to, co nazywa kategorię zamiast korzyści; **dopisać brakujące** sekcje i bloki treści
tam, gdzie strona nie odpowiada na pytanie odwiedzającego; ujednolicić ton (zwrot na „Ty”,
marka w 3. osobie, agent w 1. osobie czasu teraźniejszego).

Wiążące: `landing/LANDING_PAGE_SPEC.md` (treść i ton), decyzja właściciela z 2026-09-20 o
nagłówku hero, zakaz obietnic bez pokrycia w rejestrze `backend/nexus/tools/`.

Kryteria odbioru: każdy nagłówek zawiera czasownik albo konkret; żadne zdanie nie obiecuje
funkcji spoza rejestru narzędzi; nazwy zakładek do trzech słów; nie ma dwóch różnych nazw na
to samo; liczby zgodne ze stanem kodu.

### P2 — Sprzedaż: oferta, cennik, ścieżka zakupu

Zadania: spójny cennik na stronie produktu, w portalu i w module Płatności; pełna ścieżka od
kliknięcia do zakupu i po zakupie (powrót, potwierdzenie, faktura, zmiana planu, rezygnacja);
stany brzegowe: sprzedaż niewłączona, płatność odrzucona, subskrypcja wygasła, kupon nieważny;
czytelne komunikaty w każdym z nich.

Kryteria odbioru: jedna definicja planów w całym produkcie; kwoty i plany rozstrzyga serwer;
każdy krok ścieżki ma widok i komunikat; testy pokrywają stany brzegowe.

### P3 — Konta użytkowników

Zadania: rejestracja, logowanie, wylogowanie, odzyskiwanie hasła, zmiana hasła, profil,
usunięcie konta; komunikaty błędów mówiące, co zrobić; ograniczenie tempa prób; wygaszanie
sesji; potwierdzenie adresu poczty, jeżeli wysyłka jest skonfigurowana.

Kryteria odbioru: brak ujawniania, czy adres istnieje, przy odzyskiwaniu hasła; token
jednorazowy o krótkim czasie życia; hasło wyłącznie przez Argon2; testy na każdą ścieżkę.

### P4 — Zaufanie i zgodność prawna

Zadania: polityka prywatności, regulamin, informacja o plikach cookie i zgoda, gdy jest
potrzebna; rejestr czynności przetwarzania w dokumentacji; wskazanie administratora danych,
podstaw prawnych, okresów przechowywania, praw osoby i przekazania danych do modelu Claude.

Kryteria odbioru: dokumenty opisują stan faktyczny produktu, nie wzorzec z sieci; każda
kategoria danych wymieniona w polityce istnieje w kodzie; odsyłacze ze stopki prowadzą do
istniejących stron.

## 4. Fala 2 — ruch, widoczność, nawigacja

### P5 — Jakość wizualna: ruch, animacje, grafika, przejścia

W repozytorium leżą gotowe opracowania, które **mają zostać użyte**:

| Pakiet | Zawartość |
|---|---|
| `motion/podglad/` | dziesięć działających demonstracji animacji interfejsu (HTML + JS) |
| `motion/przyklady/` | czternaście nagrań zachowań i krzywe wygładzenia |
| `motion/start/kod/` | dziesięć gotowych animacji momentów: intro znaku, logowanie, wylogowanie, uruchomienie, instalacja, myśli, sukces, błąd, brak połączenia (+ `znak-ruch.css`, `znak-ruch.js`) |
| `motion/start/lottie/` | intro znaku w formacie Lottie |
| `motion/start/wideo/` | około sześćdziesięciu nagrań momentów w trzech formatach |
| `landing/tla/` | pięć teł na żywo (WebGL 2 i CSS) z API `mount(element, opcje)`: aurora, łuk, konstelacja, noc, świt, oraz warstwa ziarna |
| `landing/ladowanie/` | ekran ładowania |
| `branding/wizualizacje/` | key visuale, sceny, tapety |

Zadania: wpiąć tła na żywo w miejsce klatek statycznych (z klatką zastępczą i poszanowaniem
`prefers-reduced-motion`); wpiąć animacje momentów w stany aplikacji (logowanie, uruchomienie,
myśli agenta, sukces, błąd, brak połączenia, instalacja); przejścia między widokami; kaskady
wejścia sekcji; mikrointerakcje kontrolek.

Kryteria odbioru: żadna animacja nie działa poza polem widzenia; `prefers-reduced-motion`
zatrzymuje ruch; wartości czasu i krzywych wyłącznie z tokenów; strona produktu nie traci
na wydajności powyżej progu z rozdz. 6.

### P6 — SEO i widoczność

Zadania: metadane każdej strony portalu i strony produktu; dane strukturalne właściwe dla typu
strony; mapa witryny obejmująca wszystkie publiczne adresy; `robots.txt`; kanoniczne adresy;
nagłówki Open Graph; poprawna hierarchia nagłówków; teksty alternatywne obrazów; język i
kierunek pisma.

Kryteria odbioru: każda publiczna strona ma własny tytuł i opis; jeden `h1` na stronę; mapa
witryny zgadza się z trasowaniem; brak adresów zamkniętych w mapie.

### P7 — Architektura informacji i nawigacja

Zadania: układ zakładek portalu i strony produktu; głębokość i nazwy sekcji; ścieżka powrotu;
okruszki tam, gdzie są potrzebne; spójność między nawigacją, stopką i mapą witryny; strona
błędu 404 z sensownym wyjściem.

Kryteria odbioru: z każdej strony da się wrócić do strony głównej i do aplikacji; żadna pozycja
nawigacji nie prowadzi do pustej strony; nazwy w nawigacji, stopce i mapie witryny są zgodne.

## 5. Fala 3 — dostępność, wydajność, bezpieczeństwo

### P8 — Dostępność WCAG 2.2 AA

Zadania: nawigacja klawiaturą przez każdą ścieżkę; widoczny fokus; nazwy dostępne kontrolek;
poprawne role i stany; kontrast tekstu i elementów graficznych; obsługa powiększenia do 200%;
komunikaty o zmianie stanu dla czytnika ekranu; brak pułapek fokusu w oknach i arkuszach.

Kryteria odbioru: `pa11y --standard WCAG2AA` bez zgłoszeń na wszystkich publicznych adresach
i w powłoce aplikacji; ręczny przebieg klawiaturą opisany w raporcie.

### P9 — Wydajność i Core Web Vitals

Zadania: budżet ładowania strony produktu i powłoki aplikacji; podział kodu; leniwe ładowanie
obrazów i nagrań; rozmiary i formaty grafik; brak przeskoków układu; szybkość reakcji na
pierwsze działanie.

Kryteria odbioru: pomiar Lighthouse albo równoważny przed i po, z liczbami w raporcie; brak
regresji w rozmiarze paczki powyżej 5%.

### P10 — Bezpieczeństwo powierzchni publicznej

Zadania: przegląd nowych powierzchni (konta portalu, płatności, piaskownica) pod kątem
uwierzytelnienia, autoryzacji, ochrony przed CSRF, ograniczenia tempa, walidacji wejścia,
wycieku informacji w komunikatach błędów, bezpieczeństwa webhooków i obsługi plików.

Kryteria odbioru: brak podatności o wadze wysokiej i średniej; każda poprawka z testem.

## 6. Kontrole wspólne

Każda para uruchamia przed zgłoszeniem pracy i przytacza wynik:

```
cd frontend && npx tsc --noEmit
cd frontend && npx vitest run
cd frontend && npm run build
.venv/bin/python -m pytest backend/tests -q
.venv/bin/ruff check backend
```

Praca, która psuje którąkolwiek z tych kontroli, jest usterką bez względu na wartość
merytoryczną zmiany.

---

*Koniec dokumentu. Specyfikacje dziedzinowe orkiestracji par — etap 1B, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*


## Czego nauczyła fala 1 (20 września)

Wszystkie cztery pary wyczerpały trzy tury i **żadna nie została przyjęta**, mimo że zostawiły
około 10 900 wierszy działającego kodu (portal, sprzedaż, konta, piaskownica) i cztery pliki
testów. Zawiodła bramka, nie praca.

| Błąd projektu orkiestracji | Skutek | Poprawka w fali domykającej |
|---|---|---|
| Próg „zero usterek” | Weryfikator przy zakresie „cała dziedzina” zawsze coś znajdzie; pętla nie mogła się domknąć | Próg „zero usterek **wysokiej wagi**”; średnie i niskie są wypisywane, ale nie blokują |
| Zakres pary = cała dziedzina na całej witrynie | Trzy tury to za mało, a specjalista co turę dostawał nową listę | Zakres = zamknięta lista konkretnych usterek z wierszami i plikami |
| Weryfikator prowadził za każdym razem nowy audyt | Usterki mnożyły się zamiast ubywać (14 → 8 → 11) | Weryfikator sprawdza tylko, czy wymienione usterki zamknięto i czy nic nie pękło |
| Pary nie wiedziały o zmianach spoza swojej dziedziny | Zgłaszały jako usterki rzeczy już naprawione | Każdy prompt zaczyna się od opisu stanu repozytorium |
| Brak trybu „usterka nieaktualna” | Specjalista poprawiał na siłę albo ignorował | Pole `odrzucone` z uzasadnieniem i dowodem z kodu |

Zasada na przyszłość: **para domyka listę, nie dziedzinę**. Audyt dziedziny jest osobnym krokiem,
którego wynikiem jest lista — dopiero ona trafia do pary.
