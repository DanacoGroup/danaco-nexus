# Jak przepisać stos skanów na dane

Stos skanów przepisujesz jednym poleceniem: dołączasz pliki, piszesz, co ma z nich powstać,
i odbierasz arkusz albo PDF z warstwą tekstową. Nexus dzieli stos na pojedyncze dokumenty,
odczytuje tekst po polsku i układa go w tabelę.

## Przygotowanie materiału

Skaner daje lepszy wynik niż telefon. Zdjęcie zrobione pod kątem, w cieniu albo z odbiciem
światła czyta się gorzej. Nexus wyprostuje kadr i oczyści tło, natomiast nie odtworzy tego,
czego na obrazie nie ma.

Nie musisz rozdzielać stosu na osobne pliki. Jeden PDF z 200 stronami wystarczy: Nexus
rozpoznaje granice dokumentów i traktuje każdą fakturę jako osobną pozycję.

## Polecenie na cały stos

Wymień pola, które mają znaleźć się w zestawieniu, i zaznacz, co zrobić z wątpliwymi.
Przykład: „Z tych skanów zrób arkusz: data wystawienia, kontrahent, numer faktury, kwota
netto, VAT, brutto. Pole nieczytelne zostaw puste i dopisz numer strony”.

Ostatnie zdanie ma znaczenie praktyczne. Bez niego brakujące dane trzeba wyławiać ręcznie
z całego zestawienia.

## Postać wyniku

Nexus oddaje trzy rzeczy, zależnie od tego, o co poprosisz:

- **Arkusz** — XLSX albo CSV z jednym wierszem na dokument, gotowy do sumowania.
- **PDF z warstwą tekstową** — obraz oryginału z tekstem pod spodem, więc wygląda jak skan,
  a szuka się w nim jak w dokumencie.
- **Wykaz terminów** — daty wygaśnięcia, płatności i wypowiedzenia wyciągnięte z umów.

## Sprawdzenie przed użyciem

Przelicz sumę kontrolną na kilku pozycjach i porównaj z oryginałem. Odczyt z papieru bywa
omylny przy rękopisach, pieczątkach i tabelach bez ramek, a najczęstszy błąd to przecinek
dziesiętny w kwocie.

Poproś też o oznaczenie pozycji niepewnych. Krótka lista do sprawdzenia jest szybsza niż
przegląd całości.

## Archiwum, w którym da się szukać

Przepisany stos warto wrzucić do kolekcji w module Wiedza. Zapytanie własnymi słowami —
„umowa najmu z klauzulą waloryzacji” — znajduje wtedy fragment razem ze wskazaniem pliku,
z którego pochodzi.

## Od czego zacząć

Wejdź na /wyprobuj, dołącz dziesięć skanów i poproś o arkusz z datami i kwotami. Plik
dostaniesz w tej samej rozmowie i znajdziesz go później w module Pliki.
