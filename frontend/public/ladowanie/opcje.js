/* Ustawienia ekranu ładowania marki. Wczytywane przed `ladowanie.js`.
 *
 * Osobny plik, a nie skrypt wpisany w stronę: nagłówek Content-Security-Policy aplikacji
 * ma `script-src 'self'` bez `'unsafe-inline'`, więc kod w treści dokumentu przeglądarka
 * po prostu odrzuca. Na serwerze deweloperskim nagłówka nie ma i wersja wpisana w stronę
 * działała — na produkcji nie wykonała się ani razu, a wraz z nią otwarcie wracało do
 * domyślnego progu i znikało na gotowej stronie.
 */
window.DanacoLadowanieOpcje = {
  // Otwarcie gra zawsze przy pierwszym wejściu w sesji, także wtedy, gdy strona jest
  // gotowa od razu (pamięć podręczna, szybkie łącze). Domyślny próg 150 ms kasował
  // planszę na gotowej stronie — wtedy otwarcie strony nie miało żadnej animacji,
  // a to jedyne miejsce, w którym znak marki rysuje się na oczach odwiedzającego.
  prog: 0,
  // Twardy koniec czekania na gotowość. Domyślne dziesięć sekund to wieczność na ekranie:
  // przy kiepskim łączu plansza trzymałaby stronę pod zasłoną dłużej, niż ktokolwiek
  // zechce patrzeć na znak. Po tym czasie plansza schodzi tak czy inaczej.
  maks: 4000,
};
