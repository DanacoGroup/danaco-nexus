# Wydania: strefa robocza → przedsionek → produkcja

Do tej pory usługa serwowała wprost z katalogu repozytorium. Każdy zapis pliku był
natychmiast produkcją, nie było czego oglądać przed wypuszczeniem i nie było do czego
wrócić, gdy coś się posypało. Ten katalog to zamyka.

## Trzy etapy

| Etap | Co to jest | Gdzie widać | Skąd bierze kod |
|---|---|---|---|
| **Strefa robocza** | to repozytorium, tu się pracuje | nigdzie publicznie | `/danaco/projekty/danaco-nexus` |
| **Przedsionek** | gotowe wydanie po bramce, do obejrzenia i sprawdzenia | `https://test.danaco-nexus.pl` (hasło) | `wydania/przedsionek` → `wydania/wersje/<znacznik>` |
| **Produkcja** | to, co widzą użytkownicy | `https://danaco-nexus.pl` | `wydania/produkcja` → `wydania/wersje/<znacznik>` |

Oba etapy publiczne czytają kod przez dowiązanie do niezmiennego katalogu wydania.
Zmiana pliku w repozytorium nie zmienia ani przedsionka, ani produkcji — trzeba zbudować
nowe wydanie i je wypchnąć. Przedsionek ma **własną bazę** (`nexus_przedsionek`) i
**własne dane** (`wydania/dane-przedsionek`), więc testowanie nie dotyka niczyich rozmów,
plików ani płatności.

## Polecenia

```bash
# 1. Zbuduj wydanie ze strefy roboczej (sekrety, ruff, pytest, tsc, vitest, budowa interfejsu).
deploy/wydania/zbuduj.sh

# 2. Wystaw je w przedsionku i obejrzyj pod https://test.danaco-nexus.pl
deploy/wydania/wypchnij.sh przedsionek

# 3. Gdy jest dobre — promuj na produkcję (bierze to, co stoi w przedsionku).
deploy/wydania/wypchnij.sh produkcja

# W razie awarii: powrót do poprzedniego sprawnego wydania.
deploy/wydania/cofnij.sh

# Co gdzie stoi.
deploy/wydania/wersje.sh

# Ile miejsca zajmują stare wydania (sam podgląd; usuwa dopiero --wykonaj).
deploy/wydania/sprzataj.sh
```

`zbuduj.sh` przerywa pracę, gdy bramka nie przechodzi — wydanie z czerwonym testem
nie powstaje, więc nie da się go przez pomyłkę wypchnąć. Pełny dziennik budowy leży
w `.logs/wydanie-<znacznik>.log`.

Bramka to siedem kroków: **sekrety**, `ruff`, `pytest`, testy interfejsu (`tsc --noEmit`
i `vitest`), **programy narzędzi**, budowa interfejsu i **odcisk źródeł**. Krok „programy narzędzi” sprawdza
ścieżką usługi z `.env`, czy każdy program wywoływany przez narzędzia agenta jest dostępny —
testy tego nie łapią, bo przy braku programu pomijają przypadek zamiast zgłosić błąd.

Bramka sprawdza też, czy przez cały bieg pracowała na **tym samym kodzie**. Na starcie liczy
sumę kontrolną treści plików źródłowych, a przed skopiowaniem artefaktu powtarza pomiar;
różnica przerywa budowę. Bez tego wydanie potrafiło powstać z kodu, którego testy nie
widziały — bramka czyta drzewo robocze w kilku momentach rozrzuconych na kilkanaście minut.
Przy pracy równoległej w repozytorium bramka będzie się przez to przerywać; to zamierzone.

Krok „sekrety” to `gitleaks detect` na całej historii (115 commitów, 5,5 MB, ok. ćwierć
sekundy). Klucz wpisany do repozytorium „na chwilę” zostaje w historii na zawsze i zauważa
się go dopiero po wycieku. Zawężenia fałszywych trafień — hasła kont testowych i jedna stała
w skrypcie zasobów — stoją w `.gitleaks.toml` i dotyczą wyłącznie reguły ogólnej
`generic-api-key`; prawdziwy klucz w pliku testu nadal zatrzymuje bramkę (sprawdzone
podstawionym tokenem GitHuba). Bez `gitleaks` na ścieżce krok mówi o pominięciu i idzie dalej —
bramka ma działać także na maszynie bez kompletu narzędzi serwera.

Dwa pokrętła, gdy zajdzie potrzeba: `LIMIT_PYTEST_S` (domyślnie 900 s) i `BRAMKA_LOCK`
(nazwa blokady — pozwala puścić dwie budowy obok siebie, np. przy równoległej pracy).

