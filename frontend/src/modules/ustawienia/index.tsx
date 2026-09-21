// Ustawienia: jedno miejsce, w którym użytkownik dostosowuje Nexusa do siebie.
//
// Poprzednia wersja miała trzy kafelki motywu, natywną listę głosów i cztery odsyłacze —
// i na tym kończyły się „ustawienia konta”. Tutaj są rzeczy, które naprawdę należą do
// konta i działają: profil i hasło, sposób pracy (czym wysyła się wiadomość, od czego
// zaczyna się dzień, ograniczony ruch), głos, powiadomienia tej przeglądarki, zalogowane
// urządzenia i eksport danych. Każde ustawienie jest podpięte pod działające API —
// przełącznik, który niczego nie zmienia, jest gorszy niż jego brak.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, apiRequest, speakText, type VoiceConfig } from "../../api";
import { oznaczNowosciPrzeczytane } from "../../nowosci";
import { disablePush, enablePush, pushStatus, type PushStatus } from "../../shell/push";
import { SettingsIcon } from "../../shell/icons";
import { applyTheme, saveTheme, type ThemeChoice } from "../../theme";
import { MODULES } from "../registry";
import type { ModulePageProps, NexusModule } from "../registry";
import { preferencje, wczytajPreferencje, zapiszPreferencje, type Preferencje } from "../../preferencje";
import { Button, Input, Select, Switch } from "../../ui";

/** Klucz głosu — ten sam, którego używa okno rozmowy głosowej. */
const KLUCZ_GLOSU = "nexus-voice";

interface Profil {
  nazwa: string;
  email: string;
  firma: string;
  plan: string;
  gosc: boolean;
  adres_potwierdzony: boolean;
  wlasne_konto: boolean;
}

interface Sesja {
  biezaca: boolean;
  utworzona: string;
  ostatnio: string;
  wygasa: string;
  adres_ip: string;
  przegladarka: string;
}

const MOTYWY: Array<{ wartosc: ThemeChoice; nazwa: string; opis: string }> = [
  { wartosc: "system", nazwa: "Jak w systemie", opis: "Nexus idzie za ustawieniem urządzenia." },
  { wartosc: "dark", nazwa: "Ciemny", opis: "Domyślny wygląd Nexusa." },
  { wartosc: "light", nazwa: "Jasny", opis: "Do pracy przy mocnym świetle." },
];

const NAZWY_PLANOW: Record<string, string> = {
  probny: "Konto próbne",
  osobisty: "Osobisty",
  pro: "Pro",
  zespol: "Grupa",
  administrator: "Administrator instalacji",
};

function czas(iso: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pl-PL", { dateStyle: "medium", timeStyle: "short" });
}

