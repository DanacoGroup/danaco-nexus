// Strona główna portalu: czym jest produkt, dla kogo, co obejmuje i gdzie szukać szczegółów.

import { portalApi } from "../api";
import { LICZBA_NARZEDZI } from "../../dane/narzedzia";
import { useZasob } from "../dane";
import { usePozycjonowanie, witryna } from "../seo";
import { FUNKCJONALNOSCI, OFERTA } from "../tresc";
import { sciezka, type PortalStrona } from "../trasy";
import { Karta, Ladowanie, NaglowekStrony, Odsylacz, OdsylaczPrzycisk, Sekcja } from "../ui";
import { KartaWpisu } from "./ListaWpisow";

const OPIS =
  "Danaco Nexus przyjmuje zadanie opisane jednym zdaniem i oddaje gotowy plik. Dokumenty, poczta, kalendarz i wyszukiwanie w Twoich plikach stoją w jednym oknie.";

/** Sytuacje, w których czytelnik ma się rozpoznać — po jednej na rodzaj roboty, bez nazw technicznych. */
const ODBIORCY = [
  {
    nazwa: "Stos skanów do przepisania",
    opis: "Trzysta faktur w skanach wraca jako tabela z kwotami i przeszukiwalny plik PDF. Niczego nie przepisujesz ręcznie.",
  },
  {
    nazwa: "Materiał do opracowania",
    opis: "Nagranie spotkania wraca jako tekst ze znacznikami czasu. Dokument w obcym języku wraca z nienaruszonym układem.",
  },
  {
    nazwa: "Robota, do której brakuje specjalisty",
    opis: "Logo, ulotka i strona firmowa powstają w rozmowie. Nie otwierasz programu graficznego i nie zamawiasz projektu na zewnątrz.",
  },
];

/** Odpowiedź na drugą obawę czytelnika: gdzie leżą jego pliki i co wychodzi poza serwer. */
const PRZECHOWYWANIE = [
  {
    nazwa: "Jedno konto, jedna przestrzeń",
    opis: "Pliki, rozmowy, pocztę i kalendarz widzi wyłącznie właściciel konta. Chmura osobista pod adresem cloud.danaco-nexus.pl otwiera się tym samym logowaniem.",
  },
  {
    nazwa: "Co wychodzi poza serwer",
    opis: "Treść polecenia i dołączone pliki trafiają do modelu, który prowadzi rozmowę. Poza tym nic nie opuszcza Twojej przestrzeni.",
  },
  {
    nazwa: "Zgoda przed krokiem na zewnątrz",
    opis: "Wysłanie wiadomości, usunięcie wydarzenia i publikację strony zatwierdzasz sam. Funkcje sięgające cudzych danych są domyślnie wyłączone.",
  },
];

/** Mapa portalu: każda pozycja mówi, na jakie pytanie odpowiada podstrona. */
const PODSTRONY: { strona: PortalStrona; nazwa: string; opis: string }[] = [
  { strona: "oferta", nazwa: "Oferta", opis: "Osiem rodzajów pracy, z zakresem i adresatem." },
  { strona: "funkcje", nazwa: "Funkcje", opis: "Wykaz tego, co działa po zalogowaniu." },
  { strona: "zastosowania", nazwa: "Zastosowania", opis: "Osiem sytuacji z pracy, rozpisanych krok po kroku." },
  {
    strona: "narzedzia",
    nazwa: "Narzędzia",
    opis: `Katalog ${LICZBA_NARZEDZI} narzędzi w dziesięciu dziedzinach, z wyszukiwarką.`,
  },
  { strona: "cennik", nazwa: "Cennik", opis: "Plany Osobisty, Pro i Grupa oraz różnice między nimi." },
  { strona: "wiedza", nazwa: "Centrum wiedzy", opis: "Poradniki i odpowiedzi na częste pytania." },
  { strona: "blog", nazwa: "Blog", opis: "Zmiany w produkcie i praca z Nexusem." },
  { strona: "dokumentacja", nazwa: "Dokumentacja", opis: "Opis ekranów i pierwsze uruchomienie." },
  { strona: "kontakt", nazwa: "Kontakt", opis: "Pytanie o własną sprawę i dobór planu." },
];

