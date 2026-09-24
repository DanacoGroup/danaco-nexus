# Materiały centrum wiedzy

Pliki `NN-adres.md`; tytuł bierze się z nagłówka `# `, reszta jest treścią. Wczytanie:

```
deploy/nexus-cli.sh materialy-portalu --katalog docs/portal/tresci-wiedza --rodzaj wiedza --opublikuj
```

Bez `--opublikuj` pozycje lądują jako szkice do przejrzenia na `/portal/admin`.
Wczytanie jest powtarzalne — pozycja o tym samym adresie zostaje zaktualizowana.
Z `--synchronizuj` katalog jest jedynym źródłem prawdy dla swojego rodzaju: pozycje,
których nie ma wśród plików, znikają z portalu.

Spis centrum wiedzy idzie numerami z nazw plików, nie datą publikacji — numer ustala
kolejność czytania: od podstaw do spraw szczegółowych. Adres pozycji bierze się z części
nazwy po numerze, więc przenumerowanie pliku zmienia kolejność w spisie, a nie adres.
Zmiana części po numerze to już nowy adres: stara pozycja zostaje w bazie, dopóki
nie wczytasz katalogu z `--synchronizuj`.

Kolejność, jaka tu stoi: od formułowania poleceń, przez sześć zadań opisanych krok
po kroku (skany, nagrania, tłumaczenia, znak firmowy, strona, poczta z kalendarzem),
po formaty, wejścia do aplikacji i granice pracy Nexusa.

Centrum wiedzy to **opracowania, poradniki i odpowiedzi na częste pytania** (tak brzmi
podpis sekcji w portalu): rzeczy, po które czytelnik sięga, gdy chce się czegoś nauczyć,
a nie gdy szuka opisu jednego ekranu.

Podział działów, żeby się nie dublowały:

| Dział | Czym jest | Katalog |
|---|---|---|
| Dokumentacja | opis ekranów i modułów — „gdzie to jest i co robi” | `docs/portal/tresci-startowe` |
| Centrum wiedzy | poradniki i odpowiedzi — „jak to zrobić dobrze” | `docs/portal/tresci-wiedza` |
| Blog | praca z Nexusem i zmiany w produkcie — „co nowego i po co” | `docs/portal/tresci-blog` |
