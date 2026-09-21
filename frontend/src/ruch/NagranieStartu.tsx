// Odtwarzacz nagrań z pakietu motion/start.
//
// Pakiet powstał pod konkretne momenty aplikacji — uruchomienie, logowanie, myślenie,
// sukces, błąd, brak połączenia, instalację, wylogowanie — i do czasu tej zmiany żaden
// z nich nie był podpięty: okno pokazywało puste tło tam, gdzie miał być ruch.

import { useEffect, useRef } from "react";
import { START } from "../media/katalog";
import { ograniczonyRuch } from "../preferencje";
import { useOdtwarzajWWidoku } from "./wejscia";

/** Identyfikator nagrania startowego — typ pilnuje, że nazwa istnieje w katalogu. */
export type IdStartu = (typeof START)[number]["id"];

const WEDLUG_ID = new Map(START.map((pozycja) => [pozycja.id, pozycja.zrodla]));

export function zrodlaStartu(id: IdStartu) {
  return WEDLUG_ID.get(id) ?? null;
}

/** Momenty, które pakiet ruchu wydał także bez wypalonego podpisu (wariant `-alfa`).
 *
 * Nagrania mają na sobie planszę opisową („Intro znaku · 2200 ms”) — to podpis
 * z demonstracji dla zespołu, a nie element produktu; na produkcji nie ma czego szukać
 * na ekranie użytkownika. Ujęcie `-alfa` jest tym samym ruchem bez podpisu i
 * z przezroczystym tłem. Wykaz jest wypisany, a nie zgadywany ze ścieżki: pozostałe
 * momenty wariantu nie mają i próba pobrania go kończyłaby się błędem przy każdym
 * uruchomieniu okna.
 */
export const BEZ_PODPISU = new Set([
  "intro-znaku",
  "moment-instalacja",
  "moment-blad",
  "moment-brak-polaczenia",
  "moment-mysli",
  "moment-sukces",
  "moment-wylogowanie",
]);

function zrodloBezPodpisu(nazwa: IdStartu, zrodla: { webm?: string }): string | null {
  if (!BEZ_PODPISU.has(nazwa) || !zrodla.webm) return null;
  return zrodla.webm.replace(/\.webm$/, "-alfa.webm");
}

export interface NagranieStartuProps {
  nazwa: IdStartu;
  /** Nagranie chodzi w pętli — wyłącznie dla stanów, które naprawdę trwają.
   *
   * Momenty z pakietu ruchu kończą się stanem docelowym (okno otwarte, użytkownik
   * zalogowany, aplikacja zainstalowana). Zapętlone skaczą z powrotem do początku
   * i wyglądają na urwane, a w tle ekranu, przy którym ktoś siedzi i nic nie robi,
   * są zwyczajnie męczące. Pętla ma sens tam, gdzie czekanie trwa: myślenie agenta,
   * brak połączenia.
   */
  petla?: boolean;
  /** Powtórzenie po przerwie (ms) — dla krótkich momentów pokazywanych jako ilustracja.
   *
   * Moment instalacji trwa 1200 ms. Puszczony raz przy wejściu na stronę kończy się,
   * zanim ktokolwiek dojdzie do sekcji „Instalacja”, i zostaje zamrożona ostatnia klatka
   * — dokładnie to wygląda jak nagranie urwane w połowie. Ciągła pętla z kolei skacze
   * co sekundę. Powtórzenie z przerwą pokazuje cały ruch od początku i daje odetchnąć
   * między przebiegami.
   */
  powtarzaj?: number;
  /** Wywoływane po jednorazowym odtworzeniu; z `petla` nie zadziała. */
  onKoniec?: () => void;
  className?: string;
}

/** Nagranie startowe jako warstwa dekoracyjna; przy ograniczonym ruchu nic nie rysuje. */
export function NagranieStartu({
  nazwa,
  petla = false,
  powtarzaj = 0,
  onKoniec,
  className = "",
}: NagranieStartuProps) {
  const wideo = useRef<HTMLVideoElement>(null);
  const zrodla = zrodlaStartu(nazwa);

  // Odtwarzanie startuje dopiero, gdy ujęcie wejdzie w pole widzenia. Inaczej krótkie
  // momenty kończą się w nieodwiedzonej jeszcze sekcji i widać samą ostatnią klatkę.
  // Bez `IntersectionObserver` (środowisko testowe, stara przeglądarka) gramy od razu —
  // lepiej pokazać ruch za wcześnie niż nie pokazać go wcale.
  useOdtwarzajWWidoku(wideo, [nazwa]);
  useEffect(() => {
    const element = wideo.current;
    if (!element || typeof IntersectionObserver === "function") return;
    void Promise.resolve(element.play()).catch(() => onKoniec?.());
  }, [nazwa, onKoniec]);

  // Powtórzenie z przerwą: po zakończeniu ujęcie czeka, wraca na początek i gra jeszcze raz.
  useEffect(() => {
    const element = wideo.current;
    if (!element || petla || powtarzaj <= 0) return;
    let zegar = 0;
    const naKoncu = () => {
      zegar = window.setTimeout(() => {
        element.currentTime = 0;
        void Promise.resolve(element.play()).catch(() => undefined);
      }, powtarzaj);
    };
    element.addEventListener("ended", naKoncu);
    return () => {
      element.removeEventListener("ended", naKoncu);
      window.clearTimeout(zegar);
    };
  }, [nazwa, petla, powtarzaj]);

  if (!zrodla || ograniczonyRuch()) return null;
  const bezPodpisu = zrodloBezPodpisu(nazwa, zrodla);
  return (
    <video
      ref={wideo}
      key={nazwa}
      className={className}
      muted
      playsInline
      loop={petla}
      preload="auto"
      aria-hidden="true"
      onEnded={petla ? undefined : onKoniec}
      onError={() => onKoniec?.()}
    >
      {bezPodpisu && <source src={bezPodpisu} type="video/webm" />}
      {zrodla.webm && <source src={zrodla.webm} type="video/webm" />}
      {zrodla.mp4 && <source src={zrodla.mp4} type="video/mp4" />}
    </video>
  );
}
