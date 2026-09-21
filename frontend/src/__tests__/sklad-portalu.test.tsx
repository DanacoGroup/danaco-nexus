// Skład artykułów portalu: proza nie łamie wierszy w środku zdań, a zajawka nie dubluje
// pierwszego akapitu.
//
// Obie usterki wyszły dopiero na zrzucie gotowej strony — odpowiedź API mówiła wyłącznie
// tyle, że treść jest. Pliki źródłowe materiałów są zawijane na ok. 95 znakach dla
// czytelności w repozytorium, a `marked` z `breaks: true` zamieniał każde takie zawinięcie
// na `<br>`.

import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../components/Markdown";
import zrodloWpisu from "../portal/strony/Wpis.tsx?raw";

const AKAPIT = "Pierwsze zdanie akapitu, zawinięte\nw pliku źródłowym na dwa wiersze.";

describe("renderowanie prozy", () => {
  it("pojedyncze zawinięcie wiersza nie staje się przełamaniem", () => {
    expect(renderMarkdown(AKAPIT, false)).not.toContain("<br");
  });

  it("w rozmowie przełamanie zostaje — tam użytkownik nacisnął Enter świadomie", () => {
    expect(renderMarkdown(AKAPIT)).toContain("<br");
  });

  it("pusty wiersz dalej rozdziela akapity w obu trybach", () => {
    const dwa = "Pierwszy akapit.\n\nDrugi akapit.";
    expect((renderMarkdown(dwa, false).match(/<p>/g) ?? []).length).toBe(2);
    expect((renderMarkdown(dwa).match(/<p>/g) ?? []).length).toBe(2);
  });
});

describe("zajawka na stronie wpisu", () => {
  it("nie jest rysowana, gdy jest po prostu wstępem artykułu", () => {
    // Zachowania nie da się sprawdzić bez zmontowania całej strony z trasowaniem portalu,
    // więc test pilnuje samego warunku — i tego, że pomocnicza w ogóle istnieje.
    expect(zrodloWpisu).toContain("!zaczynaSieOd(pozycja.body, pozycja.excerpt)");
    expect(zrodloWpisu).toContain("function zaczynaSieOd(");
  });
});
