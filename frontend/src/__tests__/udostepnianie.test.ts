// Odbiór plików udostępnionych do Nexusa z innych aplikacji (Web Share Target).
//
// To wejście do aplikacji ogłoszone w manifeście PWA: system pokazuje Nexusa na liście
// „Udostępnij”, service worker (`public/share-target.js`) odkłada treść do pamięci
// podręcznej, a okno odbiera ją stąd. Cała droga nie miała ani jednego testu — a gdy się
// zepsuje, udostępnienie kończy się pustą rozmową i niczym więcej.

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { takeSharedContent } from "../share";

const SHARE_CACHE = "nexus-share";

/** Najprostsza atrapa Cache Storage: tyle, ile czyta `takeSharedContent`. */
function atrapaPamieci(wpisy: { url: string; response: Response }[]) {
  const magazyn = new Map<string, Response>(wpisy.map((w) => [w.url, w.response]));
  const usuniete: string[] = [];
  const cache = {
    keys: async () => [...magazyn.keys()].map((url) => ({ url })),
    match: async (request: { url: string }) => magazyn.get(request.url),
  };
  return {
    usuniete,
    caches: {
      open: async () => cache,
      delete: async (nazwa: string) => {
        usuniete.push(nazwa);
        return true;
      },
    },
  };
}

function ustawAdres(search: string): void {
  window.history.replaceState(null, "", `/${search}`);
}

afterEach(() => {
  delete (window as { caches?: unknown }).caches;
  ustawAdres("");
});

beforeEach(() => {
  ustawAdres("");
});

describe("odbiór udostępnionej treści", () => {
  it("bez znacznika w adresie nie rusza pamięci podręcznej", async () => {
    const { caches } = atrapaPamieci([]);
    (window as { caches?: unknown }).caches = caches;
    ustawAdres("?nie-share=1");
    expect(await takeSharedContent()).toBeNull();
  });

  it("tekst z adresu wraca nawet bez service workera", async () => {
    // Przy pierwszym uruchomieniu po instalacji workera jeszcze nie ma, a to właśnie wtedy
    // ktoś najczęściej próbuje udostępnić pierwszą rzecz. Serwer przenosi wtedy tekst
    // adresem; bez tego znikał razem z całym udostępnieniem.
    delete (window as { caches?: unknown }).caches;
    ustawAdres("?tekst=Zr%C3%B3b%20z%20tego%20kartk%C4%99");
    const tresc = await takeSharedContent();
    expect(tresc).toEqual({ files: [], text: "Zrób z tego kartkę" });
    // Adres jest posprzątany, żeby odświeżenie nie wstawiło tekstu drugi raz.
    expect(window.location.search).toBe("");
  });

  it("oddaje plik i tekst, czyści adres i kasuje pamięć podręczną", async () => {
    const plik = new Response(new Blob(["tresc"], { type: "text/plain" }), {
      headers: { "X-File-Name": encodeURIComponent("umowa najmu.pdf") },
    });
    const tekst = new Response("wiadomość od znajomego");
    const { caches, usuniete } = atrapaPamieci([
      { url: "https://nexus/share-target/pliki/0", response: plik },
      { url: "https://nexus/share-target/text", response: tekst },
    ]);
    (window as { caches?: unknown }).caches = caches;
    ustawAdres("?share=1");

    const wynik = await takeSharedContent();
    expect(wynik).not.toBeNull();
    expect(wynik?.text).toBe("wiadomość od znajomego");
    expect(wynik?.files.map((f) => f.name)).toEqual(["umowa najmu.pdf"]);
    // Nazwa wraca z nagłówka rozkodowana — inaczej w rozmowie stałoby „umowa%20najmu.pdf”.
    expect(wynik?.files[0].name).not.toContain("%20");
    // Adres wraca do „/”, żeby odświeżenie nie próbowało odebrać treści drugi raz.
    expect(window.location.search).toBe("");
    expect(usuniete).toEqual([SHARE_CACHE]);
  });

  it("pusta pamięć podręczna to brak treści, nie pusta rozmowa", async () => {
    const { caches } = atrapaPamieci([]);
    (window as { caches?: unknown }).caches = caches;
    ustawAdres("?share=1");
    expect(await takeSharedContent()).toBeNull();
  });

  it("niepoprawnie zakodowana nazwa nie przewraca całego odbioru", async () => {
    // Service worker koduje nazwę, ale to osobny plik z własnym cyklem życia: po wydaniu
    // w przeglądarce jeszcze przez chwilę pracuje poprzednia wersja. `decodeURIComponent`
    // rzuca wtedy `URIError` na samotnym „%” — i przepadał cały odbiór, razem z tekstem.
    const plik = new Response(new Blob(["x"]), { headers: { "X-File-Name": "rabat 50%.pdf" } });
    const tekst = new Response("nie przepadnij");
    const { caches } = atrapaPamieci([
      { url: "https://nexus/share-target/pliki/0", response: plik },
      { url: "https://nexus/share-target/text", response: tekst },
    ]);
    (window as { caches?: unknown }).caches = caches;
    ustawAdres("?share=1");

    const wynik = await takeSharedContent();
    expect(wynik?.text).toBe("nie przepadnij");
    expect(wynik?.files.map((f) => f.name)).toEqual(["rabat 50%.pdf"]);
  });
});
