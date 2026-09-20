// Ekran wyboru planu: przełącznik okresu rozliczeniowego, kod rabatowy i przejście do zakupu.
// Przy opłaconym planie serwer kieruje zmianę do rozliczeń Stripe zamiast nowej płatności.

import { useState, type FormEvent } from "react";
import { ApiError } from "../api";
import { AlertIcon, CheckIcon } from "../components/icons";
import {
  cenaPlanu,
  kwota,
  opisOkresu,
  opisOkresuProbnego,
  oszczednoscRoczna,
  planBiezacy,
  platnosciApi,
  type CennikInfo,
  type KuponInfo,
  type Okres,
  type PlanInfo,
  type SubskrypcjaInfo,
} from "./api";

const KARTA = "flex flex-col rounded-3xl border border-line bg-raised/40 p-5 md:p-6";
const PRZYCISK = "rounded-xl px-4 py-2.5 text-sm font-medium transition-colors";
const POLE =
  "w-full rounded-xl border border-line bg-app px-3.5 py-2.5 text-[15px] outline-none transition-colors focus:border-accent";

function Przelacznik({ okres, onZmiana }: { okres: Okres; onZmiana: (wartosc: Okres) => void }) {
  return (
    <div className="inline-flex rounded-xl border border-line bg-raised/40 p-1" role="group" aria-label="Okres rozliczeniowy">
      {(["miesiac", "rok"] as const).map((wartosc) => (
        <button
          key={wartosc}
          type="button"
          aria-pressed={okres === wartosc}
          onClick={() => onZmiana(wartosc)}
          className={`${PRZYCISK} ${okres === wartosc ? "bg-accent-fill text-on-accent" : "text-muted hover:text-fg"}`}
        >
          {wartosc === "miesiac" ? "Miesięcznie" : "Rocznie"}
        </button>
      ))}
    </div>
  );
}

function Cena({ plan, okres, waluta }: { plan: PlanInfo; okres: Okres; waluta: string }) {
  const groszy = cenaPlanu(plan, okres);
  if (groszy <= 0) return <p className="font-heading text-3xl text-muted">Cena przy starcie</p>;
  const oszczednosc = okres === "rok" ? oszczednoscRoczna(plan) : 0;
  return (
    <div>
      <p className="font-heading text-3xl">
        {kwota(groszy, waluta)}
        <span className="ml-1 text-base font-normal text-muted">{okres === "rok" ? "/ rok" : "/ miesiąc"}</span>
      </p>
      {oszczednosc > 0 && <p className="mt-1 text-sm text-success">Rocznie taniej o {oszczednosc}%</p>}
    </div>
  );
}

/** Napis na przycisku planu: zakup, zmiana planu albo powód, dla którego nie da się kupić. */
function etykietaZakupu(dostepny: boolean, biezacy: boolean, zmiana: boolean): string {
  if (biezacy) return "Plan aktywny";
  if (!dostepny) return "Wkrótce";
  return zmiana ? "Zmień na ten plan" : "Wybierz plan";
}

function Karta({
  plan,
  okres,
  waluta,
  subskrypcja,
  zajety,
  onKup,
}: {
  plan: PlanInfo;
  okres: Okres;
  waluta: string;
  subskrypcja: SubskrypcjaInfo;
  zajety: boolean;
  onKup: (plan: PlanInfo) => void;
}) {
  const dostepny = plan.do_kupienia[okres];
  const biezacy = planBiezacy(plan, subskrypcja, okres);
  const zmiana = subskrypcja.ma_platny_plan;
  return (
    <section className={`${KARTA} ${biezacy ? "border-accent" : ""}`}>
      <header className="flex items-start justify-between gap-3">
        <h2 className="font-heading text-xl">{plan.nazwa}</h2>
        {biezacy ? (
          <span className="rounded-lg bg-success-soft px-2.5 py-1 text-xs font-medium text-success">Twój plan</span>
        ) : (
          plan.znacznik && (
            <span className="rounded-lg bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent">{plan.znacznik}</span>
          )
        )}
      </header>
      <p className="mt-2 text-sm text-muted">{plan.opis}</p>
      <div className="mt-5">
        <Cena plan={plan} okres={okres} waluta={waluta} />
      </div>
      <ul className="mt-5 flex-1 space-y-2 text-sm">
        {plan.zawartosc.map((pozycja) => (
          <li key={pozycja} className="flex items-start gap-2">
            <CheckIcon size={16} className="mt-0.5 shrink-0 text-accent" />
            <span>{pozycja}</span>
          </li>
        ))}
      </ul>
      <p className="mt-5 text-sm">
        <strong className="font-semibold tabular-nums">
          {plan.kredyty_okresowo.toLocaleString("pl-PL")} kredytów
        </strong>{" "}
        <span className="text-muted">na okres rozliczeniowy</span>
      </p>
      <p className="mt-1 text-xs text-muted">Plik do {plan.limity.plik_mb} MB</p>
      {opisOkresuProbnego(plan) && !biezacy && (
        <p className="mt-3 text-xs text-muted">{opisOkresuProbnego(plan)}</p>
      )}
      <button
        type="button"
        disabled={!dostepny || zajety || biezacy}
        onClick={() => onKup(plan)}
        className={`${PRZYCISK} mt-5 w-full ${
          dostepny && !biezacy
            ? "bg-accent-fill text-on-accent hover:bg-accent-fill-hover"
            : "border border-line text-muted"
        } disabled:cursor-default`}
      >
        {etykietaZakupu(dostepny, biezacy, zmiana)}
      </button>
      {!dostepny && !biezacy && (
        <p className="mt-2 text-xs text-muted">
          Ten plan nie jest jeszcze w sprzedaży. Damy znać, gdy ruszy.
        </p>
      )}
    </section>
  );
}

