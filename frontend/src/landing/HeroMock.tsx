// Scena produktu w oknie aplikacji: okno PWA, panel w przeglądarce i telefon z rozmową głosową.
// Układ sceny: landing/LANDING_PAGE_SPEC.md, rozdz. 7.3.

import { CheckIcon, FileIcon, Logo, WaveIcon } from "../components/icons";
import { ChatIcon, CodeIcon, DevicesIcon, GlobeIcon, ImageIcon, InsertIcon, LayersIcon, SearchIcon } from "../shell/icons";

function KrokNarzedzia({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-line bg-raised/70 px-3 py-2 text-xs">
      <CheckIcon size={14} className="text-success" />
      <span className="font-medium">{label}</span>
      <span className="ml-auto text-muted tabular-nums">{detail}</span>
    </div>
  );
}

export function HeroMock() {
  return (
    <div className="relative mx-auto w-full max-w-[1040px]" aria-hidden="true">
      {/* Okno aplikacji (PWA): pasek tytułu bez paska adresu. */}
      <div className="overflow-hidden rounded-xl border border-line-strong bg-app shadow-[var(--shadow-floating)] md:rounded-2xl">
        <div className="titlebar-drag flex h-[38px] items-center gap-2 border-b border-line bg-side px-4">
          <Logo size={18} />
          <span className="text-xs font-medium">Danaco Nexus</span>
          <span className="ml-auto flex gap-1.5 text-line-strong">
            <span className="h-0.5 w-3 self-center bg-current" />
            <span className="size-2.5 border border-current" />
            <span className="relative size-2.5 before:absolute before:inset-x-0 before:top-1/2 before:h-px before:rotate-45 before:bg-current after:absolute after:inset-x-0 after:top-1/2 after:h-px after:-rotate-45 after:bg-current" />
          </span>
        </div>
        <div className="flex h-[340px] md:h-[420px]">
          <div className="hidden w-14 flex-col items-center gap-3 border-r border-line bg-side py-4 sm:flex">
            {[ChatIcon, WaveIcon, SearchIcon, ImageIcon, CodeIcon, DevicesIcon].map((Ikona, indeks) => (
              <span
                key={indeks}
                className={`grid size-9 place-items-center rounded-md ${indeks === 0 ? "bg-accent-soft text-accent" : "text-muted"}`}
              >
                <Ikona size={18} />
              </span>
            ))}
          </div>
          <div className="hidden w-52 flex-col gap-1 border-r border-line bg-side/60 p-3 text-xs lg:flex">
            <div className="mb-2 rounded-md border border-line px-2.5 py-1.5 font-medium">+ Nowa rozmowa</div>
            <div className="px-2 text-[11px] font-medium text-subtle">Dzisiaj</div>
            {["Kartka na 80. urodziny babci", "Faktura za sierpień", "Sobota w Kazimierzu", "Notatka z zebrania"].map(
              (tytul, indeks) => (
                <div
                  key={tytul}
                  className={`flex items-center gap-1.5 truncate rounded-md px-2 py-1.5 ${indeks === 0 ? "bg-hover" : "text-muted"}`}
                >
                  {indeks < 2 && <span className="spinner size-2.5 text-accent" />}
                  <span className="truncate">{tytul}</span>
                </div>
              ),
            )}
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-3 p-4 md:p-6 md:pr-28 lg:pr-36">
            <div className="ml-auto max-w-[80%] rounded-lg bg-bubble px-3.5 py-2 text-sm">
              Babcia kończy w niedzielę 80 lat. Odśwież to zdjęcie i zrób z niego kartkę do wydruku.
            </div>
            <div className="flex gap-2.5">
              <span className="aurora-tlo mt-0.5 grid size-6 shrink-0 place-items-center rounded-full">
                <Logo size={24} />
              </span>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="aurora-obrys rounded-md bg-raised/60 px-3 py-2 text-xs">
                  <span className="shimmer-text font-medium">Powiększenie AI 4×</span>
                  <span className="ml-2 text-muted tabular-nums">3,1 s</span>
                </div>
                <KrokNarzedzia label="Analiza zdjęcia" detail="800 × 800 px · 1,2 s" />
                <KrokNarzedzia label="Korekta zdjęcia" detail="kolory, kontrast · 4,6 s" />
                <div className="flex items-center gap-2.5 rounded-md border border-line bg-app px-3 py-2 text-xs">
                  <FileIcon size={16} className="text-accent" />
                  <span className="font-medium">kartka-babcia-80.pdf</span>
                  <span className="ml-auto text-muted">A5 · 2,8 MB</span>
                </div>
                <p className="text-sm leading-6">
                  Gotowe. Kartka A5 czeka na wydruk — życzenia ciepłe, <b>bez wierszyka</b>.
                </p>
              </div>
            </div>
            <div className="mt-auto rounded-lg border border-line bg-raised px-3.5 py-2.5 text-xs text-muted">
              Napisz do Nexusa…
            </div>
          </div>
        </div>
      </div>

      {/* Panel boczny w przeglądarce */}
      <div className="absolute -bottom-16 -left-4 hidden w-64 rounded-xl border border-line-strong bg-side p-3 shadow-[var(--shadow-floating)] md:block lg:-left-12">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium">
          <GlobeIcon size={14} className="text-accent" /> Panel na stronie
        </div>
        <div className="rounded-md bg-app p-2.5 text-xs leading-5">
          Dziękujemy za ciepłe słowa o śniadaniach! Przykro nam z powodu hałasu — w przyszłym tygodniu kończymy remont…
        </div>
        <div className="mt-2 flex gap-1.5 text-xs">
          <span className="inline-flex items-center gap-1 rounded-sm bg-accent-fill px-2 py-1 font-medium text-on-accent">
            <InsertIcon size={12} /> Wstaw
          </span>
          <span className="rounded-sm border border-line px-2 py-1 text-muted">Kopiuj</span>
        </div>
      </div>

      {/* Telefon z rozmową głosową */}
      <div className="absolute -right-2 -bottom-20 hidden h-[300px] w-[150px] flex-col items-center rounded-[28px] border-[5px] border-line-strong bg-[var(--color-neutral-950)] p-3 shadow-[var(--shadow-floating)] md:flex lg:-right-10">
        <div className="mb-auto h-1 w-10 rounded-full bg-line-strong" />
        <div className="voice-orb grid size-20 place-items-center rounded-full">
          <WaveIcon size={28} className="text-white" />
        </div>
        <div className="mt-4 text-xs font-medium text-[var(--color-neutral-50)]">Słucham…</div>
        <div className="mt-1 text-center text-[11px] leading-4 text-[var(--color-neutral-400)]">
          „Przeczytaj Zosi bajkę o smoku”
        </div>
        <div className="mt-auto flex items-center gap-1 text-[11px] text-[var(--color-neutral-400)]">
          <LayersIcon size={11} /> 3 zadania w tle
        </div>
      </div>
    </div>
  );
}
