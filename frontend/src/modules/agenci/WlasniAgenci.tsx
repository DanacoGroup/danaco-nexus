// Własni agenci: zapisane specjalizacje, które uruchamia się jednym kliknięciem.
//
// Moduł nazywał się „Agenci”, a nie dało się w nim utworzyć żadnego agenta — były tylko
// zadania w tle. Tu użytkownik opisuje raz, jak ma pracować „redaktor” albo „księgowy”,
// i potem zleca mu robotę bez powtarzania instrukcji. Agent jest zapisanym poleceniem,
// nie osobnym silnikiem: uruchomienie dokleja jego instrukcję do zadania i zleca je
// tak samo jak każde inne, więc działa w nim wszystko, co działa w rozmowie.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { MODE_LABELS, agenciApi, request, type Mode, type SzkicAgenta, type WlasnyAgent } from "./api";

/** Zestaw startowy: gotowe role do podejrzenia i przerobienia po swojemu. */
const WZORY: SzkicAgenta[] = [
  {
    nazwa: "Redaktor",
    opis: "Poprawia teksty przed wysłaniem.",
    instrukcja:
      "Poprawiasz styl, gramatykę i interpunkcję. Nie zmieniasz sensu ani faktów. " +
      "Oddajesz sam poprawiony tekst, bez komentarza o tym, co zmieniłeś.",
    tryb: "chat",
    projekt: "",
    ikona: "iskra",
  },
  {
    nazwa: "Analityk",
    opis: "Bada temat i oddaje raport ze źródłami.",
    instrukcja:
      "Badasz temat w sieci i w publikacjach naukowych. Oddajesz raport z przypisami do " +
      "źródeł. Rozdzielasz to, co potwierdzone, od tego, co jest opinią.",
    tryb: "research",
    projekt: "",
    ikona: "iskra",
  },
  {
    nazwa: "Sekretarz",
    opis: "Przegląda pocztę i pilnuje terminów.",
    instrukcja:
      "Przeglądasz pocztę, wyławiasz sprawy pilne i przygotowujesz odpowiedzi do " +
      "zatwierdzenia. Terminy, które padną w wiadomościach, wpisujesz do kalendarza.",
    tryb: "chat",
    projekt: "",
    ikona: "iskra",
  },
];

const PUSTY: SzkicAgenta = {
  nazwa: "",
  opis: "",
  instrukcja: "",
  tryb: "chat",
  projekt: "",
  ikona: "iskra",
};

const POLE = "w-full rounded-lg border border-line bg-app px-3 py-2 text-sm outline-none focus:border-accent";