function Sekcja({
  tytul,
  opis,
  children,
}: {
  tytul: string;
  opis: string;
  children: React.ReactNode;
}) {
  return (
    // `min-w-0`: bez tego kafel jako element siatki bierze szerokość najdłuższej treści
    // (adres e-mail konta próbnego to jeden nierozdzielny wyraz) i na telefonie wychodzi
    // poza ekran — pomiar pokazał kafel 506 px w kolumnie szerokiej na 358 px.
    <section className="min-w-0 rounded-2xl border border-line bg-raised p-5">
      <h2 className="font-heading text-base font-semibold text-fg">{tytul}</h2>
      <p className="mt-1 text-sm text-muted">{opis}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** Wiersz ustawienia: nazwa i wyjaśnienie po lewej, sterowanie po prawej.
 */
function Wiersz({
  tytul,
  opis,
  children,
}: {
  tytul: string;
  opis: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line/60 py-3 first:pt-0 last:border-b-0 last:pb-0">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">{tytul}</p>
        <p className="mt-0.5 text-xs text-muted">{opis}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Konto({ profil, onZmiana }: { profil: Profil | null; onZmiana: (dane: Profil) => void }) {
  const [nazwa, setNazwa] = useState("");
  const [firma, setFirma] = useState("");
  const [stan, setStan] = useState("");
  const [haslo, setHaslo] = useState({ obecne: "", nowe: "", powtorz: "" });
  const [stanHasla, setStanHasla] = useState("");
  const [zmieniaHaslo, setZmieniaHaslo] = useState(false);

  useEffect(() => {
    setNazwa(profil?.nazwa ?? "");
    setFirma(profil?.firma ?? "");
  }, [profil?.nazwa, profil?.firma]);

  if (!profil) {
    return (
      <Sekcja tytul="Konto" opis="Kto jest zalogowany.">
        <p className="text-sm text-muted">Wczytywanie…</p>
      </Sekcja>
    );
  }

  const zapisz = async () => {
    setStan("Zapisuję…");
    try {
      const dane = await apiRequest<Profil>("PATCH", "/api/konto", { name: nazwa, company: firma });
      onZmiana(dane);
      setStan("Zapisane.");
    } catch (powod) {
      setStan(powod instanceof Error ? powod.message : "Nie udało się zapisać.");
    }
  };

  const zmienHaslo = async () => {
    if (haslo.nowe !== haslo.powtorz) {
      setStanHasla("Nowe hasło i jego powtórzenie muszą być takie same.");
      return;
    }
    setStanHasla("Zmieniam…");
    try {
      await apiRequest("POST", "/api/konto/haslo", {
        current_password: haslo.obecne,
        new_password: haslo.nowe,
      });
      setHaslo({ obecne: "", nowe: "", powtorz: "" });
      setZmieniaHaslo(false);
      setStanHasla("Hasło zmienione. Pozostałe zalogowane przeglądarki zostały wylogowane.");
    } catch (powod) {
      setStanHasla(powod instanceof Error ? powod.message : "Nie udało się zmienić hasła.");
    }
  };

  return (
    <Sekcja tytul="Konto" opis="Dane, którymi podpisuje się Twoja praca.">
      <div className="grid gap-3 sm:grid-cols-2">
        <Input
          label="Nazwa"
          value={nazwa}
          onChange={setNazwa}
          disabled={!profil.wlasne_konto}
          description="Tak Nexus zwraca się do Ciebie."
        />
        <Input
          label="Firma"
          value={firma}
          onChange={setFirma}
          disabled={!profil.wlasne_konto}
          description="Trafia na faktury i do pism, które piszesz w Nexusie."
        />
      </div>
      <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        {/* `min-w-0` na wierszu, nie tylko na wartości: bez tego wiersz siatki bierze
          szerokość adresu e-mail (jeden nierozdzielny wyraz), a `truncate` w środku nie
          ma czego skracać. */}
        <div className="flex min-w-0 items-center gap-2">
          <dt className="shrink-0 whitespace-nowrap text-muted">Adres e-mail:</dt>
          <dd className="min-w-0 truncate text-fg" title={profil.email}>
            {profil.email || "—"}
          </dd>
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <dt className="shrink-0 whitespace-nowrap text-muted">Plan:</dt>
          <dd className="min-w-0 truncate text-fg">{NAZWY_PLANOW[profil.plan] ?? profil.plan}</dd>
        </div>
      </dl>
      {profil.email && !profil.adres_potwierdzony && !profil.gosc && (
        <p className="mt-3 rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
          Adres e-mail nie jest jeszcze potwierdzony. Odzyskanie hasła zadziała dopiero po potwierdzeniu.
        </p>
      )}
      {profil.gosc && (
        <p className="mt-3 rounded-lg bg-hover px-3 py-2 text-sm text-muted">
          Pracujesz na koncie próbnym — rozmowy i pliki znikną razem z nim. Załóż własne konto, żeby
          zachować pracę.
        </p>
      )}
      {profil.wlasne_konto && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => void zapisz()}>Zapisz profil</Button>
          {!profil.gosc && (
            <Button variant="secondary" onClick={() => setZmieniaHaslo((stan) => !stan)}>
              {zmieniaHaslo ? "Anuluj zmianę hasła" : "Zmień hasło"}
            </Button>
          )}
          {stan && <span className="text-sm text-muted">{stan}</span>}
        </div>
      )}
      {zmieniaHaslo && (
        <div className="mt-4 grid gap-3 rounded-xl border border-line-control p-4 sm:grid-cols-3">
          <Input
            label="Obecne hasło"
            type="password"
            autoComplete="current-password"
            value={haslo.obecne}
            onChange={(wartosc) => setHaslo((dane) => ({ ...dane, obecne: wartosc }))}
          />
          <Input
            label="Nowe hasło"
            type="password"
            autoComplete="new-password"
            value={haslo.nowe}
            onChange={(wartosc) => setHaslo((dane) => ({ ...dane, nowe: wartosc }))}
          />
          <Input
            label="Powtórz nowe"
            type="password"
            autoComplete="new-password"
            value={haslo.powtorz}
            onChange={(wartosc) => setHaslo((dane) => ({ ...dane, powtorz: wartosc }))}
          />
          <div className="sm:col-span-3 flex flex-wrap items-center gap-3">
            <Button onClick={() => void zmienHaslo()}>Zmień hasło</Button>
            {stanHasla && <span className="text-sm text-muted">{stanHasla}</span>}
          </div>
        </div>
      )}
    </Sekcja>
  );
}

function Wyglad({ dane, ustaw }: { dane: Preferencje; ustaw: (zmiany: Partial<Preferencje>) => void }) {
  return (
    <Sekcja tytul="Wygląd i ruch" opis="Motyw okna i to, ile się w nim dzieje.">
      <div role="radiogroup" aria-label="Motyw" className="grid gap-2 sm:grid-cols-3">
        {MOTYWY.map((pozycja) => (
          <button
            key={pozycja.wartosc}
            type="button"
            role="radio"
            aria-checked={dane.motyw === pozycja.wartosc}
            onClick={() => {
              ustaw({ motyw: pozycja.wartosc });
              saveTheme(pozycja.wartosc);
              applyTheme(pozycja.wartosc);
            }}
            className={`ui-nacisk rounded-xl border px-4 py-3 text-left transition-colors ${
              dane.motyw === pozycja.wartosc
                ? "border-accent bg-accent-soft text-accent"
                : "border-line-control hover:bg-hover"
            }`}
          >
            <span className="block text-sm font-medium">{pozycja.nazwa}</span>
            <span className="mt-0.5 block text-xs text-muted">{pozycja.opis}</span>
          </button>
        ))}
      </div>
      <div className="mt-4 border-t border-line/60 pt-4">
        <Switch
          label="Ograniczony ruch"
          description="Wyłącza animacje i nagrania w interfejsie. Niezależnie od tego Nexus szanuje ustawienie systemu."
          checked={dane.ograniczony_ruch}
          onChange={(wlaczone) => ustaw({ ograniczony_ruch: wlaczone })}
        />
      </div>
    </Sekcja>
  );
}

function Praca({
  dane,
  ustaw,
}: {
  dane: Preferencje;
  ustaw: (zmiany: Partial<Preferencje>) => void;
}) {
  const moduly = useMemo(
    () => [
      { value: "chat", label: "Czat" },
      ...MODULES.map((modul) => ({ value: modul.id, label: modul.label })),
    ],
    [],
  );
  return (
    <Sekcja tytul="Praca" opis="Jak zaczyna się dzień i czym wysyłasz wiadomość.">
      <Wiersz tytul="Wysyłanie wiadomości" opis="Na telefonie Enter zawsze dodaje nową linię — wysyła przycisk.">
        <Select
          label="Wysyłanie wiadomości"
          hideLabel
          size="sm"
          className="w-56"
          value={dane.wysylka}
          onChange={(wybor) => ustaw({ wysylka: wybor as Preferencje["wysylka"] })}
          options={[
            { value: "enter", label: "Enter wysyła", description: "Shift + Enter robi nową linię." },
            { value: "ctrl-enter", label: "Ctrl + Enter wysyła", description: "Enter robi nową linię." },
          ]}
        />
      </Wiersz>
      <Wiersz tytul="Moduł na start" opis="To okno otwiera się zaraz po zalogowaniu.">
        <Select
          label="Moduł na start"
          hideLabel
          size="sm"
          className="w-56"
          value={dane.modul_startowy}
          onChange={(wybor) => ustaw({ modul_startowy: wybor })}
          options={moduly}
        />
      </Wiersz>
    </Sekcja>
  );
}

function Glos({ dane, ustaw }: { dane: Preferencje; ustaw: (zmiany: Partial<Preferencje>) => void }) {
  const [konfiguracja, setKonfiguracja] = useState<VoiceConfig | null>(null);
  const [odtwarza, setOdtwarza] = useState(false);
  const dzwiek = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    api.voiceConfig().then(setKonfiguracja).catch(() => setKonfiguracja(null));
  }, []);

  const wybrany = dane.glos || konfiguracja?.voices[0]?.id || "";

  const posluchaj = async () => {
    if (!wybrany) return;
    setOdtwarza(true);
    try {
      const mowa = await speakText("Tu Danaco Nexus. Tak brzmi wybrany głos.", wybrany);
      dzwiek.current?.pause();
      const element = new Audio(URL.createObjectURL(mowa));
      dzwiek.current = element;
      element.onended = () => setOdtwarza(false);
      await element.play();
    } catch {
      setOdtwarza(false);
    }
  };

  if (!konfiguracja?.available) {
    return (
      <Sekcja tytul="Rozmowa głosowa" opis="Mówisz do Nexusa, a on odpowiada na głos.">
        <p className="text-sm text-muted">Rozmowa głosowa nie jest w tej chwili dostępna.</p>
      </Sekcja>
    );
  }

  return (
    <Sekcja tytul="Rozmowa głosowa" opis="Głos, którym Nexus czyta odpowiedzi.">
      <Wiersz tytul="Głos" opis="Ten sam głos słyszysz w oknie rozmowy głosowej.">
        <div className="flex items-center gap-2">
          <Select
            label="Głos"
            hideLabel
            size="sm"
            className="w-56"
            value={wybrany}
            onChange={(wybor) => {
              ustaw({ glos: wybor });
              try {
                localStorage.setItem(KLUCZ_GLOSU, wybor);
              } catch {
                // Zablokowane dane witryny — wybór zostaje na koncie.
              }
            }}
            options={konfiguracja.voices.map((pozycja) => ({ value: pozycja.id, label: pozycja.name }))}
          />
          <Button variant="secondary" size="sm" onClick={() => void posluchaj()} disabled={odtwarza}>
            {odtwarza ? "Gra…" : "Posłuchaj"}
          </Button>
        </div>
      </Wiersz>
    </Sekcja>
  );
}

