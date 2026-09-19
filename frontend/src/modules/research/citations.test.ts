import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../../components/Markdown";
import { expandRefs, linkCitations, parseEntry, parseReport, prepareReport } from "./citations";

const REPORT = `# Pompy ciepła w starych domach

## Najważniejsze wnioski
- Pompa opłaca się po dociepleniu budynku [1][3].
- Koszt instalacji to 35–60 tys. zł [2, 3].
- Zakres badań [1–3] obejmuje lata 2020–2026.

Kod \`tablica[1]\` i [link](https://example.com) zostają bez zmian, podobnie [7].

\`\`\`
wynik[2] = 5
\`\`\`

## Źródła
- [1] Pompy ciepła w 2026 roku – Energia Dziś, 2026 – https://example.com/pompy
- [2] [Cennik instalacji](https://instalator.example.pl/cennik) – Instalator, 2025
- [3] Kowalska, A. M., & Smith, J. (2024). Heat pumps in cold climates. *Energy and Buildings*.
  https://doi.org/10.1000/heat.2024.1
`;

describe("parseReport", () => {
  it("oddziela listę źródeł od treści i odczytuje pozycje", () => {
    const parsed = parseReport(REPORT);
    expect(parsed.heading).toBe("Źródła");
    expect(parsed.body).not.toContain("## Źródła");
    expect(parsed.body).toContain("## Najważniejsze wnioski");
    expect(parsed.sources).toEqual([
      {
        n: 1,
        title: "Pompy ciepła w 2026 roku – Energia Dziś, 2026",
        url: "https://example.com/pompy",
        text: "Pompy ciepła w 2026 roku – Energia Dziś, 2026 – https://example.com/pompy",
      },
      {
        n: 2,
        title: "Cennik instalacji",
        url: "https://instalator.example.pl/cennik",
        text: "[Cennik instalacji](https://instalator.example.pl/cennik) – Instalator, 2025",
      },
      {
        n: 3,
        title: "Kowalska, A. M., & Smith, J. (2024). Heat pumps in cold climates. *Energy and Buildings*.",
        url: "https://doi.org/10.1000/heat.2024.1",
        text:
          "Kowalska, A. M., & Smith, J. (2024). Heat pumps in cold climates. *Energy and Buildings*. " +
          "https://doi.org/10.1000/heat.2024.1",
      },
    ]);
  });

  it("obsługuje bibliografię numerowaną, przypisy [^n] i sekcję po liście źródeł", () => {
    const parsed = parseReport(
      "Tekst [^1] i [2].\n\n### Bibliografia:\n1. Nowak, J. (2020). Tytuł. https://doi.org/10.1/x.\n" +
        "2) <https://example.org/b>\n\n### Ograniczenia\nBrak danych z 2026 r.",
    );
    expect(parsed.heading).toBe("Bibliografia");
    expect(parsed.sources.map((item) => [item.n, item.url])).toEqual([
      [1, "https://doi.org/10.1/x"],
      [2, "https://example.org/b"],
    ]);
    expect(parsed.sources[1].title).toBe("example.org");
    expect(parsed.body).toContain("### Ograniczenia");
  });

  it("bez sekcji źródeł zwraca całą treść", () => {
    expect(parseReport("Zwykła odpowiedź [1].")).toEqual({ body: "Zwykła odpowiedź [1].", heading: null, sources: [] });
  });

  it("ignoruje nagłówek źródeł w bloku kodu", () => {
    const parsed = parseReport("```\n## Źródła\n- [1] x https://a.pl\n```\nKoniec.");
    expect(parsed.sources).toEqual([]);
  });
});

describe("linkCitations", () => {
  it("zamienia odwołania na odnośniki, pomijając kod, linki i nieznane numery", () => {
    const html = linkCitations(parseReport(REPORT).body, new Set([1, 2, 3]));
    expect(html).toContain('<sup class="cite-group"><a href="#zrodlo-1" data-cite="1" class="cite">1</a></sup>');
    expect(html).toContain(
      '<a href="#zrodlo-2" data-cite="2" class="cite">2</a><span class="cite-sep">,</span><a href="#zrodlo-3"',
    );
    expect(html.match(/data-cite="1"/g)).toHaveLength(2);
    expect(html).toContain("`tablica[1]`");
    expect(html).toContain("wynik[2] = 5");
    expect(html).toContain("[link](https://example.com)");
    expect(html).toContain("podobnie [7]");
  });

  it("rozwija zakresy i listy numerów", () => {
    expect(expandRefs("1, 3")).toEqual([1, 3]);
    expect(expandRefs("2–4")).toEqual([2, 3, 4]);
    expect(expandRefs("5-2")).toEqual([]);
  });

  it("odnośniki przechodzą przez renderowanie Markdown z atrybutem data-cite", () => {
    const report = prepareReport(REPORT);
    const html = renderMarkdown(report.html);
    const container = document.createElement("div");
    container.innerHTML = html;
    const links = Array.from(container.querySelectorAll<HTMLAnchorElement>("a[data-cite]"));
    expect(links.map((link) => link.dataset.cite)).toEqual(["1", "3", "2", "3", "1", "2", "3"]);
    expect(container.querySelector("h2")?.textContent).toBe("Najważniejsze wnioski");
  });
});

describe("parseEntry", () => {
  it("rozpoznaje odnośnik, którego tekstem jest adres", () => {
    expect(parseEntry(4, "Ministerstwo Klimatu – [https://gov.pl/klimat](https://gov.pl/klimat)")).toEqual({
      n: 4,
      title: "Ministerstwo Klimatu",
      url: "https://gov.pl/klimat",
      text: "Ministerstwo Klimatu – [https://gov.pl/klimat](https://gov.pl/klimat)",
    });
  });
});
