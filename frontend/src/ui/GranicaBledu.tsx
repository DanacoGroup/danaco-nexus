// Ostatnia siatka pod interfejsem: gdy któryś komponent rzuci wyjątek w trakcie rysowania,
// React zdejmuje **całe** drzewo i użytkownik zostaje z pustą stroną — bez słowa wyjaśnienia
// i bez wyjścia. Ta granica zamienia pustą stronę na zdanie i przycisk.
//
// Nie zastępuje obsługi błędów w miejscach, gdzie coś może pójść nie tak (zapytania do API
// mają własne komunikaty). Jest po to, żeby nieprzewidziany błąd nie wyglądał jak zepsuta
// aplikacja i żeby użytkownik wiedział, że jego praca została na serwerze.

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  blad: Error | null;
}

export class GranicaBledu extends Component<Props, State> {
  state: State = { blad: null };

  static getDerivedStateFromError(blad: Error): State {
    return { blad };
  }

  componentDidCatch(blad: Error, info: ErrorInfo): void {
    // Treść wyjątku zostaje w konsoli przeglądarki — na ekran idzie zdanie po ludzku.
    console.error("Błąd interfejsu:", blad, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.blad) return this.props.children;
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-app px-6 text-center text-fg">
        <h1 className="font-heading text-xl font-semibold">Coś się tu zacięło</h1>
        <p className="max-w-md text-sm text-muted">
          Okno napotkało błąd, z którego nie umie wyjść samo. Twoje rozmowy i pliki są na serwerze —
          odświeżenie strony nic nie kasuje.
        </p>
        <button
          type="button"
          className="rounded-xl bg-accent-fill px-4 py-2 text-sm font-medium text-on-accent"
          onClick={() => window.location.reload()}
        >
          Odśwież okno
        </button>
      </div>
    );
  }
}
