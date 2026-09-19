// Wyświetlanie wiadomości z blokiem kontekstu (strona, ekran) w historii rozmowy.

import type { UserTurn } from "../api";
import { splitContext } from "./embed";

/** Wiadomość z kontekstem strony pokazuje nagłówek bloku i pytanie – bez całej treści strony. */
export function displayTurn(turn: UserTurn): UserTurn {
  const { header, question } = splitContext(turn.text);
  if (!header) return turn;
  return { ...turn, text: question ? `[${header}]\n\n${question}` : `[${header}]` };
}
