// Zakres dostępu rozszerzenia do stron: co wolno czytać i kiedy.
//
// Rozszerzenie prosiło wcześniej o dostęp do wszystkich stron już przy instalacji.
// Okienko przeglądarki mówiło wtedy „odczytuj i zmieniaj wszystkie Twoje dane na
// wszystkich stronach” — zdanie prawdziwe, ale dla większości pracy niepotrzebne.
// Teraz zakres wybiera użytkownik i może go zawęzić albo poszerzyć w każdej chwili.
//
// Trzy zakresy odpowiadają trzem sposobom pracy:
//   klik      — panel otwiera się po kliknięciu ikony albo skrócie; przeglądarka
//               przyznaje wtedy dostęp do tej jednej karty (`activeTab`) i tylko na czas
//               tej wizyty. Żadnego dostępu w tle, żadnego uprawnienia przy instalacji.
//   wybrane   — wskazane witryny działają same z siebie: przycisk przy krawędzi
//               i przybornik zaznaczenia pojawiają się bez klikania ikony.
//   wszystkie — to samo na każdej stronie.
//
// Uprawnienia do stron są w manifeście opcjonalne (`optional_host_permissions`),
// więc przeglądarka pyta o nie dopiero wtedy, gdy użytkownik wybierze drugi albo
// trzeci zakres. Wybór jest odwracalny: zwężenie zakresu oddaje uprawnienie.

export type Zakres = "klik" | "wybrane" | "wszystkie";

export const ZAKRES_DOMYSLNY: Zakres = "klik";

/** Opis zakresu dla strony opcji — jedno zdanie, bez żargonu uprawnień. */
export const OPISY_ZAKRESU: Record<Zakres, { nazwa: string; opis: string }> = {
  klik: {
    nazwa: "Tylko po kliknięciu",
    opis: "Nexus czyta stronę dopiero wtedy, gdy klikniesz ikonę albo naciśniesz skrót. Nie działa w tle na żadnej witrynie.",
  },
  wybrane: {
    nazwa: "Wybrane witryny",
    opis: "Na wskazanych witrynach przycisk i przybornik pojawiają się same. Na pozostałych Nexus czeka na kliknięcie.",
  },
  wszystkie: {
    nazwa: "Wszystkie strony",
    opis: "Przycisk i przybornik pojawiają się na każdej stronie. Najwygodniejsze i najszersze — przeglądarka poprosi o zgodę.",
  },
};

/** Identyfikator dynamicznie rejestrowanego skryptu treści. */
const SKRYPT = "nexus-tresc";
const WSZYSTKIE = "<all_urls>";

function api(): typeof chrome | null {
  try {
    return globalThis.chrome?.permissions && globalThis.chrome?.scripting ? globalThis.chrome : null;
  } catch {
    return null;
  }
}

/** Zamienia adres witryny na wzorzec uprawnienia (`https://example.com/*`).
 *
 * Zwraca null, gdy adresu nie da się objąć uprawnieniem: przeglądarka nie przyznaje
 * dostępu do własnych stron (`chrome://`), sklepu z rozszerzeniami ani adresów bez hosta.
 */
export function wzorzecWitryny(adres: string): string | null {
  let url: URL;
  try {
    url = new URL(adres.trim().includes("://") ? adres.trim() : `https://${adres.trim()}`);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (!url.hostname) return null;
  return `${url.protocol}//${url.hostname}/*`;
}

/** Wzorce stron, do których rozszerzenie ma dziś przyznany dostęp. */
export async function przyznane(): Promise<string[]> {
  const chrome = api();
  if (!chrome) return [];
  try {
    const stan = await chrome.permissions.getAll();
    return [...(stan.origins ?? [])];
  } catch {
    return [];
  }
}

/** Czy przyznany jest dostęp do wszystkich stron. */
export async function maWszystkie(): Promise<boolean> {
  return (await przyznane()).includes(WSZYSTKIE);
}

/** Prosi o dostęp do podanych wzorców. Zwraca odpowiedź użytkownika.
 *
 * Wywołanie musi wyjść z gestu użytkownika (kliknięcie), inaczej przeglądarka odmawia
 * bez pokazania okienka — dlatego prośbę składa strona opcji, a nie tło.
 */
export async function popros(wzorce: string[]): Promise<boolean> {
  const chrome = api();
  if (!chrome || !wzorce.length) return false;
  try {
    return await chrome.permissions.request({ origins: wzorce });
  } catch {
    return false;
  }
}

/** Oddaje dostęp do podanych wzorców (albo do wszystkiego, gdy lista pusta). */
export async function oddaj(wzorce?: string[]): Promise<void> {
  const chrome = api();
  if (!chrome) return;
  const origins = wzorce?.length ? wzorce : await przyznane();
  if (!origins.length) return;
  try {
    await chrome.permissions.remove({ origins });
  } catch {
    // Przeglądarka bez pełnego API uprawnień — zakres zostaje taki, jaki był.
  }
}

/**
 * Dopasowuje rejestrację skryptu treści do przyznanych uprawnień.
 *
 * Skrypt treści nie jest w manifeście na stałe: gdyby był, przeglądarka żądałaby
 * dostępu do stron już przy instalacji i cały wybór zakresu nic by nie dał. Zamiast
 * tego rejestrujemy go na tych witrynach, na które użytkownik się zgodził, a przy
 * zawężeniu zakresu wyrejestrowujemy.
 */
export async function przeladujSkrypt(): Promise<void> {
  const chrome = api();
  if (!chrome?.scripting?.registerContentScripts) return;
  const wzorce = await przyznane();
  try {
    const istniejace = await chrome.scripting.getRegisteredContentScripts({ ids: [SKRYPT] });
    if (istniejace.length) await chrome.scripting.unregisterContentScripts({ ids: [SKRYPT] });
  } catch {
    // Brak rejestracji do usunięcia — to stan wyjściowy, nie błąd.
  }
  if (!wzorce.length) return;
  try {
    await chrome.scripting.registerContentScripts([
      {
        id: SKRYPT,
        js: ["tresc.js"],
        matches: wzorce,
        runAt: "document_idle",
        allFrames: false,
      },
    ]);
  } catch {
    // Przeglądarka bez rejestracji dynamicznej — panel otwiera się wtedy z ikony,
    // bo tło i tak wstrzykuje skrypt na żądanie.
  }
}

/** Zakres wynikający z tego, co przeglądarka naprawdę przyznała.
 *
 * Źródłem prawdy są uprawnienia, nie zapisane ustawienie: użytkownik może cofnąć
 * zgodę w ustawieniach przeglądarki, a rozszerzenie nie dostanie o tym pytania.
 */
export async function biezacy(): Promise<Zakres> {
  const wzorce = await przyznane();
  if (wzorce.includes(WSZYSTKIE)) return "wszystkie";
  return wzorce.length ? "wybrane" : "klik";
}

export { WSZYSTKIE };
