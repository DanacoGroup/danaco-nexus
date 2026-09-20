// Widok stanu sprzedaży: tytuł, komunikat i jedno działanie wskazane przez serwer.
// Treść przychodzi z pola „stan” odpowiedzi API, więc moduł i portal mówią to samo.

import { AlertIcon, CheckIcon, SparkIcon } from "../components/icons";
import { ExternalIcon } from "../shell/icons";
import type { DzialanieStanu, FakturaInfo, StanSprzedazy, TonStanu } from "./api";

const PRZYCISK = "rounded-xl px-4 py-2.5 text-sm font-medium transition-colors";
const RAMKA: Record<TonStanu, string> = {
  informacja: "border-line",
  sukces: "border-success/40",
  uwaga: "border-warning/40",
  blad: "border-danger/40",
};
const ZNAK: Record<TonStanu, string> = {
  informacja: "text-accent",
  sukces: "text-success",
  uwaga: "text-warning",
  blad: "text-danger",
};

function Ikona({ ton }: { ton: TonStanu }) {
  if (ton === "sukces") return <CheckIcon size={18} />;
  if (ton === "informacja") return <SparkIcon size={18} />;
  return <AlertIcon size={18} />;
}

export function StanPlanu({
  stan,
  faktura,
  zajety,
  onWybierzPlan,
  onPortal,
}: {
  stan: StanSprzedazy;
  faktura: FakturaInfo | null;
  zajety: boolean;
  onWybierzPlan: () => void;
  onPortal: () => void;
}) {
  const dzialanie: DzialanieStanu = stan.dzialanie;
  const adresFaktury = faktura?.strona_url ?? "";
  return (
    <section
      aria-live="polite"
      className={`flex flex-wrap items-start gap-3 rounded-3xl border bg-raised/40 p-5 md:p-6 ${RAMKA[stan.ton]}`}
    >
      <span className={`mt-0.5 shrink-0 ${ZNAK[stan.ton]}`} aria-hidden="true">
        <Ikona ton={stan.ton} />
      </span>
      <div className="min-w-60 flex-1">
        <h2 className="font-heading text-lg">{stan.tytul}</h2>
        <p className="mt-1 text-sm text-muted">{stan.komunikat}</p>
      </div>
      {dzialanie === "zaplac_fakture" && adresFaktury && (
        <a
          className={`${PRZYCISK} inline-flex items-center gap-1.5 bg-accent-fill text-on-accent hover:bg-accent-fill-hover`}
          href={adresFaktury}
          target="_blank"
          rel="noreferrer noopener"
        >
          <ExternalIcon size={15} /> {stan.etykieta_dzialania}
        </a>
      )}
      {dzialanie === "portal" && (
        <button
          type="button"
          className={`${PRZYCISK} bg-accent-fill text-on-accent hover:bg-accent-fill-hover`}
          disabled={zajety}
          onClick={onPortal}
        >
          {stan.etykieta_dzialania}
        </button>
      )}
      {dzialanie === "wybierz_plan" && (
        <button
          type="button"
          className={`${PRZYCISK} bg-accent-fill text-on-accent hover:bg-accent-fill-hover`}
          onClick={onWybierzPlan}
        >
          {stan.etykieta_dzialania}
        </button>
      )}
    </section>
  );
}
