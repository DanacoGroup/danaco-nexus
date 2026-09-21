// Pobieranie danych portalu: jeden hook dla wszystkich stron (stan wczytywania, błąd, odświeżenie).

import { useCallback, useEffect, useState } from "react";

export interface Zasob<T> {
  dane: T | null;
  blad: string;
  ladowanie: boolean;
  odswiez: () => void;
}

/**
 * Pobiera dane funkcją ``pobierz`` przy zmianie ``klucz``. Odpowiedzi z nieaktualnych żądań są
 * odrzucane, więc szybka zmiana trasy nie nadpisuje treści nowej strony starą.
 */
export function useZasob<T>(pobierz: () => Promise<T>, klucz: string): Zasob<T> {
  const [dane, setDane] = useState<T | null>(null);
  const [blad, setBlad] = useState("");
  const [ladowanie, setLadowanie] = useState(true);
  const [licznik, setLicznik] = useState(0);

  useEffect(() => {
    let aktualne = true;
    setLadowanie(true);
    setBlad("");
    pobierz()
      .then((wynik) => {
        if (!aktualne) return;
        setDane(wynik);
        setLadowanie(false);
      })
      .catch((error: unknown) => {
        if (!aktualne) return;
        setDane(null);
        // Komunikat serwera nie trafia na stronę. Ten hak wczytuje **treść** portalu —
        // stronę główną, wpisy, dokumentację, wyszukiwanie — czyli miejsca, które czyta
        // każdy, kto wejdzie z wyszukiwarki. Odpowiedź serwera jest pisana do klienta
        // albo do administratora i potrafi powiedzieć odwiedzającemu „Wymagane logowanie.”
        // na stronie, na której nie ma czego logować. Zdanie jest więc jedno i nasze,
        // a szczegół idzie do konsoli. Komunikaty serwera zostają tam, gdzie są na miejscu:
        // przy formularzach (`komunikat()` w `portal/api.ts`), bo tam niosą treść walidacji.
        console.warn("Portal — nie udało się pobrać treści:", error);
        setBlad("Nie udało się pobrać treści. Odśwież stronę za chwilę albo napisz do nas.");
        setLadowanie(false);
      });
    return () => {
      aktualne = false;
    };
    // Zależność to klucz trasy – funkcja pobierająca jest tworzona przy każdym renderze.
  }, [klucz, licznik]); // eslint-disable-line react-hooks/exhaustive-deps

  const odswiez = useCallback(() => setLicznik((wartosc) => wartosc + 1), []);
  return { dane, blad, ladowanie, odswiez };
}