function Formularz({
  poczatkowy,
  tytul,
  onZapisz,
  onAnuluj,
}: {
  poczatkowy: SzkicAgenta;
  tytul: string;
  onZapisz: (dane: SzkicAgenta) => Promise<void>;
  onAnuluj: () => void;
}) {
  const [dane, setDane] = useState<SzkicAgenta>(poczatkowy);
  const [projekty, setProjekty] = useState<string[]>([]);
  const [zajety, setZajety] = useState(false);
  const [blad, setBlad] = useState("");

  useEffect(() => {
    if (dane.tryb !== "code") return;
    request<{ name: string }[]>("GET", "/api/kod/projekty")
      .then((pozycje) => {
        setProjekty(pozycje.map((pozycja) => pozycja.name));
        setDane((biezace) => ({ ...biezace, projekt: biezace.projekt || pozycje[0]?.name || "" }));
      })
      .catch(() => setProjekty([]));
  }, [dane.tryb]);

  const zapisz = async (zdarzenie: FormEvent) => {
    zdarzenie.preventDefault();
    if (!dane.nazwa.trim() || !dane.instrukcja.trim() || zajety) return;
    setZajety(true);
    setBlad("");
    try {
      await onZapisz(dane);
    } catch (powod) {
      setBlad(powod instanceof Error ? powod.message : "Nie udało się zapisać agenta.");
      setZajety(false);
    }
  };

  return (
    <form onSubmit={zapisz} className="rounded-2xl border border-accent/40 bg-raised p-4">
      <h3 className="font-heading text-base font-semibold text-fg">{tytul}</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium">
          Nazwa
          <input
            value={dane.nazwa}
            onChange={(z) => setDane({ ...dane, nazwa: z.target.value })}
            maxLength={80}
            placeholder="Np. Redaktor"
            className={`mt-1 ${POLE}`}
          />
        </label>
        <label className="text-sm font-medium">
          Kiedy go używasz
          <input
            value={dane.opis}
            onChange={(z) => setDane({ ...dane, opis: z.target.value })}
            maxLength={300}
            placeholder="Np. Poprawia teksty przed wysłaniem."
            className={`mt-1 ${POLE}`}
          />
        </label>
      </div>
      <label className="mt-3 block text-sm font-medium">
        Jak ma pracować
        <textarea
          value={dane.instrukcja}
          onChange={(z) => setDane({ ...dane, instrukcja: z.target.value })}
          rows={5}
          maxLength={8000}
          placeholder="Opisz zwykłymi zdaniami, czym ten agent ma się zajmować i czego ma unikać."
          className={`mt-1 resize-y ${POLE}`}
        />
        <span className="mt-1 block text-xs text-muted">
          To jest sedno agenta — im dokładniej opiszesz sposób pracy, tym mniej będziesz musiał
          powtarzać przy każdym zadaniu.
        </span>
      </label>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="text-sm">
          Tryb{" "}
          <select
            value={dane.tryb}
            onChange={(z) => setDane({ ...dane, tryb: z.target.value as Mode })}
            className="rounded-lg border border-line bg-app px-2 py-1.5 text-sm"
          >
            {(Object.keys(MODE_LABELS) as Mode[]).map((klucz) => (
              <option key={klucz} value={klucz}>
                {MODE_LABELS[klucz]}
              </option>
            ))}
          </select>
        </label>
        {dane.tryb === "code" && (
          <label className="text-sm">
            Projekt{" "}
            <select
              value={dane.projekt}
              onChange={(z) => setDane({ ...dane, projekt: z.target.value })}
              className="rounded-lg border border-line bg-app px-2 py-1.5 text-sm"
            >
              {projekty.length === 0 && <option value="">Brak projektów</option>}
              {projekty.map((nazwa) => (
                <option key={nazwa} value={nazwa}>
                  {nazwa}
                </option>
              ))}
            </select>
          </label>
        )}
        <button type="button" onClick={onAnuluj} className="ml-auto rounded-lg px-3 py-1.5 text-sm text-muted hover:text-fg">
          Anuluj
        </button>
        <button
          type="submit"
          disabled={!dane.nazwa.trim() || !dane.instrukcja.trim() || zajety}
          className="rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent hover:bg-accent-fill-hover disabled:opacity-50"
        >
          {zajety ? "Zapisuję…" : "Zapisz agenta"}
        </button>
      </div>
      {blad && <p className="mt-2 text-sm text-danger">{blad}</p>}
    </form>
  );
}

