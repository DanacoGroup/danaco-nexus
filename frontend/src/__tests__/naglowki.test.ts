// Każdy ekran aplikacji zaczyna się nagłówkiem pierwszego stopnia.
//
// Pomiar na wydaniu 21.09.2026 (16 modułów plus adresy, których nie ma) znalazł dwa wyłomy:
// strona Płatności w stanie gotowym i ekran „ten moduł nie jest dostępny”. W obu wypadkach
// komunikat był na miejscu i po polsku — brakowało tylko nagłówka, więc czytnik ekranu nie
// miał od czego zacząć strony. Oba ekrany są trudne do zmontowania w jsdom (cała powłoka
// albo pełny cennik), więc test czyta źródło; zachowanie cennika pilnuje osobno
// `platnosci.test.tsx`.

import { describe, expect, it } from "vitest";
import zrodloPowloki from "../shell/Workspace.tsx?raw";
import zrodloPlatnosci from "../platnosci/index.tsx?raw";

describe("nagłówek pierwszego stopnia tam, gdzie nie ma strony modułu", () => {
  it("ekran nieznanego modułu ma `h1`, a nie `h2`", () => {
    const i = zrodloPowloki.indexOf("Ten moduł nie jest dostępny");
    expect(i).toBeGreaterThan(-1);
    const wiersz = zrodloPowloki.slice(zrodloPowloki.lastIndexOf("\n", i), i);
    expect(wiersz).toContain("<h1");
  });

  it("pasek kompaktowy powłoki celowo **nie** jest nagłówkiem", () => {
    // Tytuł modułu w wąskim pasku powtarza nagłówek strony modułu. Jako `h1` dawałby dwa
    // nagłówki tej samej strony i czytnik ogłaszał ją dwa razy.
    const i = zrodloPowloki.indexOf('{module?.label ?? "Moduł"}');
    expect(i).toBeGreaterThan(-1);
    expect(zrodloPowloki.slice(zrodloPowloki.lastIndexOf("\n", i), i)).toContain("<p");
  });

  it("strona Płatności ma tytuł także w stanie gotowym", () => {
    // Nie tylko w gałęzi wczytywania i błędu — tam stał od początku.
    expect(zrodloPlatnosci.split("<h1").length - 1).toBeGreaterThanOrEqual(3);
  });
});

describe("tytuł okna", () => {
  // `applyIndexing` zna tylko rodzaj ekranu („app”), więc każdy moduł miał ten sam tytuł.
  // Przy zainstalowanej aplikacji to tytuł w przełączniku okien systemu. Zmierzone na
  // zbudowanym interfejsie po poprawce: „Pliki — Danaco Nexus”, „Obrazy — Danaco Nexus”.
  it("powłoka dokłada do tytułu nazwę modułu albo rozmowy", () => {
    expect(zrodloPowloki).toContain("document.title = nazwaEkranu");
    expect(zrodloPowloki).toContain('module?.label ?? chat.detail?.title');
  });

  it("bez nazwy zostaje sam tytuł produktu, a nie myślnik na początku", () => {
    expect(zrodloPowloki).toContain('`${nazwaEkranu} — Danaco Nexus` : "Danaco Nexus"');
  });
});
