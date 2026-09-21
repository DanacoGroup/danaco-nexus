// Ekran wylogowania: ujęcie „moment-wylogowanie” z pakietu ruchu zamiast skoku do logowania.
//
// Pakiet ruchu wydał osobne ujęcie na tę chwilę i jako jedyne nie było podpięte:
// kliknięcie „Wyloguj” gasiło aplikację natychmiast, bez żadnego domknięcia. Ujęcie trwa
// krócej niż sekundę — tyle, żeby wyjście wyglądało na wyjście, a nie na awarię.
//
// Zamknięcie sesji leci od razu (nie czeka na film); ekran tylko przykrywa ten moment.

import { EkranPrzejscia } from "../ruch";

export function EkranWylogowania({ onKoniec }: { onKoniec: () => void }) {
  return (
    <EkranPrzejscia
      nazwa="moment-wylogowanie"
      etykieta="Wylogowywanie"
      onKoniec={onKoniec}
      bezpiecznikMs={1600}
      className="max-h-[40vh] w-auto"
    />
  );
}
