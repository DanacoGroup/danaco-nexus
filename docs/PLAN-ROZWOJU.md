# Danaco Nexus – plan rozwoju (etap „platforma wielu urządzeń i modułów”)

Serwer Nexusa (Claude, narzędzia, chmura, baza wiedzy, historia) jest wspólnym „mózgiem”.
Do niego podłączają się klienci (przeglądarka/PWA, Android, rozszerzenie, Windows) i moduły.

## Strumienie pracy (równolegle, każdy w osobnej gałęzi `modul/<id>`)

| # | Gałąź | Zakres |
|---|---|---|
| 1 | `modul/start` | Publiczna strona startowa (sprzedażowa) z instalacją aplikacji; powłoka aplikacji z nawigacją modułów (`frontend/src/modules`); panel zadań w toku (wiele sesji naraz); powiadomienia Web Push o zakończonych zadaniach; strona „Urządzenia” (klucze urządzeń); pobieranie instalatorów (`/pobierz/…`). |
| 2 | `modul/android` | Aplikacja Android (Capacitor + Kotlin): pełny Nexus w oknie aplikacji, rozmowa głosowa w tle (usługa pierwszoplanowa), Nexus jako asystent systemowy (przytrzymanie bocznego przycisku), języczek przy krawędzi z podglądem ekranu, szkice odpowiedzi na SMS z „Wstaw/Kopiuj”, powiadomienia; budowa APK na serwerze. |
| 3 | `modul/rozszerzenie` | Rozszerzenie Chrome/Edge/Danaco Lynx (MV3, wstrzykiwany panel boczny): czytanie bieżącej strony, streszczenia, odpowiedzi na opinie (Booking, Google), wstawianie tekstu w pola, menu kontekstowe; logowanie kluczem urządzenia. |
| 4 | `modul/pulpit` | Nexus Desktop (Windows, Electron): wysuwany panel z krawędzi i skrót klawiszowy, zrzut aktywnego okna, wklejanie odpowiedzi, lokalny agent: wyszukiwanie plików, diagnostyka i naprawy przez PowerShell (zmiany tylko po zatwierdzeniu), przekaźnik narzędzi `pc_*` serwer ↔ komputer. |
| 5 | `modul/research` | Deep Research (sieć, raport z cytatami), Scholar Research (OpenAlex, Semantic Scholar, arXiv, Crossref), baza wiedzy w stylu Wisebase (zapisywanie stron, notatki, rozmowa z wieloma dokumentami). |
| 6 | `modul/tworczy` | Twórca stron (podgląd na żywo, publikacja pod `/s/<adres>`), Obrazy (usuwanie/zmiana tła, gumka, powiększanie), Tłumacz (tekst, dokumenty, PDF z zachowaniem układu), Studio audio/wideo. |
| 7 | `modul/biuro` | Cloud w aplikacji (przeglądarka plików Nextcloud: foldery, wersje, udostępnianie, synchronizacja), poczta (IMAP/SMTP `mail.danaco-group.pl`: czytanie, szkice odpowiedzi, wysyłanie po potwierdzeniu), kalendarz (Nextcloud CalDAV). |
| 8 | `modul/agenci` | Wiele sesji równolegle (proces roboczy), orkiestracja wielu agentów (podagenci Claude Code widoczni w czacie), tryb badań z narzędziami sieci, moduł Kod: przestrzenie projektów, sesje programistyczne z Claude Code, podgląd plików, git. |

Po zakończeniu strumieni: scalenie gałęzi, testy całości, wdrożenie, dokumentacja.

## Wspólny szkielet (gotowy przed startem strumieni)

- **Moduły interfejsu:** `frontend/src/modules/<id>/index.tsx` eksportuje `module: NexusModule`
  (`frontend/src/modules/registry.ts`) – wykrywane automatycznie.
- **Moduły API:** `backend/nexus/api/modules/<id>.py` z obiektem `router` (prefiks `/api/<id>`,
  zależność `require_session`) – podłączane automatycznie.
- **Narzędzia agenta:** `backend/nexus/tools/<nazwa>.py` z `@registry.register` – ładowane automatycznie.
- **Tabele modułów:** `backend/nexus/models/<id>.py` (modele na `nexus.db.Base`); nowe kolumny
  istniejących tabel w liście `COLUMNS` – dodawane przy starcie.
- **Rozmowa w trybie modułu:** `Conversation.meta` (np. `{"mode": "code", "workspace": "sklep"}`).
- **Klucze urządzeń:** `POST /api/urzadzenia` (tylko zalogowana przeglądarka) zwraca jednorazowo
  `nxd_…`; urządzenie wysyła `Authorization: Bearer nxd_…` (bez CSRF). `request.state.device`
  opisuje urządzenie.
