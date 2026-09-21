// Scena produktu w hero: nagranie uruchomienia aplikacji z pakietu ruchu.
//
// Wcześniej stała tu makieta złożona ręcznie z elementów interfejsu. Pakiet motion ma
// gotowe nagranie tego samego ekranu — lepiej dopracowane i w ruchu, więc pokazuje
// produkt, zamiast go opisywać. Makieta zostaje jako zapas: przy ograniczonym ruchu
// w systemie i gdy nagranie się nie wczyta.
//
// Kliknięcie powiększa scenę na pełny ekran — na stronie produktu makieta bez
// powiększenia jest bezużyteczna, bo szczegółów interfejsu nie da się odczytać.
//
// Nagranie chodzi w pętli (jeden obieg to niecałe trzy sekundy), więc ruch trwa tak
// długo, jak długo ktoś patrzy na hero. WCAG 2.2.2 wymaga przy takim ruchu sposobu
// zatrzymania go — stąd przycisk „Wstrzymaj pokaz” w rogu sceny. Wstrzymanie jest
// mocniejsze niż widoczność: po przewinięciu strony w dół i z powrotem nagranie stoi
// dalej, dopóki ktoś sam go nie wznowi.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { CloseIcon, PauseIcon, PlayIcon } from "../components/icons";
import { odtworz } from "../modules/mozliwosci/odtwarzanie";
import { useOdtwarzajWWidoku } from "../ruch";
import { useOknoModalne } from "../ui/useOknoModalne";
import { HeroMock } from "./HeroMock";

const NAGRANIE = "/ruch/start/uruchomienie-komputer-ciemny";

/** Czy system prosi o ograniczenie ruchu. */
function ograniczonyRuch(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

export function ScenaHero() {
  const [bezRuchu, setBezRuchu] = useState(true);
  const [awaria, setAwaria] = useState(false);
  const [powiekszona, setPowiekszona] = useState(false);
  const [wstrzymane, setWstrzymane] = useState(false);
  const wideo = useRef<HTMLVideoElement>(null);

  useEffect(() => setBezRuchu(ograniczonyRuch()), []);

  // Scena chodzi w pętli, bo pokazuje produkt — ale tylko wtedy, gdy ktoś na nią patrzy
  // i nie poprosił o ciszę przyciskiem.
  useOdtwarzajWWidoku(wideo, [bezRuchu, awaria, powiekszona, wstrzymane], wstrzymane);

  if (bezRuchu || awaria) return <HeroMock />;

  const film = (klasa: string) => (
    <video
      ref={wideo}
      className={klasa}
      muted
      loop
      playsInline
      autoPlay={!wstrzymane}
      preload="metadata"
      poster={`${NAGRANIE}.png`}
      aria-hidden="true"
      onError={() => setAwaria(true)}
      onLoadedData={(zdarzenie) => odtworz(zdarzenie.currentTarget)}
    >
      <source src={`${NAGRANIE}.webm`} type="video/webm" />
      <source src={`${NAGRANIE}.mp4`} type="video/mp4" />
    </video>
  );

  // Przycisk sterowania nie może siedzieć w przycisku powiększenia (zagnieżdżony
  // <button> to nieprawidłowy HTML i klawiatura go nie osiąga), więc oba są rodzeństwem
  // we wspólnej ramce.
  return (
    <>
      <div className="relative mx-auto w-full max-w-[1040px]">
        <button
          type="button"
          onClick={() => setPowiekszona(true)}
          aria-label="Powiększ podgląd aplikacji"
          className="group block w-full cursor-zoom-in overflow-hidden rounded-xl border border-line-strong bg-app shadow-[var(--shadow-floating)] md:rounded-2xl"
        >
          {film("block w-full")}
          <span className="absolute right-4 bottom-4 rounded-full bg-app/85 px-3 py-1.5 text-xs text-fg opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
            Powiększ
          </span>
        </button>
        <button
          type="button"
          onClick={() => setWstrzymane((stan) => !stan)}
          aria-label={wstrzymane ? "Wznów pokaz aplikacji" : "Wstrzymaj pokaz aplikacji"}
          className="absolute bottom-4 left-4 flex items-center gap-1.5 rounded-full bg-app/85 px-3 py-1.5 text-xs text-fg backdrop-blur transition-colors hover:bg-app"
        >
          {wstrzymane ? <PlayIcon size={14} /> : <PauseIcon size={14} />}
          {wstrzymane ? "Wznów pokaz" : "Wstrzymaj pokaz"}
        </button>
      </div>

      {powiekszona && <Powiekszenie onZamknij={() => setPowiekszona(false)}>{film}</Powiekszenie>}
    </>
  );
}

/** Nakładka powiększenia: fokus wchodzi do środka, Esc zamyka, tabulacja nie ucieka w tło. */
function Powiekszenie({ onZamknij, children }: { onZamknij: () => void; children: (klasa: string) => ReactNode }) {
  const nakladka = useRef<HTMLDivElement>(null);
  useOknoModalne(nakladka, onZamknij);

  return (
    <div
      ref={nakladka}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label="Podgląd aplikacji"
      className="fixed inset-0 z-50 grid place-items-center bg-scrim p-4 backdrop-blur-sm"
      onClick={onZamknij}
    >
      <div className="w-full max-w-[min(96vw,1600px)]" onClick={(zdarzenie) => zdarzenie.stopPropagation()}>
        {children("w-full rounded-xl border border-line-strong shadow-[var(--shadow-floating)]")}
      </div>
      <button
        type="button"
        onClick={onZamknij}
        aria-label="Zamknij podgląd"
        className="absolute top-4 right-4 grid size-11 place-items-center rounded-full bg-raised text-fg transition-colors hover:bg-hover"
      >
        <CloseIcon size={20} />
      </button>
    </div>
  );
}
