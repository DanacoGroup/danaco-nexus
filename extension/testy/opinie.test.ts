import { afterEach, describe, expect, it } from "vitest";
import { skrot, wykryjSerwis, znajdzOpinie } from "../src/tresc/opinie";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("rozpoznawanie serwisu", () => {
  it.each([
    ["https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/reviews.html?hotel_id=1", "booking-partner"],
    ["https://www.booking.com/hotel/pl/pod-roza.pl.html", "booking"],
    ["https://www.google.com/maps/place/Hotel/@50,19,17z", "google-maps"],
    ["https://www.google.pl/search?q=hotel", "google-firma"],
    ["https://business.google.com/reviews", "google-firma"],
    ["https://mail.google.com/mail/u/0/#inbox/abc", "gmail"],
    ["https://outlook.office.com/mail/inbox", "outlook"],
    ["https://mail.danaco-group.pl/?_task=mail", "poczta"],
    ["https://example.com/", "inne"],
    ["nie-adres", "inne"],
  ])("%s → %s", (adres, serwis) => {
    expect(wykryjSerwis(adres)).toBe(serwis);
  });
});

describe("wyszukiwanie opinii", () => {
  it("Booking.com (strona publiczna): tytuł, plusy, minusy, autor i ocena", () => {
    document.body.innerHTML = `
      <div id="lista">
        <div data-testid="review-card">
          <div data-testid="review-avatar">Anna z Polski</div>
          <div data-testid="review-score">9,0</div>
          <h3 data-testid="review-title">Świetna lokalizacja</h3>
          <div data-testid="review-positive-text">Blisko rynku, czysto i cicho.</div>
          <div data-testid="review-negative-text">Mało miejsca na parkingu.</div>
        </div>
        <div data-testid="review-card">
          <div data-testid="review-avatar">John</div>
          <div data-testid="review-positive-text">Great breakfast and friendly staff.</div>
        </div>
      </div>`;
    const opinie = znajdzOpinie(document, "https://www.booking.com/hotel/pl/x.html");
    expect(opinie).toHaveLength(2);
    expect(opinie[0]).toMatchObject({ rodzaj: "opinia", serwis: "booking", autor: "Anna z Polski", ocena: "9,0" });
    expect(opinie[0].tekst).toContain("Świetna lokalizacja");
    expect(opinie[0].tekst).toContain("Blisko rynku");
    expect(opinie[0].tekst).toContain("Mało miejsca");
    expect(opinie[1].autor).toBe("John");
  });

  it("panel partnera Booking: karta z polem odpowiedzi", () => {
    document.body.innerHTML = `
      <div class="review-list">
        <div class="review-card">
          <span class="guest-name">Marek</span><span class="review-score">7,5</span>
          <p class="review-text">Pokój ładny, ale klimatyzacja głośno pracowała w nocy.</p>
          <textarea placeholder="Odpowiedz gościowi"></textarea>
        </div>
        <div class="review-card">
          <span class="guest-name">Ewa</span>
          <p class="review-text">Wszystko w porządku, polecam każdemu.</p>
        </div>
      </div>`;
    const opinie = znajdzOpinie(document, "https://admin.booking.com/hotel/hoteladmin/reviews");
    expect(opinie.map((o) => o.autor)).toEqual(["Marek", "Ewa"]);
    expect(opinie[0].poleOdpowiedzi).toBe(true);
    expect(opinie[0].pole?.tagName).toBe("TEXTAREA");
    expect(opinie[1].poleOdpowiedzi).toBe(false);
    expect(opinie[0].tekst).toBe("Pokój ładny, ale klimatyzacja głośno pracowała w nocy.");
  });

  it("Mapy Google: data-review-id, gwiazdki z aria-label", () => {
    document.body.innerHTML = `
      <div class="jftiEf" data-review-id="r1" aria-label="Katarzyna">
        <div class="d4r55">Katarzyna</div>
        <span class="kvMYJc" role="img" aria-label="5 gwiazdek"></span><span class="rsqaWe">tydzień temu</span>
        <div class="MyEned"><span class="wiI7pd">Przepyszne jedzenie i miła obsługa, wrócimy!</span></div>
        <div data-review-id="r1"><button>Udostępnij</button></div>
      </div>`;
    const opinie = znajdzOpinie(document, "https://www.google.com/maps/place/Restauracja");
    expect(opinie).toHaveLength(1);
    expect(opinie[0]).toMatchObject({ autor: "Katarzyna", ocena: "5 gwiazdek", data: "tydzień temu" });
    expect(opinie[0].tekst).toBe("Przepyszne jedzenie i miła obsługa, wrócimy!");
  });

  it("Gmail: rozwinięte wiadomości wątku", () => {
    document.body.innerHTML = `
      <div class="adn ads"><span class="gD" email="klient@example.com">Jan Klient</span><span class="g3">12 wrz</span>
        <div class="a3s">Dzień dobry, czy pokój jest dostępny 14–16 października? Pozdrawiam, Jan</div></div>`;
    const opinie = znajdzOpinie(document, "https://mail.google.com/mail/u/0/#inbox/1");
    expect(opinie).toHaveLength(1);
    expect(opinie[0]).toMatchObject({ rodzaj: "wiadomosc", autor: "Jan Klient", data: "12 wrz" });
    expect(opinie[0].tekst).toContain("czy pokój jest dostępny");
  });

  it("heurystyka ogólna: schema.org Review i komentarze, bez kontenerów list", () => {
    document.body.innerHTML = `
      <section class="reviews">
        <div itemprop="review"><span itemprop="author">Olga</span><span itemprop="ratingValue">4</span>
          <p itemprop="reviewBody">Dobry produkt, szybka wysyłka, polecam sklep.</p></div>
        <div itemprop="review"><span itemprop="author">Piotr</span>
          <p itemprop="reviewBody">Opakowanie uszkodzone, ale produkt cały.</p></div>
      </section>
      <div class="comments"><div class="comment"><cite>Ala</cite><p>Świetny artykuł, dziękuję za konkretne porady.</p></div></div>`;
    const opinie = znajdzOpinie(document, "https://sklep.example.com/produkt");
    expect(opinie.map((o) => [o.rodzaj, o.autor])).toEqual([
      ["opinia", "Olga"],
      ["opinia", "Piotr"],
      ["komentarz", "Ala"],
    ]);
    expect(opinie[0].tekst).toBe("Dobry produkt, szybka wysyłka, polecam sklep.");
    expect(opinie[0].ocena).toBe("4");
  });

  it("pomija panel rozszerzenia i zbyt krótkie elementy", () => {
    document.body.innerHTML = `<div class="review">ok</div><danaco-nexus><div class="review">Opinia w panelu, nie na stronie.</div></danaco-nexus>`;
    expect(znajdzOpinie(document, "https://example.com/")).toEqual([]);
  });

  it("skrót bez referencji DOM i z przyciętym tekstem", () => {
    document.body.innerHTML = `<div class="review"><p>${"Bardzo długa opinia. ".repeat(100)}</p><textarea></textarea></div>`;
    const [opinia] = znajdzOpinie(document, "https://example.com/");
    const s = skrot(opinia);
    expect(s).not.toHaveProperty("element");
    expect(s).not.toHaveProperty("pole");
    expect(s.tekst.length).toBe(600);
    expect(s.poleOdpowiedzi).toBe(true);
    expect(JSON.parse(JSON.stringify(s))).toEqual(s);
  });
});
