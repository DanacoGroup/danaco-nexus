// Pomocniczy zaczep strony produktu: tło sekcji z pakietu grafik.
// Widoczność w polu widzenia prowadzi jeden zaczep warstwy ruchu — `useWidocznosc` z `src/ruch`.

import { type CSSProperties } from "react";

/** Tło sekcji z `landing/tla/grafiki` — AVIF, a gdy go nie ma, WebP. */
export function tlo(nazwa: string, krycie = 0.55): CSSProperties {
  return {
    "--tlo": `image-set(url("/tla/${nazwa}.avif") type("image/avif"), url("/tla/${nazwa}.webp") type("image/webp"))`,
    "--tlo-krycie": krycie,
  } as CSSProperties;
}

/** Pasmo strony produktu: jedna szerokość i jeden margines boczny dla całej strony.
 *
 * Topbar, hero, każda sekcja i stopka mają zaczynać się w tej samej pionowej linii.
 * Wcześniej hero miał własną szerokość (`max-w-4xl`) i przy oknie 1280 px był o 304 px
 * węższy od reszty — rozjazd widoczny od pierwszego spojrzenia. Margines rośnie ze
 * szerokością okna, żeby na laptopie treść nie kleiła się do krawędzi.
 */
export { PASMO } from "../ui/pasmo";
