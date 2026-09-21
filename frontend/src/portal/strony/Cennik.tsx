// Cennik portalu: plany i kwoty prosto z serwera (ta sama definicja co w module Płatności)
// oraz najczęstsze pytania jako dane strukturalne FAQPage.

import { useEffect, useState } from "react";
import { ApiError } from "../../api";
import {
  PLAN_ZA_UZYTKOWNIKA,
  cenaPlanu,
  kwota,
  opisOkresuProbnego,
  opisZakresuPracy,
  oszczednoscRoczna,
  platnosciApi,
  type CennikPubliczny,
  type PlanInfo,
} from "../../platnosci/api";
import { okruszki, usePozycjonowanie } from "../seo";
import { PYTANIA } from "../tresc";
import { sciezka } from "../trasy";
import { Karta, Komunikat, Ladowanie, NaglowekStrony, OdsylaczPrzycisk, Znacznik } from "../ui";

const OPIS = "Plany korzystania z Danaco Nexus i zakres każdego z nich.";
const BLAD = "Nie udało się pobrać cennika z serwera. Odśwież stronę za chwilę albo napisz do nas.";

function pytaniaSchema(): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: PYTANIA.map((pozycja) => ({
      "@type": "Question",
      name: pozycja.pytanie,
      acceptedAnswer: { "@type": "Answer", text: pozycja.odpowiedz },
    })),
  };
}

/** Kwota planu z podziałem na okres; plan bez ceny czeka na start sprzedaży. */
function Cena({ plan, waluta }: { plan: PlanInfo; waluta: string }) {
  const miesiac = cenaPlanu(plan, "miesiac");
  if (miesiac <= 0) {
    return (
      <p>
        <span className="font-heading text-2xl font-semibold text-fg">Cena przy starcie</span>{" "}
        <span className="text-sm text-subtle">wkrótce</span>
      </p>
    );
  }
  const rok = cenaPlanu(plan, "rok");
  const oszczednosc = oszczednoscRoczna(plan);
  // Plan grupowy rozlicza się za każdego użytkownika; sama kwota obok „miesięcznie”
  // czytałaby się jak cena całej grupy, a to kilka razy mniej niż rachunek.
  const zaOsobe = plan.kod === PLAN_ZA_UZYTKOWNIKA;
  return (
    <div>
      <p>
        <span className="font-heading text-2xl font-semibold text-fg">{kwota(miesiac, waluta)}</span>{" "}
        <span className="text-sm text-subtle">{zaOsobe ? "za osobę, miesięcznie" : "miesięcznie"}</span>
      </p>
      {rok > 0 && (
        <p className="mt-1 text-sm text-muted">
          Rocznie {kwota(rok, waluta)}
          {oszczednosc > 0 ? ` — taniej o ${oszczednosc}%` : ""}
        </p>
      )}
    </div>
  );
}

/** Wezwanie do działania zależne od tego, czy plan da się już kupić. */
function Przejscie({ dostepny }: { dostepny: boolean }) {
  if (dostepny) {
    return (
      <OdsylaczPrzycisk adres="/m/platnosci" wariant="glowny" className="w-full">
        Kup w aplikacji
      </OdsylaczPrzycisk>
    );
  }
  return (
    <OdsylaczPrzycisk adres={sciezka("kontakt")} wariant="drugorzedny" className="w-full">
      Powiadom mnie
    </OdsylaczPrzycisk>
  );
}

