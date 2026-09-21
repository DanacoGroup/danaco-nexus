// Terminal pomocniczy projektu: uruchom polecenie i zobacz jego wyjście.
//
// Moduł pokazywał pliki, zmiany i historię, ale nie dawał niczego uruchomić — żeby
// zobaczyć wynik testów, trzeba było prosić agenta i czytać jego relację zamiast surowego
// wyjścia. Tu wpisujesz polecenie i dostajesz dokładnie to, co wypisał program.
//
// To nie jest powłoka i serwer tego pilnuje: jedno polecenie naraz, bez potoków
// i przekierowań, wyłącznie z wykazu programów. Komunikat o odmowie mówi, czego brakuje.

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { kodApi } from "./api";

interface Wpis {
  polecenie: string;
  kod: number | null;
  wyjscie: string;
  obciete: boolean;
}

/** Polecenia podsuwane przy pustym terminalu — po nie sięga się najczęściej. */
const PODPOWIEDZI = ["git status", "npm test", "pytest -q", "ruff check .", "ls -la"];

export function Terminal({ project }: { project: string }) {
  const [wpisy, setWpisy] = useState<Wpis[]>([]);
  const [tekst, setTekst] = useState("");
  const [zajety, setZajety] = useState(false);
  const [historia, setHistoria] = useState<string[]>([]);
  const [pozycja, setPozycja] = useState(-1);
  const dol = useRef<HTMLDivElement>(null);

  // Nowe wyjście ma być widoczne bez przewijania — jak w każdym terminalu.
  useEffect(() => {
    dol.current?.scrollIntoView({ block: "end" });
  }, [wpisy, zajety]);

  // Zmiana projektu zaczyna nową sesję: wyjście z poprzedniego byłoby mylące.
  useEffect(() => {
    setWpisy([]);
    setHistoria([]);
    setPozycja(-1);
  }, [project]);

  const uruchom = async (polecenie: string) => {
    const tresc = polecenie.trim();
    if (!tresc || zajety) return;
    setZajety(true);
    setTekst("");
    setHistoria((poprzednie) => [tresc, ...poprzednie.filter((pozycja) => pozycja !== tresc)].slice(0, 50));
    setPozycja(-1);
    try {
      const wynik = await kodApi.polecenie(project, tresc);
      setWpisy((poprzednie) => [
        ...poprzednie,
        { polecenie: wynik.polecenie, kod: wynik.kod, wyjscie: wynik.wyjscie, obciete: wynik.obciete },
      ]);
    } catch (powod) {
      setWpisy((poprzednie) => [
        ...poprzednie,
        {
          polecenie: tresc,
          kod: null,
          wyjscie: powod instanceof Error ? powod.message : "Nie udało się uruchomić polecenia.",
          obciete: false,
        },
      ]);
    } finally {
      setZajety(false);
    }
  };

  const klawisz = (zdarzenie: KeyboardEvent<HTMLInputElement>) => {
    // Strzałki przewijają historię poleceń, tak jak w powłoce.
    if (zdarzenie.key !== "ArrowUp" && zdarzenie.key !== "ArrowDown") return;
    if (!historia.length) return;
    zdarzenie.preventDefault();
    const nowa = zdarzenie.key === "ArrowUp" ? Math.min(pozycja + 1, historia.length - 1) : pozycja - 1;
    setPozycja(nowa);
    setTekst(nowa < 0 ? "" : historia[nowa]);
  };

  const wyslij = (zdarzenie: FormEvent) => {
    zdarzenie.preventDefault();
    void uruchom(tekst);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-app">
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 font-mono text-[12.5px] leading-relaxed">
        {wpisy.length === 0 && !zajety && (
          <div className="text-muted">
            <p>Uruchom polecenie w katalogu projektu. To nie jest powłoka: jedno polecenie naraz.</p>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {PODPOWIEDZI.map((podpowiedz) => (
                <li key={podpowiedz}>
                  <button
                    type="button"
                    onClick={() => void uruchom(podpowiedz)}
                    className="rounded-md border border-line px-2 py-1 text-xs transition-colors hover:bg-hover hover:text-fg"
                  >
                    {podpowiedz}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {wpisy.map((wpis, indeks) => (
          <div key={`${wpis.polecenie}-${indeks}`} className="mb-3">
            <p className="flex items-baseline gap-2">
              <span aria-hidden="true" className="text-accent">
                ›
              </span>
              <span className="min-w-0 break-all text-fg">{wpis.polecenie}</span>
              {wpis.kod !== null && (
                <span className={`ml-auto shrink-0 text-[11px] ${wpis.kod === 0 ? "text-success" : "text-danger"}`}>
                  {wpis.kod === 0 ? "ok" : `kod ${wpis.kod}`}
                </span>
              )}
            </p>
            {wpis.obciete && (
              <p className="mt-1 text-[11px] text-subtle">Pokazany jest koniec wyjścia — początek został obcięty.</p>
            )}
            {wpis.wyjscie.trim() && (
              <pre className={`mt-1 whitespace-pre-wrap ${wpis.kod === null ? "text-danger" : "text-muted"}`}>
                {wpis.wyjscie.trimEnd()}
              </pre>
            )}
          </div>
        ))}
        {zajety && <p className="shimmer-text text-muted">Pracuje…</p>}
        <div ref={dol} />
      </div>
      <form onSubmit={wyslij} className="flex items-center gap-2 border-t border-line px-3 py-2">
        <span aria-hidden="true" className="font-mono text-accent">
          ›
        </span>
        <label className="sr-only" htmlFor={`terminal-${project}`}>
          Polecenie do uruchomienia w projekcie {project}
        </label>
        <input
          id={`terminal-${project}`}
          value={tekst}
          onChange={(zdarzenie) => setTekst(zdarzenie.target.value)}
          onKeyDown={klawisz}
          disabled={zajety}
          autoComplete="off"
          spellCheck={false}
          placeholder="np. npm test"
          className="min-w-0 flex-1 bg-transparent font-mono text-[12.5px] text-fg outline-none placeholder:text-subtle disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!tekst.trim() || zajety}
          className="rounded-lg bg-accent-fill px-3 py-1 text-sm font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-50"
        >
          Uruchom
        </button>
      </form>
    </div>
  );
}
