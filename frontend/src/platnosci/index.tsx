// Moduł Płatności: wybór planu, powrót po zakupie i zarządzanie subskrypcją.
//
// Ekran domyka ścieżkę zakupu: „?zakup=udany&sesja=…” uzgadnia stan bez czekania na
// webhook, „?zakup=anulowany” wraca do cennika, a „?powrot=rozliczenia” pokazuje stan
// po zmianie planu albo rezygnacji w portalu Stripe.

import { useCallback, useEffect, useState, type SVGProps } from "react";
import { ApiError } from "../api";
import { AlertIcon, CheckIcon } from "../components/icons";
import type { NexusModule } from "../modules/registry";
import { Kredyty } from "./Kredyty";
import { MojaSubskrypcja } from "./MojaSubskrypcja";
import { Plany } from "./Plany";
import { StanPlanu } from "./StanPlanu";
import { data, opisOkresu, platnosciApi, type CennikInfo } from "./api";

type Widok = "subskrypcja" | "plany";
type Powrot = "" | "udany" | "anulowany" | "rozliczenia";

const PRZYCISK = "rounded-xl px-4 py-2.5 text-sm font-medium transition-colors";
const RAMKA = "mx-auto max-w-page space-y-5 px-4 py-6 md:px-6";

export function PlatnosciIcon({ size = 24, ...reszta }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...reszta}
    >
      <rect x="2.5" y="5" width="19" height="14" rx="3" />
      <path d="M2.5 10h19M6.5 15h3" />
    </svg>
  );
}

/** Odczytuje wynik powrotu ze Stripe i czyści adres z parametrów zakupu. */
export function odczytajPowrot(zapytanie: string): { wynik: Powrot; sesja: string } {
  const parametry = new URLSearchParams(zapytanie);
  const zakup = parametry.get("zakup");
  const powrot = parametry.get("powrot");
  if (zakup === "udany" || zakup === "anulowany") {
    return { wynik: zakup, sesja: parametry.get("sesja") ?? "" };
  }
  if (powrot === "rozliczenia") return { wynik: "rozliczenia", sesja: "" };
  return { wynik: "", sesja: "" };
}

