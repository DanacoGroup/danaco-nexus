// Konto klienta: logowanie, rejestracja, potwierdzenie adresu, odzyskiwanie i zmiana hasła,
// profil, wylogowanie, usunięcie konta.
//
// Każdy komunikat mówi, co zrobić dalej. Po zmianie hasła i po usunięciu konta serwer kończy sesję,
// więc widok nie odświeża profilu w tle – zastępuje karty konta potwierdzeniem i przyciskiem
// następnego kroku, żeby nie zostawiać czynnych kontrolek konta, którego już nie ma.

import { useEffect, useState } from "react";
import {
  dataPolska,
  komunikat,
  MIN_HASLO,
  portalApi,
  POTWIERDZENIE_USUNIECIA,
  type ProfilKlienta,
} from "../api";
import { usePozycjonowanie } from "../seo";
import { sciezka } from "../trasy";
import { Karta, Komunikat, NaglowekStrony, OdsylaczPrzycisk, Pole, Przycisk, useNawigacja } from "../ui";

type Widok = "logowanie" | "rejestracja" | "odzyskiwanie";

const TYTULY: Record<Widok, string> = {
  logowanie: "Zaloguj się do portalu",
  rejestracja: "Załóż konto",
  odzyskiwanie: "Odzyskaj hasło",
};

const PODPOWIEDZ_HASLA = `Co najmniej ${MIN_HASLO} znaków.`;

/** Token potwierdzenia adresu z odsyłacza w wiadomości; pusty, gdy adres go nie zawiera.
 *
 * Parametr czytany jest tu, a nie w trasowaniu portalu, bo `trasy.ts` należy do dziedziny
 * nawigacji i przekazuje stronie konta jeden parametr – token odzyskiwania hasła. */
function tokenPotwierdzenia(): string {
  if (typeof window === "undefined") return "";
  return (new URLSearchParams(window.location.search).get("potwierdzenie") ?? "").slice(0, 200);
}

/** Hasło niezgodne z polityką serwera; pusty wynik oznacza hasło poprawne. */
function bladHasla(haslo: string): string {
  if (haslo.length < MIN_HASLO) {
    return `Hasło jest za krótkie – dopisz znaki tak, aby było ich co najmniej ${MIN_HASLO}.`;
  }
  return "";
}