function Powiadomienia() {
  const [stan, setStan] = useState<PushStatus | null>(null);
  const [pracuje, setPracuje] = useState(false);

  useEffect(() => {
    pushStatus().then(setStan).catch(() => setStan("unsupported"));
  }, []);

  const przelacz = async (wlaczone: boolean) => {
    setPracuje(true);
    try {
      setStan(wlaczone ? await enablePush() : await disablePush());
    } finally {
      setPracuje(false);
    }
  };

  const opis: Record<PushStatus, string> = {
    unsupported: "Ta przeglądarka nie obsługuje powiadomień.",
    "server-off": "Powiadomienia nie są włączone na tym serwerze.",
    denied: "Powiadomienia są zablokowane w ustawieniach przeglądarki — odblokuj je tam.",
    off: "Wyłączone na tym urządzeniu.",
    on: "Włączone na tym urządzeniu.",
  };

  return (
    <Sekcja
      tytul="Powiadomienia"
      opis="Nexus daje znać, gdy skończy zadanie, które trwało dłużej niż chwila."
    >
      <Switch
        label="Powiadomienia w tej przeglądarce"
        description={stan ? opis[stan] : "Sprawdzam…"}
        checked={stan === "on"}
        disabled={pracuje || stan === null || stan === "unsupported" || stan === "server-off" || stan === "denied"}
        onChange={(wlaczone) => void przelacz(wlaczone)}
      />
    </Sekcja>
  );
}

