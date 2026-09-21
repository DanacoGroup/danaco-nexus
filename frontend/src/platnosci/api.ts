// Klient API sprzedaży: cennik, zakup planu, portal rozliczeniowy, faktury i kupony.
// Klient nigdy nie przekazuje kwoty – wyłącznie kod planu i okres rozliczeniowy.

import { apiRequest } from "../api";

export type Okres = "miesiac" | "rok";

export interface LimityPlanu {
  zadania_rownolegle: number;
  plik_mb: number;
  automatyzacje: number;
  konta: number;
}

/** Co obejmuje okres próbny: te same liczby, które serwer egzekwuje przez te dni. */
export interface ZakresProbny {
  dni: number;
  przestrzen_mb: number;
  kredyty: number;
  /** Ile skrzynek pocztowych wolno wtedy założyć (0 = poczta niedostępna). */
  skrzynki: number;
  wersjonowanie: number;
  synchronizacja: number;
}

export interface PlanInfo {
  kod: string;
  nazwa: string;
  opis: string;
  bezplatny: boolean;
  znacznik: string;
  zawartosc: string[];
  /** Kredyty dopisywane do konta na każdy okres rozliczeniowy. */
  kredyty_okresowo: number;
  /** Dni bez opłaty na początku planu (0 = plan płatny od pierwszego dnia). */
  okres_probny_dni: number;
  /** Zakres obowiązujący w okresie próbnym — węższy niż zakres opłaconego planu. */
  probny: ZakresProbny;
  /** Przestrzeń konta w MB, wspólna dla plików, chmury i poczty. */
  przestrzen_mb: number;
  /** Ile skrzynek pocztowych obejmuje plan (0 = poczta poza planem). */
  skrzynki_poczty: number;
  wersjonowanie: boolean;
  synchronizacja: boolean;
  limity: LimityPlanu;
  cena_miesiac_gr: number;
  cena_rok_gr: number;
  do_kupienia: Record<Okres, boolean>;
}

export type TonStanu = "informacja" | "sukces" | "uwaga" | "blad";
export type DzialanieStanu = "brak" | "wybierz_plan" | "portal" | "zaplac_fakture";

/** Stan sprzedaży rozstrzygnięty przez serwer: co się dzieje i co zrobić dalej. */
export interface StanSprzedazy {
  kod: string;
  tytul: string;
  komunikat: string;
  dzialanie: DzialanieStanu;
  etykieta_dzialania: string;
  ton: TonStanu;
}

export interface SubskrypcjaInfo {
  stan: StanSprzedazy;
  faktura_do_zaplaty: FakturaInfo | null;
  ma_platny_plan: boolean;
  plan: string;
  nazwa_planu: string;
  status: string;
  okres: string;
  okres_od: string | null;
  okres_do: string | null;
  anuluj_na_koniec: boolean;
  ma_konto_stripe: boolean;
  limity: LimityPlanu;
}

/** Cennik publiczny: te same plany co w module, bez danych konta. */
export interface CennikPubliczny {
  waluta: string;
  sprzedaz_aktywna: boolean;
  plany: PlanInfo[];
}

export interface CennikInfo extends CennikPubliczny {
  subskrypcja: SubskrypcjaInfo;
}

/** Tryb rozpoczęcia zakupu: nowa płatność albo zmiana planu w portalu rozliczeniowym. */
export interface ZakupInfo {
  url: string;
  tryb: "checkout" | "portal";
  plan: string;
  okres: Okres;
}

export interface FakturaInfo {
  id: string;
  numer: string;
  kwota_gr: number;
  waluta: string;
  status: string;
  pdf_url: string;
  strona_url: string;
  wystawiona_at: string | null;
  oplacona_at: string | null;
}

export interface KuponInfo {
  kod: string;
  rabat_procent: number;
  rabat_gr: number;
  waluta: string;
  opis: string;
  wygasa_at: string | null;
}

/** Zdarzenie w historii dostępu — co się wydarzyło, bez wartości.
 *
 * Liczby kredytów nie wychodzą poza serwer: użytkownik kupuje dostęp, nie sztuki
 * jednostek rozliczeniowych, więc historia mówi „praca agenta”, a nie „−437”.
 */
