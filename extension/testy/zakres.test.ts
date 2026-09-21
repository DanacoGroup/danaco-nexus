// Zakres dostępu do stron: co dodatek wolno czytać i kiedy.
//
// Testy pilnują tego, co widzi użytkownik przy instalacji i w opcjach: że świeży dodatek
// nie ma dostępu do żadnej witryny, że wskazanie witryny nie daje dostępu do reszty sieci,
// że zawężenie zakresu naprawdę oddaje zgodę i że skrypt treści chodzi wyłącznie tam,
// gdzie zgoda jest.

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  WSZYSTKIE,
  biezacy,
  maWszystkie,
  oddaj,
  popros,
  przeladujSkrypt,
  przyznane,
  wzorzecWitryny,
} from "../src/wspolne/zakres";

/** Atrapa przeglądarki: pamięta przyznane wzorce i zarejestrowane skrypty treści. */
function przegladarka(poczatkowe: string[] = [], { zgoda = true } = {}) {
  const origins = new Set(poczatkowe);
  const skrypty = new Map<string, { id: string; matches: string[] }>();
  const chrome = {
    permissions: {
      getAll: vi.fn(async () => ({ origins: [...origins], permissions: ["storage"] })),
      request: vi.fn(async ({ origins: prosba }: { origins: string[] }) => {
        if (!zgoda) return false;
        for (const wzorzec of prosba) origins.add(wzorzec);
        return true;
      }),
      remove: vi.fn(async ({ origins: zdejmowane }: { origins: string[] }) => {
        for (const wzorzec of zdejmowane) origins.delete(wzorzec);
        return true;
      }),
    },
    scripting: {
      getRegisteredContentScripts: vi.fn(async ({ ids }: { ids: string[] }) =>
        ids.map((id) => skrypty.get(id)).filter(Boolean),
      ),
      registerContentScripts: vi.fn(async (wpisy: Array<{ id: string; matches: string[] }>) => {
        for (const wpis of wpisy) skrypty.set(wpis.id, wpis);
      }),
      unregisterContentScripts: vi.fn(async ({ ids }: { ids: string[] }) => {
        for (const id of ids) skrypty.delete(id);
      }),
    },
  };
  (globalThis as unknown as { chrome: unknown }).chrome = chrome;
  return { chrome, origins, skrypty };
}

beforeEach(() => {
  delete (globalThis as unknown as { chrome?: unknown }).chrome;
});

describe("wzorzecWitryny", () => {
  it("robi wzorzec uprawnienia z samej nazwy witryny", () => {
    expect(wzorzecWitryny("sklep.example.pl")).toBe("https://sklep.example.pl/*");
    expect(wzorzecWitryny("https://example.com/cennik?a=1")).toBe("https://example.com/*");
  });

  it("odmawia adresom, których przeglądarka i tak nie przyzna", () => {
    // Strony przeglądarki, sklep z rozszerzeniami i adresy bez hosta są poza zasięgiem
    // uprawnień; przyjęcie ich kończyłoby się cichym błędem przy prośbie o zgodę.
    expect(wzorzecWitryny("chrome://extensions")).toBeNull();
    expect(wzorzecWitryny("file:///etc/passwd")).toBeNull();
    expect(wzorzecWitryny("   ")).toBeNull();
  });
});

describe("zakres po instalacji", () => {
  it("świeży dodatek nie ma dostępu do żadnej witryny", async () => {
    przegladarka([]);
    expect(await przyznane()).toEqual([]);
    expect(await biezacy()).toBe("klik");
    expect(await maWszystkie()).toBe(false);
  });

  it("bez API uprawnień nie udaje, że coś ma", async () => {
    expect(await przyznane()).toEqual([]);
    expect(await biezacy()).toBe("klik");
  });
});

describe("zmiana zakresu", () => {
  it("wskazanie witryny nie daje dostępu do reszty sieci", async () => {
    const { origins } = przegladarka([]);
    expect(await popros(["https://sklep.example.pl/*"])).toBe(true);
    expect([...origins]).toEqual(["https://sklep.example.pl/*"]);
    expect(await biezacy()).toBe("wybrane");
    expect(await maWszystkie()).toBe(false);
  });

  it("odmowa użytkownika zostawia zakres bez zmian", async () => {
    przegladarka([], { zgoda: false });
    expect(await popros([WSZYSTKIE])).toBe(false);
    expect(await biezacy()).toBe("klik");
  });

  it("zawężenie zakresu oddaje zgodę, a nie tylko ją ukrywa", async () => {
    const { origins } = przegladarka([WSZYSTKIE, "https://example.com/*"]);
    expect(await biezacy()).toBe("wszystkie");
    await oddaj();
    expect([...origins]).toEqual([]);
    expect(await biezacy()).toBe("klik");
  });

  it("wyjście z „wszystkich stron” na listę witryn zdejmuje samo <all_urls>", async () => {
    const { origins } = przegladarka([WSZYSTKIE, "https://example.com/*"]);
    await oddaj([WSZYSTKIE]);
    expect([...origins]).toEqual(["https://example.com/*"]);
    expect(await biezacy()).toBe("wybrane");
  });
});

describe("skrypt treści chodzi tam, gdzie jest zgoda", () => {
  it("bez zgody nie rejestruje się wcale", async () => {
    const { skrypty } = przegladarka([]);
    await przeladujSkrypt();
    expect(skrypty.size).toBe(0);
  });

  it("rejestruje się na przyznanych witrynach", async () => {
    const { skrypty } = przegladarka(["https://example.com/*"]);
    await przeladujSkrypt();
    expect([...skrypty.values()][0]?.matches).toEqual(["https://example.com/*"]);
  });

  it("po oddaniu zgody znika, zamiast zostać na starych wzorcach", async () => {
    const { skrypty } = przegladarka(["https://example.com/*"]);
    await przeladujSkrypt();
    expect(skrypty.size).toBe(1);
    await oddaj();
    await przeladujSkrypt();
    expect(skrypty.size).toBe(0);
  });
});
