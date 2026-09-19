// Ilustracja na stronie startowej: okno aplikacji, panel w przeglądarce i telefon (czysty CSS, bez zrzutów).

import { CheckIcon, FileIcon, Logo, WaveIcon } from "../components/icons";
import { ChatIcon, CodeIcon, DevicesIcon, GlobeIcon, ImageIcon, InsertIcon, LayersIcon, SearchIcon } from "../shell/icons";

function ToolRow({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-line bg-raised/70 px-3 py-2 text-[12px]">
      <CheckIcon size={14} className="text-success" />
      <span className="font-medium">{label}</span>
      <span className="ml-auto text-muted tabular-nums">{detail}</span>
    </div>
  );
}

export function HeroMock() {
  return (
    <div className="relative mx-auto w-full max-w-[1040px]" aria-hidden="true">
      <div className="landing-glow absolute -inset-x-10 -top-16 bottom-0 -z-10" />
      {/* Okno aplikacji */}
      <div className="overflow-hidden rounded-2xl border border-line-strong/70 bg-app shadow-2xl shadow-black/50 md:rounded-3xl">
        <div className="flex items-center gap-1.5 border-b border-line bg-side px-4 py-2.5">
          <span className="size-2.5 rounded-full bg-[#ff5f57]" />
          <span className="size-2.5 rounded-full bg-[#febc2e]" />
          <span className="size-2.5 rounded-full bg-[#28c840]" />
          <span className="mx-auto rounded-md bg-app/70 px-10 py-0.5 text-[11px] text-muted">danaco-nexus.pl</span>
        </div>
        <div className="flex h-[340px] md:h-[420px]">
          <div className="hidden w-14 flex-col items-center gap-3 border-r border-line bg-side py-4 sm:flex">
            <Logo size={26} className="rounded-lg" />
            {[ChatIcon, WaveIcon, SearchIcon, ImageIcon, CodeIcon, DevicesIcon].map((Icon, index) => (
              <span
                key={index}
                className={`grid size-9 place-items-center rounded-xl ${index === 0 ? "bg-accent-soft text-accent" : "text-muted"}`}
              >
                <Icon size={18} />
              </span>
            ))}
          </div>
          <div className="hidden w-52 flex-col gap-1 border-r border-line bg-side/60 p-3 text-[12px] lg:flex">
            <div className="mb-2 rounded-lg border border-line px-2.5 py-1.5 font-medium">+ Nowa rozmowa</div>
            <div className="px-2 text-[10px] font-medium text-muted">Dzisiaj</div>
            {["Umowy – przeszukiwalny PDF", "Raport z faktur Q3", "Odpowiedzi na opinie", "Montaż wywiadu"].map((title, index) => (
              <div key={title} className={`flex items-center gap-1.5 truncate rounded-lg px-2 py-1.5 ${index === 0 ? "bg-hover" : "text-muted"}`}>
                {index < 2 && <span className="spinner size-2.5 text-accent" />}
                <span className="truncate">{title}</span>
              </div>
            ))}
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-3 p-4 md:p-6">
            <div className="ml-auto max-w-[80%] rounded-2xl bg-bubble px-3.5 py-2 text-[13px]">
              Zrób z tych 12 skanów jeden przeszukiwalny PDF i streść najważniejsze terminy.
            </div>
            <div className="flex gap-2.5">
              <Logo size={24} className="mt-0.5 shrink-0 rounded-md" />
              <div className="min-w-0 flex-1 space-y-2">
                <ToolRow label="Poprawa skanów" detail="12 stron · 8,4 s" />
                <ToolRow label="OCR dokumentów" detail="pol · 21,0 s" />
                <div className="flex items-center gap-2.5 rounded-xl border border-line bg-app px-3 py-2 text-[12px]">
                  <FileIcon size={16} className="text-accent" />
                  <span className="font-medium">Umowy-2026.pdf</span>
                  <span className="ml-auto text-muted">4,2 MB</span>
                </div>
                <p className="text-[13px] leading-6 text-fg/90">
                  Gotowe. Najbliższe terminy: <b>wypowiedzenie najmu do 30 września</b>, płatność raty 15 października…
                </p>
              </div>
            </div>
            <div className="mt-auto rounded-2xl border border-line bg-raised px-3.5 py-2.5 text-[12px] text-muted">
              Napisz do Nexusa lub dodaj pliki…
            </div>
          </div>
        </div>
      </div>

      {/* Panel boczny w przeglądarce */}
      <div className="absolute -bottom-10 -left-4 hidden w-64 rounded-2xl border border-line-strong/70 bg-side p-3 shadow-2xl shadow-black/60 md:block lg:-left-10">
        <div className="mb-2 flex items-center gap-2 text-[12px] font-medium">
          <GlobeIcon size={14} className="text-accent" /> Panel na stronie · booking.com
        </div>
        <div className="rounded-xl bg-app p-2.5 text-[11.5px] leading-5 text-fg/90">
          Dziękujemy za ciepłe słowa o śniadaniach! Przykro nam z powodu hałasu – w przyszłym tygodniu kończymy remont…
        </div>
        <div className="mt-2 flex gap-1.5 text-[11px]">
          <span className="inline-flex items-center gap-1 rounded-lg bg-accent px-2 py-1 font-medium text-on-accent">
            <InsertIcon size={12} /> Wstaw
          </span>
          <span className="rounded-lg border border-line px-2 py-1 text-muted">Kopiuj</span>
        </div>
      </div>

      {/* Telefon z rozmową głosową */}
      <div className="absolute -right-3 -bottom-14 hidden h-[300px] w-[150px] rounded-[28px] border-[5px] border-[#2c2c30] bg-[#0f0f12] p-3 shadow-2xl shadow-black/60 md:flex md:flex-col md:items-center lg:-right-8">
        <div className="mb-auto h-1 w-10 rounded-full bg-[#2c2c30]" />
        <div className="voice-orb grid size-20 place-items-center rounded-full">
          <WaveIcon size={28} className="text-white" />
        </div>
        <div className="mt-4 text-[11px] font-medium text-white/90">Słucham…</div>
        <div className="mt-1 text-center text-[10px] leading-4 text-white/50">„Co mam dziś w kalendarzu?”</div>
        <div className="mt-auto flex items-center gap-1 text-[10px] text-white/50">
          <LayersIcon size={11} /> 3 zadania w tle
        </div>
      </div>
    </div>
  );
}
