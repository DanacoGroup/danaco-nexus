# Materiały bloga portalu

Pliki `NN-adres.md`; tytuł bierze się z nagłówka `# `, reszta jest treścią. Wczytanie:

```
deploy/nexus-cli.sh materialy-portalu --katalog docs/portal/tresci-blog --rodzaj blog --opublikuj
```

Bez `--opublikuj` pozycje lądują jako szkice do przejrzenia na `/portal/admin`.
Wczytanie jest powtarzalne — pozycja o tym samym adresie zostaje zaktualizowana.

Z `--synchronizuj` katalog jest jedynym źródłem prawdy dla swojego rodzaju: pozycje,
których nie ma wśród plików, znikają z portalu. Bez tej opcji wycofany materiał zostaje
w bazie, choć w repozytorium już go nie ma.

Blog opisuje **pracę z Nexusem i zmiany w produkcie** (tak brzmi podpis sekcji w portalu):
co się zmieniło, co stanęło w portalu i dlaczego produkt jest zbudowany tak, a nie inaczej.
Instrukcji „jak to zrobić dobrze” tu nie piszemy — te idą do centrum wiedzy.
Dokumentacja modułów mieszka osobno, w `docs/portal/tresci-startowe`, a poradniki
i odpowiedzi na częste pytania w `docs/portal/tresci-wiedza` — te trzy działy nie mogą
powtarzać tych samych pozycji, bo czytelnik trafia wtedy trzy razy na to samo.
