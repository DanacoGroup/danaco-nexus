// Odbiór plików udostępnionych do Nexusa z innych aplikacji (patrz public/share-target.js).

const SHARE_CACHE = "nexus-share";

/** Nazwa pliku z nagłówka — odkodowana, a gdy się nie da, wzięta wprost.
 *
 * `decodeURIComponent` rzuca `URIError` na niepełnym kodowaniu (samotny „%”). Service
 * worker zawsze koduje nazwę, ale to **osobny** plik z własnym cyklem życia: po wydaniu
 * w przeglądarce jeszcze przez chwilę pracuje poprzednia wersja. Wyjątek z jednej nazwy
 * przewracał całe odebranie — razem z pozostałymi plikami i tekstem. */
function odkoduj(naglowek: string | null): string {
  const wartosc = naglowek ?? "plik";
  try {
    return decodeURIComponent(wartosc);
  } catch {
    return wartosc;
  }
}

export interface SharedContent {
  files: File[];
  text: string;
}

/** Zwraca i usuwa treść udostępnioną do aplikacji (adres z ``?share=1`` albo ``?tekst=``). */
export async function takeSharedContent(): Promise<SharedContent | null> {
  const parametry = new URLSearchParams(window.location.search);

  // Zapas bez service workera: serwer przekierowuje udostępniony tekst adresem
  // (`/?tekst=…`), bo przy pierwszym uruchomieniu po instalacji worker jeszcze nie stoi,
  // a to właśnie wtedy ktoś najczęściej próbuje udostępnić pierwszą rzecz. Pliki tą drogą
  // nie przechodzą — przekierowanie ich nie unosi.
  const tekstZAdresu = parametry.get("tekst");
  if (tekstZAdresu) {
    window.history.replaceState(null, "", "/");
    return { files: [], text: tekstZAdresu };
  }

  if (parametry.get("share") !== "1" || !("caches" in window)) return null;
  window.history.replaceState(null, "", "/");
  const cache = await caches.open(SHARE_CACHE);
  const files: File[] = [];
  let text = "";
  for (const request of await cache.keys()) {
    const response = await cache.match(request);
    if (!response) continue;
    if (request.url.endsWith("/share-target/text")) {
      text = await response.text();
    } else {
      const name = odkoduj(response.headers.get("X-File-Name"));
      const blob = await response.blob();
      files.push(new File([blob], name, { type: blob.type }));
    }
  }
  await caches.delete(SHARE_CACHE);
  return files.length || text ? { files, text } : null;
}
