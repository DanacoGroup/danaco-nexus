// Ustawienia rozszerzenia: adres serwera Nexusa, klucz urządzenia, wygląd panelu.
//
// Podstawowym magazynem jest chrome.storage.local. Przeglądarki z niepełnym API
// rozszerzeń (np. Danaco Lynx na Electronie) mogą go nie mieć – wtedy strony
// rozszerzenia (panel, opcje) korzystają z localStorage własnego pochodzenia
// chrome-extension://, a skrypt treści pracuje na wartościach domyślnych.
// Skrypt treści nigdy nie sięga do localStorage strony ani nie czyta klucza.

export interface Ustawienia {
  /** Adres serwera Nexusa (samo pochodzenie, bez ukośnika na końcu). */
  serwer: string;
  /** Klucz urządzenia nxd_… utworzony w module Urządzenia. */
  klucz: string;
  /** Czy pokazywać pływający przycisk przy prawej krawędzi. */
  przycisk: boolean;
  /** Hosty, na których przycisk jest ukryty (panel nadal działa ze skrótu). */
  ukryteHosty: string[];
  /** Szerokość panelu w pikselach. */
  szerokosc: number;
  /** Język docelowy szybkiej akcji „Przetłumacz”. */
  jezyk: string;
  /** Czy dołączać zrzut widocznej karty do kontekstu. */
  zrzut: boolean;
  /** Czy przybornik ma się pokazywać po zaznaczeniu tekstu. */
  przybornik: boolean;
  /** Skróty przybornika — kolejność jest kolejnością przycisków. */
  skroty: SkrotPrzybornika[];
}

/** Jeden przycisk przybornika: nazwa na przycisku i polecenie wysyłane do modelu.
 *
 * Polecenie jest zwykłym zdaniem, bo model wykona wszystko, co da się opisać słowami.
 * Użytkownik układa własny zestaw: tłumaczowi wystarczą dwa przyciski, programiście
 * przydadzą się inne niż redaktorowi.
 */
export interface SkrotPrzybornika {
  /** Nadawany przy tworzeniu, stały przez całe życie skrótu. */
  id: string;
  /** Napis na przycisku — krótki, bo przybornik stoi przy kursorze. */
  nazwa: string;
  /** Polecenie dla modelu; zaznaczenie dochodzi osobno jako dane. */
  polecenie: string;
}

/** Zestaw startowy przybornika — punkt wyjścia, nie zamknięta lista.
 *
 * Skróty dobrane tak, żeby pokrywały to, po co ludzie najczęściej sięgają do modelu
 * przy zaznaczonym tekście. Użytkownik zmienia je w opcjach rozszerzenia: dokłada
 * własne, zmienia treść polecenia, usuwa te, których nie używa.
 */
export const SKROTY_STARTOWE: SkrotPrzybornika[] = [
  { id: "tlumacz", nazwa: "Przetłumacz", polecenie: "Przetłumacz ten fragment na polski. Jeśli już jest po polsku, przetłumacz na angielski." },
  { id: "wyjasnij", nazwa: "Wyjaśnij", polecenie: "Wyjaśnij prosto, o co chodzi w tym fragmencie." },
  { id: "skroc", nazwa: "Skróć", polecenie: "Skróć ten tekst do najważniejszych zdań, zachowaj sens." },
  { id: "popraw", nazwa: "Popraw", polecenie: "Popraw styl, gramatykę i interpunkcję. Oddaj sam poprawiony tekst." },
  { id: "rozwin", nazwa: "Rozwiń", polecenie: "Rozwiń ten fragment w pełniejszą, uporządkowaną treść." },
  { id: "odpowiedz", nazwa: "Odpowiedz", polecenie: "Napisz uprzejmą, rzeczową odpowiedź na tę wiadomość." },
  { id: "kod", nazwa: "Sprawdź kod", polecenie: "Znajdź w tym kodzie błędy i pułapki. Wypisz je krótko, każdy w osobnym punkcie." },
];

export const DOMYSLNE: Ustawienia = {
  serwer: "https://danaco-nexus.pl",
  klucz: "",
  przycisk: true,
  ukryteHosty: [],
  szerokosc: 420,
  jezyk: "angielski",
  zrzut: false,
  przybornik: true,
  skroty: SKROTY_STARTOWE,
};

export const SZEROKOSC_MIN = 320;
export const SZEROKOSC_MAX = 900;
const KLUCZ_LOCAL = "nexus-rozszerzenie";
const KLUCZ_URZADZENIA = /^nxd_[A-Za-z0-9_-]{20,200}$/;

type Magazyn = chrome.storage.StorageArea;

function magazyn(): Magazyn | null {
  try {
    const area = globalThis.chrome?.storage?.local;
    return area && typeof area.get === "function" ? area : null;
  } catch {
    return null;
  }
}

/** Czy klucz ma poprawny format (nie sprawdza ważności na serwerze). */
export function poprawnyKlucz(klucz: string): boolean {
  return KLUCZ_URZADZENIA.test(klucz.trim());
}

/**
 * Normalizuje adres serwera do samego pochodzenia. Dopuszcza wyłącznie HTTPS
 * (oraz HTTP dla 127.0.0.1/localhost – serwer testowy). Zwraca null dla złego adresu.
 */
