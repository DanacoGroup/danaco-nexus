# Ruch, który coś znaczy

Animacje w programach dzielą się na dwie grupy. Jedne mówią, co się właśnie stało. Drugie
są ozdobą i przeszkadzają. Staramy się robić wyłącznie te pierwsze — i to jest trudniejsze,
niż wygląda.

## Ruch zamiast komunikatu

Gdy lista plików pojawia się po odpowiedzi serwera, karty wchodzą jedna po drugiej, z małym
przesunięciem w czasie. To nie jest dekoracja: dzięki temu widać, że **to jest nowa
odpowiedź**, a nie ten sam ekran co przed chwilą. Bez ruchu treść po prostu podmienia się
w miejscu i oko tego nie zauważa.

Tak samo działa przejście między modułami: poprzedni widok wychodzi, nowy wchodzi — i wiadomo,
że coś się zmieniło, bez czytania nagłówka.

## Dwa ruchy naraz czytają się jak usterka

Najczęstszy błąd to nałożenie dwóch animacji na jedno zdarzenie. Przejście między widokami
i jednocześnie wejście treści w środku tego widoku — oko widzi wtedy szarpnięcie, a nie
choreografię.

Dlatego kaskada wejścia **milczy**, dopóki trwa przejście widoku, i rusza dopiero po nim.
Najpierw jedno, potem drugie.

## Kto prosi o mniej ruchu, dostaje mniej ruchu

System operacyjny pozwala włączyć „ograniczenie ruchu”; to samo jest w Ustawieniach Nexusa.
Wtedy znikają przesunięcia i pętle, a zostaje sama zmiana widoczności.

Tu kryje się pułapka, w którą łatwo wpaść: wyciszenie czasu trwania **nie wystarcza**. Jeżeli
animacja ma opóźnienie, treść dalej czeka — tylko zamiast płynnie wejść, wyskakuje skokiem,
jedna pozycja po drugiej. Efekt jest gorszy niż sama animacja. Wyciszenie musi obejmować
cały przebieg, razem z opóźnieniem.

## Ruch, który nie kończy się sam, ma hamulec

Nagranie w pętli na stronie produktu chodzi tak długo, jak długo ktoś na nią patrzy. Przy
takim ruchu wytyczne dostępności wymagają sposobu na zatrzymanie — i to nie w ustawieniach
systemu, tylko na miejscu. Dlatego przy scenie jest przycisk „Wstrzymaj pokaz”, a pasek
z przykładami zatrzymuje się pod kursorem i po wejściu w niego tabulatorem.

## Po co o tym piszemy

Bo to jest ta część produktu, której nikt nie zauważa, gdy jest zrobiona dobrze — i która
od razu rzuca się w oczy, gdy jest zrobiona źle. Wolimy, żeby było wiadomo, że myślimy o niej
tak samo poważnie jak o tym, co Nexus potrafi policzyć.