export function Cennik() {
  const [cennik, setCennik] = useState<CennikPubliczny | null>(null);
  const [blad, setBlad] = useState("");

  usePozycjonowanie({
    tytul: "Cennik",
    opis: OPIS,
    sciezka: sciezka("cennik"),
    dane: [
      pytaniaSchema(),
      okruszki([
        { nazwa: "Portal", sciezka: sciezka("glowna") },
        { nazwa: "Cennik", sciezka: sciezka("cennik") },
      ]),
    ],
  });

  useEffect(() => {
    let aktualne = true;
    const wczytaj = async () => {
      try {
        const dane = await platnosciApi.cennikPubliczny();
        if (aktualne) setCennik(dane);
      } catch (awaria) {
        // Komunikat serwera **nie** trafia na stronę publiczną. Cennik czyta każdy, kto
        // wejdzie z wyszukiwarki, a treść błędu jest pisana do zalogowanego klienta albo
        // do administratora: przy 401 odwiedzający zobaczyłby „Wymagane logowanie.” na
        // stronie, na której nie ma czego logować. Zdanie jest więc jedno i nasze,
        // a szczegół idzie do konsoli — dla nas, nie dla niego.
        if (awaria instanceof ApiError) console.warn("Cennik publiczny:", awaria.message);
        if (aktualne) setBlad(BLAD);
      }
    };
    void wczytaj();
    return () => {
      aktualne = false;
    };
  }, []);

  return (
    <>
      <NaglowekStrony tytul="Cennik" opis={OPIS} />

      {blad && (
        <div className="mt-8">
          <Komunikat tekst={blad} rodzaj="blad" />
        </div>
      )}
      {!cennik && !blad && (
        <div className="mt-8">
          <Ladowanie wierszy={4} etykieta="Wczytywanie cennika" />
        </div>
      )}

      {cennik && !cennik.sprzedaz_aktywna && (
        <Karta className="mt-8">
          <h2 className="font-heading text-lg font-semibold text-fg">
            Sprzedaż nie jest jeszcze włączona
          </h2>
          <p className="mt-2 text-sm text-muted">
            Planów nie da się jeszcze kupić. Zostaw nam wiadomość, a damy znać, gdy sprzedaż
            ruszy.
          </p>
        </Karta>
      )}

      {cennik && (
        <ul className="mt-8 grid gap-6 lg:grid-cols-3">
          {cennik.plany.map((plan) => {
            const dostepny = plan.do_kupienia.miesiac || plan.do_kupienia.rok;
            return (
              <li key={plan.kod}>
                <Karta className="flex h-full flex-col gap-4">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-heading text-xl font-semibold text-fg">{plan.nazwa}</h2>
                    <Znacznik
                      tekst={dostepny ? "Dostępny" : "Wkrótce"}
                      ton={dostepny ? "dostepny" : "cichy"}
                    />
                  </div>
                  <Cena plan={plan} waluta={cennik.waluta} />
                  <p className="text-sm text-muted">{plan.opis}</p>
                  <ul className="flex flex-col gap-1.5 text-sm text-muted">
                    {plan.zawartosc.map((element) => (
                      <li key={element} className="flex gap-2">
                        <span aria-hidden="true" className="text-accent">
                          •
                        </span>
                        {element}
                      </li>
                    ))}
                  </ul>
                  {/* Bez liczby kredytów — patrz `opisZakresuPracy` w module płatności. */}
                  <p className="text-sm text-muted">{opisZakresuPracy(plan)}</p>
                  {/* Bez słowa „kredyt”: jednostka rozliczeniowa jest nasza, nie
                    użytkownika. Klient ma wiedzieć, ile pracy mieści się w planie i jak
                    duży plik wgra, a nie przeliczać zdania na sztuki. */}
                  <p className="text-xs text-subtle">
                    Gdy zakres planu się wyczerpie, dostęp przedłużasz w aplikacji dowolną kwotą.
                    Plik do {plan.limity.plik_mb} MB.
                  </p>
                  <div className="mt-auto space-y-2 pt-2">
                    {opisOkresuProbnego(plan) && (
                      <p className="text-xs text-muted">{opisOkresuProbnego(plan)}</p>
                    )}
                    <Przejscie dostepny={dostepny} />
                  </div>
                </Karta>
              </li>
            );
          })}
        </ul>
      )}

      <section aria-labelledby="pytania" className="mt-14">
        <h2 id="pytania" className="font-heading text-2xl font-semibold text-fg">
          Najczęstsze pytania
        </h2>
        <dl className="mt-6 flex flex-col gap-5">
          {PYTANIA.map((pozycja) => (
            <div key={pozycja.pytanie} className="rounded-xl border border-line bg-raised p-5">
              <dt className="font-heading text-base font-semibold text-fg">{pozycja.pytanie}</dt>
              <dd className="mt-2 text-sm text-muted">{pozycja.odpowiedz}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}