export function normalizujSerwer(adres: string): string | null {
  let url: URL;
  try {
    url = new URL(adres.trim().includes("://") ? adres.trim() : `https://${adres.trim()}`);
  } catch {
    return null;
  }
  const lokalny = url.hostname === "127.0.0.1" || url.hostname === "localhost";
  if (url.protocol !== "https:" && !(url.protocol === "http:" && lokalny)) return null;
  if (url.username || url.password) return null;
  return url.origin;
}

function uzupelnij(surowe: Partial<Ustawienia> | undefined): Ustawienia {
  const wynik: Ustawienia = { ...DOMYSLNE, ...(surowe ?? {}) };
  wynik.serwer = normalizujSerwer(wynik.serwer) ?? DOMYSLNE.serwer;
  wynik.szerokosc = Math.min(SZEROKOSC_MAX, Math.max(SZEROKOSC_MIN, Number(wynik.szerokosc) || DOMYSLNE.szerokosc));
  wynik.ukryteHosty = Array.isArray(wynik.ukryteHosty) ? wynik.ukryteHosty.filter((h) => typeof h === "string") : [];
  wynik.przybornik = wynik.przybornik !== false;
  wynik.skroty = oczyscSkroty(wynik.skroty);
  return wynik;
}

/** Odsiewa skróty, których nie da się pokazać ani wykonać.
 *
 * Ustawienia mogą pochodzić ze starszej wersji rozszerzenia albo z ręcznej edycji
 * magazynu, więc kształt trzeba sprawdzić, a nie założyć. Pusty wynik znaczy „brak
 * przybornika”, nie „przywróć zestaw startowy” — skasowanie wszystkich skrótów jest
 * dozwolonym wyborem użytkownika.
 */
export function oczyscSkroty(surowe: unknown): SkrotPrzybornika[] {
  if (!Array.isArray(surowe)) return [...SKROTY_STARTOWE];
  const widziane = new Set<string>();
  const wynik: SkrotPrzybornika[] = [];
  for (const pozycja of surowe) {
    if (!pozycja || typeof pozycja !== "object") continue;
    const { id, nazwa, polecenie } = pozycja as Partial<SkrotPrzybornika>;
    if (typeof nazwa !== "string" || typeof polecenie !== "string") continue;
    const czysta = nazwa.trim().slice(0, 40);
    const tresc = polecenie.trim().slice(0, 2000);
    if (!czysta || !tresc) continue;
    const klucz = typeof id === "string" && id.trim() ? id.trim().slice(0, 60) : czysta.toLowerCase();
    if (widziane.has(klucz)) continue;
    widziane.add(klucz);
    wynik.push({ id: klucz, nazwa: czysta, polecenie: tresc });
    if (wynik.length >= LIMIT_SKROTOW) break;
  }
  return wynik;
}

/** Ile skrótów mieści się w przyborniku, żeby nie zasłonił strony. */
export const LIMIT_SKROTOW = 20;

function czytajLocal(): Partial<Ustawienia> {
  try {
    return JSON.parse(localStorage.getItem(KLUCZ_LOCAL) ?? "{}") as Partial<Ustawienia>;
  } catch {
    return {};
  }
}

/**
 * Wczytuje ustawienia. `zapasowyLocal` = true tylko na stronach rozszerzenia
 * (panel, opcje), gdzie localStorage należy do rozszerzenia, a nie do odwiedzanej witryny.
 */
export async function wczytaj(zapasowyLocal = false): Promise<Ustawienia> {
  const area = magazyn();
  if (area) {
    try {
      const dane = (await area.get(KLUCZ_LOCAL)) as Record<string, Partial<Ustawienia> | undefined>;
      return uzupelnij(dane?.[KLUCZ_LOCAL]);
    } catch {
      // Magazyn niedostępny mimo obecności API – przejście do zapasu.
    }
  }
  return uzupelnij(zapasowyLocal ? czytajLocal() : undefined);
}

/** Zapisuje zmiany ustawień (scalane z bieżącymi). */
export async function zapisz(zmiany: Partial<Ustawienia>, zapasowyLocal = false): Promise<Ustawienia> {
  const nowe = uzupelnij({ ...(await wczytaj(zapasowyLocal)), ...zmiany });
  const area = magazyn();
  if (area) {
    try {
      await area.set({ [KLUCZ_LOCAL]: nowe });
      return nowe;
    } catch {
      // jak wyżej
    }
  }
  if (zapasowyLocal) localStorage.setItem(KLUCZ_LOCAL, JSON.stringify(nowe));
  return nowe;
}

/** Wywołuje `zmiana` po każdej zmianie ustawień (jeśli przeglądarka to obsługuje). */
export function obserwuj(zmiana: (ustawienia: Ustawienia) => void): void {
  try {
    globalThis.chrome?.storage?.onChanged?.addListener((zmiany, obszar) => {
      if (obszar === "local" && zmiany[KLUCZ_LOCAL]) {
        zmiana(uzupelnij(zmiany[KLUCZ_LOCAL].newValue as Partial<Ustawienia> | undefined));
      }
    });
  } catch {
    // Brak zdarzeń magazynu – zmiany zadziałają po przeładowaniu strony.
  }
}
