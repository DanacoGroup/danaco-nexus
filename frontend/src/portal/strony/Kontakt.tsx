// Kontakt: formularz zapytania (zapisywany w bazie i widoczny w panelu administratora).

import { useState } from "react";
import { komunikat, portalApi } from "../api";
import { okruszki, usePozycjonowanie } from "../seo";
import { KONTAKT } from "../tresc";
import { sciezka } from "../trasy";
import { Komunikat, NaglowekStrony, Okruszki, Pole, Przycisk } from "../ui";

const OPIS =
  "Napisz, co chcesz załatwiać w Nexusie. Odpowiadamy na wskazany adres w dni robocze; wiadomość z weekendu odbieramy w poniedziałek.";

/** Adres musi dać się odpisać: znak małpy, kropka w domenie, bez spacji. */
const ADRES_POCZTY = /^[^\s@]+@[^\s@.]+\.[^\s@]+$/;

/** Pierwszy brak w formularzu albo pusty napis, gdy komplet. Komunikat wskazuje jedno pole. */
export function sprawdzPola(imie: string, adres: string, wiadomosc: string): string {
  if (imie.trim().length < 2) return "Wpisz imię i nazwisko — co najmniej dwa znaki. Tak wiemy, do kogo piszemy.";
  if (!ADRES_POCZTY.test(adres.trim())) return "Popraw adres e-mail — potrzebujemy postaci nazwa@domena.pl, bo na ten adres idzie odpowiedź.";
  if (wiadomosc.trim().length < 10) return "Opisz sprawę w co najmniej 10 znakach — napisz, co masz do zrobienia i w jakich plikach.";
  return "";
}

export function Kontakt() {
  const [imie, setImie] = useState("");
  const [adres, setAdres] = useState("");
  const [temat, setTemat] = useState("");
  const [wiadomosc, setWiadomosc] = useState("");
  const [blad, setBlad] = useState("");
  const [wyslano, setWyslano] = useState(false);
  const [trwa, setTrwa] = useState(false);

  usePozycjonowanie({
    tytul: "Kontakt",
    opis: OPIS,
    sciezka: sciezka("kontakt"),
    dane: okruszki([
      { nazwa: "Portal", sciezka: sciezka("glowna") },
      { nazwa: "Kontakt", sciezka: sciezka("kontakt") },
    ]),
  });

  const wyslij = async () => {
    setBlad("");
    // Każdy brak osobno: formularz ma `noValidate`, więc to jedyny komunikat, jaki zobaczy piszący.
    const brak = sprawdzPola(imie, adres, wiadomosc);
    if (brak) {
      setBlad(brak);
      return;
    }
    setTrwa(true);
    try {
      await portalApi.kontakt({
        name: imie.trim(),
        email: adres.trim(),
        subject: temat.trim(),
        message: wiadomosc.trim(),
      });
      setWyslano(true);
      setImie("");
      setAdres("");
      setTemat("");
      setWiadomosc("");
    } catch (error) {
      setBlad(komunikat(error, "Nie udało się wysłać wiadomości. Spróbuj jeszcze raz albo napisz wprost na support@danaco-group.pl."));
    } finally {
      setTrwa(false);
    }
  };

  return (
    <>
      <Okruszki
        pozycje={[
          { nazwa: "Portal", sciezka: sciezka("glowna") },
          { nazwa: "Kontakt", sciezka: sciezka("kontakt") },
        ]}
      />
      <div className="mt-4">
        <NaglowekStrony tytul="Napisz, co masz do zrobienia" opis={OPIS} />
      </div>
      {/* items-start: bez tego karta obok formularza rozciąga się na jego wysokość
          i zostaje pod tekstem kilkaset pikseli pustego tła. */}
      <div className="mt-8 grid items-start gap-10 lg:grid-cols-[1fr_20rem]">
        <form
          noValidate
          onSubmit={(zdarzenie) => {
            zdarzenie.preventDefault();
            void wyslij();
          }}
          className="flex flex-col gap-5"
        >
          <Pole etykieta="Imię i nazwisko" wartosc={imie} naZmiane={setImie} wymagane autoUzupelnianie="name" />
          <Pole
            etykieta="Adres e-mail"
            typ="email"
            wartosc={adres}
            naZmiane={setAdres}
            wymagane
            autoUzupelnianie="email"
            podpowiedz="Na ten adres wyślemy odpowiedź. Nie trafi on do żadnej wysyłki reklamowej."
          />
          <Pole etykieta="Temat (opcjonalnie)" wartosc={temat} naZmiane={setTemat} />
          <Pole
            etykieta="Treść zapytania"
            wartosc={wiadomosc}
            naZmiane={setWiadomosc}
            wieloliniowe
            wymagane
            podpowiedz="Trzy rzeczy skracają drogę do odpowiedzi: co ma powstać, na jakich plikach pracujesz i ile osób będzie korzystać."
          />
          {blad && <Komunikat tekst={blad} rodzaj="blad" />}
          {wyslano && (
            <Komunikat
              tekst="Wiadomość przyjęta. Odpowiedź pójdzie na podany adres w dni robocze. Zanim odpiszemy, zrób własne zadanie na /wyprobuj — bez rejestracji."
              rodzaj="sukces"
            />
          )}
          <div>
            <Przycisk type="submit" disabled={trwa}>
              {trwa ? "Wysyłanie…" : "Wyślij zapytanie"}
            </Przycisk>
          </div>
        </form>
        <aside className="rounded-xl border border-line bg-raised p-5">
          <h2 className="font-heading text-lg font-semibold text-fg">Napisz wprost</h2>
          <p className="mt-3 text-sm text-muted">{KONTAKT.opis}</p>
          <p className="mt-4 text-sm">
            <a href={`mailto:${KONTAKT.adresPoczty}`} className="text-accent hover:underline">
              {KONTAKT.adresPoczty}
            </a>
          </p>
        </aside>
      </div>
    </>
  );
}
