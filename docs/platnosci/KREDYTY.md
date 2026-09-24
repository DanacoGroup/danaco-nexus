# Kredyty konta — przelicznik Danaco Nexus

Kredyt jest **naszą** jednostką pracy agenta i nigdy nie wychodzi do użytkownika.
Klient kupuje **dostęp**: plan daje zakres pracy na okres rozliczeniowy, a po jego
wyczerpaniu dostęp przedłuża się kwotą, którą klient sam wpisuje (przelicznik
`platnosci/kredyty.py:kredyty_za_kwote`). W interfejsie widać pasek wykorzystania bez
liczb — decyzja właściciela, wrzesień 2026. To, na jakich warunkach i z jakimi limitami
rozliczamy się z dostawcą modelu, jest sprawą między nami a dostawcą: nie pojawia się
w interfejsie, w komunikatach błędów ani w odpowiedziach API.

**Czego nie robić:** nie wprowadzać słowa „kredyt”, liczby kredytów ani „pakietów
kredytów” do cennika, opisu okresu próbnego, regulaminu i komunikatów aplikacji. Ten
dokument opisuje mechanikę rozliczeń, a nie język produktu.

## Dlaczego kredyty, a nie „nieograniczone”

W fazie testów silnik pracuje na kontach subskrypcyjnych właściciela. Bez licznika jeden
użytkownik potrafi wyczerpać zasób całej grupy. Kredyt jest więc równocześnie pozycją
w cenniku i zaworem chroniącym wspólny limit.

## Cennik

| Pozycja | Stawka | Zmienna środowiskowa |
|---|---|---|
| 1000 żetonów wysłanych do modelu | 1 kredyt | `NEXUS_KREDYT_1K_WEJSCIE` |
| 1000 żetonów wygenerowanych przez model | 5 kredytów | `NEXUS_KREDYT_1K_WYJSCIE` |
| Opłata minimalna za przebieg | 1 kredyt | `NEXUS_KREDYT_MINIMUM` |

Żetony odczytane z pamięci podręcznej liczą się jak wejściowe — to nadal praca modelu.
Koszt zaokrągla się w górę do pełnego kredytu. Stawki odczytuje się przy każdym naliczeniu,
więc zmiana cennika wymaga tylko restartu usługi.

### Dopłata za narzędzia liczone czasem maszyny

Część narzędzi kosztuje minuty procesora, a w rozmowie zostawia dwa zdania. Bez osobnej
stawki byłyby dla użytkownika praktycznie darmowe, a dla nas najdroższe. Tabela w
`backend/nexus/platnosci/kredyty.py` (`KOSZT_NARZEDZI`):

| Narzędzie | Dopłata |
|---|---|
| `upscale_image` | 20 |
| `transcribe_audio` | 15 |
| `erase_objects`, `media_process` | 10 |
| `enhance_photo`, `retouch_portrait`, `ocr_documents` | 8 |
| `remove_background`, `change_background`, `enhance_document_scan`, `detect_document_boundaries` | 6 |
| `index_documents`, `translate_document` | 5 |
| `scholar_search` | 4 |
| `web_search`, `web_fetch_page` | 2 |

Dopłata liczy się za każde wywołanie narzędzia w przebiegu.

## Przydziały

| Zdarzenie | Co się dzieje | Powód w księdze |
|---|---|---|
| Pierwsze zlecenie na koncie bez wcześniejszego przydziału (`POWODY_PRZYDZIALU`; zakup i wpis zerowy się nie liczą) | zakres próbny planu domyślnego (`probny_kredyty` Osobistego) — `kredyty.pierwszy_przydzial`; właściciel instalacji (`ADMIN_OWNER`) dostaje pełny przydział planu (`kredyty_okresowo`) | `start` |
| Konto próbne bez rejestracji (`POST /api/auth/gosc`) | zakres próbny planu domyślnego (`probny_kredyty` Osobistego) | `start` |
| Opłacona faktura na 0 zł otwierająca okres próbny (`billing_reason` = `subscription_create`, plan z okresem próbnym) | zakres próbny planu (`probny_kredyty`) przez `pierwszy_przydzial` — tylko gdy konto nie dostało jeszcze przydziału, więc konto, które już dostało `start`, nie dostaje zakresu drugi raz | `okres-probny` |
| Pierwsza opłacona faktura okresu płatnego i każde odnowienie (`invoice.paid`) | pełny przydział planu (`kredyty_okresowo`); plan bez okresu próbnego dostaje go od pierwszej faktury. Plan bierze się z faktury (cena pozycji, potem `subscription_details.metadata.plan`), rekord subskrypcji w bazie jest rezerwą | `odnowienie` |
| Doładowanie kwotą albo pakiet (sesja Checkout w trybie `payment`, potwierdzona wpłata) | kredyty z przelicznika `kredyty_za_kwote` albo z pakietu | `zakup` |
| `nexus.cli konto-testowe` | pełny przydział planu wskazanego `--plan` (`kredyty_okresowo`) plus opcjonalne `--kredyty` | `konto-testowe` |

Kredyty w katalogu planów (`kredyty_okresowo`): Osobisty 2 000, Pro 20 000, Grupa 60 000. Zakres
próbny (`probny_kredyty`) ma tylko plan z okresem próbnym: Osobisty 300 (7 dni). Praca członka
grupy schodzi z salda założyciela (`platnosci/grupy.py:konto_rozliczeniowe`) niezależnie od
przydziałów na jego własnym koncie.

## Zasady naliczania

- **Każdy zakończony przebieg kosztuje**, także nieudany i anulowany: praca została wykonana,
  maszyna była zajęta.
- **Saldo nie schodzi poniżej zera.** Przebieg droższy niż saldo zabiera resztę i nic więcej —
  dług na koncie byłby dla użytkownika niezrozumiały.
- **Puste konto nie przyjmuje zlecenia.** Sprawdzenie następuje przed uruchomieniem pracy;
  dowiedzenie się o braku środków w połowie zadania byłoby gorsze niż odmowa na wejściu.
- **Każda zmiana salda ma wpis w księdze** (`platnosci_kredyty_ruchy`): kiedy, ile, za co
  i z jakim saldem po operacji. Bez księgi nie da się odpowiedzieć na pytanie „za co zeszły
  mi kredyty”, a to pierwsze pytanie płacącego użytkownika.

## Co widzi użytkownik

`GET /api/platnosci/kredyty` zwraca saldo, sumę przydziałów, sumę zużycia i ostatnie 30 zmian.
Nie zwraca niczego o kontach silnika: ani ich liczby, ani limitów, ani tego, które obsłużyło
dany przebieg. Komunikat przy przeciążeniu brzmi „Usługa jest chwilowo przeciążona”, a stan
limitów kont operatora trafia wyłącznie do dziennika (`nexus.agent.runner`).

Pilnuje tego test `backend/tests/test_kredyty.py::test_komunikaty_bledow_nie_zdradzaja_kont_silnika`.
