// Jeden obszar „status” osadzony w powłoce na stałe. Czytnik ekranu zna go od chwili
// otwarcia powłoki, więc tekst wpisany później jest ogłaszany bez zależności od tego,
// czy czytnik zdążył podchwycić świeżo wstawiony region (WCAG 2.2, 4.1.3).

import { useSyncExternalStore } from "react";

let tresc = "";
const sluchacze = new Set<() => void>();

/** Wpisuje komunikat do obszaru powłoki; pusty ciąg go czyści. */
export function ogloszenie(tekst: string): void {
  if (tekst === tresc) return;
  tresc = tekst;
  for (const sluchacz of sluchacze) sluchacz();
}

function subskrybuj(sluchacz: () => void): () => void {
  sluchacze.add(sluchacz);
  return () => void sluchacze.delete(sluchacz);
}

export function ObszarOgloszen() {
  const tekst = useSyncExternalStore(
    subskrybuj,
    () => tresc,
    () => "",
  );
  return (
    <span role="status" aria-live="polite" className="sr-only">
      {tekst}
    </span>
  );
}
