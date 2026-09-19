import { beforeEach, describe, expect, it } from "vitest";
import { skroc, tekstElementu, trescStrony, tytulStrony, wyodrebnij, zaznaczonyTekst } from "../src/tresc/ekstraktor";

const AKAPIT =
  "Hotel położony jest w centrum Krakowa, dwie minuty od Rynku Głównego, w odrestaurowanej kamienicy z XIX wieku. " +
  "Pokoje mają klimatyzację, sejf i ekspres do kawy, a śniadania podawane są w ogrodzie, przy dobrej pogodzie.";

function strona(html: string, tytul = "Hotel Pod Różą – opis"): void {
  document.title = tytul;
  document.body.innerHTML = html;
}

describe("ekstraktor treści", () => {
  beforeEach(() => {
    document.getSelection()?.removeAllRanges();
  });

  it("wybiera artykuł i pomija nawigację, stopkę, skrypty i elementy ukryte", () => {
    strona(`
      <header><nav><a href="/">Start</a> <a href="/oferta">Oferta</a> <a href="/kontakt">Kontakt z recepcją hotelu</a></nav></header>
      <div class="sidebar"><p>Reklama: najlepsze kredyty w mieście, sprawdź, kliknij, zyskaj teraz, bez zobowiązań.</p></div>
      <main>
        <article class="post-content">
          <h1>Hotel Pod Różą</h1>
          <p>${AKAPIT}</p>
          <p>${AKAPIT}</p>
          <p style="display:none">Ukryty tekst promocyjny, którego nie widać na stronie, a jest w kodzie.</p>
          <script>var sekret = "nie-w-tresci";</script>
          <ul><li>Parking płatny, 80 zł za dobę, rezerwacja wymagana.</li><li>Zwierzęta akceptowane po wcześniejszym uzgodnieniu.</li></ul>
        </article>
      </main>
      <footer><p>© 2026 Hotel Pod Różą, wszystkie prawa zastrzeżone, polityka prywatności, regulamin.</p></footer>
    `);
    const tresc = trescStrony(document);
    expect(tresc.zrodlo).toBe("artykul");
    expect(tresc.tekst).toContain("# Hotel Pod Różą");
    expect(tresc.tekst).toContain("dwie minuty od Rynku Głównego");
    expect(tresc.tekst).toContain("- Parking płatny");
    expect(tresc.tekst).not.toContain("Reklama");
    expect(tresc.tekst).not.toContain("Kontakt z recepcją");
    expect(tresc.tekst).not.toContain("wszystkie prawa zastrzeżone");
    expect(tresc.tekst).not.toContain("Ukryty tekst");
    expect(tresc.tekst).not.toContain("sekret");
    expect(tresc.skrocono).toBe(false);
  });

  it("bez wyraźnego artykułu zwraca czytelną treść całej strony", () => {
    strona(`<div><span>Cena: 420 zł</span><br><span>Termin: 12–14 października</span></div>`);
    const tresc = trescStrony(document);
    expect(tresc.zrodlo).toBe("strona");
    expect(tresc.tekst).toBe("Cena: 420 zł\nTermin: 12–14 października");
  });

  it("zachowuje strukturę tabel", () => {
    strona(`<table><tr><th>Pokój</th><th>Cena</th></tr><tr><td>Dwuosobowy</td><td>420 zł</td></tr></table>`);
    expect(tekstElementu(document.body)).toBe("Pokój | Cena\nDwuosobowy | 420 zł");
  });

  it("pomija panel rozszerzenia na stronie", () => {
    strona(`<p>Treść strony widoczna dla użytkownika.</p><danaco-nexus>Panel Nexusa</danaco-nexus>`);
    expect(tekstElementu(document.body)).toBe("Treść strony widoczna dla użytkownika.");
  });

  it("preferuje zaznaczony tekst", () => {
    strona(`<article><p>${AKAPIT}</p><p id="z">Zaznaczony fragment opinii o hotelu.</p></article>`);
    const zakres = document.createRange();
    zakres.selectNodeContents(document.getElementById("z")!);
    document.getSelection()!.addRange(zakres);
    const tresc = wyodrebnij(document);
    expect(tresc.zrodlo).toBe("zaznaczenie");
    expect(tresc.tekst).toBe("Zaznaczony fragment opinii o hotelu.");
  });

  it("odczytuje zaznaczenie w polu tekstowym", () => {
    strona(`<textarea id="t">Dzień dobry, dziękujemy za opinię.</textarea>`);
    const pole = document.getElementById("t") as HTMLTextAreaElement;
    pole.focus();
    pole.setSelectionRange(0, 11);
    expect(zaznaczonyTekst(document)).toBe("Dzień dobry");
  });

  it("skraca długą treść z oznaczeniem", () => {
    const dlugi = Array.from({ length: 400 }, (_, i) => `Akapit numer ${i} z pewną treścią.`).join("\n");
    const wynik = skroc(dlugi, 1000);
    expect(wynik.skrocono).toBe(true);
    expect(wynik.tekst.length).toBeLessThan(1100);
    expect(wynik.tekst.endsWith("[…treść skrócona]")).toBe(true);
    expect(wynik.tekst).toContain("Akapit numer 0");
  });

  it("stosuje limit długości do treści strony", () => {
    strona(`<article>${Array.from({ length: 200 }, () => `<p>${AKAPIT}</p>`).join("")}</article>`);
    const tresc = trescStrony(document, 5000);
    expect(tresc.skrocono).toBe(true);
    expect(tresc.tekst.length).toBeLessThanOrEqual(5100);
  });

  it("tytuł z document.title albo og:title", () => {
    strona("<p>x</p>", "");
    document.head.innerHTML = '<meta property="og:title" content="Tytuł z Open Graph">';
    expect(tytulStrony(document)).toBe("Tytuł z Open Graph");
    document.title = "Właściwy tytuł";
    expect(tytulStrony(document)).toBe("Właściwy tytuł");
  });
});