function FormularzGoscia({
  rejestracjaOtwarta,
  pocztaDziala,
  poZalogowaniu,
}: {
  rejestracjaOtwarta: boolean;
  pocztaDziala: boolean;
  poZalogowaniu: () => void;
}) {
  const [widok, setWidok] = useState<Widok>("logowanie");
  const [adres, setAdres] = useState("");
  const [haslo, setHaslo] = useState("");
  const [imie, setImie] = useState("");
  const [firma, setFirma] = useState("");
  const [blad, setBlad] = useState("");
  const [informacja, setInformacja] = useState("");
  const [trwa, setTrwa] = useState(false);

  const przelacz = (nowy: Widok) => {
    setWidok(nowy);
    setBlad("");
    setInformacja("");
  };

  const wyslij = async () => {
    setBlad("");
    setInformacja("");
    if (!adres.trim()) {
      setBlad("Wpisz adres e-mail konta.");
      return;
    }
    if (widok === "rejestracja") {
      const niezgodne = bladHasla(haslo);
      if (niezgodne) {
        setBlad(niezgodne);
        return;
      }
    }
    setTrwa(true);
    try {
      if (widok === "logowanie") {
        await portalApi.konto.logowanie({ email: adres.trim(), password: haslo });
        poZalogowaniu();
      } else if (widok === "rejestracja") {
        await portalApi.konto.rejestracja({
          email: adres.trim(),
          password: haslo,
          name: imie.trim(),
          company: firma.trim(),
        });
        poZalogowaniu();
      } else {
        await portalApi.konto.odzyskiwanie(adres.trim());
        // Bez podłączonej skrzynki wiadomość nie wychodzi — trafia do dziennika aplikacji.
        // Obiecywanie jej użytkownikowi jest nieprawdą, a przy odzyskiwaniu hasła najbardziej
        // dotkliwą: człowiek czeka na coś, co nie przyjdzie, i nie ma jak się dowiedzieć dlaczego.
        setInformacja(
          pocztaDziala
            ? "Jeżeli konto o tym adresie istnieje, wysłaliśmy odsyłacz do ustawienia nowego hasła. " +
                "Sprawdź skrzynkę, także folder ze spamem – odsyłacz działa raz i przez ograniczony czas."
            : "Wysyłka wiadomości nie jest jeszcze podłączona na tym serwerze, więc odsyłacz do Ciebie " +
                "nie dojdzie. Napisz do nas ze strony Kontakt – ustawimy nowe hasło ręcznie.",
        );
      }
    } catch (error) {
      setBlad(komunikat(error, "Operacja się nie powiodła. Spróbuj ponownie za chwilę."));
    } finally {
      setTrwa(false);
    }
  };

  return (
    <Karta className="mx-auto mt-8 max-w-lg">
      <h2 className="font-heading text-xl font-semibold text-fg">{TYTULY[widok]}</h2>
      {widok === "odzyskiwanie" && (
        <p className="mt-2 text-sm text-muted">
          Podaj adres konta. Wyślemy na niego jednorazowy odsyłacz do ustawienia nowego hasła.
        </p>
      )}
      <form
        noValidate
        className="mt-5 flex flex-col gap-4"
        onSubmit={(zdarzenie) => {
          zdarzenie.preventDefault();
          void wyslij();
        }}
      >
        <Pole
          etykieta="Adres e-mail"
          typ="email"
          wartosc={adres}
          naZmiane={setAdres}
          wymagane
          autoUzupelnianie="email"
        />
        {widok !== "odzyskiwanie" && (
          <Pole
            etykieta="Hasło"
            typ="password"
            wartosc={haslo}
            naZmiane={setHaslo}
            wymagane
            autoUzupelnianie={widok === "logowanie" ? "current-password" : "new-password"}
            podpowiedz={widok === "rejestracja" ? PODPOWIEDZ_HASLA : undefined}
          />
        )}
        {widok === "rejestracja" && (
          <>
            <Pole etykieta="Imię i nazwisko" wartosc={imie} naZmiane={setImie} autoUzupelnianie="name" />
            <Pole etykieta="Firma" wartosc={firma} naZmiane={setFirma} autoUzupelnianie="organization" />
          </>
        )}
        {blad && <Komunikat tekst={blad} rodzaj="blad" />}
        {informacja && <Komunikat tekst={informacja} rodzaj="sukces" />}
        <Przycisk type="submit" disabled={trwa}>
          {trwa ? "Chwileczkę…" : TYTULY[widok]}
        </Przycisk>
      </form>
      <div className="mt-5 flex flex-wrap gap-4 text-sm">
        {widok !== "logowanie" && (
          <Przycisk wariant="cichy" onClick={() => przelacz("logowanie")}>
            Mam już konto
          </Przycisk>
        )}
        {widok !== "rejestracja" && rejestracjaOtwarta && (
          <Przycisk wariant="cichy" onClick={() => przelacz("rejestracja")}>
            Załóż konto
          </Przycisk>
        )}
        {widok !== "odzyskiwanie" && (
          <Przycisk wariant="cichy" onClick={() => przelacz("odzyskiwanie")}>
            Nie pamiętam hasła
          </Przycisk>
        )}
      </div>
      {/* Uprzedzenie **przed** wpisaniem adresu, a nie dopiero po wysłaniu formularza:
        kto wie z góry, że wiadomość nie dojdzie, nie traci czasu na czekanie. */}
      {widok === "odzyskiwanie" && !pocztaDziala && (
        <p className="mt-4 rounded-xl border border-line px-3.5 py-2.5 text-sm text-muted">
          Wysyłka wiadomości nie jest jeszcze podłączona na tym serwerze. Odsyłacz do ustawienia
          hasła nie dojdzie — napisz do nas ze strony Kontakt, ustawimy hasło ręcznie.
        </p>
      )}
    </Karta>
  );
}

