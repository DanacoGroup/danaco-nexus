# Danaco Nexus — Zgodność prawna i ochrona danych

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
| **Tytuł** | Zgodność prawna produktu — dokumenty publikowane i dokumentacja wewnętrzna |
| **Klasa dokumentu** | Opis stanu wykonania |
| **Odbiorcy** | właściciel produktu · radca prawny · deweloper warstwy klienckiej · weryfikator |
| **Przeznaczenie** | Wskazuje, gdzie leżą dokumenty prawne produktu, skąd pochodzi ich treść i co trzeba zrobić, żeby odsyłacze ze stopki prowadziły do istniejących stron. |
| **Zakres** | Polityka prywatności, regulamin, informacja o plikach cookie, rejestr czynności przetwarzania, mapa danych w kodzie |
| **Poza zakresem** | Bezpieczeństwo powierzchni publicznej — para P10; nawigacja i stopka — para P7; mapa witryny — para P6 |
| **Źródła normatywne** | `frontend/src/portal/tresc-prawna.ts` · `backend/nexus/models/**` · `backend/nexus/portal/**` · `backend/nexus/platnosci/**` |
| **Zasada nadrzędna** | Dokument prawny opisuje stan faktyczny produktu. Każda wymieniona kategoria danych ma odpowiednik w kodzie; kategoria bez pokrycia w kodzie jest usterką dokumentu, nie kodu. |

## Spis treści