function KartaAgenta({
  agent,
  onUruchom,
  onEdytuj,
  onUsun,
}: {
  agent: WlasnyAgent;
  onUruchom: (tekst: string) => Promise<void>;
  onEdytuj: () => void;
  onUsun: () => void;
}) {
  const [zadanie, setZadanie] = useState("");
  const [otwarte, setOtwarte] = useState(false);
  const [zajety, setZajety] = useState(false);
  const [blad, setBlad] = useState("");

  const uruchom = async (zdarzenie: FormEvent) => {
    zdarzenie.preventDefault();
    if (!zadanie.trim() || zajety) return;
    setZajety(true);
    setBlad("");
    try {
      await onUruchom(zadanie.trim());
      setZadanie("");
      setOtwarte(false);
    } catch (powod) {
      setBlad(powod instanceof Error ? powod.message : "Nie udało się uruchomić agenta.");
    } finally {
      setZajety(false);
    }
  };

  return (
    <li className="rounded-2xl border border-line bg-raised/50 p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="font-heading text-base font-semibold text-fg">{agent.nazwa}</h3>
          {agent.opis && <p className="mt-0.5 text-sm text-muted">{agent.opis}</p>}
          <p className="mt-1 text-xs text-subtle">
            {MODE_LABELS[agent.tryb] ?? agent.tryb}
            {agent.projekt && ` · ${agent.projekt}`}
            {agent.uruchomienia > 0 && ` · uruchomiony ${agent.uruchomienia} ×`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" onClick={onEdytuj} className="rounded-lg px-2.5 py-1.5 text-sm text-muted hover:bg-hover hover:text-fg">
            Zmień
          </button>
          <button type="button" onClick={onUsun} className="rounded-lg px-2.5 py-1.5 text-sm text-muted hover:bg-hover hover:text-danger">
            Usuń
          </button>
          <button
            type="button"
            onClick={() => setOtwarte((stan) => !stan)}
            className="rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent hover:bg-accent-fill-hover"
          >
            Zleć zadanie
          </button>
        </div>
      </div>
      {otwarte && (
        <form onSubmit={uruchom} className="mt-3">
          <label className="sr-only" htmlFor={`zadanie-${agent.id}`}>
            Zadanie dla agenta {agent.nazwa}
          </label>
          <textarea
            id={`zadanie-${agent.id}`}
            value={zadanie}
            onChange={(z) => setZadanie(z.target.value)}
            rows={3}
            autoFocus
            placeholder="Co ma teraz zrobić?"
            className={`resize-y ${POLE}`}
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={() => setOtwarte(false)} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:text-fg">
              Anuluj
            </button>
            <button
              type="submit"
              disabled={!zadanie.trim() || zajety}
              className="rounded-lg bg-accent-fill px-3 py-1.5 text-sm font-medium text-on-accent hover:bg-accent-fill-hover disabled:opacity-50"
            >
              {zajety ? "Uruchamiam…" : "Uruchom"}
            </button>
          </div>
          {blad && <p className="mt-2 text-sm text-danger">{blad}</p>}
        </form>
      )}
    </li>
  );
}

export function WlasniAgenci({ onOtworzRozmowe }: { onOtworzRozmowe: (id: string) => void }) {
  const [agenci, setAgenci] = useState<WlasnyAgent[] | null>(null);
  const [edytowany, setEdytowany] = useState<WlasnyAgent | null>(null);
  const [nowy, setNowy] = useState<SzkicAgenta | null>(null);
  const [blad, setBlad] = useState("");

  const odswiez = useCallback(async () => {
    try {
      setAgenci(await agenciApi.wlasni());
      setBlad("");
    } catch (powod) {
      setBlad(powod instanceof Error ? powod.message : "Nie udało się pobrać agentów.");
    }
  }, []);

  useEffect(() => {
    void odswiez();
  }, [odswiez]);

  const zapisz = async (dane: SzkicAgenta) => {
    if (edytowany) await agenciApi.zmienAgenta(edytowany.id, dane);
    else await agenciApi.utworzAgenta(dane);
    setEdytowany(null);
    setNowy(null);
    await odswiez();
  };

  const usun = async (agent: WlasnyAgent) => {
    await agenciApi.usunAgenta(agent.id);
    await odswiez();
  };

  const uruchom = async (agent: WlasnyAgent, tekst: string) => {
    const wynik = await agenciApi.uruchomAgenta(agent.id, tekst);
    await odswiez();
    onOtworzRozmowe(wynik.conversation_id);
  };

  return (
    <section aria-labelledby="wlasni-agenci" className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <h2 id="wlasni-agenci" className="font-heading text-lg font-semibold text-fg">
            Twoi agenci
          </h2>
          <p className="text-sm text-muted">
            Opisz raz, jak ma pracować, a potem zlecaj mu zadania bez powtarzania instrukcji.
          </p>
        </div>
        {!nowy && !edytowany && (
          <button
            type="button"
            onClick={() => setNowy(PUSTY)}
            className="rounded-lg border border-line-control px-3 py-1.5 text-sm font-medium transition-colors hover:bg-hover"
          >
            Nowy agent
          </button>
        )}
      </div>

      {blad && <p className="text-sm text-danger">{blad}</p>}

      {(nowy || edytowany) && (
        <Formularz
          poczatkowy={edytowany ?? nowy ?? PUSTY}
          tytul={edytowany ? `Zmień agenta „${edytowany.nazwa}”` : "Nowy agent"}
          onZapisz={zapisz}
          onAnuluj={() => {
            setNowy(null);
            setEdytowany(null);
          }}
        />
      )}

      {agenci && agenci.length > 0 && (
        <ul className="grid gap-2">
          {agenci.map((agent) => (
            <KartaAgenta
              key={agent.id}
              agent={agent}
              onUruchom={(tekst) => uruchom(agent, tekst)}
              onEdytuj={() => {
                setNowy(null);
                setEdytowany(agent);
              }}
              onUsun={() => void usun(agent)}
            />
          ))}
        </ul>
      )}

      {agenci && agenci.length === 0 && !nowy && (
        <div className="rounded-2xl border border-dashed border-line p-4">
          <p className="text-sm text-muted">
            Nie masz jeszcze żadnego agenta. Zacznij od gotowego wzoru — zmienisz go, kiedy zechcesz.
          </p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-3">
            {WZORY.map((wzor) => (
              <li key={wzor.nazwa}>
                <button
                  type="button"
                  onClick={() => setNowy(wzor)}
                  className="ui-nacisk w-full rounded-xl border border-line-control px-3 py-2.5 text-left transition-colors hover:bg-hover"
                >
                  <span className="block text-sm font-medium text-fg">{wzor.nazwa}</span>
                  <span className="mt-0.5 block text-xs text-muted">{wzor.opis}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
