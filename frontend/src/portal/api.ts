// Klient API portalu: treści, wyszukiwanie, konto klienta i punkty edycyjne administratora.
// Uwierzytelnienie i nagłówek CSRF zapewnia wspólny klient aplikacji (src/api.ts).

import { apiRequest, ApiError } from "../api";

export type RodzajTresci = "blog" | "wiedza" | "dokumentacja" | "strona";
export type StatusTresci = "szkic" | "opublikowany";

export interface SkrotTresci {
  id: string;
  kind: RodzajTresci;
  slug: string;
  title: string;
  excerpt: string;
  author: string;
  tags: string[];
  status: StatusTresci;
  position: number;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface MetadaneSeo {
  meta_title?: string;
  meta_description?: string;
  og_image?: string;
  canonical?: string;
  noindex?: boolean;
}

export interface PelnaTresc extends SkrotTresci {
  body: string;
  seo: MetadaneSeo;
  related?: SkrotTresci[];
}

export interface StronaListy {
  items: SkrotTresci[];
  total: number;
  page: number;
  pages: number;
  per_page: number;
}

export interface WynikSzukania {
  query: string;
  items: (SkrotTresci & { score: number })[];
  total: number;
}

export interface ProfilKlienta {
  id: string;
  email: string;
  name: string;
  company: string;
  plan: string;
  /** Czy adres e-mail konta został potwierdzony odsyłaczem z wiadomości. */
  email_confirmed: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface WiadomoscKontaktowa {
  id: string;
  name: string;
  email: string;
  subject: string;
  body: string;
  handled: boolean;
  created_at: string;
}

export interface StanPortalu {
  registration_open: boolean;
  admin: boolean;
  /** Czy wiadomości portalu naprawdę wychodzą (podłączona skrzynka i nadawca SMTP).
   *
   * Bez tego interfejs obiecywał wiadomość, która nigdy nie przychodziła. Starsze wydania
   * serwera tego pola nie mają — wtedy zostaje `undefined` i ekrany zachowują się jak dotąd.
   */
  poczta_dziala?: boolean;
}

export interface ZnacznikTresci {
  tag: string;
  count: number;
}

const PORTAL = "/api/portal";

function zapytanie(wartosci: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [nazwa, wartosc] of Object.entries(wartosci)) {
    if (wartosc !== undefined && wartosc !== "") params.set(nazwa, String(wartosc));
  }
  const tekst = params.toString();
  return tekst ? `?${tekst}` : "";
}

export const portalApi = {
  stan: () => apiRequest<StanPortalu>("GET", `${PORTAL}/stan`),

  lista: (opcje: { typ?: RodzajTresci; tag?: string; q?: string; strona?: number; na_stronie?: number }) =>
    apiRequest<StronaListy>("GET", `${PORTAL}/tresci${zapytanie(opcje)}`),

  szczegoly: (typ: RodzajTresci, slug: string) =>
    apiRequest<PelnaTresc>("GET", `${PORTAL}/tresci/${typ}/${encodeURIComponent(slug)}`),

  znaczniki: (typ?: RodzajTresci) =>
    apiRequest<ZnacznikTresci[]>("GET", `${PORTAL}/znaczniki${zapytanie({ typ })}`),

  szukaj: (q: string, typ?: RodzajTresci) =>
    apiRequest<WynikSzukania>("GET", `${PORTAL}/szukaj${zapytanie({ q, typ })}`),

  kontakt: (dane: { name: string; email: string; subject: string; message: string }) =>
    apiRequest<{ ok: boolean }>("POST", `${PORTAL}/kontakt`, dane),

  konto: {
    ja: () => apiRequest<ProfilKlienta>("GET", `${PORTAL}/konto/ja`),
    /** Kto jest zalogowany (albo nikt) — pytanie o stan, więc bez 401 dla gościa. */
    sesja: () => apiRequest<{ konto: ProfilKlienta | null }>("GET", `${PORTAL}/konto/sesja`),
    rejestracja: (dane: { email: string; password: string; name: string; company?: string }) =>
      apiRequest<ProfilKlienta>("POST", `${PORTAL}/konto/rejestracja`, dane),
    logowanie: (dane: { email: string; password: string }) =>
      apiRequest<ProfilKlienta>("POST", `${PORTAL}/konto/logowanie`, dane),
    wylogowanie: () => apiRequest<{ ok: boolean }>("POST", `${PORTAL}/konto/wylogowanie`),
    profil: (dane: { name: string; company: string }) =>
      apiRequest<ProfilKlienta>("PATCH", `${PORTAL}/konto/profil`, dane),
    haslo: (dane: { current_password: string; new_password: string }) =>
      apiRequest<{ ok: boolean }>("POST", `${PORTAL}/konto/haslo`, dane),
    odzyskiwanie: (email: string) =>
      apiRequest<{ ok: boolean }>("POST", `${PORTAL}/konto/odzyskiwanie`, { email }),
    ustawHaslo: (token: string, password: string) =>
      apiRequest<{ ok: boolean }>("POST", `${PORTAL}/konto/odzyskiwanie/potwierdz`, { token, password }),
    potwierdzAdres: (token: string) =>
      apiRequest<{ ok: boolean }>("POST", `${PORTAL}/konto/potwierdzenie`, { token }),
    wyslijPotwierdzenie: () =>
      apiRequest<{ ok: boolean }>("POST", `${PORTAL}/konto/potwierdzenie/wyslij`),
    usun: (dane: { password: string; confirmation: string }) =>
      apiRequest<{ ok: boolean }>("POST", `${PORTAL}/konto/usuniecie`, dane),
  },

  admin: {
    lista: (opcje: { typ?: RodzajTresci; status?: StatusTresci; q?: string; na_stronie?: number }) =>
      apiRequest<StronaListy>("GET", `${PORTAL}/admin/tresci${zapytanie(opcje)}`),
    szczegoly: (id: string) => apiRequest<PelnaTresc>("GET", `${PORTAL}/admin/tresci/${id}`),
    utworz: (dane: Partial<PelnaTresc>) => apiRequest<PelnaTresc>("POST", `${PORTAL}/admin/tresci`, dane),
    zmien: (id: string, dane: Partial<PelnaTresc>) =>
      apiRequest<PelnaTresc>("PATCH", `${PORTAL}/admin/tresci/${id}`, dane),
    publikacja: (id: string, status: StatusTresci) =>
      apiRequest<PelnaTresc>("POST", `${PORTAL}/admin/tresci/${id}/publikacja`, { status }),
    usun: (id: string) => apiRequest<{ ok: boolean }>("DELETE", `${PORTAL}/admin/tresci/${id}`),
    wiadomosci: () => apiRequest<WiadomoscKontaktowa[]>("GET", `${PORTAL}/admin/wiadomosci`),
    klienci: () => apiRequest<ProfilKlienta[]>("GET", `${PORTAL}/admin/klienci`),
  },
};

/** Komunikat błędu do pokazania użytkownikowi. */
export function komunikat(error: unknown, zapasowy = "Nie udało się wykonać operacji."): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return zapasowy;
}

/** Czy błąd oznacza brak sesji (klient niezalogowany). */
export function brakSesji(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/** Słowo, które klient wpisuje, aby potwierdzić nieodwracalne usunięcie konta. */
export const POTWIERDZENIE_USUNIECIA = "USUWAM";

/** Najkrótsze dopuszczalne hasło konta klienta (polityka serwera: nexus.portal.konta). */
export const MIN_HASLO = 12;

/** Data w formacie czytelnym dla czytelnika strony (np. 20 września 2026). */
export function dataPolska(iso: string | null): string {
  if (!iso) return "";
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "";
  return data.toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric" });
}
