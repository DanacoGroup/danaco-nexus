# Moduł Płatności: subskrypcje Stripe, faktury, kupony i limity planów

| | |
|---|---|
| **Zakres** | `backend/nexus/platnosci/`, `backend/nexus/api/modules/platnosci.py`, `backend/tests/test_platnosci.py`, `backend/tests/test_kredyty.py`, `frontend/src/platnosci/`, `frontend/src/portal/strony/Cennik.tsx`, sekcja `NEXUS_PLATNOSCI_*` w `.env.example` |
| **Treść wiążąca cennika** | `backend/nexus/platnosci/plany.py` (katalog planów) — jedyne źródło nazw, zakresów, przydziałów kredytów i limitów |
| **Kredyty** | `docs/platnosci/KREDYTY.md` — przelicznik, przydziały i zasady naliczania |
| **Status** | Gotowe do konfiguracji. Wszystkie trzy plany są płatne; najniższy zaczyna się 7-dniowym okresem próbnym z podaniem karty. Sprzedaż rusza po założeniu produktów, cen planów i cen pakietów kredytów w panelu Stripe oraz uzupełnieniu zmiennych środowiskowych. |
| **Data** | 2026-09-20 |

## Spis treści

1. [Decyzja: bez biblioteki `stripe`](#1-decyzja-bez-biblioteki-stripe)
2. [Model danych](#2-model-danych)
3. [Wykaz tras](#3-wykaz-tras)
4. [Ścieżka zakupu i stany brzegowe](#4-ścieżka-zakupu-i-stany-brzegowe)
5. [Mapa zdarzeń Stripe](#5-mapa-zdarzeń-stripe)
6. [Zmienne środowiskowe](#6-zmienne-środowiskowe)
7. [Konfiguracja produktów i cen w panelu Stripe](#7-konfiguracja-produktów-i-cen-w-panelu-stripe)
8. [Testowanie webhooków](#8-testowanie-webhooków)
9. [Limity planu: kredyty i reszta katalogu](#9-limity-planu-kredyty-i-reszta-katalogu)
10. [Wpięcie ekranów w interfejs](#10-wpięcie-ekranów-w-interfejs)
11. [Zasady bezpieczeństwa przyjęte w module](#11-zasady-bezpieczeństwa-przyjęte-w-module)
12. [Plan Grupa: miejsca, wspólny zakres pracy, przekazanie roli](#12-plan-grupa-miejsca-wspólny-zakres-pracy-przekazanie-roli)

## 1. Decyzja: bez biblioteki `stripe`

Biblioteki `stripe` nie ma w środowisku projektu (`.venv`), a instalowanie zależności
z sieci było poza zakresem zadania. Moduł rozmawia ze Stripe przez publiczne API REST,
korzystając z `httpx` — zależności, którą projekt już ma (`backend/pyproject.toml`).

Dostęp opisuje protokół `KlientStripe` (`backend/nexus/platnosci/klient.py`) z jedną
implementacją produkcyjną `KlientHttpStripe`. Dzięki temu:

- testy podstawiają atrapę protokołu i nie dotykają sieci,
- przejście na oficjalną bibliotekę sprowadza się do napisania drugiej implementacji
  protokołu i podstawienia jej w `nexus/api/modules/platnosci.py` (`_klient`) albo
  przez `app.state.platnosci_klient`; reszta modułu zostaje bez zmian,
- weryfikacja podpisu webhooka jest własna (`platnosci/podpis.py`, `hmac` + `hashlib`)
  i nie wymaga żadnej zależności zewnętrznej.

Punkt rozszerzenia: `app.state.platnosci_klient`. Obiekt spełniający protokół
`KlientStripe` przypisany do tego pola ma pierwszeństwo przed implementacją HTTP.

## 2. Model danych

Tabele powstają razem z pozostałymi w `Database.create_schema()`; rejestruje je import
routera modułu (`nexus/api/modules/platnosci.py` → `nexus.platnosci.model`), który
wykonuje się przed cyklem życia aplikacji. Wszystkie kwoty są w **groszach** (liczby
całkowite) — w module nie ma liczb zmiennoprzecinkowych.

| Tabela | Klasa | Zawartość |
|---|---|---|
| `platnosci_plany` | `Plan` | `kod` (klucz), `nazwa`, `opis`, `cena_miesiac_gr`, `cena_rok_gr`, `limity` (JSON), `kolejnosc`, `aktywny`, `updated_at` |
| `platnosci_subskrypcje` | `Subskrypcja` | `uzytkownik` (unikalny), `plan_kod`, `status`, `okres`, `stripe_customer_id`, `stripe_subscription_id`, `okres_od`, `okres_do`, `anuluj_na_koniec`, `kupon` |
| `platnosci_faktury` | `Faktura` | `stripe_invoice_id` (unikalny), `uzytkownik`, `numer`, `kwota_gr`, `waluta`, `status`, `pdf_url`, `strona_url`, `wystawiona_at`, `oplacona_at` |
| `platnosci_kupony` | `Kupon` | `kod` (unikalny), `stripe_promotion_id`, `stripe_coupon_id`, `rabat_procent`, `rabat_gr`, `waluta`, `opis`, `aktywny`, `wygasa_at` |
| `platnosci_zdarzenia` | `ZdarzenieStripe` | `id` = identyfikator zdarzenia Stripe (klucz główny, podstawa idempotencji), `typ`, `status`, `blad`, `ladunek` (JSON), `otrzymane_at`, `przetworzone_at` |

Katalog planów (nazwy, opisy, przydział kredytów, limity, wykaz zawartości) mieszka
w kodzie — `backend/nexus/platnosci/plany.py` — i jest jedynym źródłem tej treści.
Przy starcie API `synchronizuj_plany()` przepisuje katalog do tabeli `platnosci_plany`
i dokłada kwoty ze zmiennej `NEXUS_PLATNOSCI_KWOTY`. Plan jest do kupienia tylko wtedy,
gdy sprzedaż jest włączona (jest klucz Stripe) i plan ma kwotę oraz identyfikator ceny;
inaczej interfejs pokazuje go jako „Wkrótce”. Warunek klucza
zamyka przypadek niepełnej konfiguracji — ceny i kwoty w środowisku, ale klucz pusty
albo nie do odczytu — w którym cennik pokazywałby „Dostępny”, a zakup kończył się `409`.

Stany subskrypcji (`Subskrypcja.status`) i ich odpowiedniki w Stripe:

| Nexus | Stripe | Uprawnia do planu |
|---|---|---|
| `brak` | — (konto bez zakupu) | nie (plan Osobisty) |
| `probna` | `trialing` | tak |
| `aktywna` | `active` | tak |
| `zalegla` | `past_due`, `unpaid` | tak (okres łaski do decyzji Stripe) |
| `niepelna` | `incomplete` | nie |
| `anulowana` | `canceled`, `incomplete_expired`, `paused` | nie (powrót do planu Osobistego) |

## 3. Wykaz tras

Prefiks `/api/platnosci`. Sesji wymagają wszystkie trasy poza webhookiem i publicznym
cennikiem, a trasy zmieniające stan dodatkowo nagłówka aplikacji `X-Nexus-Request: 1`
(ochrona CSRF z `nexus/api/auth.py`).

| Metoda | Trasa | Ochrona | Działanie |
|---|---|---|---|
| GET | `/api/platnosci/cennik` | **brak** (publiczna) | Cennik dla portalu i strony produktu: plany, kwoty, przydział kredytów, dni okresu próbnego i możliwość zakupu. Bez danych konta |
| GET | `/api/platnosci/kredyty` | sesja | Saldo kredytów konta, sumy przydziałów i zużycia oraz 30 ostatnich zmian |
| GET | `/api/platnosci/pakiety` | sesja | Pakiety kredytów do dokupienia poza subskrypcją |
| POST | `/api/platnosci/pakiety/checkout` | sesja + CSRF | Jednorazowy zakup pakietu kredytów (Stripe `mode: "payment"`) |
| GET | `/api/platnosci/plany` | sesja | To samo co wyżej plus `subskrypcja` konta wraz ze stanem sprzedaży |
| GET | `/api/platnosci/subskrypcja` | sesja | Stan subskrypcji, limity planu, `stan` i ewentualna `faktura_do_zaplaty` |
| POST | `/api/platnosci/checkout` | sesja + CSRF | Zakup planu; przy opłaconym planie zwraca `tryb: "portal"` i adres zmiany planu |
| POST | `/api/platnosci/portal` | sesja + CSRF | Sesja Billing Portal (karta, rezygnacja, historia) |
| POST | `/api/platnosci/rezygnacja` | sesja + CSRF | Portal rozliczeniowy otwarty od razu na rezygnacji z bieżącego planu |
| POST | `/api/platnosci/kupon` | sesja + CSRF | Sprawdzenie kodu rabatowego w Stripe |
| POST | `/api/platnosci/powrot` | sesja + CSRF | Uzgodnienie stanu po powrocie z Checkoutu, bez czekania na webhook |
| GET | `/api/platnosci/faktury` | sesja | Faktury z bazy; `?odswiez=1` pobiera je najpierw ze Stripe |
| POST | `/api/platnosci/webhook` | podpis Stripe | Przyjęcie zdarzenia; **bez sesji i bez ciasteczek** |

Kody odpowiedzi warte uwagi: `402` — konto nie ma kredytów na kolejne zlecenie
(`BrakKredytow`, `POST /api/rozmowy/{id}/messages`) albo działanie przekracza limit planu
(`LimitPrzekroczony`), `409` — sprzedaż niewłączona, plan spoza sprzedaży, plan już
aktywny, brak zakupu albo rezygnacja już złożona, `400` — nieznany plan, nieznany
okres, nieważny kupon albo zły podpis webhooka, `503` — brak klucza Stripe przy
wywołaniu, które mimo to dotarło do klienta HTTP.

## 4. Ścieżka zakupu i stany brzegowe

Cennik jest jeden: katalog z `backend/nexus/platnosci/plany.py` plus kwoty ze
środowiska. Ta sama odpowiedź zasila moduł Płatności (`/plany`) i publiczny cennik
portalu (`/cennik`, strona `frontend/src/portal/strony/Cennik.tsx`), więc nazwy,
zakresy i kwoty nie mogą się rozjechać między powierzchniami. Walutę też rozstrzyga
serwer: pole `waluta` (z `NEXUS_PLATNOSCI_WALUTA`) idzie w odpowiedzi cennika, kuponu
i faktury, a funkcja `kwota()` w `frontend/src/platnosci/api.ts` formatuje kwotę według
tego pola — interfejs nie zakłada złotych.

Interfejs nie ma własnej treści o planach: cennik portalu i ekran planów w module
biorą nazwy, zakresy, kwoty, przydział kredytów i dni okresu próbnego z tej jednej
odpowiedzi. Subskrypcja jest kluczowana identyfikatorem konta (`UserSession.owner_id`),
tym samym, po którym rozdzielone są rozmowy, pliki i kredyty — nie loginem instalacji.

Zakres planu opisuje wyłącznie to, co jest w kodzie. Katalog nie zapowiada funkcji spoza
rejestru narzędzi (`backend/nexus/tools/`) ani nie sprzedaje limitów, których nikt nie
egzekwuje — liczby zadań równoległych ani automatyzacji (rozdz. 9). Jedyna liczba planu
naprawdę egzekwowana to przydział kredytów (`kredyty_okresowo`) i tylko ona jest
pokazywana w cenniku; plany Pro i Grupa mają poza tym zdanie o zawartości planu niższego
oraz zapowiedź, że zakres ponad niego zostanie podany przy starcie sprzedaży.

Ścieżka od kliknięcia do zakupu i po zakupie:

| Krok | Skąd | Dokąd |
|---|---|---|
| Wybór planu | cennik portalu → „Kup w aplikacji” albo moduł Płatności → „Wybierz plan” | `POST /checkout` |
| Płatność | Stripe Checkout (`tryb: "checkout"`) | `?zakup=udany&sesja=…` albo `?zakup=anulowany` |
| Potwierdzenie | `POST /powrot` uzgadnia stan bez czekania na webhook | karta „Zakup przyjęty” z planem i datą odnowienia |
| Faktura | `GET /faktury?odswiez=1` zaraz po powrocie | lista faktur z PDF i podglądem |
| Dokupienie kredytów | moduł Płatności → saldo kredytów → wybór pakietu | `POST /pakiety/checkout`; kredyty dopisuje webhook po potwierdzeniu wpłaty |
| Zmiana planu | `POST /checkout` przy opłaconym planie (`tryb: "portal"`) | przepływ `subscription_update_confirm` w Billing Portal, z wybraną ceną i kuponem |
| Rezygnacja | `POST /rezygnacja` | przepływ `subscription_cancel`, powrót na `?powrot=rozliczenia` |

Druga sesja Checkout założyłaby drugą subskrypcję temu samemu klientowi, dlatego
zmiana planu przy opłaconym planie **zawsze** idzie przez portal rozliczeniowy. Serwer
przekazuje tam pozycję bieżącej subskrypcji, identyfikator ceny wybranego planu oraz kod
promocyjny, jeżeli został podany — portal otwiera się na potwierdzeniu zmiany, a nie na
liście planów z panelu Stripe, więc wybór z cennika Nexusa nie jest powtarzany.

Stany brzegowe rozstrzyga `backend/nexus/platnosci/stany.py` (funkcja `stan_sprzedazy`)
i to serwer podaje tytuł, komunikat oraz działanie; interfejs (`StanPlanu.tsx`) zamienia
je na widok i przycisk:

| Kod stanu | Kiedy | Co widzi użytkownik |
|---|---|---|
| `sprzedaz_wylaczona` | brak klucza Stripe | Informacja, że konto pracuje na przydzielonych kredytach; zakup i kupon kończą się `409` z tym samym zdaniem |
| `plan_bezplatny` | konto bez zakupu (kod stanu historyczny) | „Konto bez wykupionego planu”: praca na przydzielonych kredytach i przycisk „Wybierz plan” |
| `plan_aktywny` / `okres_probny` | `active`, `trialing` | Data odnowienia i przejście do rozliczeń |
| `platnosc_niedokonczona` | `incomplete` | Co zrobić, żeby dokończyć płatność |
| `platnosc_odrzucona` | `past_due`, `unpaid` | Przycisk „Zapłać fakturę” (gdy jest nieopłacona faktura) albo poprawa karty |
| `subskrypcja_wygasla` | `canceled` albo zamknięty okres bez odnowienia | Powrót do stanu bez wykupionego planu i przycisk „Wybierz plan” |
| `rezygnacja_zlozona` | `cancel_at_period_end` | Data zakończenia i możliwość wznowienia; po minięciu opłaconego okresu — informacja o zakończeniu planu i przycisk „Wybierz plan”. Rozstrzyga przed `subskrypcja_wygasla`, bo odnowienia nie miało być |

Kupon nieważny nie jest stanem konta, tylko odpowiedzią `400` na `POST /kupon`; treść
bierze się z `KOMUNIKATY_KUPONU` i rozróżnia kod nieznany, wyłączony, przeterminowany
(z datą) oraz wyczerpany. Każdy komunikat kończy się podpowiedzią, co zrobić dalej.

## 5. Mapa zdarzeń Stripe

Kolejność jest stała: **zapis zdarzenia → zmiana stanu → zamknięcie wpisu**. Zdarzenie
trafia najpierw do `platnosci_zdarzenia` (klucz główny = identyfikator zdarzenia), więc
ponowne doręczenie tego samego zdarzenia kończy się odpowiedzią `{"duplikat": true}`
bez żadnej zmiany w bazie.

| Zdarzenie | Obsługa | Skutek |
|---|---|---|
| `checkout.session.completed` | `_checkout_zakonczony` | Powiązanie konta z klientem Stripe i wybranym planem (pełny stan przyniesie zdarzenie subskrypcji). Sesja z metadaną `pakiet` nie dotyka subskrypcji — dopisuje kredyty pakietu |
| `customer.subscription.created` | `_subskrypcja_zmieniona` | Zapis planu (rozpoznanego po identyfikatorze ceny), okresu, stanu i dat |
| `customer.subscription.updated` | `_subskrypcja_zmieniona` | To samo: zmiana planu, wznowienie, zaległość, `cancel_at_period_end` |
| `customer.subscription.deleted` | `_subskrypcja_usunieta` | Stan `anulowana`, powrót do planu domyślnego |
| `invoice.paid` | `_faktura` | Faktura w historii ze stanem `paid`, adresem PDF i adresem podglądu; przy fakturze subskrypcji także przydział kredytów na nowy okres |
| `invoice.payment_failed` | `_faktura` | Faktura w historii ze stanem nieopłaconym |

Zdarzenia spoza wykazu są zapisywane ze stanem `pominiete` i kwitowane odpowiedzią
`200` — Stripe nie ponawia ich bez potrzeby. Błąd przetwarzania kończy się stanem
`blad` we wpisie i odpowiedzią `500`, czyli ponowieniem doręczenia przez Stripe.

Konto Stripe jest wspólne dla Nexusa, danaco-lex.pl i e-kancelaria.app, więc webhook
dostaje też faktury, subskrypcje i sesje zakupu innych produktów. Przed obsługą
`_uzytkownik` (`platnosci/zdarzenia.py`) ustala konto Nexusa: z `metadata.uzytkownik`,
`client_reference_id` albo metadanych subskrypcji na fakturze (`subscription_details`,
od API 2025-03-31 `parent.subscription_details`), a gdy ich brak — po kliencie Stripe
zapisanym w `platnosci_subskrypcje` (kasa zakłada go przed każdą sesją zakupu). Oznaczenie
liczy się tylko wtedy, gdy wskazuje konto Nexusa: identyfikator konta w zapisie z łącznikami,
adres konta portalu albo login administratora tej instalacji. Zdarzenie bez konta Nexusa
dostaje stan `pominiete`, w polu `blad` opis przyczyny, i niczego nie zmienia: nie zakłada
rekordu subskrypcji, nie zapisuje faktury, nie dopisuje kredytów. Nie trafia też do
właściciela instalacji. Zdarzenie z ceną z cennika Nexusa, ale bez konta (np. subskrypcja
założona ręcznie w panelu Stripe), ma w `blad` osobny opis i ostrzeżenie w dzienniku
aplikacji — do wyjaśnienia ręcznie.

## 6. Zmienne środowiskowe

Pełna sekcja znajduje się na końcu `.env.example`. W repozytorium nie ma i nie może się
znaleźć żadnego klucza, sekretu ani identyfikatora ceny.

| Zmienna | Znaczenie |
|---|---|
| `NEXUS_PLATNOSCI_STRIPE_KLUCZ` | Klucz tajny konta (`sk_…`). Pusty = sprzedaż wyłączona |
| `NEXUS_PLATNOSCI_STRIPE_KLUCZ_PLIK` | Plik z kluczem (uprawnienia 600); ma pierwszeństwo przed wartością wprost |
| `NEXUS_PLATNOSCI_WEBHOOK_SEKRET` | Sekret podpisu webhooka (`whsec_…`) |
| `NEXUS_PLATNOSCI_WEBHOOK_SEKRET_PLIK` | Plik z sekretem webhooka |
| `NEXUS_PLATNOSCI_CENY` | `plan:okres=price_…;pakiet:kod=price_…` — identyfikatory cen z panelu Stripe. Subskrypcja planu ma okres (`miesiac`, `rok`), pakiet kredytów zamiast okresu ma swój kod (`maly`, `sredni`, `duzy`); pozycja z innym drugim członem jest pomijana z ostrzeżeniem w dzienniku |
| `NEXUS_PLATNOSCI_KWOTY` | `plan:okres=kwota_w_groszach` — kwoty pokazywane w interfejsie |
| `NEXUS_PLATNOSCI_WALUTA` | Waluta rozliczeń (domyślnie `pln`) |
| `NEXUS_PLATNOSCI_API_URL` | Adres API Stripe (domyślnie `https://api.stripe.com/v1`) |
| `NEXUS_PLATNOSCI_WERSJA_API` | Nagłówek `Stripe-Version`; pusty = wersja konta |
| `NEXUS_PLATNOSCI_TIMEOUT_S` | Limit czasu jednego wywołania API (domyślnie 20 s) |
| `NEXUS_PLATNOSCI_ADRES_POWROTU` | Adres powrotu po zakupie; pusty = `NEXUS_PUBLIC_URL` |

Najprościej jednym poleceniem — skrypt pyta o klucz i ceny, zapisuje je z prawami 600,
uzupełnia `.env`, restartuje API i sprawdza, czy cennik naprawdę pokazuje przyciski zakupu:

```bash
deploy/zapisz-stripe.sh
```

Skrypt przyjmuje klucze prawdziwe (`sk_live_…`) i testowe (`sk_test_…`). Sprzedaż testowa
z prawdziwymi płatnościami to klucz `sk_live_…` — wtedy zakupy testerów są rzeczywiste
i widać, czy ktoś naprawdę płaci. Tryb testowy Stripe służy wyłącznie do sprawdzenia, czy
ścieżka zakupu działa, i nie zastępuje pierwszej sprzedaży.

Ręcznie, gdyby skrypt nie pasował:

```bash
install -m 600 -o danaco-serwis -g danaco-serwis /dev/null /danaco/projekty/danaco-nexus/dane/app/stripe-klucz
printf '%s' 'sk_live_…' > /danaco/projekty/danaco-nexus/dane/app/stripe-klucz
```

## 7. Konfiguracja produktów i cen w panelu Stripe

Do wykonania ręcznie, raz, przed uruchomieniem sprzedaży.

1. **Konto i waluta.** W panelu Stripe ustaw walutę rozliczeń na PLN i uzupełnij dane
   firmy (Danaco Holding Group Sp. z o.o.) — trafiają one na faktury.
2. **Produkty.** *Product catalog → Add product*: załóż produkty **Danaco Nexus
   Osobisty**, **Danaco Nexus Pro** i **Danaco Nexus Grupa**. Wszystkie trzy plany są
   płatne, więc każdy potrzebuje produktu; Osobisty zaczyna się okresem próbnym, a nie
   bezpłatnym planem.
3. **Ceny planów.** Do każdego produktu dodaj dwie ceny cykliczne w PLN: miesięczną
   i roczną. Zapisz ich identyfikatory (`price_…`).
4. **Ceny pakietów kredytów.** Załóż produkt **Danaco Nexus — kredyty** i dodaj mu
   trzy ceny **jednorazowe** (nie cykliczne) w PLN: dla pakietu małego, średniego
   i dużego (`backend/nexus/platnosci/pakiety.py`). Pakiet to jedna płatność, więc cena
   cykliczna nie zadziała.
5. **Cennik w środowisku.** Uzupełnij `NEXUS_PLATNOSCI_CENY` cenami planów i pakietów, np.
   `pro:miesiac=price_…;pro:rok=price_…;zespol:miesiac=price_…;zespol:rok=price_…;`
   `pakiet:maly=price_…;pakiet:sredni=price_…;pakiet:duzy=price_…`,
   oraz `NEXUS_PLATNOSCI_KWOTY` tymi samymi kwotami, które ustawiono w Stripe (w groszach).
   Bez pozycji `pakiet:<kod>` ekran kredytów pokazuje „Dokupienie kredytów będzie możliwe,
   gdy ruszy sprzedaż”, nawet przy włączonej sprzedaży planów.
   Rozjazd kwot oznacza, że interfejs pokazuje inną cenę niż pobiera Stripe — to jedyne
   miejsce, w którym trzeba pilnować zgodności ręcznie.
6. **Portal rozliczeniowy.** *Settings → Billing → Customer portal*: włącz portal, zezwól
   na zmianę metody płatności, rezygnację i pobieranie faktur, ustaw język polski.
7. **Faktury.** *Settings → Billing → Invoices*: włącz automatyczne wystawianie faktur
   i generowanie PDF — bez tego pole `invoice_pdf` pozostaje puste i lista faktur nie ma
   czego pokazać.
8. **Kupony.** *Product catalog → Coupons*: załóż kupon i **kod promocyjny** (kod
   promocyjny, nie sam kupon — moduł szuka kodu przez `/v1/promotion_codes`; od API
   2025-09-30.clover kod podaje tylko identyfikator kuponu, więc moduł dociąga go
   z `/v1/coupons/{id}`).
9. **Webhook.** *Developers → Webhooks → Add endpoint*: adres
   `https://<adres-nexusa>/api/platnosci/webhook` i sześć zdarzeń obsługiwanych przez
   `OBSLUGA` w `backend/nexus/platnosci/zdarzenia.py` (rozdz. 5):
   `checkout.session.completed`, `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`,
   `invoice.payment_failed`. Konto Stripe jest wspólne z danaco-lex.pl i e-kancelaria.app,
   więc punkt dostanie zdarzenia tych typów z całego konta, także cudze faktury i subskrypcje.
   Obsługa pomija zdarzenia bez konta Nexusa (stan `pominiete`, bez zmian w bazie — rozdz. 5).
   Wersja API punktu może zostać wersją konta (2026-06-24.dahlia): moduł czyta obiekty i w tym
   kształcie, i w starszym. Sekret (`whsec_…`) zapisz w `NEXUS_PLATNOSCI_WEBHOOK_SEKRET_PLIK`.
10. **Restart usług.** Katalog planów i kwoty wczytują się przy starcie API.

## 8. Testowanie webhooków

**Bez sieci (test regresyjny).** `backend/tests/test_platnosci.py` podpisuje utrwalone
ładunki zdarzeń funkcją `podpisz_ladunek` i wysyła je na trasę webhooka. Sprawdzane są:
brak podpisu (400), zły podpis (400), zapis stanu, idempotencja powtórzonego zdarzenia,
anulowanie i faktury. Ten sam plik pokrywa stany brzegowe sprzedaży: serwer bez klucza
Stripe, płatność odrzuconą i niedokończoną, wygaśnięcie subskrypcji, złożoną rezygnację,
zmianę planu przez portal oraz kupon nieznany, przeterminowany i wyczerpany. Widoki
tych stanów sprawdza `frontend/src/platnosci/platnosci.test.tsx`.

```bash
.venv/bin/python -m pytest backend/tests/test_platnosci.py -q
```

**Z kontem testowym Stripe.** Na maszynie z dostępem do sieci i narzędziem `stripe`:

```bash
stripe login
stripe listen --forward-to http://127.0.0.1:8000/api/platnosci/webhook
# sekret z wyjścia polecenia (whsec_…) wpisz do NEXUS_PLATNOSCI_WEBHOOK_SEKRET
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger invoice.paid
```

**Sprawdzenie idempotencji na żywo.** W panelu Stripe (*Webhooks → wybrane zdarzenie →
Resend*) wyślij to samo zdarzenie drugi raz. Odpowiedź powinna brzmieć
`{"otrzymano": true, "duplikat": true, …}`, a w tabeli `platnosci_zdarzenia` ma pozostać
jeden wiersz.

**Dziennik.** Przebieg przetwarzania widać w `platnosci_zdarzenia` (kolumny `status`,
`blad`, `przetworzone_at`) oraz w dzienniku API (`dane/app/logs`), który czyta `lnav`.

## 9. Limity planu: kredyty i reszta katalogu

Najważniejszy limit planu to **przydział kredytów** — to on rozstrzyga, ile pracy konto
wykona między odnowieniami. Opisuje go
[`docs/platnosci/KREDYTY.md`](KREDYTY.md): przelicznik pracy na kredyty, przydziały
z planu, pakiety do dokupienia i zasady naliczania. Kod: `backend/nexus/platnosci/kredyty.py`.

| Gdzie | Co się dzieje |
|---|---|
| `POST /api/rozmowy/{id}/messages` (`backend/nexus/api/conversations.py`) | `sprawdz_przed_zleceniem` zatrzymuje zlecenie przed rozpoczęciem pracy; puste konto dostaje `402` z powodem |
| Zakończony przebieg (`backend/nexus/agent/runner.py`) | `obciaz` pomniejsza saldo o koszt policzony ze zużycia modelu i dopłat za ciężkie narzędzia |
| `checkout.session.completed` z metadaną `pakiet`, `invoice.paid` subskrypcji | przydział kredytów pakietu albo nowego okresu (`backend/nexus/platnosci/zdarzenia.py`) |
| `GET /api/platnosci/kredyty` | saldo, sumy i 30 ostatnich zmian dla widoku `frontend/src/platnosci/Kredyty.tsx` |

Kredyty są kluczowane kontem (`owner_id`), tak samo jak subskrypcja, rozmowy i pliki.
Żadna odpowiedź ani komunikat błędu nie zdradza silnika ani kont usługodawcy; pilnuje
tego `backend/tests/test_kredyty.py`.

Pozostałe limity planu rozstrzyga `limity_uzytkownika()`
(`backend/nexus/platnosci/uprawnienia.py`) na podstawie aktywnej subskrypcji:

| Limit | Gdzie egzekwowany |
|---|---|
| `zadania_rownolegle` | przyjęcie wiadomości w rozmowie (`backend/nexus/api/conversations.py`) — ponad limit odpowiedź `409` z nazwą planu |
| `przestrzen_mb` | przyjęcie pliku (`backend/nexus/api/files.py`) — pełna przestrzeń kończy się `413` |
| `automatyzacje` | **nigdzie** — modułu automatyzacji w repozytorium nie ma, więc katalog tej liczby nie sprzedaje |
| `konta` | **nigdzie** — do czasu zakładania kont zespołowych przez portal |

Dla limitów bez wpięcia zostaje `sprawdz_limit(database, rodzaj, wartosc, uzytkownik="")`,
która zgłasza `LimitPrzekroczony` (`status = 402`).

`plik_mb` nie jest cechą planu: pozycje katalogu go nie zawierają, a
`limity_pozycji()` (`backend/nexus/platnosci/plany.py`) dopisuje wartość
`NEXUS_UPLOAD_LIMIT_MB` (`backend/nexus/api/files.py`) wspólną dla wszystkich planów.
Przestrzeń konta to co innego: jest cechą planu (`przestrzen_mb`) i rośnie wraz z nim.

Zalecany sposób zamiany wyjątku na odpowiedź HTTP w module:

```python
try:
    await sprawdz_limit(database, "konta", liczba_kont + 1)
except LimitPrzekroczony as blad:
    raise HTTPException(blad.status, str(blad)) from blad
```

## 10. Wpięcie ekranów w interfejs

Ekrany leżą w `frontend/src/platnosci/`:

| Plik | Zawartość |
|---|---|
| `api.ts` | Klient API, typy stanu sprzedaży, formatowanie kwot w złotych i dat w zapisie polskim |
| `Kredyty.tsx` | Saldo kredytów, historia zmian i dokupienie pakietu (`POST /pakiety/checkout`) |
| `BrakKredytow.tsx` | Stan „konto bez kredytów” pokazywany w oknie rozmowy po odmowie `402`, z przejściem do dokupienia |
| `Plany.tsx` | Wybór planu: przełącznik miesiąc/rok, kod rabatowy, przydział kredytów, okres próbny, zakup albo zmiana planu |
| `MojaSubskrypcja.tsx` | Stan planu, limity, faktury (z zapłatą zaległej) i rezygnacja |
| `StanPlanu.tsx` | Widok stanu sprzedaży: tytuł, komunikat i jedno działanie wskazane przez serwer |
| `index.tsx` | Strona modułu i powroty ze Stripe (`?zakup=udany&sesja=…`, `?zakup=anulowany`, `?powrot=rozliczenia`) |
| `platnosci.test.tsx` | Testy widoków: stany brzegowe, rezygnacja, zaległa faktura, powroty |

Rejestr interfejsu wykrywa moduły wzorcem `src/modules/*/index.tsx`. Moduł jest już
zarejestrowany plikiem `frontend/src/modules/platnosci/index.tsx`, który wskazuje na kod
ekranów:

```ts
// Rejestracja modułu Płatności. Kod modułu mieszka w src/platnosci/.
export { module } from "../../platnosci";
```

Adresy powrotu ze Stripe wskazują na `/m/platnosci`, czyli na ten właśnie moduł, więc
ścieżka zakupu jest domknięta po stronie interfejsu. Stripe jest już skonfigurowany:
`GET /api/platnosci/cennik` na produkcji odpowiada `"sprzedaz_aktywna": true`
(stan na 21.09.2026).

## 11. Zasady bezpieczeństwa przyjęte w module

- Publiczny jest wyłącznie cennik (`GET /api/platnosci/cennik`): katalog planów i kwoty,
  czyli treść przeznaczona do publikacji. Żadne pole tej odpowiedzi nie dotyczy konta.
- Klucze i sekrety wyłącznie ze środowiska albo z plików wskazanych środowiskiem; nic
  z tego nie trafia do repozytorium ani do odpowiedzi API.
- Cenę rozstrzyga serwer. Żądanie zakupu niesie wyłącznie kod planu, okres rozliczeniowy
  i opcjonalny kod rabatowy; identyfikator ceny pochodzi z konfiguracji, a nie od klienta.
- Webhook nie korzysta z sesji ani z ciasteczek. Brak nagłówka `Stripe-Signature`, zły
  podpis albo znacznik czasu poza oknem 300 s kończą się odpowiedzią `400`, zanim treść
  zostanie w ogóle rozebrana.
- Pozostałe punkty zmieniające stan działają pod istniejącą ochroną sesji i CSRF.
- Zdarzenie jest zapisywane przed zmianą stanu, a jego identyfikator jest kluczem
  głównym — to jedyny mechanizm idempotencji i nie wymaga dodatkowej blokady.
- Testy nie łączą się z siecią: Stripe zastępuje atrapa protokołu `KlientStripe`.

---

## 12. Plan Grupa: miejsca, wspólny zakres pracy, przekazanie roli

Plan `zespol` (w interfejsie: **Grupa**) rozlicza się **za każdego użytkownika**, a zakres
pracy jest wspólny i kupuje go założyciel. Do wrześniowej zmiany był to sam opis w cenniku:
plan dawało się kupić, ale nie dawało się nikogo do grupy dodać.

**Rozliczenie.** Pozycja kasy dla tego planu ma `adjustable_quantity` (od 2 do 20 miejsc) —
kupujący ustala liczbę w kasie Stripe i zmienia ją później w portalu rozliczeniowym
(`platnosci/uslugi.py:_pozycja_zakupu`). Ilość z pozycji subskrypcji zapisuje webhook do
`platnosci_subskrypcje.miejsca` (`_miejsca_subskrypcji`). To ona, a nie `limity["konta"]`
z katalogu planów, rozstrzyga pojemność grupy — limit katalogu jest wartością zastępczą,
dopóki subskrypcji nie ma (konto testowe, chwila przed pierwszą płatnością).

**Kto płaci.** `platnosci/grupy.py:konto_rozliczeniowe` zwraca konto, z którego schodzi
praca: dla osoby poza grupą ją samą, dla członka — założyciela. Wywołują je cztery miejsca
i tylko te cztery: sprawdzenie przed zleceniem (`api/conversations.py`), naliczenie po
przebiegu (`agent/runner.py`), szybka akcja rozszerzenia (`api/modules/rozszerzenie.py`,
sprawdzenie i obciążenie) i widok wykorzystania (`api/modules/platnosci.py`).

**Limity planu.** Członek grupy, której założyciel ma opłaconą subskrypcję planu Grupa
(status z `STATUSY_UPRAWNIAJACE`), dostaje limity tego planu: `uprawnienia.limity_uzytkownika`
bierze je z `grupy.subskrypcja_grupy`, więc obejmuje to wszystkie miejsca egzekwowania
(zadania naraz, przestrzeń, konto Nextcloud z synchronizacją). Po wyjściu z grupy, jej
rozwiązaniu albo wygaśnięciu subskrypcji założyciela członek wraca do limitów własnego planu;
limit jego konta Nextcloud uzgadniają `DELETE /api/grupa…`, `POST /api/grupa/przyjmij`,
`POST /api/grupa/zalozyciel` i webhook subskrypcji założyciela
(`chmura_konta.uzgodnij_limit_po_zmianie_planu`, w tle po odpowiedzi dla Stripe). Zadania naraz
(8) liczą się **na całą opłaconą grupę** (`grupy.konta_wspolnego_limitu_zadan`): trwające
przebiegi założyciela i wszystkich członków. Przestrzeń (10 GB) liczy się **na każde konto
osobno** — kod nie ma wspólnego licznika przestrzeni grupy.

**Zaproszenia.** Jednorazowy token, w bazie wyłącznie jako skrót, z terminem ważności
(`WAZNOSC_ZAPROSZENIA_DNI`). Przyjąć je może tylko konto o adresie, na który je wystawiono.
Odsyłacz wraca do interfejsu zapraszającego zamiast iść pocztą: skrzynka bywa
nieskonfigurowana, a wtedy zaproszenie przepadałoby bez śladu.

**Role.** Założyciel jest dokładnie jeden. `przekaz_zalozyciela` zamienia role, a nie dodaje
drugiego założyciela; od tej chwili płaci i rozlicza się nowy. Subskrypcja Stripe nie
przechodzi z rolą, więc odbiorca musi mieć własny opłacony plan Grupa — inaczej przekazanie
jest odrzucane (członkowie straciliby limity planu i pulę pracy). Założyciel nie wyjdzie
z grupy, dopóki roli nie przekaże — inaczej zostałaby grupa bez płatnika. Konto należy
najwyżej do jednej grupy (warunek jednoznaczności w `grupy_czlonkowie`).

**Trasy.** `GET/POST/DELETE /api/grupa`, `POST /api/grupa/zaproszenia`,
`POST /api/grupa/przyjmij`, `DELETE /api/grupa/czlonkowie/{id}`, `POST /api/grupa/zalozyciel`
(`api/modules/grupy.py`). Ekran: `frontend/src/platnosci/Grupa.tsx` w module Płatności.

**Testy.** `backend/tests/test_grupy.py` (reguły i trasy), `frontend/src/platnosci/grupa.test.tsx`
(co widzi założyciel, czego nie widzi członek, gdzie stoją działania nieodwracalne).
