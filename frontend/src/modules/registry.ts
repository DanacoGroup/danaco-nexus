// Rejestr modułów aplikacji (Czat, Cloud, Research, Kod…).
//
// Każdy moduł to katalog src/modules/<id>/ z plikiem index.tsx eksportującym
// `module: NexusModule`. Moduły są wykrywane automatycznie (import.meta.glob) –
// nowy moduł nie wymaga zmian w App.tsx ani w nawigacji.

import type { ComponentType, SVGProps } from "react";

export interface ModulePageProps {
  /** Otwiera rozmowę na czacie (np. po zleceniu zadania z modułu). */
  openConversation: (id: string) => void;
  /** Przechodzi do innego modułu. */
  openModule: (id: string) => void;
  /** Otwiera nową rozmowę; podany tekst trafia do pola wiadomości gotowy do wysłania. */
  openChat: (prefill?: string) => void;
}

export interface NexusModule {
  /** Identyfikator w adresie: /m/<id>. */
  id: string;
  /** Inne identyfikatory prowadzące do tego modułu (adresy w obiegu, nazwa po polsku).
   *
   * Dwa moduły mają identyfikator po angielsku, a w nawigacji polską nazwę: `cloud`
   * („Chmura”) i `research` („Badania”). Kto przepisał adres z nazwy na pasku albo
   * dostał go od kogoś, trafiał pod `/m/chmura` na komunikat „Ten moduł nie jest
   * zainstalowany w tej wersji Nexusa” — moduł był na miejscu, tylko pod inną nazwą.
   */
  aliasy?: readonly string[];
  /** Krótka nazwa w nawigacji (1–2 słowa). */
  label: string;
  /** Opis w podpowiedzi i na stronie startowej. */
  description: string;
  /** Ikona 24×24 (obrys, currentColor). */
  icon: ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;
  /** Kolejność w nawigacji (mniejsza = wyżej). */
  order: number;
  /** Treść modułu (pełna szerokość obszaru roboczego). */
  Page: ComponentType<ModulePageProps>;
}

const found = import.meta.glob<{ module: NexusModule }>("./*/index.tsx", { eager: true });

export const MODULES: NexusModule[] = Object.values(found)
  .map((entry) => entry.module)
  .filter(Boolean)
  .sort((a, b) => a.order - b.order);

export function findModule(id: string | null): NexusModule | undefined {
  if (!id) return undefined;
  return MODULES.find((item) => item.id === id || item.aliasy?.includes(id));
}
