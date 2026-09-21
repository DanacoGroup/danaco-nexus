// Panel grupy: skład, miejsca, zaproszenia i przekazanie roli założyciela.
//
// Plan „Grupa” dawało się kupić, ale nie dawało się nikogo do grupy dodać — cennik
// obiecywał mechanikę, której nie było. Tutaj jest jej obsługa.
//
// Formy dobrane do wagi działania, nie wszystkie pod jedną modłę: skład to lista z rolami,
// zaproszenie to jedno pole i przycisk, a rzeczy nieodwracalne (usunięcie kogoś,
// przekazanie roli, rozwiązanie grupy) stoją pod trzema kropkami i pytają o potwierdzenie.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api";
import { MoreIcon } from "../shell/icons";
import { grupaApi, type CzlonekGrupy, type GrupaInfo } from "./api";

const PRZYCISK = "rounded-xl px-4 py-2.5 text-sm font-medium transition-colors";
const GLOWNY = `${PRZYCISK} bg-accent-fill text-on-accent hover:bg-accent-fill-hover disabled:opacity-60`;
const DRUGI = `${PRZYCISK} border border-line text-muted hover:text-fg`;

/** Menu działań przy członku grupy — pod trzema kropkami, bo to rzeczy nieodwracalne. */
function MenuCzlonka({
  czlonek,
  jestemZalozycielem,
  onUsun,
  onPrzekaz,
}: {
  czlonek: CzlonekGrupy;
  jestemZalozycielem: boolean;
  onUsun: () => void;
  onPrzekaz: () => void;
}) {
  const [otwarte, setOtwarte] = useState(false);
  const mogeUsunac = (jestemZalozycielem && czlonek.rola !== "zalozyciel") || (czlonek.to_ja && czlonek.rola !== "zalozyciel");
  const mogePrzekazac = jestemZalozycielem && czlonek.rola !== "zalozyciel";
  if (!mogeUsunac && !mogePrzekazac) return null;
  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Działania: ${czlonek.email}`}
        aria-expanded={otwarte}
        onClick={() => setOtwarte((stan) => !stan)}
        className="grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-hover hover:text-fg"
      >
        <MoreIcon size={16} />
      </button>
      {otwarte && (
        <div
          role="menu"
          className="absolute right-0 z-10 mt-1 w-56 overflow-hidden rounded-xl border border-line bg-raised shadow-lg"
        >
          {mogePrzekazac && (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOtwarte(false);
                onPrzekaz();
              }}
              className="block w-full px-3 py-2.5 text-left text-sm text-fg hover:bg-hover"
            >
              Przekaż rolę założyciela
            </button>
          )}
          {mogeUsunac && (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOtwarte(false);
                onUsun();
              }}
              className="block w-full px-3 py-2.5 text-left text-sm text-danger hover:bg-hover"
            >
              {czlonek.to_ja ? "Wyjdź z grupy" : "Usuń z grupy"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function Grupa() {
  const [grupa, setGrupa] = useState<GrupaInfo | null>(null);
  const [miejsca, setMiejsca] = useState(0);
  const [wczytane, setWczytane] = useState(false);
  const [blad, setBlad] = useState("");
  const [nazwa, setNazwa] = useState("");
  const [email, setEmail] = useState("");
  const [odsylacz, setOdsylacz] = useState("");
  const [zajety, setZajety] = useState(false);

  const wczytaj = useCallback(async () => {
    try {
      const dane = await grupaApi.moja();
      setGrupa(dane.grupa);
      setMiejsca(dane.grupa?.miejsca ?? dane.miejsca ?? 0);
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się wczytać grupy.");
    } finally {
      setWczytane(true);
    }
  }, []);

  useEffect(() => {
    void wczytaj();
  }, [wczytaj]);

  const dzialaj = async (praca: () => Promise<{ grupa: GrupaInfo | null }>) => {
    setBlad("");
    setZajety(true);
    try {
      const dane = await praca();
      setGrupa(dane.grupa);
      if (dane.grupa) setMiejsca(dane.grupa.miejsca);
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się wykonać działania.");
    } finally {
      setZajety(false);
    }
  };

  if (!wczytane) return null;

  if (!grupa) {
    return (
      <section aria-labelledby="grupa-naglowek" className="rounded-2xl border border-line p-5">
        <h2 id="grupa-naglowek" className="font-heading text-lg font-semibold text-fg">
          Grupa
        </h2>
        <p className="mt-1.5 text-sm text-muted">
          Na planie Grupa pracuje do {miejsca || 5} osób na jednej puli dostępu — kupuje ją
          założyciel, a rozliczenie idzie za każdego użytkownika. Rolę założyciela można
          później przekazać komuś innemu.
        </p>
        {blad && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {blad}
          </p>
        )}
        <form
          className="mt-4 flex flex-wrap gap-2"
          onSubmit={(zdarzenie) => {
            zdarzenie.preventDefault();
            void dzialaj(() => grupaApi.zaloz(nazwa));
          }}
        >
          <input
            value={nazwa}
            onChange={(zdarzenie) => setNazwa(zdarzenie.target.value)}
            placeholder="Nazwa grupy (np. Kancelaria Nowak)"
            aria-label="Nazwa grupy"
            maxLength={120}
            className="h-11 min-w-0 flex-1 rounded-xl border border-line bg-app px-3 text-sm text-fg placeholder:text-subtle focus:border-accent focus:outline-none"
          />
          <button type="submit" disabled={zajety} className={GLOWNY}>
            Załóż grupę
          </button>
        </form>
      </section>
    );
  }

  const wolne = Math.max(0, grupa.miejsca - grupa.czlonkowie.length - grupa.zaproszenia.length);

  return (
    <section aria-labelledby="grupa-naglowek" className="rounded-2xl border border-line p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="grupa-naglowek" className="font-heading text-lg font-semibold text-fg">
          {grupa.nazwa || "Grupa"}
        </h2>
        <p className="text-sm text-muted">
          {grupa.czlonkowie.length} z {grupa.miejsca} miejsc
          {wolne > 0 ? ` · wolne: ${wolne}` : " · komplet"}
        </p>
      </div>
      <p className="mt-1.5 text-sm text-muted">
        {grupa.jestem_zalozycielem
          ? "Praca całej grupy schodzi z Twojej puli dostępu — to Ty ją przedłużasz."
          : "Pracujesz na wspólnej puli założyciela grupy."}
      </p>

      {blad && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {blad}
        </p>
      )}

      <ul className="mt-4 divide-y divide-line/60 rounded-xl border border-line">
        {grupa.czlonkowie.map((czlonek) => (
          <li key={czlonek.uzytkownik_id} className="flex items-center gap-3 px-3 py-2.5">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm text-fg">
                {czlonek.nazwa || czlonek.email}
                {czlonek.to_ja && <span className="text-muted"> — to Ty</span>}
              </span>
              <span className="block truncate text-xs text-muted">{czlonek.email}</span>
            </span>
            <span
              className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs ${
                czlonek.rola === "zalozyciel" ? "bg-accent-soft text-accent" : "text-muted"
              }`}
            >
              {czlonek.rola === "zalozyciel" ? "założyciel" : "członek"}
            </span>
            <MenuCzlonka
              czlonek={czlonek}
              jestemZalozycielem={grupa.jestem_zalozycielem}
              onUsun={() => void dzialaj(() => grupaApi.usun(czlonek.uzytkownik_id))}
              onPrzekaz={() => void dzialaj(() => grupaApi.przekaz(czlonek.uzytkownik_id))}
            />
          </li>
        ))}
      </ul>

      {grupa.zaproszenia.length > 0 && (
        <p className="mt-3 text-sm text-muted">
          Zaproszenia czekają na przyjęcie: {grupa.zaproszenia.map((pozycja) => pozycja.email).join(", ")}.
        </p>
      )}

      {grupa.jestem_zalozycielem && (
        <>
          <form
            className="mt-4 flex flex-wrap gap-2"
            onSubmit={(zdarzenie) => {
              zdarzenie.preventDefault();
              void dzialaj(async () => {
                const dane = await grupaApi.zapros(email);
                setOdsylacz(`${window.location.origin}${dane.odsylacz}`);
                setEmail("");
                return dane;
              });
            }}
          >
            <input
              type="email"
              value={email}
              onChange={(zdarzenie) => setEmail(zdarzenie.target.value)}
              placeholder="adres@example.com"
              aria-label="Adres osoby zapraszanej"
              required
              className="h-11 min-w-0 flex-1 rounded-xl border border-line bg-app px-3 text-sm text-fg placeholder:text-subtle focus:border-accent focus:outline-none"
            />
            <button type="submit" disabled={zajety || wolne === 0} className={GLOWNY}>
              Zaproś
            </button>
          </form>
          {odsylacz && (
            <p className="mt-2 text-sm text-muted">
              Przekaż ten odsyłacz osobie zapraszanej:{" "}
              <code className="rounded-md border border-line px-1.5 py-0.5 text-xs break-all">{odsylacz}</code>
            </p>
          )}
          <button
            type="button"
            disabled={zajety}
            onClick={() => {
              if (window.confirm("Rozwiązać grupę? Każdy wróci do rozliczania się na własnym koncie.")) {
                void dzialaj(() => grupaApi.rozwiaz());
              }
            }}
            className={`${DRUGI} mt-4`}
          >
            Rozwiąż grupę
          </button>
        </>
      )}
    </section>
  );
}
