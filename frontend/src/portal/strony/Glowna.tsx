// Strona główna portalu: czym jest produkt, dla kogo, co obejmuje i gdzie szukać szczegółów.

import { portalApi } from "../api";
import { useZasob } from "../dane";
import { usePozycjonowanie, witryna } from "../seo";
import { FUNKCJONALNOSCI, OFERTA } from "../tresc";
import { sciezka } from "../trasy";
import { Karta, Ladowanie, NaglowekStrony, Odsylacz, OdsylaczPrzycisk, Sekcja } from "../ui";
import { KartaWpisu } from "./ListaWpisow";

const OPIS =
  "Danaco Nexus łączy rozmowę z agentem, dokumenty, pocztę, kalendarz i wyszukiwanie w Twoich plikach w jednym oknie. Zadanie zlecasz zdaniem, wynik odbierasz jako plik.";

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

      <Sekcja tytul="Do czego to służy" opis="Pięć rodzajów pracy, które Nexus przejmuje w całości — od skanu faktury po raport z przypisami.">
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

      <Sekcja tytul="Co dostajesz po zalogowaniu" opis="Sześć rzeczy, z których korzysta się codziennie. Cała reszta — w pełnym wykazie.">
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

      <Sekcja tytul="Z bloga" opis="Jak inni pracują z Nexusem i co doszło w ostatnich wydaniach.">
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
        opis="Pięć gotowych zadań uruchomisz w przeglądarce, bez zakładania konta. Plan Osobisty zaczyna się od 7 dni próbnych, a dokumentacja prowadzi przez pierwsze uruchomienie krok po kroku."
      >
        <div className="flex flex-wrap gap-3">
          <OdsylaczPrzycisk adres="/wyprobuj">Uruchom gotowe zadanie</OdsylaczPrzycisk>
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
