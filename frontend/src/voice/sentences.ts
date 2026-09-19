// Podział strumieniowanej odpowiedzi na zdania do przeczytania (synteza zdanie po zdaniu).

const BOUNDARY = /[.!?…](?=["'”)\]]?(\s|$))|\n+/g;
const MIN_CHUNK = 24;
// Pierwszy fragment odpowiedzi może się kończyć przecinkiem lub dwukropkiem – czytanie rusza szybciej.
const FIRST_BOUNDARY = /[,;:–—](?=\s)/g;
const FIRST_MIN = 30;

/**
 * Zwraca gotowe do przeczytania fragmenty tekstu od pozycji ``from``.
 * Bez ``final`` ostatni, niedokończony fragment czeka na dalszy tekst;
 * krótkie zdania są łączone, żeby mowa brzmiała płynnie.
 */
export function takeSentences(text: string, from: number, final: boolean): { chunks: string[]; next: number } {
  if (from === 0 && !final) {
    const early = takeFirstClause(text);
    if (early) {
      const rest = takeSentences(text, early.next, false);
      return { chunks: [early.chunk, ...rest.chunks], next: rest.next };
    }
  }
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

/** Pierwsza część odpowiedzi do przecinka (min. 30 znaków), gdy zdanie jeszcze się nie skończyło. */
function takeFirstClause(text: string): { chunk: string; next: number } | null {
  BOUNDARY.lastIndex = 0;
  const sentenceEnd = BOUNDARY.exec(text);
  FIRST_BOUNDARY.lastIndex = FIRST_MIN;
  const clause = FIRST_BOUNDARY.exec(text);
  if (!clause || (sentenceEnd && sentenceEnd.index <= clause.index)) return null;
  const next = clause.index + clause[0].length;
  return { chunk: text.slice(0, next).trim(), next };
}