function UstawienieHasla({ token, poUstawieniu }: { token: string; poUstawieniu: () => void }) {
  const [haslo, setHaslo] = useState("");
  const [blad, setBlad] = useState("");
  const [gotowe, setGotowe] = useState(false);
  const [trwa, setTrwa] = useState(false);

  const zapisz = async () => {
    setBlad("");
    const niezgodne = bladHasla(haslo);
    if (niezgodne) {
      setBlad(niezgodne);
      return;
    }
    setTrwa(true);
    try {
      await portalApi.konto.ustawHaslo(token, haslo);
      setGotowe(true);
    } catch (error) {
      setBlad(komunikat(error, "Nie udało się ustawić hasła. Poproś o nowy odsyłacz."));
    } finally {
      setTrwa(false);
    }
  };

  return (
    <Karta className="mx-auto mt-8 max-w-lg">
      <h2 className="font-heading text-xl font-semibold text-fg">Ustaw nowe hasło</h2>
      {gotowe ? (
        <div className="mt-5 flex flex-col gap-4">
          <Komunikat
            tekst="Hasło zostało zmienione, a wszystkie sesje konta zakończone. Zaloguj się nowym hasłem."
            rodzaj="sukces"
          />
          <div>
            <Przycisk onClick={poUstawieniu}>Przejdź do logowania</Przycisk>
          </div>
        </div>
      ) : (
        <form
          noValidate
          className="mt-5 flex flex-col gap-4"
          onSubmit={(zdarzenie) => {
            zdarzenie.preventDefault();
            void zapisz();
          }}
        >
          <Pole
            etykieta="Nowe hasło"
            typ="password"
            wartosc={haslo}
            naZmiane={setHaslo}
            wymagane
            autoUzupelnianie="new-password"
            podpowiedz={PODPOWIEDZ_HASLA}
          />
          {blad && <Komunikat tekst={blad} rodzaj="blad" />}
          <Przycisk type="submit" disabled={trwa}>
            {trwa ? "Zapisywanie…" : "Zapisz hasło"}
          </Przycisk>
        </form>
      )}
    </Karta>
  );
}

function PotwierdzenieAdresu({ token, dalej }: { token: string; dalej: () => void }) {
  const [gotowe, setGotowe] = useState(false);
  const [blad, setBlad] = useState("");

  // Klient przyszedł z odsyłacza i niczego nie wypełnia – potwierdzenie idzie na serwer od razu.
  useEffect(() => {
    let czynne = true;
    portalApi.konto
      .potwierdzAdres(token)
      .then(() => {
        if (czynne) setGotowe(true);
      })
      .catch((error: unknown) => {
        if (czynne) setBlad(komunikat(error, "Nie udało się potwierdzić adresu. Poproś o nowy odsyłacz."));
      });
    return () => {
      czynne = false;
    };
  }, [token]);

  return (
    <Karta className="mx-auto mt-8 max-w-lg">
      <h2 className="font-heading text-xl font-semibold text-fg">Potwierdzenie adresu e-mail</h2>
      <div className="mt-5 flex flex-col gap-4">
        {blad && <Komunikat tekst={blad} rodzaj="blad" />}
        {gotowe && <Komunikat tekst="Adres e-mail został potwierdzony. Dziękujemy." rodzaj="sukces" />}
        {!blad && !gotowe && <Komunikat tekst="Sprawdzamy odsyłacz…" />}
        {(blad || gotowe) && (
          <div>
            <Przycisk onClick={dalej}>Przejdź do konta</Przycisk>
          </div>
        )}
      </div>
    </Karta>
  );
}

function PasekPotwierdzenia({ adres, pocztaDziala }: { adres: string; pocztaDziala: boolean }) {
  const [wynik, setWynik] = useState("");
  const [blad, setBlad] = useState("");
  const [trwa, setTrwa] = useState(false);

  const wyslij = async () => {
    setBlad("");
    setWynik("");
    setTrwa(true);
    try {
      await portalApi.konto.wyslijPotwierdzenie();
      setWynik(
        pocztaDziala
          ? "Wysłaliśmy odsyłacz. Sprawdź skrzynkę, także folder ze spamem."
          : "Wysyłka wiadomości nie jest jeszcze podłączona na tym serwerze, więc odsyłacz nie dojdzie. " +
              "Potwierdzenie adresu niczego nie blokuje — konto działa normalnie.",
      );
    } catch (error) {
      setBlad(komunikat(error, "Nie udało się wysłać odsyłacza. Spróbuj ponownie za chwilę."));
    } finally {
      setTrwa(false);
    }
  };

  return (
    <Karta className="mt-8">
      <h2 className="font-heading text-lg font-semibold text-fg">Adres e-mail bez potwierdzenia</h2>
      <p className="mt-2 text-sm text-muted">
        Konto działa normalnie, ale adresu {adres} jeszcze nie potwierdzono. Potwierdzenie daje nam
        pewność, że wiadomości o koncie – w tym odsyłacz do zmiany hasła – docierają do Ciebie.
      </p>
      {blad && <div className="mt-4"><Komunikat tekst={blad} rodzaj="blad" /></div>}
      {wynik && <div className="mt-4"><Komunikat tekst={wynik} rodzaj="sukces" /></div>}
      <div className="mt-5">
        <Przycisk wariant="drugorzedny" disabled={trwa} onClick={() => void wyslij()}>
          {trwa ? "Wysyłanie…" : "Wyślij odsyłacz ponownie"}
        </Przycisk>
      </div>
    </Karta>
  );
}