export interface ZdarzenieDostepu {
  powod: string;
  opis: string;
  kiedy: string;
}

/** Warunki przedłużenia dostępu podane przez serwer (kwoty w groszach). */
export interface WarunkiDoladowania {
  minimum_gr: number;
  maksimum_gr: number;
  kwoty_szybkie_gr: number[];
  sprzedaz: boolean;
}

export interface KredytyInfo {
  /** Udział zużycia od 0 do 1 — z tego interfejs rysuje pasek. */
  zuzycie: number;
  stan: "w_porzadku" | "konczy_sie" | "wyczerpany";
  wyczerpane: boolean;
  historia: ZdarzenieDostepu[];
  doladowanie: WarunkiDoladowania;
}

/** Pakiet kredytów do dokupienia poza subskrypcją (jedna płatność). */
export interface PakietInfo {
  kod: string;
  nazwa: string;
  opis: string;
  kredyty: number;
  do_kupienia: boolean;
}

export interface PakietyInfo {
  sprzedaz: boolean;
  pakiety: PakietInfo[];
}

/** Opis powodu zmiany salda w języku użytkownika. */
export const POWODY: Record<string, string> = {
  start: "Dostęp na start",
  plan: "Dostęp z planu",
  zakup: "Przedłużenie dostępu",
  odnowienie: "Odnowienie planu",
  przebieg: "Praca agenta",
  "konto-testowe": "Dostęp konta testowego",
};

/** Plan rozliczany za każdego użytkownika — cenę pokazujemy wtedy jako cenę za osobę. */
export const PLAN_ZA_UZYTKOWNIKA = "zespol";

/** Członek grupy widziany w panelu: adres, nazwa konta i rola. */
export interface CzlonekGrupy {
  uzytkownik_id: string;
  email: string;
  nazwa: string;
  rola: "zalozyciel" | "czlonek";
  to_ja: boolean;
}

export interface GrupaInfo {
  id: string;
  nazwa: string;
  jestem_zalozycielem: boolean;
  miejsca: number;
  czlonkowie: CzlonekGrupy[];
  zaproszenia: Array<{ email: string; wygasa: string }>;
}

export interface OdpowiedzGrupy {
  grupa: GrupaInfo | null;
  miejsca?: number;
}

/** Grupa: wspólna pula dostępu kupiona przez założyciela. */
export const grupaApi = {
  moja: () => apiRequest<OdpowiedzGrupy>("GET", "/api/grupa"),
  zaloz: (nazwa: string) => apiRequest<OdpowiedzGrupy>("POST", "/api/grupa", { nazwa }),
  zapros: (email: string) =>
    apiRequest<OdpowiedzGrupy & { odsylacz: string }>("POST", "/api/grupa/zaproszenia", { email }),
  przyjmij: (token: string) => apiRequest<OdpowiedzGrupy>("POST", "/api/grupa/przyjmij", { token }),
  usun: (uzytkownikId: string) =>
    apiRequest<OdpowiedzGrupy>("DELETE", `/api/grupa/czlonkowie/${uzytkownikId}`),
  przekaz: (uzytkownikId: string) =>
    apiRequest<OdpowiedzGrupy>("POST", "/api/grupa/zalozyciel", { uzytkownik_id: uzytkownikId }),
  rozwiaz: () => apiRequest<OdpowiedzGrupy>("DELETE", "/api/grupa"),
};