1. [Co powstało](#1-co-powstało)
2. [Skąd pochodzi treść dokumentów](#2-skąd-pochodzi-treść-dokumentów)
3. [Trasowanie](#3-trasowanie)
4. [Utrzymanie: kiedy dokument trzeba zmienić](#4-utrzymanie-kiedy-dokument-trzeba-zmienić)
5. [Sprawy do rozstrzygnięcia przez właściciela produktu](#5-sprawy-do-rozstrzygnięcia-przez-właściciela-produktu)

---

## 1. Co powstało

| Dokument | Miejsce | Adres publiczny |
|---|---|---|
| Polityka prywatności | `frontend/src/portal/strony/Prywatnosc.tsx` | `/portal/prywatnosc` |
| Regulamin | `frontend/src/portal/strony/Regulamin.tsx` | `/portal/regulamin` |
| Informacja o plikach cookie | `frontend/src/portal/strony/Cookies.tsx` | `/portal/cookies` |
| Treść wszystkich trzech dokumentów | `frontend/src/portal/tresc-prawna.ts` | — |
| Rejestr czynności przetwarzania | [REJESTR-CZYNNOSCI.md](REJESTR-CZYNNOSCI.md) | — |
| Mapa danych w kodzie | [DANE-W-KODZIE.md](DANE-W-KODZIE.md) | — |

Treść jest oddzielona od układu tak samo jak w `frontend/src/portal/tresc.ts`: strona
renderuje dane, redakcja zmienia wyłącznie `tresc-prawna.ts`. Każdy rozdział jest osobną
sekcją z własną kotwicą, więc do pojedynczego postanowienia da się odesłać adresem.

Wartości wizualne pochodzą z ról semantycznych (`bg-raised`, `border-line`, `text-muted`,
`text-accent`, `font-heading`); treść rozdziałów renderuje komponent `Markdown`, którego
typografia jest w całości opisana tokenami w `frontend/src/styles.css`.

## 2. Skąd pochodzi treść dokumentów

Dokumenty nie są wzorcem z sieci. Każde twierdzenie ma źródło w kodzie — pełne
zestawienie podaje [mapa danych w kodzie](DANE-W-KODZIE.md). Najważniejsze zależności:

| Twierdzenie w dokumencie | Źródło |
|---|---|
| Trzy ciasteczka: `nexus_session`, `nexus_portal`, `nexus_demo` | `backend/nexus/api/auth.py`, `backend/nexus/portal/konta.py`, `backend/nexus/demo/sesje.py` |
| Flagi `HttpOnly`, `SameSite=Lax`; `Secure` z ustawienia, nie z rodzaju połączenia | te same pliki, wywołania `set_cookie`; `settings.cookie_secure` — `backend/nexus/config.py:64` |
| Zasięg `nexus_session` i `nexus_portal` obejmuje poddomeny | `domain=settings.cookie_domain or None` — `backend/nexus/api/auth.py:244`, `backend/nexus/portal/konta.py:189`; `NEXUS_COOKIE_DOMAIN` — `.env.example:60` |
| Sesja portalu: 14 dni, wygaszanie po 7 dniach bezczynności | `backend/nexus/portal/ustawienia.py`, `konta.py` (`BEZCZYNNOSC`) |
| Sesja aplikacji: 30 dni | `backend/nexus/config.py` (`session_days`) |
| Token odzyskiwania hasła: 30 minut | `backend/nexus/portal/ustawienia.py` (`reset_ttl_minutes`) |
| Hasło konta wyłącznie jako skrót Argon2, minimum 12 znaków | `backend/nexus/portal/konta.py` (`MIN_HASLO`, `auth.hasher.hash`), `backend/nexus/api/auth.py:49-52` |
| Hasło podłączonej skrzynki i hasło do chmury przechowywane czytelnie, bo serwer loguje się nimi w imieniu użytkownika | `backend/nexus/mail.py` (`config_path`, `save_accounts`), `settings.chmura_token_file` |
| Każde konto ma własną przestrzeń; na pliki przypada 2 GB | `owner_id` w `backend/nexus/db.py:45-52` i `models/research.py:28`, `auth.wlasciciel`, `mail.config_path`; limit `config.py:86-87` i `api/files.py:73-79` |
| Kredyty konta i księga ich zmian | `backend/nexus/platnosci/kredyty.py`, `docs/platnosci/KREDYTY.md`, `GET /api/platnosci/kredyty` |
| Usunięcie konta wymaga hasła i słowa potwierdzenia, jest nieodwracalne | `backend/nexus/api/modules/portal.py`, `konta.py` (`usun_konto`) |
| Limity pokazu bez konta: 6 wiadomości, 4 pliki po 8 MB, 500 znaków, 30 minut | `backend/nexus/demo/sesje.py` (`Limity`) |
| Trzy klucze pamięci lokalnej i wpis pamięci sesji `dn-ladowanie` | `frontend/src/theme.ts`, `frontend/src/voice/VoiceMode.tsx`, `frontend/src/modules/research/index.tsx`, `frontend/public/ladowanie/ladowanie.js:32-33` |
| Zasobnik `nexus-share` z plikami przekazanymi przez „Udostępnij” | `frontend/public/share-target.js:14-31`, `frontend/src/share.ts:14-28` |
| Brak analityki i ciasteczek podmiotów trzecich | brak skryptów zewnętrznych w `frontend/index.html` |
| Co trafia do modelu Claude, model domyślny i zapasowy | `backend/nexus/agent/runner.py`, `backend/nexus/agent/prompt.py`, `backend/nexus/config.py` |
| Wyszukiwanie i odczyt stron po stronie Anthropic | `backend/nexus/agent/runner.py` (`WEB_TOOLS`) |
| Rozmowa głosowa przez Google Cloud: nagranie i tekst czytany na głos, model lokalny jako zapas | `backend/nexus/voice.py:97-99` i `:179-181`, `backend/nexus/voice_google.py`, `settings.voice_google_key_file` |
| Serwer poczty jako odbiorca: wiadomości portalu i wysyłka zlecona agentowi | `backend/nexus/portal/poczta_portalu.py` (`NadawcaSmtp`), `backend/nexus/mail.py` |
| Poczta, kalendarz i chmura osobista jako kategorie danych | `backend/nexus/mail.py`, `backend/nexus/calendar.py`, `backend/nexus/cloud_service.py`, `backend/nexus/config.py:49-52` |
| Strony użytkownika pod `/s/<adres>` mogą wczytywać skrypty zewnętrzne | `backend/nexus/api/modules/strony.py:35-44` (`SITE_CSP`) |
| Plany Osobisty, Pro, Zespół — wszystkie płatne; Osobisty z 7-dniowym okresem próbnym | `backend/nexus/platnosci/plany.py` (`KATALOG`, `okres_probny_dni`), `backend/nexus/platnosci/uslugi.py` |
| Pakiety kredytów do dokupienia poza subskrypcją | `backend/nexus/platnosci/pakiety.py`, `POST /api/platnosci/pakiety/checkout` |
| Płatności i faktury przez Stripe, bez przyjmowania danych kart | `backend/nexus/platnosci/klient.py`, `docs/platnosci/README.md` |
| Działania poza Nexusem dopiero po zatwierdzeniu | `backend/nexus/models/biuro.py` (`PendingAction`), `desktop/src/agent/powershellPolicy.js` |

## 3. Trasowanie

Trzy strony prawne są osiągalne: mają wartości w typie `PortalStrona` i wpisy w mapie
`PROSTE` (`frontend/src/portal/trasy.ts:23-25`, `:57-59`) oraz gałęzie w `Zawartosc`
(`frontend/src/portal/Portal.tsx:343-348`). Odsyłacze prowadzą do nich ze stopki portalu
(`Portal.tsx:79-81`). Sprawdza to `frontend/src/portal/weryfikacja-p7.test.tsx`.

Do mapy witryny trafiają przez `STRONY_STALE` (`backend/nexus/portal/kanaly.py:32-34`,
para P6). Trasowanie jest zamknięte — nie zostaje tu nic do zrobienia.

## 4. Utrzymanie: kiedy dokument trzeba zmienić

Zmiana w kodzie wymaga zmiany dokumentu w następujących przypadkach:

| Zmiana w kodzie | Co poprawić |
|---|---|
| Nowa tabela w `backend/nexus/models/**` albo nowa kolumna z danymi osobowymi | rozdz. 3 polityki, rejestr czynności, mapa danych |
| Nowe ciasteczko albo zmiana czasu życia sesji | rozdz. 2 informacji o cookie, rozdz. 8 polityki |
| Nowy klucz w `localStorage`, `sessionStorage` albo nowy zasobnik `Cache Storage` | rozdz. 3 informacji o cookie |
| Zmiana cennika kredytów, przydziału w planie albo katalogu pakietów | rozdz. 3, 4 i 8 polityki, rozdz. 5 regulaminu, CZ-13 rejestru, rozdz. 6 mapy danych |
| Nowa tabela z `owner_id` albo zmiana zakresu rozdzielenia kont | rozdz. 2 polityki, CZ-5 i rozdz. 5 rejestru |
| Nowy dostawca zewnętrzny (analityka, wysyłka, magazyn) | rozdz. 6 i 7 polityki, rejestr czynności; analityka wymaga też okna zgody |
| Zmiana zakresu danych przekazywanych do Claude | rozdz. 5 polityki |
| Dodanie albo usunięcie klucza Google Cloud dla mowy (`voice_google_key_file`) | rozdz. 3, 6, 7 i 10 polityki, CZ-11 rejestru, rozdz. 5 mapy danych |
| Zmiana `NEXUS_CHMURA_URL` na adres poza serwerem Danaco | rozdz. 3, 6 i 7 polityki, CZ-12 rejestru, rozdz. 4 i 5 mapy danych |
| Uruchomienie sprzedaży planów Pro i Zespół | rozdz. 5 regulaminu |
| Rozdzielenie kolekcji w bazie wektorowej albo chmury osobistej między konta | rozdz. 2 i 3 polityki, rozdz. 5 rejestru — dziś opisują stan nierozdzielony |
| Zmiana limitów pokazu bez konta | rozdz. 2 regulaminu |

Każda zmiana dokumentu podnosi `WERSJA` i `OBOWIAZUJE_OD` w `tresc-prawna.ts`. Reguła
działa od pierwszej publikacji: dopóki strony nie są osiągalne (rozdz. 3), redakcja pracuje
na wersji 1.0 z datą pierwszego wydania, bo nie ma wersji wcześniejszej, od której
czytelnik miałby odróżnić obecną.

## 5. Sprawy do rozstrzygnięcia przez właściciela produktu

| Sprawa | Dlaczego |
|---|---|
| Dane rejestrowe spółki: KRS, NIP, adres siedziby | pole `ADMINISTRATOR.daneRejestrowe` jest puste; ustawa o świadczeniu usług drogą elektroniczną wymaga podania danych usługodawcy |
| Inspektor ochrony danych — czy wyznaczony | polityka nie twierdzi ani że jest, ani że go nie ma |
| Rodzaj konta Anthropic, na które zalogowany jest Claude Code CLI | od tego zależy, czy przekazane treści mogą posłużyć do rozwoju modeli; polityka odsyła dziś do warunków konta, zamiast rozstrzygać |
| Umowa powierzenia przetwarzania z Anthropic, Google i ze Stripe | art. 28 RODO; bez niej rejestr czynności ma lukę |
| Kwalifikacja dostawcy serwera poczty portalu | polityka (rozdz. 6) i rejestr (rozdz. 3) opisują go zgodnie jako odbiorcę technicznego. Jeżeli dostawca przechowuje wiadomości portalu na zlecenie Danaco, potrzebna jest umowa z art. 28 RODO i zmiana obu dokumentów |
| Czy rozmowa głosowa ma iść przez Google Cloud | dziś rozstrzyga o tym obecność pliku `dane/app/google-api-key`, a nie osobne ustawienie produktu; przy kluczu nagranie głosu trafia do Google przy każdej wypowiedzi (CZ-11) |
| Instrument przekazania poza EOG | rozdz. 7 polityki wskazuje rozdział V RODO ogólnie, bo konkretny instrument wynika z umowy |
| Przegląd prawniczy całości | przytoczone przepisy i terminy wymagają potwierdzenia przez radcę prawnego przed publikacją |

---

*Koniec dokumentu. Zgodność prawna produktu — etap 1B, 2026-09-20.*

---
*Danaco Nexus — Personal AI Workspace · etap 1B · status Deweloperski*
*© 2026 Danaco Holding Group Sp. z o.o. Wszelkie prawa zastrzeżone — Dariusz Naharnowicz.*
*Kontakt: support@danaco-group.pl*
