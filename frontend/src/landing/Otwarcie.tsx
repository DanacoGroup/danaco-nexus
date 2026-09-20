// Animacja otwarcia strony produktu.
//
// Pakiet ruchu ma na to gotowe ujęcie (motion/start, `intro-znaku`), ale nic go nie
// odtwarzało — pierwszy ekran zaczynał się od statycznego nagłówka. Nakładka leży nad
// gotową stroną i gaśnie sama, więc nie opóźnia ani treści, ani pomiaru LCP.
//
// Gra raz na sesję przeglądarki: przy każdym powrocie na stronę ta sama plansza byłaby
// przeszkodą, nie wrażeniem. Zamyka ją koniec nagrania, kliknięcie, klawisz, przewinięcie
// oraz twardy limit czasu — żadne z nich nie może zostawić strony pod zasłoną.

import { useCallback, useEffect, useState } from "react";
import { NagranieStartu, ograniczonyRuch } from "../ruch";

const KLUCZ = "nexus:otwarcie";

/** Najdłuższy czas, przez jaki nakładka ma prawo zasłaniać stronę. */
const LIMIT_MS = 2600;

/** Czy w tej sesji przeglądarki otwarcie już grało (brak pamięci = graj). */
function jużGrało(): boolean {
  try {
    return window.sessionStorage.getItem(KLUCZ) === "1";
  } catch {
    return false;
  }
}

function zapamietaj(): void {
  try {
    window.sessionStorage.setItem(KLUCZ, "1");
  } catch {
    // Tryb prywatny albo zablokowane dane witryny — otwarcie zagra ponownie, i tyle.
  }
}

export function Otwarcie() {
  const [stan, setStan] = useState<"gra" | "gasnie" | "koniec">(() =>
    jużGrało() || ograniczonyRuch() ? "koniec" : "gra",
  );

  const zakoncz = useCallback(() => {
    setStan((biezacy) => (biezacy === "gra" ? "gasnie" : biezacy));
    zapamietaj();
  }, []);

  useEffect(() => {
    if (stan !== "gra") return;
    const stoper = window.setTimeout(zakoncz, LIMIT_MS);
    const zdarzenia = ["pointerdown", "keydown", "wheel", "touchstart"] as const;
    for (const nazwa of zdarzenia) window.addEventListener(nazwa, zakoncz, { once: true, passive: true });
    return () => {
      window.clearTimeout(stoper);
      for (const nazwa of zdarzenia) window.removeEventListener(nazwa, zakoncz);
    };
  }, [stan, zakoncz]);

  if (stan === "koniec") return null;
  return (
    <div
      aria-hidden="true"
      data-gasnie={stan === "gasnie" ? "true" : "false"}
      onTransitionEnd={() => setStan("koniec")}
      className="otwarcie fixed inset-0 z-(--z-drop-overlay) flex items-center justify-center bg-app"
    >
      <NagranieStartu nazwa="intro-znaku" onKoniec={zakoncz} className="max-h-[42vh] w-auto" />
    </div>
  );
}