Wydanie zabiera ze sobą **źródła klientów** (`zrodla/`): `frontend/src`, `frontend/scripts`,
pliki konfiguracyjne budowy, `desktop/src`, `extension` i `android/scripts`. Do 21 września
artefakt miał `frontend/dist` bez map źródeł i nie dawało się z niego odtworzyć tego, z czego
powstał; kopia zapasowa serwera obejmuje dane użytkowników, nie repozytorium. Koszt jest
niewielki (`frontend/src` 2,4 MB, reszta poniżej 0,4 MB), a wydanie przestaje być ślepą
kopią. Poza wydaniem zostają `landing/` (395 MB) i `motion/` (114 MB) — to materiały
źródłowe, a ich wynik jest już w `frontend/dist`.

Nowe wydanie zajmuje kilkanaście megabajtów, nie 652 MB: gotowy interfejs kopiuje się
przez `rsync --link-dest` do poprzedniego wydania, więc nagrania (589 MB z 645 MB `dist`)
są współdzielone twardymi dowiązaniami zamiast kopiowane. Usunięcie starego wydania
zwalnia miejsce dopiero wtedy, gdy zniknie ostatnie dowiązanie — i o to chodzi.

## Cofnięcie

Promocja zapisuje poprzedni znacznik w `wydania/POPRZEDNIA-PRODUKCJA`. `cofnij.sh` bez
argumentu wraca właśnie tam; z argumentem — do dowolnego wydania z `wydania/wersje`.
Cofnięcie jest przestawieniem dowiązania i restartem usługi, więc trwa sekundy i nie
wymaga budowania. Dane i baza nie są cofane — wydanie zmienia wyłącznie kod.

## Sprzątanie

Nowe wydania są tanie (nagrania współdzielą się dowiązaniami), ale te zbudowane
wcześniej trzymają po 652 MB każde — `du -sh wydania` mówi, ile się nazbierało.

`sprzataj.sh` bez argumentów tylko pokazuje, co poszłoby do usunięcia: zostawia pięć
najnowszych (`--ile N` zmienia liczbę) oraz wydania wskazane przez przedsionek, produkcję
i `POPRZEDNIA-PRODUKCJA`, nawet gdy są starsze. Usuwa dopiero `--wykonaj`, a razem
z wydaniem kasuje jego dziennik budowy (`.logs/wydanie-<znacznik>.log`) — po katalogu,
którego nie ma, dziennik jest już tylko śladem.

## Hasło do przedsionka

Caddy czyta je z `/etc/danaco/przedsionek-haslo` (wiersz `<login> <hasz bcrypt>`;
hasz robi `caddy hash-password`). Bez tego pliku host `test.danaco-nexus.pl` się nie
podniesie — to celowe: przedsionek nigdy nie ma stać otworem.

## Usługi przedsionka

Przedsionek ma dwie jednostki, nie jedną:

| Jednostka | Rola |
|---|---|
| `danaco-nexus-przedsionek.service` | API i pliki wydania (127.0.0.1:8950) |
| `danaco-nexus-worker-przedsionek.service` | proces roboczy: wykonuje zlecenia agenta |

Kolejką zadań jest tabela `runs` w bazie, a przedsionek ma własną bazę — bez własnego
procesu roboczego przyjmuje zlecenie kodem 202 i nigdy go nie wykonuje, bez śladu na
ekranie. Obie jednostki należą do `danaco-nexus.target`; stan sprawdza
`systemctl is-active danaco-nexus-worker-przedsionek`.

## Materiały portalu

Wydanie wnosi kod, nie treść: blog, centrum wiedzy i dokumentacja mieszkają w bazie i
przeżywają wymianę wydania. Materiały przygotowane w repozytorium wczytuje osobne
polecenie — uruchamiane w środowisku, którego dotyczy (`przedsionek.env` albo `.env`):

```
deploy/nexus-cli.sh materialy-portalu --katalog docs/portal/tresci-startowe
```

Domyślnie powstają szkice, `--opublikuj` publikuje od razu, a powtórne wczytanie nadpisuje
pozycję o tym samym adresie. Szczegóły: `docs/portal/tresci-startowe/README.md`.

**Poprawka w pliku sama nie dochodzi do klienta.** Wydanie jej nie wnosi, a portal czyta
bazę — dopóki nikt nie uruchomi polecenia powyżej, na stronie stoi poprzednia wersja
tekstu. Po każdej zmianie w `docs/portal/tresci-startowe` wczytaj materiały ponownie
w obu środowiskach. Uwaga: wczytanie nadpisuje pozycję o tym samym adresie, więc zabierze
też poprawki naniesione wcześniej w panelu portalu.
