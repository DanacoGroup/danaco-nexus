import { SCIEZKA } from "./shell/route";

/** Ślad „ktoś się tu logował” — podpowiedź dla przycisku na stronie produktu
 * („Otwórz aplikację” zamiast „Zaloguj się”).
 *
 * Nie jest to stan sesji i nie wolno go tak używać: o tym, kto patrzy, rozstrzyga wyłącznie
 * odpowiedź serwera. Nieaktualny ślad prowadzi najwyżej na ekran logowania, a jego brak
 * (prywatne okno, wyczyszczone dane, zablokowane `localStorage`) niczego nie psuje.
 */
const SLAD_LOGOWANIA = "dn:byl-zalogowany";

export function bylZalogowany(): boolean {
  try {
    return localStorage.getItem(SLAD_LOGOWANIA) === "1";
  } catch {
    return false;
  }
}

export function zapamietajZalogowanie(tak: boolean): void {
  try {
    if (tak) localStorage.setItem(SLAD_LOGOWANIA, "1");
    else localStorage.removeItem(SLAD_LOGOWANIA);
  } catch {
    /* prywatne okno albo zablokowane dane witryny — podpowiedź jest opcjonalna */
  }
}

/** Wejście do aplikacji ze strony produktu: zalogowany idzie prosto do okna, gość na logowanie. */
export function wejscieDoAplikacji(): { adres: string; etykieta: string } {
  return bylZalogowany()
    ? { adres: SCIEZKA.czat, etykieta: "Otwórz aplikację" }
    : { adres: SCIEZKA.aplikacja, etykieta: "Zaloguj się" };
}
