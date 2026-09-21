// Wejście do aplikacji bez rejestracji: serwer zakłada konto próbne, a gość trafia
// do tego samego okna co klient płacący.

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { Logo } from "../components/icons";
import { EkranPrzejscia } from "../ruch";
import { SCIEZKA } from "../shell/route";

interface Props {
  /** Konto próbne gotowe: powłoka pobiera dane użytkownika i pokazuje aplikację. */
  onWejscie: () => void;
}

export function WejscieGoscia({ onWejscie }: Props) {
  const [blad, setBlad] = useState("");
  // Konto gotowe: zanim okno się pokaże, leci to samo ujęcie co po zwykłym logowaniu.
  // Wcześniej pasek postępu znikał, a aplikacja pojawiała się w tej samej klatce.
  const [gotowe, setGotowe] = useState(false);
  const wystartowano = useRef(false);

  useEffect(() => {
    if (wystartowano.current) return;
    wystartowano.current = true;
    api
      .gosc()
      .then(() => setGotowe(true))
      .catch((error: unknown) => {
        // Na ekran trafia tylko komunikat serwera (po polsku); awarie sieci mają treść techniczną.
        const odpowiedzSerwera = error instanceof ApiError ? error.message : "";
        setBlad(
          odpowiedzSerwera ||
            "Nie udało się teraz otworzyć konta próbnego. Sprawdź połączenie i spróbuj ponownie.",
        );
      });
  }, [onWejscie]);

  // To samo domknięcie, co po zwykłym logowaniu: znak rysuje się i zapala. Ujęcie
  // `logowanie-*` jest makietą produktu z cudzym adresem i powitaniem „Dzień dobry,
  // Dariuszu” — na koncie próbnym wyglądałoby to jak cudza sesja, nie jak własna.
  if (gotowe) return <EkranPrzejscia moment="logowanie" etykieta="Otwieranie konta próbnego" onKoniec={onWejscie} />;

  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 bg-app px-6 text-center">
      <Logo size={36} />
      {blad ? (
        <>
          {/* Bez roli „alert” czytnik ekranu nie ogłosiłby niepowodzenia (WCAG 2.2, 4.1.3). */}
          <p role="alert" className="max-w-md text-sm text-fg">
            {blad}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <a
              href={SCIEZKA.aplikacja}
              className="rounded-lg bg-accent-fill px-4 py-2 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover"
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
