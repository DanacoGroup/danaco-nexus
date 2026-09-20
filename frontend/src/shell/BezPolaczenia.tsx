// Pasek braku połączenia.
//
// Okno działa offline (powłoka jest w pamięci podręcznej), ale każde zlecenie wymaga
// serwera. Bez tego paska wysłana wiadomość po prostu nie wracała i wyglądało to na
// awarię aplikacji. Ujęcie „moment-brak-polaczenia” z pakietu ruchu było zrobione
// dokładnie na tę chwilę.

import { useEffect, useState } from "react";
import { NagranieStartu, ograniczonyRuch } from "../ruch";

/** Czy przeglądarka widzi sieć (bez pewności, że serwer odpowiada). */
function polaczone(): boolean {
  return typeof navigator === "undefined" || navigator.onLine !== false;
}

export function BezPolaczenia() {
  const [jest, setJest] = useState(polaczone);

  useEffect(() => {
    const odswiez = () => setJest(polaczone());
    window.addEventListener("online", odswiez);
    window.addEventListener("offline", odswiez);
    return () => {
      window.removeEventListener("online", odswiez);
      window.removeEventListener("offline", odswiez);
    };
  }, []);

  if (jest) return null;
  return (
    <div
      role="status"
      className="flex items-center gap-3 border-b border-warning/40 bg-warning-soft px-4 py-2 text-sm text-warning"
    >
      {!ograniczonyRuch() && (
        <NagranieStartu nazwa="moment-brak-polaczenia" petla className="h-7 w-10 shrink-0 object-contain" />
      )}
      <span>Brak połączenia. Okno działa, ale zlecenia ruszą dopiero, gdy sieć wróci.</span>
    </div>
  );
}
