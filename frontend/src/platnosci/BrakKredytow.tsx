// Stan „konto bez kredytów” w oknie rozmowy.
//
// Serwer odmawia zlecenia (402) i podaje powód. Pokazany jak zwykły błąd wyglądałby na
// awarię, a to jest stan konta z jednym wyjściem — dlatego osobny widok z przejściem do
// dokupienia pakietu zamiast czerwonego paska.

const PRZYCISK = "rounded-xl px-4 py-2.5 text-sm font-medium transition-colors";

export function BrakKredytow({
  komunikat,
  onDokup,
  onZamknij,
}: {
  komunikat: string;
  onDokup: () => void;
  onZamknij: () => void;
}) {
  return (
    <section
      role="alert"
      aria-labelledby="brak-kredytow-naglowek"
      className="rounded-2xl border border-warning/50 bg-raised p-4 shadow-lg"
    >
      <h2 id="brak-kredytow-naglowek" className="font-heading text-base font-semibold text-fg">
        Skończyły się kredyty
      </h2>
      <p className="mt-1 text-sm text-muted">{komunikat}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onDokup}
          className={`${PRZYCISK} bg-accent-fill text-on-accent hover:bg-accent-fill-hover`}
        >
          Dokup kredyty
        </button>
        <button type="button" onClick={onZamknij} className={`${PRZYCISK} border border-line text-muted hover:text-fg`}>
          Zamknij
        </button>
      </div>
    </section>
  );
}
