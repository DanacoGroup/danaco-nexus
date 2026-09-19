// Podział strumieniowanej odpowiedzi na zdania do przeczytania (synteza zdanie po zdaniu).

const BOUNDARY = /[.!?…](?=["'”)\]]?(\s|$))|\n+/g;
const MIN_CHUNK = 24;

/**
 * Zwraca gotowe do przeczytania fragmenty tekstu od pozycji ``from``.
 * Bez ``final`` ostatni, niedokończony fragment czeka na dalszy tekst;
 * krótkie zdania są łączone, żeby mowa brzmiała płynnie.
 */
export function takeSentences(text: string, from: number, final: boolean): { chunks: string[]; next: number } {
  const chunks: string[] = [];
  let start = from;
  let pending = "";
  BOUNDARY.lastIndex = from;
  for (let match = BOUNDARY.exec(text); match; match = BOUNDARY.exec(text)) {
    const end = match.index + match[0].length;
    pending += text.slice(start, end);
    start = end;
    if (pending.trim().length >= MIN_CHUNK) {
      chunks.push(pending.trim());
      pending = "";
    }
  }
  if (final) {
    pending += text.slice(start);
    start = text.length;
    if (pending.trim()) chunks.push(pending.trim());
    return { chunks, next: start };
  }
  // Niedokończone zdanie wraca do bufora (pozycja cofnięta o nieprzeczytany fragment).
  return { chunks, next: start - pending.length };
}

/** Tekst odpowiedzi do czytania: bez bloków kodu i znaczników Markdown. */
export function speakable(text: string): string {
  return text
    .replace(/```[\s\S]*?(```|$)/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[*_`#>|]/g, " ");
}