export function Plany({ cennik }: { cennik: CennikInfo }) {
  const [okres, setOkres] = useState<Okres>(
    cennik.subskrypcja.okres === "rok" ? "rok" : "miesiac",
  );
  const [kupon, setKupon] = useState("");
  const [rabat, setRabat] = useState<KuponInfo | null>(null);
  const [zajety, setZajety] = useState(false);
  const [przekierowanie, setPrzekierowanie] = useState("");
  const [blad, setBlad] = useState("");

  const sprawdzKupon = async (event: FormEvent) => {
    event.preventDefault();
    setBlad("");
    setRabat(null);
    if (!kupon.trim()) {
      setBlad("Wpisz kod rabatowy albo kup plan bez kodu.");
      return;
    }
    try {
      setRabat(await platnosciApi.kupon(kupon.trim()));
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się sprawdzić kodu. Spróbuj ponownie.");
    }
  };

  const usunKupon = () => {
    setKupon("");
    setRabat(null);
    setBlad("");
  };

  const kup = async (plan: PlanInfo) => {
    setZajety(true);
    setBlad("");
    try {
      const wynik = await platnosciApi.zakup(plan.kod, okres, rabat ? rabat.kod : "");
      const nazwa = cennik.plany.find((pozycja) => pozycja.kod === wynik.plan)?.nazwa ?? plan.nazwa;
      const rozliczenie = opisOkresu(wynik.okres);
      setPrzekierowanie(
        wynik.tryb === "portal"
          ? `Zmianę na plan ${nazwa} (${rozliczenie}) potwierdzisz w rozliczeniach Stripe — otwieram je…`
          : `Przechodzę do bezpiecznej płatności Stripe za plan ${nazwa} (${rozliczenie})…`,
      );
      window.location.assign(wynik.url);
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się rozpocząć zakupu.");
      setPrzekierowanie("");
      setZajety(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-heading text-2xl">Wybierz plan</h1>
        <p className="text-sm text-muted">
          Każdy plan daje kredyty na okres rozliczeniowy — to z nich pracuje Nexus. Plan zmienisz
          i zakończysz w każdej chwili. Płatność obsługuje Stripe — Nexus nie przechowuje danych karty.
        </p>
      </header>

      {!cennik.sprzedaz_aktywna && (
        <section className="rounded-3xl border border-line bg-raised/40 p-5 md:p-6">
          <h2 className="font-heading text-lg">Sprzedaż nie jest jeszcze włączona</h2>
          <p className="mt-2 text-sm text-muted">
            Planów nie da się dziś kupić. Konto pracuje na przydzielonych kredytach — ich stan
            widzisz w sekcji „Moja subskrypcja”.
          </p>
        </section>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Przelacznik okres={okres} onZmiana={setOkres} />
        <form className="flex items-center gap-2" onSubmit={(event) => void sprawdzKupon(event)}>
          <label className="sr-only" htmlFor="kod-rabatowy">
            Kod rabatowy
          </label>
          <input
            id="kod-rabatowy"
            className={`${POLE} w-44`}
            placeholder="Np. LATO2026"
            value={kupon}
            maxLength={64}
            onChange={(event) => setKupon(event.target.value)}
          />
          <button type="submit" className={`${PRZYCISK} border border-line hover:bg-hover`}>
            Sprawdź
          </button>
          {rabat && (
            <button type="button" className={`${PRZYCISK} text-muted hover:text-fg`} onClick={usunKupon}>
              Usuń kod
            </button>
          )}
        </form>
      </div>

      {rabat && (
        <p className="flex items-center gap-2 rounded-xl bg-success-soft px-3.5 py-2.5 text-sm text-success">
          <CheckIcon size={16} />
          Kod {rabat.kod} działa:{" "}
          {rabat.rabat_procent > 0
            ? `${rabat.rabat_procent}% taniej`
            : `${kwota(rabat.rabat_gr, rabat.waluta || cennik.waluta)} rabatu`}
          {rabat.opis ? ` (${rabat.opis})` : ""}. Rabat doliczy się przy płatności.
        </p>
      )}
      {blad && (
        <p
          role="alert"
          className="flex items-center gap-2 rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-sm text-danger"
        >
          <AlertIcon size={16} /> {blad}
        </p>
      )}
      {przekierowanie && (
        <p aria-live="polite" className="flex items-center gap-2 text-sm text-muted">
          <span className="spinner" /> {przekierowanie}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cennik.plany.map((plan) => (
          <Karta
            key={plan.kod}
            plan={plan}
            okres={okres}
            waluta={cennik.waluta}
            subskrypcja={cennik.subskrypcja}
            zajety={zajety}
            onKup={(wybrany) => void kup(wybrany)}
          />
        ))}
      </div>
    </div>
  );
}