export function Glowna() {
  const wpisy = useZasob(() => portalApi.lista({ typ: "blog", na_stronie: 3 }), "glowna-blog");
  usePozycjonowanie({ tytul: "Portal produktowy", opis: OPIS, sciezka: sciezka("glowna"), dane: witryna() });

  return (
    <>
      <NaglowekStrony tytul="Powiedz, co ma powstać. Odbierz gotowy plik." opis={OPIS}>
        <div className="flex flex-wrap gap-3">
          <OdsylaczPrzycisk adres="/wyprobuj">Wejdź bez rejestracji</OdsylaczPrzycisk>
          <OdsylaczPrzycisk adres={sciezka("oferta")} wariant="drugorzedny">
            Poznaj ofertę
          </OdsylaczPrzycisk>
          <OdsylaczPrzycisk adres="/zaloguj" wariant="drugorzedny">
            Zaloguj się do aplikacji
          </OdsylaczPrzycisk>
        </div>
      </NaglowekStrony>

      <Sekcja
        tytul="Dla kogo jest Nexus"
        opis="Nexus trafia do osób, które mają na biurku konkretną robotę i nie mają do niej ani programu, ani czasu."
      >
        <ul className="grid gap-4 sm:grid-cols-3">
          {ODBIORCY.map((pozycja) => (
            <li key={pozycja.nazwa} className="rounded-xl border border-line bg-raised p-4">
              <h3 className="font-heading text-base font-semibold text-fg">{pozycja.nazwa}</h3>
              <p className="mt-1.5 text-sm text-muted">{pozycja.opis}</p>
            </li>
          ))}
        </ul>
      </Sekcja>

      <Sekcja
        tytul="Do czego to służy"
        opis="Osiem rodzajów pracy, które Nexus przejmuje w całości — od skanu faktury po raport z przypisami do źródeł."
      >
        <ul className="grid gap-5 sm:grid-cols-2">
          {OFERTA.map((pozycja) => (
            <li key={pozycja.nazwa}>
              <Karta className="flex h-full flex-col gap-2">
                <h3 className="font-heading text-lg font-semibold text-fg">{pozycja.nazwa}</h3>
                <p className="text-sm text-muted">{pozycja.opis}</p>
                <p className="mt-auto text-xs text-subtle">{pozycja.dla}</p>
              </Karta>
            </li>
          ))}
        </ul>
      </Sekcja>

      <Sekcja tytul="Co dostajesz po zalogowaniu" opis="Sześć funkcji z codziennej pracy. Pozostałe opisuje pełny wykaz.">
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FUNKCJONALNOSCI.slice(0, 6).map((funkcja) => (
            <li key={funkcja.nazwa} className="rounded-xl border border-line bg-raised p-4">
              <h3 className="font-heading text-base font-semibold text-fg">{funkcja.nazwa}</h3>
              <p className="mt-1.5 text-sm text-muted">{funkcja.opis}</p>
            </li>
          ))}
        </ul>
        <p className="mt-5 text-sm">
          <Odsylacz adres={sciezka("funkcje")} className="text-accent hover:underline">
            Zobacz wszystkie funkcjonalności
          </Odsylacz>
        </p>
      </Sekcja>

      <Sekcja
        tytul="Gdzie zostają Twoje pliki"
        opis="Serwer stoi w Polsce. Na urządzeniu zostaje sam interfejs, więc dokumenty nie rozchodzą się po dyskach."
      >
        <ul className="grid gap-4 sm:grid-cols-3">
          {PRZECHOWYWANIE.map((pozycja) => (
            <li key={pozycja.nazwa} className="rounded-xl border border-line bg-raised p-4">
              <h3 className="font-heading text-base font-semibold text-fg">{pozycja.nazwa}</h3>
              <p className="mt-1.5 text-sm text-muted">{pozycja.opis}</p>
            </li>
          ))}
        </ul>
      </Sekcja>

      <Sekcja
        tytul="Podstrony portalu"
        opis="Każda podstrona odpowiada na inne pytanie. Zacznij od tej, która pasuje do Twojej sprawy."
      >
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PODSTRONY.map((pozycja) => (
            <li key={pozycja.strona} className="rounded-xl border border-line bg-raised p-4">
              <h3 className="font-heading text-base font-semibold text-fg">
                <Odsylacz adres={sciezka(pozycja.strona)} className="text-accent hover:underline">
                  {pozycja.nazwa}
                </Odsylacz>
              </h3>
              <p className="mt-1.5 text-sm text-muted">{pozycja.opis}</p>
            </li>
          ))}
        </ul>
      </Sekcja>

      <Sekcja tytul="Z bloga" opis="Zmiany w produkcie i notatki z pracy nad Nexusem.">
        <div>
          {wpisy.ladowanie && <Ladowanie wierszy={2} etykieta="Wczytywanie wpisów" />}
          {!wpisy.ladowanie && (wpisy.dane?.items.length ?? 0) === 0 && (
            <p className="text-muted">
              Pierwsze wpisy powstają. Zanim się pojawią, zajrzyj do dokumentacji — opisuje uruchomienie krok po kroku.
            </p>
          )}
          {(wpisy.dane?.items.length ?? 0) > 0 && (
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {(wpisy.dane?.items ?? []).map((pozycja) => (
                <KartaWpisu key={pozycja.id} pozycja={pozycja} adres={sciezka("blog", pozycja.slug)} />
              ))}
            </ul>
          )}
        </div>
      </Sekcja>

      <Sekcja
        tytul="Od czego zacząć"
        opis={
          "Przepisz jeden skan na koncie próbnym, a plik dostaniesz w tej samej rozmowie. Konto próbne działa " +
          "bez rejestracji, bez karty i bez instalacji. Plan Osobisty zaczyna się od 7\u00a0dni próbnych ze 100\u00a0MB miejsca."
        }
      >
        <div className="flex flex-wrap gap-3">
          <OdsylaczPrzycisk adres="/wyprobuj">Przepisz pierwszy skan</OdsylaczPrzycisk>
          <OdsylaczPrzycisk adres={sciezka("cennik")} wariant="drugorzedny">
            Sprawdź plany
          </OdsylaczPrzycisk>
          <OdsylaczPrzycisk adres={sciezka("dokumentacja")} wariant="drugorzedny">
            Przeczytaj dokumentację
          </OdsylaczPrzycisk>
        </div>
      </Sekcja>
    </>
  );
}
