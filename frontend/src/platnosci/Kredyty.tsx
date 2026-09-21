// Wykorzystanie dostępu: pasek zamiast liczb i przedłużenie dostępu kwotą.
//
// Kredyt jest jednostką rozliczeniową między nami a dostawcą modelu, nie towarem dla
// użytkownika. Pokazywanie salda w sztukach zmuszałoby go do liczenia, ile „kosztuje”
// jedno zdanie, i robiłoby z rozmowy licznik taksówki. Dlatego widać wyłącznie pasek
// wykorzystania — tyle, żeby dało się ocenić wzrokiem, ile zostało.
//
// Z tego samego powodu nie kupuje się tu „kredytów”, tylko przedłużenie dostępu: wpisujesz
// kwotę, za jaką chcesz dalej pracować. Ile pracy z tego wyjdzie, przelicza serwer.

import { useEffect, useState } from "react";
import { ApiError } from "../api";
import { kwota, platnosciApi, POWODY, type KredytyInfo } from "./api";

function data(iso: string): string {
  const kiedy = new Date(iso);
  return Number.isNaN(kiedy.getTime())
    ? ""
    : kiedy.toLocaleString("pl-PL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Barwa paska i komunikatu zależnie od tego, ile dostępu zostało. */
const BARWY: Record<KredytyInfo["stan"], { pasek: string; tekst: string }> = {
  w_porzadku: { pasek: "bg-accent-fill", tekst: "text-muted" },
  konczy_sie: { pasek: "bg-warning", tekst: "text-warning" },
  wyczerpany: { pasek: "bg-danger", tekst: "text-danger" },
};

const OPISY: Record<KredytyInfo["stan"], string> = {
  w_porzadku: "Dostęp w tym okresie rozliczeniowym.",
  konczy_sie: "Dostęp w tym okresie dobiega końca — warto go przedłużyć, zanim zadania staną.",
  wyczerpany: "Dostęp w tym okresie się wyczerpał. Nowe zadania ruszą po przedłużeniu.",
};

function Pasek({ stan }: { stan: KredytyInfo }) {
  const procent = Math.round(Math.min(1, Math.max(0, stan.zuzycie)) * 100);
  return (
    <div className="mt-4">
      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-hover"
        role="meter"
        aria-valuenow={procent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Wykorzystanie dostępu"
      >
        <div
          className={`h-full rounded-full transition-[width] duration-(--duration-slower) ${BARWY[stan.stan].pasek}`}
          style={{ width: `${procent}%` }}
        />
      </div>
      <p className={`mt-2 text-sm ${BARWY[stan.stan].tekst}`} role={stan.stan === "w_porzadku" ? undefined : "status"}>
        {OPISY[stan.stan]}
      </p>
    </div>
  );
}

/** Wybór kwoty przedłużenia: szybkie stawki i własna, nie niższa niż minimum. */
function Przedluzenie({
  stan,
  zajety,
  onKup,
}: {
  stan: KredytyInfo;
  zajety: boolean;
  onKup: (kwotaGr: number) => void;
}) {
  const { minimum_gr, maksimum_gr, kwoty_szybkie_gr, sprzedaz } = stan.doladowanie;
  const [wlasna, setWlasna] = useState("");

  if (!sprzedaz) {
    return (
      <p className="mt-6 text-sm text-muted">
        Przedłużenie dostępu będzie możliwe, gdy ruszy sprzedaż. Do tego czasu dostęp przychodzi
        wraz z planem.
      </p>
    );
  }

  const zWlasnej = Math.round(Number(wlasna.replace(",", ".")) * 100);
  const wlasnaPoprawna = Number.isFinite(zWlasnej) && zWlasnej >= minimum_gr && zWlasnej <= maksimum_gr;

  return (
    <>
      <h3 className="mt-6 text-xs font-semibold tracking-[0.08em] text-subtle uppercase">
        Przedłuż dostęp
      </h3>
      <p className="mt-2 text-sm text-muted">
        Jedna płatność poza abonamentem. Wybierz kwotę albo wpisz własną — od{" "}
        {kwota(minimum_gr)}.
      </p>
      <ul className="mt-3 flex flex-wrap gap-2">
        {kwoty_szybkie_gr.map((gr) => (
          <li key={gr}>
            <button
              type="button"
              disabled={zajety}
              onClick={() => onKup(gr)}
              className="ui-nacisk rounded-xl border border-line-control px-4 py-2.5 text-sm font-medium transition-colors hover:bg-hover disabled:opacity-60"
            >
              {kwota(gr)}
            </button>
          </li>
        ))}
      </ul>
      <form
        className="mt-3 flex flex-wrap items-center gap-2"
        onSubmit={(zdarzenie) => {
          zdarzenie.preventDefault();
          if (wlasnaPoprawna) onKup(zWlasnej);
        }}
      >
        <label className="text-sm text-muted">
          Własna kwota
          <span className="mt-1 flex items-center gap-2">
            <input
              value={wlasna}
              onChange={(zdarzenie) => setWlasna(zdarzenie.target.value)}
              inputMode="decimal"
              placeholder={String(minimum_gr / 100)}
              aria-label="Kwota przedłużenia w złotych"
              className="h-10 w-28 rounded-lg border border-line-control bg-app px-3 text-fg outline-none focus:border-accent"
            />
            <span aria-hidden="true">zł</span>
          </span>
        </label>
        <button
          type="submit"
          disabled={zajety || !wlasnaPoprawna}
          className="ui-nacisk mt-6 h-10 rounded-lg bg-accent-fill px-4 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-60"
        >
          Przedłuż
        </button>
      </form>
      {wlasna && !wlasnaPoprawna && (
        <p role="alert" className="mt-2 text-sm text-danger">
          Kwota musi mieścić się między {kwota(minimum_gr)} a {kwota(maksimum_gr)}.
        </p>
      )}
    </>
  );
}

export function Kredyty() {
  const [stan, setStan] = useState<KredytyInfo | null>(null);
  const [zajety, setZajety] = useState(false);
  const [blad, setBlad] = useState("");
  const [bladZakupu, setBladZakupu] = useState("");

  useEffect(() => {
    platnosciApi
      .kredyty()
      .then(setStan)
      .catch((awaria) =>
        setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się pobrać stanu dostępu."),
      );
  }, []);

  const kup = async (kwotaGr: number) => {
    setZajety(true);
    setBladZakupu("");
    try {
      const { url } = await platnosciApi.doladowanie(kwotaGr);
      window.location.assign(url);
    } catch (awaria) {
      setBladZakupu(
        awaria instanceof ApiError ? awaria.message : "Nie udało się rozpocząć płatności.",
      );
      setZajety(false);
    }
  };

  if (blad) {
    return (
      <section className="rounded-2xl border border-line bg-raised p-5">
        <p role="alert" className="text-sm text-danger">
          {blad}
        </p>
      </section>
    );
  }
  if (!stan) {
    return (
      <section className="rounded-2xl border border-line bg-raised p-5">
        <p className="text-sm text-muted">Wczytywanie…</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="kredyty-naglowek" className="rounded-2xl border border-line bg-raised p-5">
      <h2 id="kredyty-naglowek" className="font-heading text-base font-semibold text-fg">
        Wykorzystanie
      </h2>
      <p className="mt-1 text-sm text-muted">
        Pasek pokazuje, ile pracy Nexusa wykorzystałeś w tym okresie. Dłuższe zadania i narzędzia,
        które liczą dłużej, zużywają go szybciej.
      </p>

      <Pasek stan={stan} />
      <Przedluzenie stan={stan} zajety={zajety} onKup={(gr) => void kup(gr)} />

      {bladZakupu && (
        <p role="alert" className="mt-3 rounded-lg border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
          {bladZakupu}
        </p>
      )}

      {stan.historia.length > 0 && (
        <>
          <h3 className="mt-6 text-xs font-semibold tracking-[0.08em] text-subtle uppercase">
            Ostatnie zdarzenia
          </h3>
          <ul className="mt-2 divide-y divide-line/60">
            {stan.historia.map((ruch, indeks) => (
              <li key={`${ruch.kiedy}-${indeks}`} className="py-2 text-sm">
                <span className="block truncate text-fg">{POWODY[ruch.powod] ?? (ruch.opis || ruch.powod)}</span>
                <span className="text-xs text-subtle">{data(ruch.kiedy)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
