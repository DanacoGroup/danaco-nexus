# Materiały centrum wiedzy

Pliki `NN-adres.md`; tytuł bierze się z nagłówka `# `, reszta jest treścią. Wczytanie:

```
deploy/nexus-cli.sh materialy-portalu --katalog docs/portal/tresci-wiedza --rodzaj wiedza --opublikuj
```

Centrum wiedzy to **opracowania, poradniki i odpowiedzi na częste pytania** (tak brzmi
podpis sekcji w portalu): rzeczy, po które czytelnik sięga, gdy chce się czegoś nauczyć,
a nie gdy szuka opisu jednego ekranu.

Podział działów, żeby się nie dublowały:

| Dział | Czym jest | Katalog |
|---|---|---|
| Dokumentacja | opis ekranów i modułów — „gdzie to jest i co robi” | `docs/portal/tresci-startowe` |
| Centrum wiedzy | poradniki i odpowiedzi — „jak to zrobić dobrze” | `docs/portal/tresci-wiedza` |
| Blog | praca z Nexusem i zmiany w produkcie — „co nowego i po co” | `docs/portal/tresci-blog` |
