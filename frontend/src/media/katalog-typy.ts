// Spis materiałów ruchomych. Wynik frontend/scripts/zasoby.py — nie edytować ręcznie.
// Źródła: promocja/film, promocja/kampania, motion/stany, motion/start.

export type Zrodla = { mp4?: string; webm?: string };
export type Film = { id: string; tytul: string; opis: string; kadr: string; zrodla: Zrodla; plakat: string; napisy: Record<string, string> };
export type Kampania = Film & { temat: string };
export type Nagranie = { id: string; zrodla: Zrodla };
export type Stan = Nagranie & { rodzina: string };