export const platnosciApi = {
  kredyty: () => apiRequest<KredytyInfo>("GET", "/api/platnosci/kredyty"),
  /** Przedłużenie dostępu kwotą podaną przez użytkownika (w groszach). */
  doladowanie: (kwotaGr: number) =>
    apiRequest<{ url: string; tryb: string }>("POST", "/api/platnosci/doladowanie/checkout", {
      kwota_gr: kwotaGr,
    }),
  cennik: () => apiRequest<CennikInfo>("GET", "/api/platnosci/plany"),
  cennikPubliczny: () => apiRequest<CennikPubliczny>("GET", "/api/platnosci/cennik"),
  subskrypcja: () => apiRequest<SubskrypcjaInfo>("GET", "/api/platnosci/subskrypcja"),
  faktury: (odswiez = false) =>
    apiRequest<FakturaInfo[]>("GET", `/api/platnosci/faktury${odswiez ? "?odswiez=1" : ""}`),
  kupon: (kod: string) => apiRequest<KuponInfo>("POST", "/api/platnosci/kupon", { kod }),
  zakup: (plan: string, okres: Okres, kupon = "") =>
    apiRequest<ZakupInfo>("POST", "/api/platnosci/checkout", { plan, okres, kupon }),
  portal: () => apiRequest<{ url: string }>("POST", "/api/platnosci/portal"),
  rezygnacja: () => apiRequest<{ url: string }>("POST", "/api/platnosci/rezygnacja"),
  powrot: (sesja: string) => apiRequest<SubskrypcjaInfo>("POST", "/api/platnosci/powrot", { sesja }),
};

export const WALUTA_DOMYSLNA = "pln";
const FORMATY = new Map<string, Intl.NumberFormat>();

/** Formater kwot dla waluty podanej przez serwer; nieznany kod wraca do złotych. */
function formater(waluta: string, pelne: boolean): Intl.NumberFormat {
  const kod = (waluta || WALUTA_DOMYSLNA).toUpperCase();
  const klucz = `${kod}:${pelne}`;
  const gotowy = FORMATY.get(klucz);
  if (gotowy) return gotowy;
  const opcje: Intl.NumberFormatOptions = { style: "currency", currency: kod };
  if (pelne) opcje.maximumFractionDigits = 0;
  let format: Intl.NumberFormat;
  try {
    format = new Intl.NumberFormat("pl-PL", opcje);
  } catch {
    format = new Intl.NumberFormat("pl-PL", { ...opcje, currency: WALUTA_DOMYSLNA.toUpperCase() });
  }
  FORMATY.set(klucz, format);
  return format;
}

/** Kwota w groszach jako cena w walucie serwera (pełne jednostki bez końcówki „,00”). */
export function kwota(groszy: number, waluta: string = WALUTA_DOMYSLNA): string {
  return formater(waluta, groszy % 100 === 0).format(groszy / 100);
}

/** Data w zapisie polskim (pusta wartość → myślnik). */
export function data(wartosc: string | null): string {
  if (!wartosc) return "—";
  return new Date(wartosc).toLocaleDateString("pl-PL", { dateStyle: "long" });
}

export const OPISY_STATUSU: Record<string, string> = {
  brak: "Bez wykupionego planu",
  probna: "Okres próbny",
  aktywna: "Aktywna",
  zalegla: "Zaległa płatność",
  anulowana: "Zakończona",
  niepelna: "Płatność niedokończona",
};

export const OPISY_FAKTURY: Record<string, string> = {
  paid: "Opłacona",
  open: "Do zapłaty",
  draft: "Szkic",
  void: "Anulowana",
  uncollectible: "Nieściągalna",
};

/** Cena planu za wybrany okres (w groszach). */
export function cenaPlanu(plan: PlanInfo, okres: Okres): number {
  return okres === "rok" ? plan.cena_rok_gr : plan.cena_miesiac_gr;
}

/** Ile procent taniej wychodzi płatność roczna (0 = brak korzyści albo brak ceny). */
export function oszczednoscRoczna(plan: PlanInfo): number {
  if (plan.cena_miesiac_gr <= 0 || plan.cena_rok_gr <= 0) return 0;
  const pelny = plan.cena_miesiac_gr * 12;
  return Math.max(0, Math.round(((pelny - plan.cena_rok_gr) / pelny) * 100));
}

/** Przestrzeń tak, jak mówi o niej człowiek: „100 MB”, „1 GB”, „10 GB”. */
export function opisPrzestrzeni(mb: number): string {
  if (mb < 1024) return `${mb} MB`;
  const gb = mb / 1024;
  return Number.isInteger(gb) ? `${gb} GB` : `${gb.toFixed(1)} GB`;
}

