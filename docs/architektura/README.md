# Danaco Nexus — Pakiet dokumentacji architektury

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Rodzaj** | Personal AI Workspace |
| **Opis** | Osobisty agent AI działający na serwerze Danaco: rozmowa z modelem Claude przez Claude Code CLI, narzędzia na plikach, OCR, obrazy, poczta, kalendarz, chmura osobista, baza wiedzy, moduł Kod, klienci PWA / Android / Windows / rozszerzenie przeglądarki. |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Twórca** | Dariusz Naharnowicz |
| **Wersja** | 1.0 |
| **Status** | Deweloperski |
| **Data** | 2026-09-20 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Pakiet dokumentacji architektury — spis, zasady pakietu, kolejność czytania, zasady utrzymania |
| **Klasa dokumentu** | Dokument spinający |
| **Odbiorcy** | każdy, kto sięga po dokumentację architektury Danaco Nexus |
| **Przeznaczenie** | Wskazuje, który dokument odpowiada na które pytanie, i ustala zasady utrzymania pakietu w zgodzie z kodem. |
| **Zakres** | Cztery dokumenty pakietu, ich role, granice i wzajemne zależności |
| **Poza zakresem** | Treść merytoryczna — w dokumentach składowych; opisy funkcjonalne modułów — [`docs/moduly/`](../moduly/) |
| **Dokument nadrzędny** | brak |
| **Dokumenty powiązane** | [`README.md`](../../README.md) repozytorium · [`docs/PLAN-ROZWOJU.md`](../PLAN-ROZWOJU.md) · [System projektowy](../../design-system/DESIGN_SYSTEM.md) |
| **Źródła normatywne** | kod repozytorium `/danaco/projekty/danaco-nexus` w rewizji `ddfac78` |
| **Zasada nadrzędna** | Gdy dokument i kod się rozchodzą, rozstrzyga kod — a dokument poprawia się tego samego dnia. |

## Spis treści

