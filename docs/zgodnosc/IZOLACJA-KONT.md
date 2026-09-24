# Izolacja kont — przegląd z 24 września 2026

Nexus obsługuje w jednej instalacji konto właściciela, konta klientów portalu i konta próbne.
Wszystkie mają tę samą sesję aplikacji i ten sam zestaw narzędzi agenta, więc rozdział danych
robi wyłącznie kod: warunek na `owner_id` w zapytaniu, przedrostek konta w ścieżce albo osobne
konto w usłudze zewnętrznej. Ten dokument zbiera wynik przeglądu wszystkich takich miejsc.

## Stan po przeglądzie

| Obszar | Rozdział | Stan przed | Naprawa |
|---|---|---|---|
| Rozmowy, przebiegi, zdarzenia, zadania w toku | `owner_id` rozmowy | poprawny | — |
| Pliki (API, moduł Pliki) | `owner_id` pliku | poprawny | — |
| Pliki widziane przez narzędzia (`FileService`) | brak | narzędzie otwierało plik dowolnego konta po numerze; wyniki zapisywały się na konto właściciela | `a4caf01` |
| Chmura — moduł Pliki | `/Konta/<owner>` w koncie technicznym | poprawny | — |
| Chmura — kosz | brak | klient widział i przywracał cudze usunięte pliki | `b8cb155` |
| Chmura — narzędzia agenta (`cloud_*`) | brak | korzeń konta technicznego: pliki właściciela i wszystkich kont | `5e79f9e` |
| Chmura — synchronizacja i SSO | konto Nextcloud | klient dostawał login `admin` | `57a3cd9`, `42ebd05` (własne konto `nexus-<owner>` dla planów z synchronizacją) |
| Kalendarz — wydarzenia | przedrostek `konto-<owner>-` | poprawny | — |
| Kalendarz — CalDAV | konto techniczne albo konto Nextcloud klienta | klient dostawał login `admin` | `42ebd05`, `28ae146` (plany Pro i Grupa: kalendarze w koncie `nexus-<owner>`, własny login) |
| Baza wiedzy — API modułu | `owner_id` kolekcji | poprawny | — |
| Baza wiedzy — narzędzia agenta | brak | lista i odczyt kolekcji, źródeł i notatek wszystkich kont | `5e79f9e` |
| Baza wiedzy — indeks wektorowy | `owner_id` w ładunku | wpisy bez właściciela (nieznajdowalne) | `5e79f9e` + `nexus-cli.sh przeindeksuj-wiedze` |
| Poczta — skrzynki | plik konfiguracji konta | poprawny | — |
| Działania oczekujące (szkice maili, usunięcia wydarzeń) | `owner_id` działania | lista zawierała szkice maili i prośby wszystkich kont | kolumna `owner_id`, kontrola w liście, odczycie i zatwierdzeniu |
| Powiadomienia push | brak | tytuł rozmowy szedł na urządzenia wszystkich kont | `6e532c3` |
| Tryb Kod — projekty | wykaz właścicieli | API poprawne, przebieg bez kontroli | `f012c2c` |
| Strony | właściciel w metadanych | poprawny | — |
| Zadania modułów twórczych | właściciel zadania | brak kontroli właściciela (numer nie do zgadnięcia, pliki wyników już z kontrolą) | stan i anulowanie tylko dla konta zlecającego |
| Usunięcie konta | — | kasowało tylko logowanie; dane i sesja aplikacji zostawały | `12aa3ee` |
| Konta próbne | — | nigdy nie znikały, choć portal obiecuje dwa dni | `12aa3ee` |

Sprawdzone w bazie produkcyjnej 24.09.2026: żaden agent konta klienta nie wywołał narzędzi
chmury ani bazy wiedzy, baza wiedzy była pusta, nie było subskrypcji push ani źle przypisanych
wyników. Luki nie zostały wykorzystane.

## Zasada na przyszłość

Każde nowe narzędzie agenta, tabela i punkt API, które dotykają danych, dostają konto
w tym samym kroku, w którym powstają: `ctx.owner_id` w narzędziu, `owner_id` w modelu
(z wpisem w `COLUMNS` dla istniejących baz), `require_session(...).owner_id` w API. Test
izolacji zakłada dwa konta i sprawdza, że drugie nie widzi niczego z pierwszego —
wzór w `backend/tests/test_izolacja_kont.py`, `test_cloud.py`, `test_research.py`.