/** Wylicza z zakresu próbnego, czego przez te dni nie ma; kolejność jak na liście planu. */
function brakiOkresuProbnego(zakres: ZakresProbny): string[] {
  const braki: string[] = [];
  if (!zakres.skrzynki) braki.push("poczty");
  if (!zakres.synchronizacja) braki.push("synchronizacji");
  if (!zakres.wersjonowanie) braki.push("wersji plików");
  return braki;
}

/** Łączy wyliczenie po polsku: „a”, „a i b”, „a, b i c”. */
function wyliczenie(czesci: string[]): string {
  if (czesci.length < 2) return czesci.join("");
  return `${czesci.slice(0, -1).join(", ")} i ${czesci[czesci.length - 1]}`;
}

/** Zdanie o okresie próbnym planu; plan bez okresu próbnego nie dostaje żadnego.
 *
 * Zdanie podaje zakres tych dni, a nie samą ich liczbę: okres próbny jest węższy niż
 * plan (mniej miejsca, bez poczty), a lista obok pokazuje zakres docelowy. Bez tego
 * użytkownik czyta „1 GB”, po czym przy 100 MB dostaje odmowę przyjęcia pliku.
 */
export function opisOkresuProbnego(plan: PlanInfo): string {
  if (plan.okres_probny_dni <= 0) return "";
  const zakres = plan.probny;
  const braki = brakiOkresuProbnego(zakres);
  // Bez liczby kredytów: to jednostka rozliczeniowa między nami a dostawcą modelu, nie
  // towar, który klient kupuje. Zdanie ma powiedzieć, ile pracy się mieści i czego w tych
  // dniach nie ma — resztę i tak widać paskiem wykorzystania w aplikacji.
  const obejmuje =
    `Pierwsze ${plan.okres_probny_dni} dni bez opłaty obejmują ${opisZakresuProbnego(zakres)} ` +
    `i ${opisPrzestrzeni(zakres.przestrzen_mb)} miejsca`;
  const zastrzezenie = braki.length > 0 ? `, bez ${wyliczenie(braki)}` : "";
  return `${obejmuje}${zastrzezenie}. Kartę podajesz od razu — po tym czasie plan przechodzi w płatny i dostajesz pełny zakres opisany wyżej.`;
}

/** Ile pracy mieści się w okresie próbnym — słowami, nie w jednostkach rozliczeniowych. */
function opisZakresuProbnego(zakres: PlanInfo["probny"]): string {
  if (zakres.kredyty >= 1_000) return "swobodną pracę z Nexusem";
  if (zakres.kredyty >= 200) return "kilkadziesiąt zadań";
  return "kilka pierwszych zadań";
}

/** Nazwa okresu rozliczeniowego w zdaniu („rozliczenie roczne”). */
export function opisOkresu(okres: string): string {
  if (okres === "rok") return "rozliczenie roczne";
  if (okres === "miesiac") return "rozliczenie miesięczne";
  return "";
}

/** Zakres pracy planu opisany słowami zamiast liczbą kredytów.
 *
 * Kupujący ma zobaczyć różnicę między planami, a nie porównywać jednostki, których
 * nigdzie indziej w produkcie nie widzi. Opis idzie za tym, co plan naprawdę zmienia:
 * ile zadań naraz i jak długo można pracować bez przedłużania dostępu.
 */
export function opisZakresuPracy(plan: PlanInfo): string {
  const zadania =
    plan.limity.zadania_rownolegle > 1
      ? `${plan.limity.zadania_rownolegle} zadania naraz`
      : "jedno zadanie naraz";
  const ile =
    plan.kredyty_okresowo >= 40_000
      ? "Praca bez oglądania się na limity"
      : plan.kredyty_okresowo >= 10_000
        ? "Codzienna praca z Nexusem"
        : "Praca od czasu do czasu";
  return `${ile} · ${zadania}`;
}

/** Czy plan w danym okresie jest właśnie tym, który konto ma opłacony. */
export function planBiezacy(plan: PlanInfo, subskrypcja: SubskrypcjaInfo, okres: Okres): boolean {
  if (plan.kod !== subskrypcja.plan) return false;
  return !subskrypcja.ma_platny_plan || subskrypcja.okres === okres;
}
