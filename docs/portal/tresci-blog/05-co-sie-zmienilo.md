# Co się ostatnio zmieniło

Wydania wychodzą często i po cichu — aplikacja aktualizuje się sama, a pasek „jest nowa
wersja” pyta tylko o moment odświeżenia. Tu zbieramy to, co widać gołym okiem.

## Ruch w oknie aplikacji

Treść, która dociera po odpowiedzi serwera — lista plików, karty stron, gotowy obraz, wyniki
wyszukiwania w bazie wiedzy — wchodzi teraz kaskadą zamiast pojawiać się skokiem. Po zmianie
modułu najpierw kończy się przejście widoku, a dopiero potem rusza kaskada: dwa ruchy naraz
czytały się jak usterka.

Przy włączonym ograniczeniu ruchu wyciszamy **cały** przebieg, razem z opóźnieniem. Wcześniej
treść potrafiła wyskakiwać schodkami komuś, kto prosił o mniej ruchu.

## Aplikacja mówi, co ma na ekranie

Tytuł okna to teraz „Pliki — Danaco Nexus”, „Obrazy — Danaco Nexus” i tak dalej. Przy
zainstalowanej aplikacji to jest nazwa w przełączniku okien systemu — przy dwóch otwartych
oknach nie dało się ich dotąd odróżnić.

Menu ikony aplikacji (długie przytrzymanie na telefonie, prawy przycisk na pulpicie) ma
cztery skróty zamiast jednego: Nowa rozmowa, Pliki, Obrazy, Możliwości.

## Strona produktu wczytuje się szybciej

Strona pobierała pakiet okna aplikacji, którego odwiedzający najczęściej nigdy nie zobaczy —
560 kB kodu na wejściu. Teraz pobiera go dopiero wtedy, gdy jest po co. Razem z odłożeniem
nagrania z sekcji instalacji daje to **787 kB mniej** na pierwszym wejściu i wyraźnie
szybsze wyświetlenie treści.

## Wyszukiwarka portalu zna odmianę

„Fakturami” znajduje to samo co „faktur”, „dokumentów” to samo co „dokument”. Wcześniej
trzeba było trafić w dokładną formę słowa.

## Drobiazgi, które zabierały czas

* komunikat błędu nad polem wiadomości da się zamknąć klawiaturą, nie tylko myszą,
* strona Płatności i ekran nieznanego modułu odzyskały nagłówek — dla czytnika ekranu
  strona zaczynała się donikąd,
* odpowiedzi serwera przy błędnym formularzu mówią po polsku, czego brakuje, zamiast
  „Błąd serwera (422)”,
* adres pliku, którego nie ma, zwraca uczciwe „nie znaleziono” zamiast strony aplikacji.

## Co dalej

Pracujemy nad dokończeniem centrum wiedzy i nad paczkami do pobrania (Android, Windows,
dodatek do przeglądarki) w wersjach zgodnych z bieżącym wydaniem.
