# Przetwarzanie danych w Danaco Nexus

Streszczenie zasad przetwarzania danych. Wiążące brzmienie zawiera polityka prywatności.

## Miejsce przetwarzania

Nexus działa na serwerze Danaco w Polsce. Konto, rozmowy, pliki i przestrzeń robocza
znajdują się na serwerze; na urządzeniu użytkownika pozostaje wyłącznie interfejs.
Z tego wynika dostęp do tej samej przestrzeni z komputera, telefonu i tabletu bez
przenoszenia danych.

## Zakres przekazywany do modelu

Wykonanie zadania wymaga przekazania modelowi językowemu treści polecenia oraz plików
dołączonych do zadania. Pliki, których użytkownik nie dołączył, oraz rozmowy, których nie
dotyczy polecenie, nie są przekazywane. Agent pracuje w wydzielonej przestrzeni konta;
granicę egzekwuje piaskownica systemowa, a nie treść instrukcji.

## Funkcje obejmujące dane osób trzecich

Cztery funkcje wprowadzają do usługi dane osób innych niż użytkownik:

- rozpoznawanie twarzy na zdjęciach użytkownika,
- odczyt treści stron przez dodatek do przeglądarki,
- szkice odpowiedzi na wiadomości SMS w aplikacji Android,
- przekazanie zawartości ekranu telefonu do rozmowy.

Każda z nich jest domyślnie wyłączona, wymaga osobnej zgody systemowej i działa wyłącznie
na polecenie użytkownika — żadna nie odczytuje danych w tle. Przed włączeniem warto wiedzieć,
jaki zakres obejmuje: w wątku SMS znajdują się również wiadomości nadawcy, a na zrzucie
ekranu wszystko, co w danej chwili widać.

Podstawy prawne przetwarzania w tych przypadkach opisuje polityka prywatności.

## Poświadczenia i klucze

Hasła do skrzynek pocztowych zapisywane są po stronie serwera w postaci nieodczytywalnej
dla przeglądarki. Klucze urządzeń są odrębne dla każdego urządzenia i podlegają
unieważnieniu pojedynczo.

## Usuwanie

Rozmowy i pliki usuwa się pojedynczo, konto — w całości, z poziomu ustawień. Usunięcie
konta obejmuje rozmowy, pliki i przestrzeń roboczą.
