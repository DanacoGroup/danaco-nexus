// Ekran przejścia: ujęcie z pakietu ruchu na czas zmiany stanu aplikacji.
//
// Logowanie i wejście na konto próbne kończyły się skokiem — formularz znikał, okno
// aplikacji pojawiało się w tej samej klatce. Pakiet ruchu ma na tę chwilę gotowe ujęcie;
// tutaj jest jego jedyne miejsce, wspólne dla obu wejść i dla wyjścia.
//
// Przejście nigdy nie blokuje: zamknięcie sesji leci swoim torem, a ekran ma bezpiecznik
// na wypadek, gdyby nagranie się nie wczytało. Przy `prefers-reduced-motion` nie ma ruchu
// i przejście jest natychmiastowe — o to właśnie prosi to ustawienie.

import { useEffect } from "react";
// Import wprost z sąsiadów, nie przez `./index`: beczka eksportuje ten plik, więc import
// z niej domykał cykl (madge: `ruch/index.ts > ruch/EkranPrzejscia.tsx`).
import { ograniczonyRuch } from "../preferencje";
import { NagranieStartu, type IdStartu } from "./NagranieStartu";
import { ZnakRuchu, type MomentZnaku } from "./ZnakRuchu";

export interface EkranPrzejsciaProps {
  /** Nagranie z pakietu ruchu — dla momentów, które pakiet wydał jako ujęcie znaku. */
  nazwa?: IdStartu;
  /** Znak w ruchu zamiast nagrania. Ma pierwszeństwo przed `nazwa`.
   *
   * Pakiet wydał na logowanie ujęcie, które jest makietą produktu, a nie ruchem znaku:
   * widać na nim cudzy formularz logowania z wpisanym adresem i powitanie „Dzień dobry,
   * Dariuszu”. Puszczone komuś po jego własnym zalogowaniu pokazywało obce imię i drugi
   * raz czynność, którą ten ktoś przed chwilą wykonał — w kadrze 1920 × 1080 obciętym
   * do okna, więc nieczytelnym. Znak rysuje tę samą choreografię, jest w barwach marki
   * i skaluje się do każdego ekranu.
   */
  moment?: MomentZnaku;
  etykieta: string;
  onKoniec: () => void;
  /** Po tylu ms przechodzimy dalej, nawet gdy ujęcie się nie wczytało. */
  bezpiecznikMs?: number;
  className?: string;
}

export function EkranPrzejscia({
  nazwa,
  moment,
  etykieta,
  onKoniec,
  bezpiecznikMs = 1800,
  className = "size-full object-cover",
}: EkranPrzejsciaProps) {
  const bezRuchu = ograniczonyRuch();

  useEffect(() => {
    if (bezRuchu) {
      onKoniec();
      return;
    }
    const zegar = window.setTimeout(onKoniec, bezpiecznikMs);
    return () => window.clearTimeout(zegar);
  }, [bezRuchu, bezpiecznikMs, onKoniec]);

  if (bezRuchu) return <div className="h-full bg-app" />;
  return (
    <div
      role="status"
      aria-label={etykieta}
      className="flex h-full items-center justify-center overflow-hidden bg-app"
    >
      {moment ? (
        <ZnakRuchu moment={moment} rozmiar={112} />
      ) : nazwa ? (
        <NagranieStartu nazwa={nazwa} onKoniec={onKoniec} className={className} />
      ) : null}
    </div>
  );
}