function Bezpieczenstwo() {
  const [sesje, setSesje] = useState<Sesja[] | null>(null);
  const [stan, setStan] = useState("");

  const wczytaj = useCallback(() => {
    apiRequest<Sesja[]>("GET", "/api/konto/sesje")
      .then(setSesje)
      .catch(() => setSesje([]));
  }, []);

  useEffect(wczytaj, [wczytaj]);

  const zakoncz = async () => {
    setStan("Wylogowuję…");
    try {
      const wynik = await apiRequest<{ zakonczone: number }>("POST", "/api/konto/sesje/zakoncz-pozostale");
      setStan(
        wynik.zakonczone === 0
          ? "Nie było innych zalogowanych przeglądarek."
          : `Wylogowano ${wynik.zakonczone}.`,
      );
      wczytaj();
    } catch (powod) {
      setStan(powod instanceof Error ? powod.message : "Nie udało się wylogować pozostałych.");
    }
  };

  const pobierz = async () => {
    const dane = await apiRequest<unknown>("GET", "/api/konto/eksport");
    const plik = new Blob([JSON.stringify(dane, null, 2)], { type: "application/json" });
    const adres = URL.createObjectURL(plik);
    const odsylacz = document.createElement("a");
    odsylacz.href = adres;
    odsylacz.download = "danaco-nexus-moje-dane.json";
    odsylacz.click();
    URL.revokeObjectURL(adres);
  };

  return (
    <Sekcja tytul="Bezpieczeństwo i dane" opis="Gdzie jesteś zalogowany i co Nexus o Tobie trzyma.">
      <ul className="divide-y divide-line/60">
        {sesje === null && <li className="py-3 text-sm text-muted">Wczytywanie…</li>}
        {sesje?.length === 0 && <li className="py-3 text-sm text-muted">Brak zapisanych sesji.</li>}
        {sesje?.map((sesja) => (
          <li key={`${sesja.utworzona}-${sesja.adres_ip}`} className="flex flex-wrap items-center gap-2 py-3">
            <span className="min-w-0 flex-1 text-sm text-fg">
              {sesja.przegladarka || "Nieznana przeglądarka"}
              {sesja.biezaca && <span className="ml-2 rounded-md bg-accent-soft px-1.5 py-0.5 text-xs text-accent">ta przeglądarka</span>}
            </span>
            <span className="text-xs text-muted">
              {sesja.adres_ip || "—"} · ostatnio {czas(sesja.ostatnio)}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="secondary" onClick={() => void zakoncz()}>
          Wyloguj pozostałe przeglądarki
        </Button>
        <Button variant="secondary" onClick={() => void pobierz()}>
          Pobierz moje dane (JSON)
        </Button>
        {stan && <span className="text-sm text-muted">{stan}</span>}
      </div>
    </Sekcja>
  );
}

interface Nowosc {
  tytul: string;
  tresc: string;
  rodzaj: string;
}

/** Co przyniosło bieżące wydanie.
 *
 * Produkt zmienia się po kilkanaście razy dziennie, a jedyną informacją o nowym wydaniu
 * było to, że coś wygląda inaczej. Wykaz bierze się z dziennika zmian wydania, więc nie
 * trzeba go pisać drugi raz i nie da się go zapomnieć zaktualizować.
 */
export function CoNowego() {
  const [dane, setDane] = useState<{ pozycje: Nowosc[]; wszystkich: number; wydanie: string } | null>(null);
  const [wszystkie, setWszystkie] = useState(false);

  useEffect(() => {
    void apiRequest<{ pozycje: Nowosc[]; wszystkich: number; wydanie: string }>("GET", "/api/nowosci")
      .then(setDane)
      .catch(() => setDane({ pozycje: [], wszystkich: 0, wydanie: "" }));
  }, []);

  // Otwarte Ustawienia z widocznym wykazem gaszą kropkę przy „Więcej” w pasku modułów.
  useEffect(() => {
    if (dane?.wydanie && dane.pozycje.length) oznaczNowosciPrzeczytane(dane.wydanie);
  }, [dane]);

  if (!dane || !dane.pozycje.length) return null;
  const widoczne = wszystkie ? dane.pozycje : dane.pozycje.slice(0, 4);
  return (
    <Sekcja
      tytul="Co nowego"
      opis={dane.wydanie ? `Zmiany z wydania z ${dane.wydanie}.` : "Zmiany z bieżącego wydania."}
    >
      <ul className="grid gap-3">
        {widoczne.map((pozycja) => (
          <li key={pozycja.tytul} className="min-w-0 border-l-2 border-accent/40 pl-3">
            <span className="block text-sm font-medium text-fg">{pozycja.tytul}</span>
            <span className="mt-0.5 block text-xs leading-relaxed text-muted">{pozycja.tresc}</span>
          </li>
        ))}
      </ul>
      {dane.pozycje.length > widoczne.length && (
        <button
          type="button"
          className="mt-3 text-sm text-accent hover:underline"
          onClick={() => setWszystkie(true)}
        >
          Pokaż pozostałe ({dane.pozycje.length - widoczne.length})
        </button>
      )}
    </Sekcja>
  );
}

/** Odsyła tam, gdzie ustawienie musi zajść w swoim kontekście. */
function Skroty({ openModule }: { openModule: (id: string) => void }) {
  const pozycje: Array<{ id: string; tytul: string; opis: string }> = [
    { id: "poczta", tytul: "Skrzynki pocztowe", opis: "Podłącz własną pocztę, ustaw podpis i konto do wysyłki." },
    { id: "urzadzenia", tytul: "Urządzenia", opis: "Klucze dla telefonu, komputera i rozszerzenia przeglądarki." },
    { id: "platnosci", tytul: "Plan i dostęp", opis: "Wykorzystanie, przedłużenie dostępu, faktury." },
    { id: "cloud", tytul: "Chmura osobista", opis: "Pliki, wersje i synchronizacja z komputerem." },
  ];
  return (
    <Sekcja tytul="Pozostałe ustawienia" opis="Rzeczy, które ustawia się tam, gdzie z nich korzystasz.">
      <ul className="grid gap-2 sm:grid-cols-2">
        {pozycje.map((pozycja) => (
          <li key={pozycja.id}>
            <button
              type="button"
              onClick={() => openModule(pozycja.id)}
              className="ui-nacisk w-full rounded-xl border border-line-control px-4 py-3 text-left transition-colors hover:bg-hover"
            >
              <span className="block text-sm font-medium text-fg">{pozycja.tytul}</span>
              <span className="mt-0.5 block text-xs text-muted">{pozycja.opis}</span>
            </button>
          </li>
        ))}
      </ul>
    </Sekcja>
  );
}

function UstawieniaPage({ openModule }: ModulePageProps) {
  const [dane, setDane] = useState<Preferencje>(preferencje);
  const [profil, setProfil] = useState<Profil | null>(null);

  useEffect(() => {
    wczytajPreferencje().then(setDane).catch(() => undefined);
    apiRequest<Profil>("GET", "/api/konto").then(setProfil).catch(() => setProfil(null));
  }, []);

  const ustaw = useCallback((zmiany: Partial<Preferencje>) => {
    setDane((biezace) => ({ ...biezace, ...zmiany }));
    void zapiszPreferencje(zmiany).then(setDane).catch(() => undefined);
  }, []);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 md:px-6">
      <h1 className="font-heading text-2xl font-bold tracking-tight">Ustawienia</h1>
      <p className="mt-1 text-muted">Konto, wygląd, praca, głos, powiadomienia i Twoje dane.</p>
      <div className="mt-6 grid gap-4">
        <Konto profil={profil} onZmiana={setProfil} />
        <Wyglad dane={dane} ustaw={ustaw} />
        <Praca dane={dane} ustaw={ustaw} />
        <Glos dane={dane} ustaw={ustaw} />
        <Powiadomienia />
        <Bezpieczenstwo />
        <CoNowego />
        <Skroty openModule={openModule} />
      </div>
    </div>
  );
}

export const module: NexusModule = {
  id: "ustawienia",
  label: "Ustawienia",
  description: "Konto, wygląd, praca, głos, powiadomienia i dane",
  icon: SettingsIcon,
  order: 800,
  Page: UstawieniaPage,
};