/** Usuwa z adresu parametry powrotu, żeby odświeżenie strony nie powtarzało komunikatu. */
function wyczyscAdres(): void {
  const parametry = new URLSearchParams(window.location.search);
  ["zakup", "sesja", "powrot"].forEach((nazwa) => parametry.delete(nazwa));
  const zapytanie = parametry.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${zapytanie ? `?${zapytanie}` : ""}`);
}

function Potwierdzenie({ cennik }: { cennik: CennikInfo }) {
  const { nazwa_planu, okres, okres_do } = cennik.subskrypcja;
  const rozliczenie = opisOkresu(okres);
  return (
    <section className="rounded-3xl border border-success/40 bg-raised/40 p-5 md:p-6">
      <h2 className="flex items-center gap-2 font-heading text-lg text-success">
        <CheckIcon size={18} /> Zakup przyjęty
      </h2>
      <p className="mt-2 text-sm text-muted">
        Plan {nazwa_planu} jest włączony{rozliczenie ? ` — ${rozliczenie}` : ""}
        {okres_do ? `, kolejne odnowienie ${data(okres_do)}` : ""}. Faktura pojawia się na liście niżej
        w ciągu kilku minut od potwierdzenia płatności przez Stripe.
      </p>
    </section>
  );
}

export function PlatnosciPage() {
  const [cennik, setCennik] = useState<CennikInfo | null>(null);
  const [widok, setWidok] = useState<Widok>("subskrypcja");
  const [powrot, setPowrot] = useState<Powrot>("");
  const [zajety, setZajety] = useState(false);
  const [blad, setBlad] = useState("");

  const wczytaj = useCallback(async () => {
    try {
      setCennik(await platnosciApi.cennik());
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się wczytać cennika.");
    }
  }, []);

  useEffect(() => {
    const { wynik, sesja } = odczytajPowrot(window.location.search);
    setPowrot(wynik);
    if (wynik) wyczyscAdres();
    if (wynik === "anulowany") setWidok("plany");
    const start = async () => {
      if (wynik === "udany" && sesja) {
        try {
          await platnosciApi.powrot(sesja);
        } catch (awaria) {
          // Brak uzgodnienia nie jest błędem zakupu – stan przyniesie webhook Stripe.
          setBlad(awaria instanceof ApiError ? awaria.message : "");
        }
      }
      await wczytaj();
    };
    void start();
  }, [wczytaj]);

  const otworzPortal = useCallback(async () => {
    setZajety(true);
    setBlad("");
    try {
      const { url } = await platnosciApi.portal();
      window.location.assign(url);
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się otworzyć rozliczeń.");
      setZajety(false);
    }
  }, []);

  if (blad && !cennik) {
    return (
      <div className={RAMKA}>
        <h1 className="font-heading text-2xl font-bold tracking-tight">Płatności</h1>
        <p
          role="alert"
          className="flex items-center gap-2 rounded-xl border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-sm text-danger"
        >
          <AlertIcon size={16} /> {blad}
        </p>
        <p className="text-sm text-muted">
          Cennik pobiera się z serwera. Odśwież stronę za chwilę — saldo kredytów i plan pozostają
          bez zmian.
        </p>
      </div>
    );
  }
  if (!cennik) {
    return (
      <div className={RAMKA}>
        <h1 className="font-heading text-2xl font-bold tracking-tight">Płatności</h1>
        <p className="flex items-center gap-2 text-sm text-muted">
          <span className="spinner" /> Wczytywanie cennika…
        </p>
      </div>
    );
  }

  return (
    <div className={RAMKA}>
      {powrot === "udany" && <Potwierdzenie cennik={cennik} />}
      {powrot === "anulowany" && (
        <p className="rounded-xl border border-line px-3.5 py-2.5 text-sm text-muted">
          Zakup został przerwany, nic nie zostało pobrane. Plan wybierzesz ponownie w każdej chwili.
        </p>
      )}
      {powrot === "rozliczenia" && (
        <p className="rounded-xl border border-line px-3.5 py-2.5 text-sm text-muted">
          Wracasz z rozliczeń Stripe. Zmiany widać poniżej — jeżeli jeszcze ich nie ma, odśwież stronę
          za chwilę.
        </p>
      )}

      <StanPlanu
        stan={cennik.subskrypcja.stan}
        faktura={cennik.subskrypcja.faktura_do_zaplaty}
        zajety={zajety}
        onWybierzPlan={() => setWidok("plany")}
        onPortal={() => void otworzPortal()}
      />

      <nav className="inline-flex rounded-xl border border-line bg-raised/40 p-1" aria-label="Sekcje płatności">
        {(
          [
            ["subskrypcja", "Moja subskrypcja"],
            ["plany", "Plany i ceny"],
          ] as const
        ).map(([klucz, etykieta]) => (
          <button
            key={klucz}
            type="button"
            aria-current={widok === klucz}
            onClick={() => setWidok(klucz)}
            className={`${PRZYCISK} ${widok === klucz ? "bg-accent-fill text-on-accent" : "text-muted hover:text-fg"}`}
          >
            {etykieta}
          </button>
        ))}
      </nav>

      {blad && (
        <p role="alert" className="flex items-center gap-2 rounded-xl border border-line px-3.5 py-2.5 text-sm text-muted">
          <AlertIcon size={16} /> {blad}
        </p>
      )}

      {widok === "plany" ? (
        <Plany cennik={cennik} />
      ) : (
        <>
          <Kredyty />
          <MojaSubskrypcja
            subskrypcja={cennik.subskrypcja}
            poZakupie={powrot === "udany"}
            onZmienPlan={() => setWidok("plany")}
            onPortal={() => void otworzPortal()}
            onOdswiez={() => void wczytaj()}
          />
        </>
      )}
    </div>
  );
}

/** Opis modułu dla rejestru interfejsu (src/modules/platnosci/index.tsx re-eksportuje go). */
export const module: NexusModule = {
  id: "platnosci",
  label: "Płatności",
  description: "Plan, subskrypcja, faktury i kody rabatowe. Płatność obsługuje Stripe.",
  icon: PlatnosciIcon,
  order: 95,
  Page: PlatnosciPage,
};