function DaneKonta({ konto, odswiez }: { konto: ProfilKlienta; odswiez: () => void }) {
  const [imie, setImie] = useState(konto.name);
  const [firma, setFirma] = useState(konto.company);
  const [wynik, setWynik] = useState("");
  const [blad, setBlad] = useState("");
  const [trwa, setTrwa] = useState(false);

  const zapisz = async () => {
    setBlad("");
    setWynik("");
    setTrwa(true);
    try {
      await portalApi.konto.profil({ name: imie.trim(), company: firma.trim() });
      setWynik("Profil zapisany.");
      odswiez();
    } catch (error) {
      setBlad(komunikat(error, "Nie udało się zapisać profilu. Spróbuj ponownie za chwilę."));
    } finally {
      setTrwa(false);
    }
  };

  return (
    <Karta>
      <h2 className="font-heading text-lg font-semibold text-fg">Dane konta</h2>
      <p className="mt-2 text-sm text-muted">{konto.email}</p>
      <p className="mt-1 text-sm text-subtle">
        Konto założone {dataPolska(konto.created_at)}
        {konto.last_login_at ? `, ostatnie logowanie ${dataPolska(konto.last_login_at)}` : ""}.
      </p>
      <form
        noValidate
        className="mt-5 flex flex-col gap-4"
        onSubmit={(zdarzenie) => {
          zdarzenie.preventDefault();
          void zapisz();
        }}
      >
        <Pole etykieta="Imię i nazwisko" wartosc={imie} naZmiane={setImie} autoUzupelnianie="name" />
        <Pole etykieta="Firma" wartosc={firma} naZmiane={setFirma} autoUzupelnianie="organization" />
        {blad && <Komunikat tekst={blad} rodzaj="blad" />}
        {wynik && <Komunikat tekst={wynik} rodzaj="sukces" />}
        <Przycisk type="submit" disabled={trwa}>
          {trwa ? "Zapisywanie…" : "Zapisz profil"}
        </Przycisk>
      </form>
    </Karta>
  );
}

function ZmianaHasla({ poZmianie }: { poZmianie: () => void }) {
  const [obecne, setObecne] = useState("");
  const [nowe, setNowe] = useState("");
  const [blad, setBlad] = useState("");
  const [trwa, setTrwa] = useState(false);

  const zmien = async () => {
    setBlad("");
    const niezgodne = bladHasla(nowe);
    if (niezgodne) {
      setBlad(niezgodne);
      return;
    }
    if (nowe === obecne) {
      setBlad("Nowe hasło musi się różnić od obecnego.");
      return;
    }
    setTrwa(true);
    try {
      await portalApi.konto.haslo({ current_password: obecne, new_password: nowe });
      setObecne("");
      setNowe("");
      poZmianie();
    } catch (error) {
      setBlad(komunikat(error, "Nie udało się zmienić hasła. Spróbuj ponownie za chwilę."));
    } finally {
      setTrwa(false);
    }
  };

  return (
    <Karta>
      <h2 className="font-heading text-lg font-semibold text-fg">Zmiana hasła</h2>
      <form
        noValidate
        className="mt-5 flex flex-col gap-4"
        onSubmit={(zdarzenie) => {
          zdarzenie.preventDefault();
          void zmien();
        }}
      >
        <Pole
          etykieta="Obecne hasło"
          typ="password"
          wartosc={obecne}
          naZmiane={setObecne}
          wymagane
          autoUzupelnianie="current-password"
        />
        <Pole
          etykieta="Nowe hasło"
          typ="password"
          wartosc={nowe}
          naZmiane={setNowe}
          wymagane
          autoUzupelnianie="new-password"
          podpowiedz={`${PODPOWIEDZ_HASLA} Zmiana kończy wszystkie sesje konta.`}
        />
        {blad && <Komunikat tekst={blad} rodzaj="blad" />}
        <Przycisk type="submit" disabled={trwa}>
          {trwa ? "Zapisywanie…" : "Zmień hasło"}
        </Przycisk>
      </form>
    </Karta>
  );
}

