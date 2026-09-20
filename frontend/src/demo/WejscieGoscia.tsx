// Wejście do aplikacji bez rejestracji: serwer zakłada konto próbne, a gość trafia
// do tego samego okna co klient płacący. Pod „Wypróbuj” ma się otworzyć produkt,
// nie jego makieta — dlatego ten ekran nie rysuje niczego poza chwilą oczekiwania.

import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Logo } from "../components/icons";
import { SCIEZKA } from "../shell/route";

interface Props {
  /** Konto próbne gotowe: powłoka pobiera dane użytkownika i pokazuje aplikację. */
  onWejscie: () => void;
}

export function WejscieGoscia({ onWejscie }: Props) {
  const [blad, setBlad] = useState("");
  const wystartowano = useRef(false);

  useEffect(() => {
    if (wystartowano.current) return;
    wystartowano.current = true;
    api
      .gosc()
      .then(() => onWejscie())
      .catch((error: unknown) => setBlad(error instanceof Error ? error.message : "Nie udało się otworzyć konta próbnego."));
  }, [onWejscie]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 bg-app px-6 text-center">
      <Logo size={36} />
      {blad ? (
        <>
          <p className="max-w-md text-sm text-fg">{blad}</p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <a
              href={SCIEZKA.aplikacja}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-on-accent"
            >
              Zaloguj się
            </a>
            <a href={SCIEZKA.stronaProduktu} className="text-sm text-muted underline-offset-4 hover:underline">
              Wróć na stronę
            </a>
          </div>
        </>
      ) : (
        <>
          <p className="text-sm text-muted" role="status" aria-live="polite">
            Przygotowuję Twoje konto próbne…
          </p>
          <div className="h-1 w-40 overflow-hidden rounded-full bg-raised">
            <div className="pasek-czekania h-full w-1/3 rounded-full bg-accent" />
          </div>
        </>
      )}
    </div>
  );
}
