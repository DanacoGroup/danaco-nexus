// Treść poleceń szybkich akcji wysyłanych do Nexusa (z kontekstem strony).

import type { OpiniaSkrot } from "../wspolne/komunikaty";

export type Akcja = "stresc" | "odpowiedz" | "popraw" | "przetlumacz" | "zapytaj";

export interface Polecenie {
  text: string;
  /** true – wysłać od razu; false – wstawić do pola wiadomości do uzupełnienia. */
  send: boolean;
}

export const JEZYKI = ["polski", "angielski", "niemiecki", "ukraiński", "hiszpański", "francuski", "włoski", "czeski"];

const ODPOWIEDZ_OPINIA =
  "Przygotuj odpowiedź właściciela na tę opinię. Pisz w języku opinii, uprzejmie, konkretnie i naturalnie: " +
  "podziękuj, odnieś się do mocnych stron i do każdej uwagi, bez obietnic, których nie da się sprawdzić, " +
  "bez danych osobowych gości. Zwróć wyłącznie treść odpowiedzi, gotową do wklejenia.";

const ODPOWIEDZ_WIADOMOSC =
  "Przygotuj odpowiedź na tę wiadomość e-mail w języku wiadomości, uprzejmie i rzeczowo, odnosząc się do " +
  "wszystkich pytań. Nie wymyślaj faktów – brakujące informacje oznacz w nawiasach kwadratowych. " +
  "Zwróć wyłącznie treść odpowiedzi (bez tematu), gotową do wklejenia.";

const ODPOWIEDZ_KOMENTARZ =
  "Przygotuj krótką, uprzejmą odpowiedź na ten komentarz w jego języku. Zwróć wyłącznie treść odpowiedzi.";

/** Polecenie dla akcji; `rodzaj` dotyczy akcji „odpowiedz”, `jezyk` – „przetlumacz”. */
export function polecenie(akcja: Akcja, opcje: { rodzaj?: OpiniaSkrot["rodzaj"]; jezyk?: string } = {}): Polecenie {
  switch (akcja) {
    case "stresc":
      return {
        text:
          "Streść tę stronę po polsku: najważniejsze informacje w punktach, liczby i terminy bez zmian, " +
          "na końcu jednozdaniowy wniosek.",
        send: true,
      };
    case "odpowiedz":
      return {
        text:
          opcje.rodzaj === "wiadomosc"
            ? ODPOWIEDZ_WIADOMOSC
            : opcje.rodzaj === "komentarz"
              ? ODPOWIEDZ_KOMENTARZ
              : ODPOWIEDZ_OPINIA,
        send: true,
      };
    case "popraw":
      return {
        text:
          "Popraw ten tekst: pisownia, gramatyka, interpunkcja i styl. Zachowaj sens, ton, język i formatowanie. " +
          "Zwróć wyłącznie poprawiony tekst.",
        send: true,
      };
    case "przetlumacz":
      return {
        text: `Przetłumacz ten tekst na język ${opcje.jezyk || "angielski"}. Zachowaj znaczenie, ton i formatowanie; zwróć wyłącznie tłumaczenie.`,
        send: true,
      };
    case "zapytaj":
      return { text: "", send: false };
  }
}
