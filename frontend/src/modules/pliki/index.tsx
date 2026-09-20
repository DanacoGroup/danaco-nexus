// Moduł Pliki: jedna przestrzeń konta zamiast osobnych ekranów „chmura” i „baza wiedzy”.
//
// Pliki wgrane przez użytkownika i wytworzone przez agenta leżą obok siebie, a układ
// wyznacza sam użytkownik — własne katalogi i projekty, wyszukiwarka, filtr rodzaju.

import type { SVGProps } from "react";
import type { NexusModule } from "../registry";
import { PlikiPage } from "./PlikiPage";

export function PlikiIcon({ size = 24, ...reszta }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...reszta}
    >
      <path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4l2 2.5h7A1.5 1.5 0 0 1 19 10v7a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 3 17Z" />
      <path d="M7 11.5h8" />
    </svg>
  );
}

export const module: NexusModule = {
  id: "pliki",
  label: "Pliki",
  description: "Twoje pliki i wyniki pracy: własne katalogi i projekty, wyszukiwanie, porządkowanie",
  icon: PlikiIcon,
  order: 15,
  Page: PlikiPage,
};
