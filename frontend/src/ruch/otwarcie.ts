// Otwarcie: kiedy treść ma ruszyć ze swoim wejściem po ekranie ładowania marki.
//
// Plik leżał w `landing/`, ale ekran ładowania jest wpięty w `index.html` i zasłania
// **każdą** powierzchnię, nie tylko stronę produktu — także logowanie. Dlatego hak
// mieszka razem z resztą ruchu i korzystają z niego obie strony progu.
//
// Otwarcie rysuje ekran ładowania marki (`public/ladowanie/ladowanie.js`, wpięty prosto
// w `index.html`): iskra pociągnięciem światła rysuje łuk znaku, punkt opada, Aurora
// rozlewa się z punktu, a na koniec łuk znaku przelatuje w łuk hero. Zaczyna się przy
// pierwszej klatce dokumentu, bo nie czeka na pakiet aplikacji.
//
// Wcześniej stała tu druga plansza: nakładka Reacta z nagraniem `intro-znaku`. Pakiet
// wchodził po ponad sekundzie, więc otwarcie wyglądało tak — ekran marki, gotowa strona,
// a po chwili znowu zasłona z tym samym znakiem, tym razem białym, bez Aurory. Jedno
// otwarcie zamiast dwóch: nakładka znika, a strona dowiaduje się od ekranu ładowania,
// kiedy ma wejść.

import { useEffect, useState } from "react";
import { ograniczonyRuch } from "../preferencje";

/** Co ile sprawdzamy stan planszy, dopóki strona wstrzymuje swoje wejście (ms). */
const KROK_SPRAWDZENIA_MS = 80;

/** Do której chwili od otwarcia dokumentu wolno wstrzymywać wejście strony (ms).
 *
 * To nie jest tylko bezpiecznik na wypadek, gdyby skrypt planszy nie wczytał się albo padł.
 * Wejście hero stoi na `animation-play-state: paused`, czyli przy kryciu zero — a element
 * o kryciu zero nie liczy się do „największego wyrysowania treści”. Pomiar Lighthouse na
 * dławionym łączu pokazał to co do sekundy: to samo wydanie bez wstrzymania miało LCP 4,0 s,
 * ze wstrzymaniem 5,2 s.
 *
 * Limit liczy się **od otwarcia dokumentu**, nie od chwili, w której powstał ten komponent.
 * Na normalnym łączu pakiet wchodzi ok. 450 ms, a przelot łuku zaczyna się ok. 600 ms —
 * czyli grubo przed limitem i choreografia („najpierw znak, potem strona”) zostaje.
 * Na łączu tak wolnym, że sam pakiet wchodzi później niż limit, wstrzymania nie ma wcale:
 * pierwsze wyrysowanie i tak jest później, więc nie ma czego opóźniać.
 */
const GRANICA_WSTRZYMANIA_MS = 1400;

/** Ile czasu minęło od otwarcia dokumentu. */
function odOtwarcia(): number {
  return typeof performance === "undefined" ? Number.MAX_SAFE_INTEGER : performance.now();
}

/** Czy ekran ładowania nadal zasłania stronę (jeszcze nie ruszył w stronę hero).
 *
 * Sam znacznik `dn-ladowanie-trwa` nie wystarczy: plansza może zejść, zanim pakiet
 * aplikacji zdąży się wykonać, i wtedy `dn:ladowanie-przejscie` przepada — nikogo
 * jeszcze nie ma, żeby go usłyszał. Dlatego liczy się też koniec (`dn-ladowanie-koniec`)
 * i to, czy warstwa w ogóle jest jeszcze w dokumencie.
 */
function planszaTrwa(doKonca = false): boolean {
  if (typeof document === "undefined") return false;
  // Przy ograniczonym ruchu strona nie czeka na nic. Wejście jest wtedy skrócone do
  // 0,01 ms, ale `animation-play-state: paused` zatrzymałoby je mimo to w pierwszej
  // klatce — czyli przy kryciu zero. Ustawienie, które ma ruch wyciszyć, schowałoby
  // nagłówek na czas planszy zamiast pokazać go od razu.
  if (ograniczonyRuch()) return false;
  // Za późno na wstrzymywanie: strona ma wejść od razu (patrz `GRANICA_WSTRZYMANIA_MS`).
  if (odOtwarcia() > GRANICA_WSTRZYMANIA_MS) return false;
  const html = document.documentElement;
  if (html.classList.contains("dn-ladowanie-koniec")) return false;
  if (!html.classList.contains("dn-ladowanie-trwa")) return false;
  const warstwa = document.querySelector(".dn-ladowanie");
  if (!warstwa) return false;
  // „Pomiń” to plansza zdejmowana bez przelotu — strona ma wtedy wejść od razu.
  if (warstwa.classList.contains("dn-ladowanie--pomin")) return false;
  // Strona produktu wchodzi **w trakcie** przelotu: znak wtapia się w łuk hero, więc oba
  // ruchy mają się zazębić. Powierzchnia bez łuku hero (logowanie, okno aplikacji) nie ma
  // w co wtopić znaku — tam przelotu nie ma, znak gaśnie w miejscu, a treść czeka, aż
  // zejdzie. Inaczej gasnący znak leży na formularzu i wygląda jak zabrudzenie ekranu.
  if (doKonca) return true;
  return !warstwa.classList.contains("dn-ladowanie--przejscie");
}

/** Czy strona ma na starcie wstrzymać swoje wejście (plansza jeszcze zasłania). */
export function otwarcieZagra(doKonca = false): boolean {
  return planszaTrwa(doKonca);
}

/** Stan otwarcia dla korzenia strony: „gra”, dopóki plansza marki zasłania treść.
 *
 * Przelot łuku w hero trwa dalej, gdy strona już wchodzi — tak ma być: znak wtapia się
 * w łuk nagłówka, a nie gaśnie przed nim. Dlatego sygnałem jest `dn:ladowanie-przejscie`
 * (początek przelotu), nie `dn:ladowanie-koniec`.
 */
export function useOtwarcie(doKonca = false): boolean {
  const [trwa, setTrwa] = useState(() => otwarcieZagra(doKonca));

  useEffect(() => {
    if (!trwa) return;
    const zwolnij = () => setTrwa(false);
    const sygnal = doKonca ? "dn:ladowanie-koniec" : "dn:ladowanie-przejscie";
    window.addEventListener(sygnal, zwolnij, { once: true });
    // Zdarzenie mogło pójść, zanim ten komponent powstał — stan planszy czytamy więc
    // również wprost z dokumentu, dopóki strona czeka.
    const zegar = window.setInterval(() => {
      if (!planszaTrwa(doKonca)) zwolnij();
    }, KROK_SPRAWDZENIA_MS);
    // Bezpiecznik: gdyby skrypt planszy nie wczytał się albo padł, strona nie może
    // zostać z wejściem zatrzymanym w pierwszej klatce na zawsze.
    const stoper = window.setTimeout(zwolnij, Math.max(0, GRANICA_WSTRZYMANIA_MS - odOtwarcia()));
    return () => {
      window.removeEventListener(sygnal, zwolnij);
      window.clearInterval(zegar);
      window.clearTimeout(stoper);
    };
  }, [trwa, doKonca]);

  return trwa;
}