1. [Co zawiera pakiet](#1-co-zawiera-pakiet)
2. [Kolejność czytania](#2-kolejność-czytania)
3. [Gdzie szukać odpowiedzi](#3-gdzie-szukać-odpowiedzi)
4. [Zależności między dokumentami](#4-zależności-między-dokumentami)
5. [Zasady pakietu](#5-zasady-pakietu)
6. [Najważniejsze ustalenia](#6-najważniejsze-ustalenia)
7. [Utrzymanie](#7-utrzymanie)

---

## 1. Co zawiera pakiet

| Dokument | Klasa | Odpowiada na pytanie |
|---|---|---|
| [STAN-OBECNY.md](STAN-OBECNY.md) | opis stanu faktycznego | Jak system jest zbudowany dzisiaj i czego w nim nie ma? |
| [ARCHITEKTURA-DOCELOWA.md](ARCHITEKTURA-DOCELOWA.md) | specyfikacja docelowa | Jak ma być zbudowany i dlaczego właśnie tak? |
| [ROADMAPA.md](ROADMAPA.md) | plan wdrożenia | W jakiej kolejności przejść z pierwszego do drugiego i kiedy etap jest zamknięty? |
| [BACKLOG.md](BACKLOG.md) | rejestr zadań | Co konkretnie trzeba zrobić, w jakich plikach i jakim nakładem? |

Pakiet nie opisuje funkcji produktu. Te opisują [`docs/moduly/`](../moduly/) i
[`README.md`](../../README.md) repozytorium.

---

## 2. Kolejność czytania

```
              ┌───────────────────────┐
              │  STAN-OBECNY.md        │  co jest — z odsyłaczami plik:linia
              │  rozdz. 20: ograniczenia│
              │  rozdz. 21: czego nie ma│
              └───────────┬───────────┘
                          │ każde ograniczenie ma odpowiedź
                          ▼
              ┌───────────────────────┐
              │ ARCHITEKTURA-DOCELOWA │  jak ma być i dlaczego
              │ rozdz. 17: kryteria    │
              └───────────┬───────────┘
                          │ kryteria stają się warunkami odbioru
                          ▼
              ┌───────────────────────┐
              │ ROADMAPA.md            │  siedem etapów, każdy z dowodem
              └───────────┬───────────┘
                          │ etapy rozbite na zadania
                          ▼
              ┌───────────────────────┐
              │ BACKLOG.md             │  64 zadania: pliki, nakład, priorytet
              └───────────────────────┘
```

Kto czyta pierwszy raz — po kolei. Kto szuka konkretu — przez tabelę w rozdziale 3.

---

## 3. Gdzie szukać odpowiedzi

| Pytanie | Dokument i miejsce |
|---|---|
| Jak wygląda przebieg zadania od wiadomości do odpowiedzi? | [Stan obecny, rozdz. 4](STAN-OBECNY.md#4-przebieg-agenta) |
| Jak działa kolejka i dlaczego bez brokera? | [Stan obecny, rozdz. 5](STAN-OBECNY.md#5-kolejka-zadań) · [Architektura docelowa, rozdz. 16](ARCHITEKTURA-DOCELOWA.md#16-decyzje-i-odrzucone-warianty) |
| Jak działa strumień zdarzeń i wznowienie po zerwaniu? | [Stan obecny, rozdz. 6](STAN-OBECNY.md#6-strumieniowanie-zdarzeń) |
| Jakie są tabele i skąd się bierze schemat? | [Stan obecny, rozdz. 8](STAN-OBECNY.md#8-model-danych) |
| Jak uwierzytelniają się klienci? | [Stan obecny, rozdz. 9](STAN-OBECNY.md#9-uwierzytelnianie-i-autoryzacja) |
| Ile jest narzędzi agenta i jakie mają zasady? | [Stan obecny, rozdz. 10](STAN-OBECNY.md#10-narzędzia-agenta) |
| Co blokuje uruchomienie drugiej repliki API? | [Stan obecny, rozdz. 20](STAN-OBECNY.md#20-ograniczenia-stanu-obecnego) |
| Czego w systemie nie ma? | [Stan obecny, rozdz. 21](STAN-OBECNY.md#21-czego-nie-ma-w-kodzie) |
| Jak ma wyglądać docelowy podział na warstwy? | [Architektura docelowa, rozdz. 2–3](ARCHITEKTURA-DOCELOWA.md#2-warstwy) |
| Dlaczego rozmowa musi trafiać do tego samego procesu roboczego? | [Architektura docelowa, rozdz. 5](ARCHITEKTURA-DOCELOWA.md#5-warstwa-wykonawcza-i-powinowactwo-sesji) |
| Jak mierzyć, że system działa? | [Architektura docelowa, rozdz. 12](ARCHITEKTURA-DOCELOWA.md#12-obserwowalność) |
| Jakie są cele kopii zapasowych? | [Architektura docelowa, rozdz. 13](ARCHITEKTURA-DOCELOWA.md#13-kopie-zapasowe-i-odtworzenie) |
| Od czego zacząć? | [Roadmapa, etap 1](ROADMAPA.md#3-etap-1--fundament-jakości-i-odtwarzalność) |
| Które zadanie wziąć teraz? | [Backlog, rozdz. 2](BACKLOG.md#2-grupa-fundament-jakości-i-odtwarzalność) — pozycje o priorytecie krytycznym |

---

## 4. Zależności między dokumentami

| Zmiana | Skutek dla pakietu |
|---|---|
| Zmiana w kodzie, której dotyczy odsyłacz `plik:linia` | poprawa odsyłacza w [Stanie obecnym](STAN-OBECNY.md) |
| Usunięcie ograniczenia z rozdziału 20 Stanu obecnego | skreślenie pozycji tam, zamknięcie zadań w [Backlogu](BACKLOG.md) |
| Nowe ograniczenie wykryte w trakcie pracy | dopisanie do rozdziału 20, potem zadanie w Backlogu |
| Zmiana decyzji architektonicznej | wpis w rozdziale 16 [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md) z wariantem odrzuconym |
| Zamknięcie etapu | aktualizacja [Stanu obecnego](STAN-OBECNY.md) i przegląd priorytetów w Backlogu |

---

## 5. Zasady pakietu

1. **Fakt ma odsyłacz.** Każde zdanie o działaniu kodu wskazuje plik i numer linii.
   Zdanie bez odsyłacza jest projektem, nie opisem.
2. **Brak funkcji nazywa się wprost.** Piszemy „brak w kodzie”, nigdy „planowane”
   w dokumencie opisującym stan.
3. **Zmiana ma powód.** Każdy element architektury docelowej wskazuje ograniczenie,
   które usuwa. Bez ograniczenia element nie wchodzi do dokumentu.
4. **Kryterium jest sprawdzalne.** Odbiór opisuje obserwację albo polecenie, nie opinię.
5. **Identyfikator opisuje.** Zadania w Backlogu mają nazwy mówiące, czego dotyczą,
   a nie kody literowo-numeryczne.
6. **Diagram jest tekstem.** Rysunki są blokami znaków w kodzie źródłowym dokumentu,
   żeby dało się je czytać w przeglądzie zmian i poprawiać razem z treścią.

---

## 6. Najważniejsze ustalenia

Skrót dla osoby, która ma pięć minut.

**Co jest mocne w dzisiejszej architekturze.**

- Wykonanie zadań jest rozdzielone od API i oparte o kolejkę transakcyjną w PostgreSQL
  z `FOR UPDATE SKIP LOCKED` — wiele procesów roboczych zadziała bez zmian w kodzie
  (`backend/nexus/worker.py:35-50`).
- Strumień zdarzeń ma trwałe źródło prawdy i wznowienie po identyfikatorze, więc
  zerwane połączenie nie gubi treści (`backend/nexus/api/runs.py:74-119`).
- Rozszerzanie jest tanie: moduł API, moduł interfejsu, narzędzie agenta i tabela modułu
  są wykrywane automatycznie (`backend/nexus/api/modules/__init__.py:16-26`,
  `backend/nexus/tools/__init__.py:15-17`, `frontend/src/modules/registry.ts:31-40`,
  `backend/nexus/models/__init__.py:14-21`).
- Działania nieodwracalne wymagają zatwierdzenia przez człowieka — wysyłka poczty,
  usunięcie wydarzenia, polecenie zmieniające system na komputerze
  (`backend/nexus/tools/poczta.py:332-357`, `backend/nexus/oczekujace.py:19`,
  `backend/nexus/tools/pc.py:224-241`).
- Granica narzędzi jest wyraźna: pliki wyłącznie po identyfikatorach, programy bez
  powłoki, limit czasu i anulowanie (`backend/nexus/tools/base.py:106-112`,
  `tools/base.py:133-173`).

**Co jest najpilniejsze.**

1. **Brak kopii zapasowych.** W `deploy/` nie ma ani jednego skryptu kopii bazy, plików
   czy wektorów. Awaria dysku oznacza utratę wszystkiego.
2. **Brak migracji schematu.** Schemat powstaje przez `create_all` i ręczne
   `ALTER TABLE … ADD COLUMN` (`backend/nexus/db.py:243-260`), bez możliwości zmiany typu,
   usunięcia kolumny i wycofania.
3. **Stan w pamięci procesu API** blokuje drugą replikę: licznik logowań
   (`backend/nexus/api/auth.py:60-83`), zadania modułów twórczych
   (`backend/nexus/tworczy/zadania.py:57-78`), rejestr gniazd komputerów
   (`backend/nexus/api/modules/pulpit.py:53-55`), nasłuch powiadomień
   (`backend/nexus/api/modules/push.py:50-54`).
4. **Cicha degradacja kontekstu.** Gdy proces roboczy nie widzi pliku sesji CLI, rozmowa
   traci kontekst i dostaje streszczenie ostatnich 16 wiadomości
   (`backend/nexus/agent/runner.py:704-752`). Nie jest to błąd, więc bez metryki nikt
   tego nie zauważy.
5. **Brak obserwowalności.** Nie ma metryk, śladów ani alarmów — tylko dzienniki tekstowe
   (`backend/nexus/logging_setup.py:9-22`) i polecenie diagnostyczne
   (`backend/nexus/doctor.py`).
6. **Brak potoku bramek.** `ruff`, `pytest`, `tsc` i `vitest` istnieją jako polecenia,
   ale nic ich nie uruchamia automatycznie.

**Ograniczenie, którego nie da się obejść kodem.** Przepustowość systemu wyznacza limit
subskrypcji konta Claude, nie liczba rdzeni. System już go odczytuje i pokazuje
(`backend/nexus/agent/runner.py:1066-1081`), więc planowanie zdolności musi zaczynać się
od tej wielkości.

---

## 7. Utrzymanie

| Zdarzenie | Działanie |
|---|---|
| Zamknięcie etapu roadmapy | aktualizacja rozdziałów 20 i 21 [Stanu obecnego](STAN-OBECNY.md), przegląd priorytetów w [Backlogu](BACKLOG.md) |
| Zmiana struktury kodu | sprawdzenie odsyłaczy `plik:linia` w [Stanie obecnym](STAN-OBECNY.md) |
| Nowy moduł API, interfejsu albo narzędzie | dopisanie do tabel w rozdziałach 10 i 11 [Stanu obecnego](STAN-OBECNY.md) |
| Decyzja architektoniczna | wpis w rozdziale 16 [Architektury docelowej](ARCHITEKTURA-DOCELOWA.md) |
| Wersja pakietu | wersję podnosi się wspólnie dla wszystkich czterech dokumentów |

Kontrola spójności przed wydaniem wersji pakietu:

| Kontrola | Sposób |
|---|---|
| Odsyłacze plikowe wskazują istniejące pliki | przegląd ścieżek z dokumentów |
| Liczby (narzędzia, moduły, tabele) zgadzają się z kodem | zliczenie rejestracji, katalogów modułów i klas modeli |
| Każde ograniczenie z rozdziału 20 ma zadanie w Backlogu | zestawienie obu list |
| Każde zadanie Backlogu należy do etapu albo grupy „poza etapami” | przegląd grup |
| Każdy etap ma sprawdzalne kryteria odbioru | przegląd tabel odbioru |

---

*Koniec dokumentu. Pakiet dokumentacji architektury — Dokument spinający, wersja 1.0, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Warunki korzystania: [DO DECYZJI OPERATORA] — repozytorium nie zawiera pliku licencji. Kontakt: support@danaco-group.pl*
