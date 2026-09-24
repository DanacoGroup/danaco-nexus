# Przetwarzanie danych w Danaco Nexus

Konto, rozmowy, pliki i przestrzeń robocza leżą na serwerze w Polsce, a na Twoim urządzeniu
zostaje sam interfejs. Poza serwer wychodzi to, czego wymaga bieżące zadanie, a także dane
potrzebne do płatności, do wiadomości z portalu (na przykład przy odzyskiwaniu hasła)
i do powiadomień w przeglądarce, jeśli je włączysz. Poniżej streszczenie zasad; wiążące
brzmienie, z pełnym wykazem odbiorców, zawiera polityka prywatności.

## Praca po stronie serwera

Praca na serwerze rozstrzyga o dwóch rzeczach naraz. Ta sama przestrzeń otwiera się
z komputera, telefonu i tabletu bez przenoszenia plików. Zadanie liczy się dalej, gdy
zamkniesz okno, bo nie liczy się na Twoim sprzęcie.

Cenę tego rozwiązania mówimy wprost: pliki, z którymi pracujesz, muszą trafić na serwer.
Dlatego zakres przekazywanych danych opisujemy poniżej, zamiast zbywać go ogólnym zdaniem
o bezpieczeństwie.

## Zakres przekazywany do modelu

Wykonanie zadania wymaga przekazania modelowi językowemu treści polecenia i historii
bieżącej rozmowy. Trafia tam też to, co agent musi przeczytać, żeby wykonać zadanie:
fragmenty plików (także znalezione w bazie wiedzy), treść wiadomości e-mail, wydarzenia
z kalendarza i inne wyniki narzędzi, na przykład wypis katalogu w chmurze. Pełna treść
plików, których zadanie nie dotyczy, zostaje w przestrzeni Twojego konta.

Agent pracuje w wydzielonej przestrzeni Twojego konta. Granicy pilnuje piaskownica
systemowa, a nie treść instrukcji — instrukcję da się obejść zdaniem, piaskownicy nie.

## Funkcje obejmujące dane osób trzecich

Dane osób innych niż Ty trafiają do usługi przede wszystkim przez pocztę. Gdy podłączysz
skrzynkę, moduł Poczta i agent czytają nadawców, adresatów, treść wiadomości i załączniki.
Poza pocztą robią to cztery funkcje.

- Rozpoznawanie twarzy na Twoich zdjęciach.
- Odczyt treści stron przez dodatek do przeglądarki.
- Szkice odpowiedzi na wiadomości SMS w aplikacji na Androida.
- Przekazanie zawartości ekranu telefonu do rozmowy.

W aplikacji na Androida szkice odpowiedzi na SMS i przekazanie ekranu telefonu startują
wyłączone, wymagają osobnej zgody systemowej i działają wyłącznie na Twoje polecenie.
Dodatek do przeglądarki domyślnie czyta stronę dopiero wtedy, gdy klikniesz jego ikonę
albo naciśniesz skrót. Rozpoznawanie twarzy nie ma osobnego wyłącznika. To narzędzie
agenta: działa na zdjęciach z Twojej przestrzeni i nie ustala tożsamości, pokazuje tylko,
które twarze są do siebie podobne. Żadna z tych funkcji nie czyta danych w tle. Ich zasięg
omawia materiał „Co Nexus robi sam, co po zatwierdzeniu, a co zostaje Tobie”. Podstawy
prawne przetwarzania danych konta, rozmów, plików, poczty i kalendarza opisuje polityka
prywatności. Za podstawę przetwarzania danych osób trzecich zawartych w materiałach, które
przekazujesz agentowi, odpowiadasz Ty; tak stanowi regulamin w rozdziale „Zasady korzystania”.

## Poświadczenia i klucze

Hasła do skrzynek pocztowych trzymamy na serwerze w pliku dostępnym tylko dla usługi
Nexusa i nigdy nie odsyłamy ich do przeglądarki. Każde urządzenie łączy się własnym
kluczem, a klucz unieważniasz pojedynczo przyciskiem „Cofnij” w module Sprzęt
(z Ustawień prowadzi tam skrót „Urządzenia”).

## Usuwanie

Rozmowy i pliki usuwasz pojedynczo. Całe konto usuwasz w portalu, na stronie Konto
klienta: przyciskiem „Chcę usunąć konto”, po podaniu hasła i słowa potwierdzenia.
Usunięcie kasuje konto razem z rozmowami, plikami, bazą wiedzy, stronami, projektami
i chmurą. Zostają dane rozliczeniowe, które musimy przechowywać niezależnie od konta.
Z kopii zapasowych serwera usunięte dane znikają najpóźniej po 14 dniach.
Operacji nie da się cofnąć, więc najpierw pobierz to, co chcesz zachować. Konta
z opłacanym planem nie usuniesz, dopóki nie zrezygnujesz z planu w module Twój plan.

## Co z tego wynika w praktyce

Wejdź na /wyprobuj i sprawdź to na własnym pliku, zanim wgrasz cokolwiek wrażliwego. Połączone
urządzenia i ich klucze przejrzysz później w module Sprzęt, a dane konta w Ustawieniach.
