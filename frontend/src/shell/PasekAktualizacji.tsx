// Pasek „jest nowa wersja” nad rozmową.
//
// Nowa wersja zgłaszała się dotąd wyłącznie przyciskiem w stopce panelu rozmów. Pomiar na
// zbudowanym interfejsie (21.09.2026) pokazał, że panel ma na telefonie `visibility:
// hidden` — a telefon jest podstawowym miejscem tej aplikacji, bo klient to instalacja PWA.
// Znaczyło to, że użytkownik telefonu dowiadywał się o nowej wersji tylko wtedy, gdy sam
// otworzył szufladę z historią rozmów. Service worker sprawdza aktualizacje co godzinę,
// więc niezauważona aktualizacja potrafiła czekać dowolnie długo.
//
// Pasek stoi tam, gdzie „brak połączenia” i „konto próbne” — pod nagłówkiem, na każdej
// szerokości. Nie znika sam: zamknięcie jest decyzją użytkownika, a odświeżenie przeładuje
// aplikację, więc nie można go zrobić bez pytania.

import { useState } from "react";
import { usePwa } from "../pwa";

export function PasekAktualizacji() {
  const pwa = usePwa();
  const [schowany, setSchowany] = useState(false);
  if (!pwa.updateReady || schowany) return null;
  return (
    <div className="flex flex-nowrap items-center gap-x-3 border-b border-line/60 bg-accent-soft px-4 py-2 text-sm">
      <span className="shrink-0 font-medium whitespace-nowrap text-accent">Jest nowa wersja</span>
      {/* Na telefonie w wierszu mieści się tylko tyle, ile naprawdę trzeba powiedzieć. */}
      <span className="hidden min-w-0 flex-1 truncate text-muted sm:inline">
        Odświeżenie wczyta ją od razu. Rozmowy i pliki zostają na koncie.
      </span>
      <button
        type="button"
        className="ml-auto shrink-0 rounded-lg bg-accent-fill px-3 py-1 font-medium text-on-accent"
        onClick={pwa.update}
      >
        Odśwież
      </button>
      <button
        type="button"
        className="shrink-0 rounded-lg px-2 py-1 text-muted hover:text-fg"
        onClick={() => setSchowany(true)}
      >
        Później
      </button>
    </div>
  );
}
