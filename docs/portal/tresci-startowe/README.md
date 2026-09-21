# Materiały dokumentacji portalu

Dokumentacja opisuje ekrany i moduły Nexusa — „gdzie to jest i co robi”. Poradniki
mieszkają osobno, w `docs/portal/tresci-wiedza`, a zmiany w produkcie w `tresci-blog`;
te trzy działy nie mogą powtarzać tych samych pozycji.

Te pliki są **materiałami źródłowymi**: treść mieszka w bazie (`portal_content`), bo to
z niej portal buduje adresy, zajawki, indeks wyszukiwania i mapę witryny, a pliki są jej
wersją do przejrzenia w historii zmian.

## Jak opublikować

Poleceniem — wczytuje cały katalog za jednym razem:

```
deploy/nexus-cli.sh materialy-portalu --katalog docs/portal/tresci-startowe
```

Domyślnie pozycje lądują jako **szkice**: nie widać ich w portalu, dopóki ktoś ich nie
obejrzy na `/portal/admin` i nie opublikuje. `--opublikuj` zapisuje od razu jako
opublikowane, `--rodzaj` wybiera dział (`blog`, `wiedza`, `dokumentacja`, `strona`),
a `--autor` dokłada podpis. Wczytanie jest powtarzalne: pozycja o tym samym adresie
zostaje nadpisana, a nie powielona, więc poprawiony plik wystarczy wczytać ponownie.

`--synchronizuj` czyni katalog jedynym źródłem prawdy dla swojego rodzaju: pozycja,
której nie ma wśród plików, znika z portalu. Bez tej opcji materiał wycofany
z repozytorium — albo taki, któremu zmieniono adres — zostaje w bazie sierotą.

Ręcznie — przez panel administratora (`/portal/admin`), gdy chodzi o jedną pozycję:
dodaj pozycję rodzaju **dokumentacja**, wklej tytuł i treść, zapisz jako szkic,
obejrzyj podgląd, dopiero potem opublikuj.

Po publikacji pozycja pojawia się w spisie dokumentacji, w wyszukiwarce portalu
(`/portal/szukaj`) i w mapie witryny.

## Co jest w tym katalogu

| Plik | Rodzaj | Temat |
|---|---|---|
| `01-pierwsze-uruchomienie.md` | dokumentacja | Od wejścia na stronę do pierwszego gotowego pliku |
| `02-jak-zlecac-zadania.md` | dokumentacja | Jak pisać zlecenia, dołączać pliki i przerywać pracę |
| `03-ustawienia-okna.md` | dokumentacja | Motyw, ruch, wysyłanie wiadomości, moduł na start |
| `04-pliki-i-chmura.md` | dokumentacja | Gdzie lądują wyniki pracy, ile jest miejsca, kto to widzi |
| `05-mapa-modulow.md` | dokumentacja | Co znajdziesz w którym module paska |
| `06-poczta-i-kalendarz.md` | dokumentacja | Podłączenie skrzynki, odpowiedzi do zatwierdzenia, terminy |
| `07-strony-www.md` | dokumentacja | Twórca stron: opis, podgląd, wersje, publikacja |
| `08-praca-glosem.md` | dokumentacja | Dyktowanie i rozmowa głosowa |
| `09-urzadzenia-i-zgody.md` | dokumentacja | Telefon, komputer, rozszerzenie, powiadomienia i granice zgody |

Każdy szkic opisuje wyłącznie zachowanie sprawdzone w działającym wydaniu — bez obietnic
na przyszłość. Przy zmianie interfejsu trzeba je przejrzeć razem z resztą treści.

Nazwa pliku ma znaczenie: `NN-adres.md`, gdzie `NN` ustala kolejność w spisie dokumentacji,
a `adres` staje się adresem pozycji (`/portal/dokumentacja/<adres>`). Tytuł polecenie bierze
z nagłówka `# ` i nie wkłada go do treści — stronę pozycji rysuje tytuł osobno, więc w pliku
występuje dokładnie raz.

Akapity są w jednym wierszu bez zawijania — portal renderuje treść przez `marked`
z opcją `breaks: true`, więc pojedyncze złamanie wiersza stałoby się `<br>` w środku
zdania. Przy pisaniu kolejnych materiałów warto o tym pamiętać.
