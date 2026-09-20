// Saldo kredytów konta, historia zmian i dokupienie pakietu.
//
// Kredyt jest jednostką pracy agenta. Użytkownik ma widzieć nie tylko liczbę, ale i to,
// za co zeszła — „za co mi to zniknęło” jest pierwszym pytaniem płacącego użytkownika.
// Świadomie nie pokazujemy tu niczego o silniku: ani modeli, ani limitów usług, z których
// korzysta serwis. To rozliczenie użytkownika z nami, nie nasze z dostawcą.
//
// Pakiety stoją obok salda, bo tu użytkownik orientuje się, że kredyty się kończą; odesłanie
// go w tym miejscu do cennika planów kazałoby mu zmieniać plan zamiast dokupić jedną porcję.

import { useEffect, useState } from "react";
import { ApiError } from "../api";
import { platnosciApi, POWODY, type KredytyInfo, type PakietInfo, type PakietyInfo } from "./api";

function data(iso: string): string {
  const kiedy = new Date(iso);
  return Number.isNaN(kiedy.getTime())
    ? ""
    : kiedy.toLocaleString("pl-PL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

const PRZYCISK_PAKIETU =
  "flex flex-col gap-0.5 rounded-xl border px-3.5 py-2.5 text-left text-sm transition-colors";

function Pakiety({ pakiety, zajety, onKup }: { pakiety: PakietInfo[]; zajety: boolean; onKup: (kod: string) => void }) {
  const dostepne = pakiety.filter((pozycja) => pozycja.do_kupienia);
  return (
    <>
      <h3 className="mt-6 text-xs font-semibold tracking-[0.08em] text-subtle uppercase">Dokup kredyty</h3>
      {dostepne.length === 0 ? (
        <p className="mt-2 text-sm text-muted">
          Dokupienie kredytów będzie możliwe, gdy ruszy sprzedaż. Do tego czasu kredyty przychodzą
          wraz z planem.
        </p>
      ) : (
        <>
          <p className="mt-2 text-sm text-muted">
            Pakiet to jedna płatność poza abonamentem — kredyty zostają na koncie do wykorzystania.
          </p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-3">
            {dostepne.map((pozycja) => (
              <li key={pozycja.kod}>
                <button
                  type="button"
                  disabled={zajety}
                  onClick={() => onKup(pozycja.kod)}
                  className={`${PRZYCISK_PAKIETU} w-full border-line hover:border-accent hover:bg-hover disabled:cursor-default disabled:opacity-60`}
                >
                  <span className="font-medium text-fg">{pozycja.nazwa}</span>
                  <span className="font-heading text-lg tabular-nums text-accent">
                    +{pozycja.kredyty.toLocaleString("pl-PL")}
                  </span>
                  <span className="text-xs text-subtle">{pozycja.opis}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

export function Kredyty() {
  const [stan, setStan] = useState<KredytyInfo | null>(null);
  const [pakiety, setPakiety] = useState<PakietyInfo | null>(null);
  const [zajety, setZajety] = useState(false);
  const [blad, setBlad] = useState("");
  const [bladZakupu, setBladZakupu] = useState("");

  useEffect(() => {
    platnosciApi
      .kredyty()
      .then(setStan)
      .catch((awaria) => setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się pobrać salda."));
    // Brak listy pakietów nie może przesłonić salda — ekran działa dalej, tylko bez dokupienia.
    platnosciApi.pakiety().then(setPakiety).catch(() => setPakiety(null));
  }, []);

  const kup = async (kod: string) => {
    setZajety(true);
    setBladZakupu("");
    try {
      const { url } = await platnosciApi.zakupPakietu(kod);
      window.location.assign(url);
    } catch (awaria) {
      setBladZakupu(
        awaria instanceof ApiError ? awaria.message : "Nie udało się rozpocząć zakupu pakietu.",
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
        <p className="text-sm text-muted">Wczytywanie salda…</p>
      </section>
    );
  }

  const niskie = stan.saldo > 0 && stan.saldo < 200;
  const lista = Array.isArray(pakiety?.pakiety) ? pakiety.pakiety : [];
  return (
    <section aria-labelledby="kredyty-naglowek" className="rounded-2xl border border-line bg-raised p-5">
      <h2 id="kredyty-naglowek" className="font-heading text-base font-semibold text-fg">
        Kredyty
      </h2>
      <p className="mt-1 text-sm text-muted">
        Kredyt to jednostka pracy Nexusa. Zużywa się przy każdym zleconym zadaniu — więcej przy
        dłuższej pracy i przy narzędziach, które liczą dłużej.
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-6">
        <p>
          <span className="block text-xs text-subtle">Dostępne</span>
          <span
            className={`font-heading text-3xl font-bold tabular-nums ${
              stan.saldo === 0 ? "text-danger" : niskie ? "text-warning" : "text-fg"
            }`}
          >
            {stan.saldo.toLocaleString("pl-PL")}
          </span>
        </p>
        <p>
          <span className="block text-xs text-subtle">Przydzielone łącznie</span>
          <span className="text-sm tabular-nums text-muted">{stan.przydzielone.toLocaleString("pl-PL")}</span>
        </p>
        <p>
          <span className="block text-xs text-subtle">Zużyte łącznie</span>
          <span className="text-sm tabular-nums text-muted">{stan.zuzyte.toLocaleString("pl-PL")}</span>
        </p>
      </div>

      {stan.saldo === 0 && (
        <p role="status" className="mt-4 rounded-lg border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
          Kredyty się skończyły — nowe zadania ruszą po doładowaniu konta.
        </p>
      )}
      {niskie && (
        <p role="status" className="mt-4 rounded-lg border border-warning/40 bg-warning-soft px-3.5 py-2.5 text-sm text-warning">
          Zostało niewiele kredytów. Warto doładować, zanim zadania staną.
        </p>
      )}

      {lista.length > 0 && <Pakiety pakiety={lista} zajety={zajety} onKup={(kod) => void kup(kod)} />}
      {bladZakupu && (
        <p role="alert" className="mt-3 rounded-lg border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
          {bladZakupu}
        </p>
      )}

      {stan.historia.length > 0 && (
        <>
          <h3 className="mt-6 text-xs font-semibold tracking-[0.08em] text-subtle uppercase">Ostatnie zmiany</h3>
          <ul className="mt-2 divide-y divide-line/60">
            {stan.historia.map((ruch) => (
              <li key={ruch.id} className="flex items-center justify-between gap-4 py-2 text-sm">
                <span className="min-w-0">
                  <span className="block truncate text-fg">{POWODY[ruch.powod] ?? (ruch.opis || ruch.powod)}</span>
                  <span className="text-xs text-subtle">{data(ruch.kiedy)}</span>
                </span>
                <span className={`shrink-0 tabular-nums ${ruch.zmiana >= 0 ? "text-success" : "text-muted"}`}>
                  {ruch.zmiana >= 0 ? "+" : ""}
                  {ruch.zmiana.toLocaleString("pl-PL")}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
