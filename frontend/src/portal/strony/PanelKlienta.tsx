// Panel klienta: stan subskrypcji, skróty do aplikacji i materiałów, wylogowanie z portalu.

import { dataPolska, portalApi, type ProfilKlienta } from "../api";
import { usePozycjonowanie } from "../seo";
import { PLANY } from "../tresc";
import { sciezka } from "../trasy";
import { Karta, Komunikat, NaglowekStrony, OdsylaczPrzycisk, Przycisk } from "../ui";

const SKROTY = [
  { nazwa: "Dokumentacja", adres: sciezka("dokumentacja"), opis: "Pierwsze uruchomienie, poczta, kalendarz i chmura krok po kroku." },
  { nazwa: "Centrum wiedzy", adres: sciezka("wiedza"), opis: "Gotowe sposoby na powtarzalne zadania i odpowiedzi na częste pytania." },
  { nazwa: "Blog", adres: sciezka("blog"), opis: "Co doszło w ostatnich wydaniach i jak inni pracują z Nexusem." },
  { nazwa: "Kontakt", adres: sciezka("kontakt"), opis: "Pytanie o plan, dostęp albo sprawę, której Nexus nie ogarnia." },
];

export function PanelKlienta({ konto, odswiez }: { konto: ProfilKlienta | null; odswiez: () => void }) {
  usePozycjonowanie({
    tytul: "Panel klienta",
    opis: "Stan konta i subskrypcji w portalu Danaco Nexus.",
    sciezka: sciezka("panel"),
    noindex: true,
  });

  if (!konto) {
    return (
      <>
        <NaglowekStrony tytul="Panel klienta" opis="Stan konta zobaczysz po zalogowaniu." />
        <div className="mt-6">
          <Komunikat tekst="Zaloguj się, aby zobaczyć plan, datę założenia konta i skróty do materiałów." />
          <div className="mt-5">
            <OdsylaczPrzycisk adres={sciezka("konto")}>Przejdź do logowania</OdsylaczPrzycisk>
          </div>
        </div>
      </>
    );
  }

  const plan = PLANY.find((pozycja) => pozycja.nazwa.toLowerCase() === konto.plan.toLowerCase()) ?? PLANY[0];
  return (
    <>
      <NaglowekStrony tytul="Panel klienta" opis={`Konto ${konto.email}`} />
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Karta>
          <h2 className="font-heading text-lg font-semibold text-fg">Subskrypcja</h2>
          <p className="mt-3 text-sm text-muted">
            Plan <span className="text-fg">{plan.nazwa}</span> — {plan.opis}
          </p>
          <ul className="mt-4 flex flex-col gap-1.5 text-sm text-muted">
            {plan.zakres.map((element) => (
              <li key={element} className="flex gap-2">
                <span aria-hidden="true" className="text-accent">
                  •
                </span>
                {element}
              </li>
            ))}
          </ul>
          <div className="mt-5 flex flex-wrap gap-3">
            <OdsylaczPrzycisk adres={sciezka("cennik")} wariant="drugorzedny">
              Porównaj plany
            </OdsylaczPrzycisk>
            <OdsylaczPrzycisk adres={sciezka("kontakt")} wariant="drugorzedny">
              Zmień plan
            </OdsylaczPrzycisk>
          </div>
        </Karta>
        <Karta>
          <h2 className="font-heading text-lg font-semibold text-fg">Konto</h2>
          <dl className="mt-3 flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-subtle">Nazwa</dt>
              <dd className="text-fg">{konto.name || "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-subtle">Firma</dt>
              <dd className="text-fg">{konto.company || "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-subtle">Konto założone</dt>
              <dd className="text-fg">{dataPolska(konto.created_at)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-subtle">Ostatnie logowanie</dt>
              <dd className="text-fg">{dataPolska(konto.last_login_at) || "—"}</dd>
            </div>
          </dl>
          <div className="mt-5 flex flex-wrap gap-3">
            <OdsylaczPrzycisk adres={sciezka("konto")} wariant="drugorzedny">
              Ustawienia konta
            </OdsylaczPrzycisk>
            <Przycisk
              wariant="drugorzedny"
              onClick={() => {
                void portalApi.konto.wylogowanie().finally(odswiez);
              }}
            >
              Wyloguj z portalu
            </Przycisk>
          </div>
        </Karta>
      </div>

      <section aria-labelledby="skroty" className="mt-12">
        <h2 id="skroty" className="font-heading text-xl font-semibold text-fg">
          Skróty
        </h2>
        <ul className="mt-5 grid gap-4 sm:grid-cols-2">
          {SKROTY.map((skrot) => (
            <li key={skrot.adres} className="rounded-xl border border-line bg-raised p-4">
              <h3 className="font-heading text-base font-semibold text-fg">{skrot.nazwa}</h3>
              <p className="mt-1.5 text-sm text-muted">{skrot.opis}</p>
              <div className="mt-3">
                <OdsylaczPrzycisk adres={skrot.adres} wariant="cichy">
                  Otwórz
                </OdsylaczPrzycisk>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
