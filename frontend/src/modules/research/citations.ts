// Przypisy raportu badań: odczyt listy źródeł z końca raportu i zamiana odwołań [1] w tekście
// na klikalne odnośniki (funkcje czyste, testowane w citations.test.ts).

export interface Citation {
  /** Numer przypisu. */
  n: number;
  /** Tytuł źródła (tekst pozycji bez adresu, gdy brak jawnego tytułu). */
  title: string;
  /** Adres źródła (pusty, gdy pozycja go nie zawiera). */
  url: string;
  /** Pełny tekst pozycji listy (np. cytowanie APA). */
  text: string;
}

export interface ParsedReport {
  /** Treść raportu bez sekcji źródeł. */
  body: string;
  /** Nagłówek sekcji źródeł (np. „Źródła”, „Bibliografia”) albo null. */
  heading: string | null;
  sources: Citation[];
}

const SOURCES_HEADING =
  /^(#{1,6})\s*\**\s*(źródła|zrodla|bibliografia|przypisy|literatura|sources|references|bibliography)\s*\**\s*:?\s*$/i;
const ENTRY = /^\s*(?:[-*+]\s+)?(?:\[\^?(\d{1,3})\]:?|(\d{1,3})[.)])\s+(.*)$/;
const MARKDOWN_LINK = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/;
const BARE_URL = /https?:\/\/[^\s<>()[\]]+/;
const FENCE = /^\s*(```|~~~)/;

function trimUrl(url: string): string {
  return url.replace(/[.,;:!?'"»]+$/, "");
}

function cleanTitle(text: string): string {
  return text
    .replace(/<\s*>/g, "")
    .replace(/\s*[–—-]\s*$/, "")
    .replace(/^[\s–—:-]+|[\s–—:,;-]+$/g, "")
    .replace(/\*\*|__/g, "")
    .trim();
}

/** Odczytuje jedną pozycję listy źródeł (bez numeru). */
export function parseEntry(n: number, rest: string): Citation {
  const text = rest.trim();
  const link = text.match(MARKDOWN_LINK);
  if (link) {
    const remainder = cleanTitle(text.replace(link[0], ""));
    const title = cleanTitle(link[1]);
    // „[Tytuł](adres) – wydawca” albo „Autor – [adres](adres)”.
    const linkIsUrl = /^https?:\/\//.test(title);
    return { n, title: linkIsUrl ? remainder || hostname(link[2]) : title, url: trimUrl(link[2]), text };
  }
  const bare = text.match(BARE_URL);
  if (bare) {
    const url = trimUrl(bare[0]);
    const title = cleanTitle(text.replace(bare[0], "").replace(/\(\s*\)/g, "")) || hostname(url);
    return { n, title, url, text };
  }
  return { n, title: cleanTitle(text), url: "", text };
}

export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Dzieli raport na treść i listę źródeł (ostatnia sekcja „Źródła”/„Bibliografia” poza blokami kodu). */
export function parseReport(markdown: string): ParsedReport {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  let inFence = false;
  let start = -1;
  let level = 0;
  let heading: string | null = null;
  lines.forEach((line, index) => {
    if (FENCE.test(line)) inFence = !inFence;
    if (inFence) return;
    const match = line.match(SOURCES_HEADING);
    if (match) {
      start = index;
      level = match[1].length;
      heading = line.replace(/^#+\s*/, "").replace(/[*:]/g, "").trim();
    }
  });
  if (start < 0) return { body: markdown, heading: null, sources: [] };

  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    const next = lines[index].match(/^(#{1,6})\s/);
    if (next && next[1].length <= level) {
      end = index;
      break;
    }
  }
  const sources: Citation[] = [];
  let current: { n: number; rest: string } | null = null;
  const flush = () => {
    if (current && !sources.some((item) => item.n === current!.n)) sources.push(parseEntry(current.n, current.rest));
    current = null;
  };
  for (const line of lines.slice(start + 1, end)) {
    const entry = line.match(ENTRY);
    if (entry) {
      flush();
      current = { n: Number(entry[1] ?? entry[2]), rest: entry[3] };
    } else if (current && line.trim() && /^\s+/.test(line)) {
      current.rest += ` ${line.trim()}`;
    } else if (!line.trim()) {
      flush();
    }
  }
  flush();
  if (sources.length === 0) return { body: markdown, heading: null, sources: [] };
  const body = [...lines.slice(0, start), ...lines.slice(end)].join("\n").trimEnd();
  return { body, heading, sources };
}

/** Numery w odwołaniu „1, 3” lub „2–4”. */
export function expandRefs(inner: string): number[] {
  const numbers: number[] = [];
  for (const part of inner.split(/\s*,\s*/)) {
    const range = part.match(/^(\d+)\s*[–—-]\s*(\d+)$/);
    if (range) {
      const [from, to] = [Number(range[1]), Number(range[2])];
      if (to >= from && to - from <= 50) for (let n = from; n <= to; n += 1) numbers.push(n);
    } else if (/^\d+$/.test(part)) {
      numbers.push(Number(part));
    }
  }
  return numbers;
}

const REFERENCE = /\[\^?(\d{1,3}(?:\s*[,–—-]\s*\d{1,3})*)](?![(:])/g;

/** Zamienia odwołania [n] na odnośniki HTML do przypisów (poza kodem i odnośnikami Markdown). */
export function linkCitations(markdown: string, known: Set<number>): string {
  if (known.size === 0) return markdown;
  const segments = markdown.split(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/);
  return segments
    .map((segment, index) => {
      if (index % 2 === 1) return segment;
      return segment.replace(REFERENCE, (whole, inner: string) => {
        const numbers = expandRefs(inner).filter((n) => known.has(n));
        if (numbers.length === 0) return whole;
        const links = numbers
          .map((n) => `<a href="#zrodlo-${n}" data-cite="${n}" class="cite">${n}</a>`)
          .join('<span class="cite-sep">,</span>');
        return `<sup class="cite-group">${links}</sup>`;
      });
    })
    .join("");
}

/** Raport gotowy do wyświetlenia: treść z odnośnikami i lista źródeł. */
export function prepareReport(markdown: string): ParsedReport & { html: string } {
  const parsed = parseReport(markdown);
  const known = new Set(parsed.sources.map((item) => item.n));
  return { ...parsed, html: linkCitations(parsed.body, known) };
}
