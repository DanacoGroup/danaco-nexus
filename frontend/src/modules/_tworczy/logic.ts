// Czyste funkcje modułów twórczych (testowane w vitest).

const TRANSLITERATION: Record<string, string> = {
  ą: "a",
  ć: "c",
  ę: "e",
  ł: "l",
  ń: "n",
  ó: "o",
  ś: "s",
  ź: "z",
  ż: "z",
};

/** Adres strony z tytułu (zgodny z walidacją serwera): „Kawiarnia Pod Lipą” → „kawiarnia-pod-lipa”. */
export function slugify(title: string): string {
  const base = title
    .toLowerCase()
    .replace(/[ąćęłńóśźż]/g, (char) => TRANSLITERATION[char] ?? char)
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48)
    .replace(/-+$/g, "");
  return base || "strona";
}

export const ADDRESS_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$/;

export function isValidAddress(address: string): boolean {
  return ADDRESS_PATTERN.test(address);
}

/** Znacznik adresu strony dołączany do wiadomości w trybie Twórcy stron. */
export function sitePrefix(address: string): string {
  return `[Strona: ${address}]\n`;
}

/** Tekst wiadomości bez technicznego znacznika strony (do wyświetlenia). */
export function stripSitePrefix(text: string): string {
  return text.replace(/^\[Strona: [a-z0-9-]+\]\n?/, "");
}

export type Device = "desktop" | "tablet" | "phone";

export const DEVICE_WIDTHS: Record<Device, number | null> = { desktop: null, tablet: 820, phone: 390 };

/** Czas w sekundach jako „m:ss” lub „h:mm:ss” (z dziesiątymi częściami, gdy są). */
export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  const tenths = Math.round((seconds - whole) * 10);
  const carry = tenths === 10 ? 1 : 0;
  const total = whole + carry;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const fraction = tenths && tenths !== 10 ? `.${tenths}` : "";
  const mm = hours ? String(minutes).padStart(2, "0") : String(minutes);
  return `${hours ? `${hours}:` : ""}${mm}:${String(secs).padStart(2, "0")}${fraction}`;
}

/** Czas „h:mm:ss”, „m:ss” albo sekundy → liczba sekund; `null`, gdy zapis jest błędny. */
export function parseTime(value: string): number | null {
  const text = value.trim().replace(",", ".");
  if (!/^\d+(:\d{1,2}){0,2}(\.\d+)?$/.test(text)) return null;
  const parts = text.split(":").map(Number);
  if (parts.slice(1).some((part) => part >= 60)) return null;
  return parts.reduce((total, part) => total * 60 + part, 0);
}

/** Czas dla FFmpeg: „HH:MM:SS.s”. */
export function ffmpegTime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds - hours * 3600 - minutes * 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  const rounded = Math.round(secs * 10) / 10;
  const [whole, fraction] = rounded.toFixed(1).split(".");
  return `${pad(hours)}:${pad(minutes)}:${pad(Number(whole))}${fraction !== "0" ? `.${fraction}` : ""}`;
}

export type StudioAction =
  | "transcribe"
  | "subtitles"
  | "trim"
  | "convert"
  | "extract_audio"
  | "normalize"
  | "compress"
  | "summary";

export interface StudioOptions {
  language: string;
  subtitleFormat: "srt" | "vtt";
  format: string;
  start: number | null;
  end: number | null;
  withNotes: boolean;
}

/** Polecenie dla asystenta realizujące akcję Studia na załączonym nagraniu. */
export function studioPrompt(action: StudioAction, options: StudioOptions, fileName: string): string {
  const language = options.language === "auto" ? "wykryj język automatycznie" : `język mowy: ${options.language}`;
  const range =
    options.start !== null || options.end !== null
      ? `od ${ffmpegTime(options.start ?? 0)}${options.end !== null ? ` do ${ffmpegTime(options.end)}` : " do końca"}`
      : "";
  switch (action) {
    case "transcribe":
      return `Zrób transkrypcję nagrania „${fileName}” (transcribe_audio, ${language}) i oddaj plik TXT ze znacznikami czasu. Krótko opisz, o czym jest nagranie.`;
    case "subtitles":
      return `Przygotuj napisy ${options.subtitleFormat.toUpperCase()} do nagrania „${fileName}” (transcribe_audio, ${language}). Sprawdź i popraw oczywiste błędy rozpoznania.`;
    case "trim":
      return `Wytnij z nagrania „${fileName}” fragment ${range || "wskazany przeze mnie"} (media_process: trim)${
        options.format ? ` i zapisz jako ${options.format.toUpperCase()}` : ""
      }.`;
    case "convert":
      return `Przekonwertuj nagranie „${fileName}” do formatu ${options.format.toUpperCase()} (media_process: convert), zachowując dobrą jakość.`;
    case "extract_audio":
      return `Wyodrębnij ścieżkę dźwiękową z „${fileName}” jako ${(options.format || "mp3").toUpperCase()} (media_process: extract_audio).`;
    case "normalize":
      return `Wyrównaj głośność nagrania „${fileName}” do standardu EBU R128 (media_process: normalize_audio).`;
    case "compress":
      return `Skompresuj wideo „${fileName}” do rozsądnego rozmiaru z zachowaniem czytelności obrazu (media_process: compress_video).`;
    case "summary":
      return `Zrób transkrypcję nagrania „${fileName}” (${language}) i przygotuj zwięzłe streszczenie: najważniejsze tematy, ustalenia, zadania z osobami i terminami${
        options.withNotes ? ". Zapisz notatkę ze spotkania jako DOCX (write_document)" : ""
      }.`;
  }
}

/** Czy plik wygląda na wideo (po typie MIME lub rozszerzeniu). */
export function isVideo(mime: string, name: string): boolean {
  return mime.startsWith("video/") || /\.(mp4|mov|mkv|webm|avi)$/i.test(name);
}

/** Ograniczenie wartości do przedziału. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Tekst podzielony na partie do tłumaczenia „na żywo” – czy zmiana jest warta nowego zapytania. */
export function worthTranslating(text: string, previous: string): boolean {
  const current = text.trim();
  return current.length > 0 && current !== previous.trim();
}