function UsuniecieKonta({ poUsunieciu }: { poUsunieciu: () => void }) {
  const [otwarte, setOtwarte] = useState(false);
  const [haslo, setHaslo] = useState("");
  const [potwierdzenie, setPotwierdzenie] = useState("");
  const [blad, setBlad] = useState("");
  const [trwa, setTrwa] = useState(false);

  const usun = async () => {
    setBlad("");
    if (potwierdzenie.trim().toUpperCase() !== POTWIERDZENIE_USUNIECIA) {
      setBlad(`Aby usunąć konto, wpisz w polu potwierdzenia słowo ${POTWIERDZENIE_USUNIECIA}.`);
      return;
    }
    setTrwa(true);
    try {
      await portalApi.konto.usun({ password: haslo, confirmation: potwierdzenie.trim() });
      setHaslo("");
      setPotwierdzenie("");
      poUsunieciu();
    } catch (error) {
      setBlad(komunikat(error, "Nie udało się usunąć konta. Spróbuj ponownie za chwilę."));
    } finally {
      setTrwa(false);
    }
  };

  return (
    <Karta>
      <h2 className="font-heading text-lg font-semibold text-fg">Usunięcie konta</h2>
      <p className="mt-2 text-sm text-muted">
        Usunięcie kasuje dane profilu, sesje i odsyłacze do zmiany hasła. Operacji nie da się cofnąć.
      </p>
      {otwarte ? (
        <form
          noValidate
          className="mt-5 flex flex-col gap-4"
          onSubmit={(zdarzenie) => {
            zdarzenie.preventDefault();
            void usun();
          }}
        >
          <Pole
            etykieta="Hasło"
            typ="password"
            wartosc={haslo}
            naZmiane={setHaslo}
            wymagane
            autoUzupelnianie="current-password"
          />
          <Pole
            etykieta="Potwierdzenie"
            wartosc={potwierdzenie}
            naZmiane={setPotwierdzenie}
            wymagane
            podpowiedz={`Wpisz słowo ${POTWIERDZENIE_USUNIECIA}, aby potwierdzić.`}
          />
          {blad && <Komunikat tekst={blad} rodzaj="blad" />}
          <div className="flex flex-wrap gap-3">
            <Przycisk type="submit" wariant="drugorzedny" disabled={trwa}>
              {trwa ? "Usuwanie…" : "Usuń konto na zawsze"}
            </Przycisk>
            <Przycisk wariant="cichy" onClick={() => setOtwarte(false)}>
              Rezygnuję
            </Przycisk>
          </div>
        </form>
      ) : (
        <div className="mt-5">
          <Przycisk wariant="drugorzedny" onClick={() => setOtwarte(true)}>
            Chcę usunąć konto
          </Przycisk>
        </div>
      )}
    </Karta>
  );
}

// Zmiana hasła i usunięcie konta kończą sesję po stronie serwera. Widok zastępuje wtedy całe konto
// jednym potwierdzeniem – gdyby karty profilu zostały, klient klikałby w kontrolki, które już nie działają.
type Zakonczenie = "haslo" | "usuniecie";

const ZAKONCZENIA: Record<Zakonczenie, { tytul: string; tekst: string; dzialanie: string }> = {
  haslo: {
    tytul: "Hasło zmienione",
    tekst:
      "Ze względu na bezpieczeństwo zakończyliśmy wszystkie sesje tego konta – także tę w przeglądarce. " +
      "Zaloguj się nowym hasłem.",
    dzialanie: "Zaloguj się ponownie",
  },
  usuniecie: {
    tytul: "Konto usunięte",
    tekst:
      "Konto zostało usunięte razem z danymi profilu i sesjami. Operacji nie da się cofnąć – aby wrócić, " +
      "załóż konto od nowa.",
    dzialanie: "Wróć na stronę konta",
  },
};

function PoZakonczeniuSesji({ rodzaj, dalej }: { rodzaj: Zakonczenie; dalej: () => void }) {
  const { tytul, tekst, dzialanie } = ZAKONCZENIA[rodzaj];
  return (
    <Karta className="mx-auto mt-8 max-w-lg">
      <h2 className="font-heading text-xl font-semibold text-fg">{tytul}</h2>
      <div className="mt-5 flex flex-col gap-4">
        <Komunikat tekst={tekst} rodzaj="sukces" />
        <div>
          <Przycisk onClick={dalej}>{dzialanie}</Przycisk>
        </div>
      </div>
    </Karta>
  );
}

