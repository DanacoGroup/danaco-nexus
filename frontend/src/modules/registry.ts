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
  return MODULES.find((item) => item.id === id);
}
