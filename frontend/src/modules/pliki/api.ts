// Klient API przestrzeni plików konta (moduł Pliki).

import { call } from "../_biuro/http";

export interface Katalog {
  id: string;
  parent_id: string | null;
  nazwa: string;
  opis: string;
  rodzaj: "katalog" | "projekt";
  kolor: string;
  przypiety: boolean;
  plikow: number;
  updated_at: string;
}

export interface PlikPrzestrzeni {
  id: string;
  name: string;
  tytul: string;
  mime: string;
  size: number;
  created_at: string;
  katalog_id: string | null;
}

export interface Przestrzen {
  zajete: number;
  limit: number;
  opis_limitu: string;
  plan: string;
}

export interface Zawartosc {
  pliki: PlikPrzestrzeni[];
  przestrzen: Przestrzen;
}

/** Filtry paska nad listą; puste znaczy „wszystko”. */
export type RodzajTresci = "" | "zdjecia" | "dokumenty" | "nagrania" | "archiwa";

export const RODZAJE: { id: RodzajTresci; etykieta: string }[] = [
  { id: "", etykieta: "Wszystko" },
  { id: "zdjecia", etykieta: "Zdjęcia" },
  { id: "dokumenty", etykieta: "Dokumenty" },
  { id: "nagrania", etykieta: "Nagrania" },
  { id: "archiwa", etykieta: "Archiwa" },
];

function zapytanie(parametry: Record<string, string | number | boolean | undefined>): string {
  const pary = Object.entries(parametry).filter(([, wartosc]) => wartosc !== undefined && wartosc !== "");
  if (!pary.length) return "";
  return "?" + new URLSearchParams(pary.map(([klucz, wartosc]) => [klucz, String(wartosc)])).toString();
}

export const plikiApi = {
  katalogi: () => call<Katalog[]>("GET", "/api/pliki/katalogi"),
  utworzKatalog: (dane: { nazwa: string; rodzaj?: string; opis?: string; kolor?: string }) =>
    call<Katalog>("POST", "/api/pliki/katalogi", dane),
  zmienKatalog: (id: string, dane: Partial<Pick<Katalog, "nazwa" | "opis" | "kolor" | "przypiety">>) =>
    call<Katalog>("PATCH", `/api/pliki/katalogi/${id}`, dane),
  usunKatalog: (id: string, zPlikami = false) =>
    call<{ ok: boolean; usuniete_pliki: number }>(
      "DELETE",
      `/api/pliki/katalogi/${id}${zPlikami ? "?z_plikami=true" : ""}`,
    ),
  zawartosc: (parametry: { katalog_id?: string; rodzaj?: RodzajTresci; q?: string; bez_katalogu?: boolean }) =>
    call<Zawartosc>("GET", `/api/pliki${zapytanie(parametry)}`),
  przypisz: (pliki: string[], katalog_id: string | null) =>
    call<{ ok: boolean; przeniesione: number }>("POST", "/api/pliki/przypisz", { pliki, katalog_id }),
  zmienTytul: (id: string, tytul: string) =>
    call<PlikPrzestrzeni>("PATCH", `/api/pliki/${id}`, { tytul }),
  usun: (id: string) => call<{ ok: boolean }>("DELETE", `/api/pliki/${id}`),
};