function Profil({
  konto,
  odswiez,
  pocztaDziala,
  token,
  poZakonczeniu,
}: {
  konto: ProfilKlienta;
  odswiez: () => void;
  pocztaDziala: boolean;
  token: string;
  poZakonczeniu: () => void;
}) {
  const [blad, setBlad] = useState("");
  const [trwa, setTrwa] = useState(false);
  const [zakonczenie, setZakonczenie] = useState<Zakonczenie | null>(null);

  const wyloguj = async () => {
    setBlad("");
    setTrwa(true);
    try {
      await portalApi.konto.wylogowanie();
    } catch (error) {
      setBlad(komunikat(error, "Nie udało się wylogować. Spróbuj ponownie za chwilę."));
    } finally {
      setTrwa(false);
      odswiez();
    }
  };

  if (zakonczenie) return <PoZakonczeniuSesji rodzaj={zakonczenie} dalej={poZakonczeniu} />;

  return (
    <>
      {!konto.email_confirmed && <PasekPotwierdzenia adres={konto.email} pocztaDziala={pocztaDziala} />}
      {token && (
        <Karta className="mt-8">
          <Komunikat
            tekst={
              "Odsyłacz z wiadomości otwarto w zalogowanej przeglądarce. Hasło zmienisz niżej w karcie " +
              "„Zmiana hasła”; odsyłacz pozostaje ważny do czasu użycia albo wygaśnięcia."
            }
          />
        </Karta>
      )}
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <DaneKonta konto={konto} odswiez={odswiez} />
        <ZmianaHasla poZmianie={() => setZakonczenie("haslo")} />
        <Karta>
          <h2 className="font-heading text-lg font-semibold text-fg">Dostęp</h2>
          <p className="mt-2 text-sm text-muted">
            Plan {konto.plan}. Wylogowanie kończy tę sesję; pozostałe urządzenia zostają zalogowane
            do czasu zmiany hasła.
          </p>
          {blad && <div className="mt-4"><Komunikat tekst={blad} rodzaj="blad" /></div>}
          <div className="mt-5 flex flex-wrap gap-3">
            <OdsylaczPrzycisk adres={sciezka("panel")} wariant="drugorzedny">
              Przejdź do panelu klienta
            </OdsylaczPrzycisk>
            <Przycisk wariant="cichy" disabled={trwa} onClick={() => void wyloguj()}>
              {trwa ? "Wylogowywanie…" : "Wyloguj się"}
            </Przycisk>
          </div>
        </Karta>
        <UsuniecieKonta poUsunieciu={() => setZakonczenie("usuniecie")} />
      </div>
    </>
  );
}

export function Konto({
  konto,
  odswiez,
  rejestracjaOtwarta,
  pocztaDziala,
  token,
}: {
  konto: ProfilKlienta | null;
  odswiez: () => void;
  rejestracjaOtwarta: boolean;
  /** Czy wiadomości portalu naprawdę wychodzą. Fałsz zmienia treść ekranów, które je obiecują. */
  pocztaDziala: boolean;
  token: string;
}) {
  const nawiguj = useNawigacja();
  const potwierdzenie = tokenPotwierdzenia();
  // Po zmianie hasła, po usunięciu konta i po potwierdzeniu adresu token z adresu jest już zużyty.
  // Przejście na adres konta bez parametru zdejmuje go – inaczej odświeżenie profilu otwierałoby
  // formularz „Ustaw nowe hasło” albo ponawiało potwierdzenie tokenem, którego serwer już skasował.
  const zakonczSesje = () => {
    nawiguj(sciezka("konto"));
    odswiez();
  };
  usePozycjonowanie({
    tytul: "Konto",
    opis: "Logowanie i zarządzanie kontem klienta portalu Danaco Nexus.",
    sciezka: sciezka("konto"),
    noindex: true,
  });

  return (
    <>
      <NaglowekStrony
        tytul="Konto"
        opis={konto ? "Dane konta klienta i ustawienia dostępu." : "Zaloguj się albo załóż konto klienta."}
      />
      {potwierdzenie && <PotwierdzenieAdresu token={potwierdzenie} dalej={zakonczSesje} />}
      {!potwierdzenie && token && !konto && (
        <UstawienieHasla token={token} poUstawieniu={() => nawiguj(sciezka("konto"))} />
      )}
      {!potwierdzenie && !token && !konto && (
        <FormularzGoscia
          rejestracjaOtwarta={rejestracjaOtwarta}
          pocztaDziala={pocztaDziala}
          poZalogowaniu={odswiez}
        />
      )}
      {!potwierdzenie && konto && (
        <Profil
          konto={konto}
          odswiez={odswiez}
          pocztaDziala={pocztaDziala}
          token={token}
          poZakonczeniu={zakonczSesje}
        />
      )}
    </>
  );
}
