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

/** Ruch kredytów: przydział (dodatni) albo zużycie (ujemne). */
export interface RuchKredytow {
  id: string;
  zmiana: number;
  saldo_po: number;
  powod: string;
  opis: string;
  run_id: string | null;
  kiedy: string;
}

export interface KredytyInfo {
  saldo: number;
  przydzielone: number;
  zuzyte: number;
  historia: RuchKredytow[];
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
  start: "Przydział startowy",
  plan: "Przydział z planu",
  zakup: "Zakup pakietu",
  odnowienie: "Odnowienie planu",
  przebieg: "Praca agenta",
  "konto-testowe": "Przydział konta testowego",
};

export const platnosciApi = {
  kredyty: () => apiRequest<KredytyInfo>("GET", "/api/platnosci/kredyty"),
  pakiety: () => apiRequest<PakietyInfo>("GET", "/api/platnosci/pakiety"),
  zakupPakietu: (pakiet: string) =>
    apiRequest<{ url: string; tryb: string; pakiet: string }>("POST", "/api/platnosci/pakiety/checkout", {
      pakiet,
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
  const kredyty = zakres.kredyty.toLocaleString("pl-PL");
  const braki = brakiOkresuProbnego(zakres);
  const obejmuje =
    `Pierwsze ${plan.okres_probny_dni} dni bez opłaty obejmują ${kredyty} kredytów ` +
    `i ${opisPrzestrzeni(zakres.przestrzen_mb)} miejsca`;
  const zastrzezenie = braki.length > 0 ? `, bez ${wyliczenie(braki)}` : "";
  return `${obejmuje}${zastrzezenie}. Kartę podajesz od razu — po tym czasie plan przechodzi w płatny i dostajesz pełny zakres opisany wyżej.`;
}

/** Nazwa okresu rozliczeniowego w zdaniu („rozliczenie roczne”). */
export function opisOkresu(okres: string): string {
  if (okres === "rok") return "rozliczenie roczne";
  if (okres === "miesiac") return "rozliczenie miesięczne";
  return "";
}

/** Czy plan w danym okresie jest właśnie tym, który konto ma opłacony. */
export function planBiezacy(plan: PlanInfo, subskrypcja: SubskrypcjaInfo, okres: Okres): boolean {
  if (plan.kod !== subskrypcja.plan) return false;
  return !subskrypcja.ma_platny_plan || subskrypcja.okres === okres;
}
