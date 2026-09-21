// Składanie filmu z ujęć: zdjęcia i klipy + napisy + ruch kamery + podkład z biblioteki serwera.
// Studio umiało dotąd wyłącznie przerabiać gotowe nagranie; tu powstaje nowy materiał.

import { useState } from "react";
import { thumbnailUrl, type FileInfo } from "../../api";
import { FileDrop, buttonPrimary, buttonSecondary, inputClass, labelClass } from "../_tworczy/ui";
import { isVideo } from "../_tworczy/logic";

export const MONTAZ_ACCEPT = ".jpg,.jpeg,.png,.webp,.avif,.heic,.mp4,.mov,.mkv,.webm";

export type Ruch = "najazd" | "odjazd" | "w-lewo" | "w-prawo" | "brak";
export type Kadr = "16:9" | "9:16" | "1:1" | "4:5";

export type Ujecie = { plik: FileInfo; sekundy: number; napis: string; ruch: Ruch; lektor: string };

export const RUCHY: { id: Ruch; label: string }[] = [
  { id: "najazd", label: "Najazd" },
  { id: "odjazd", label: "Odjazd" },
  { id: "w-lewo", label: "Panorama w lewo" },
  { id: "w-prawo", label: "Panorama w prawo" },
  { id: "brak", label: "Bez ruchu" },
];

export const KADRY: { id: Kadr; label: string; gdzie: string }[] = [
  { id: "16:9", label: "16:9", gdzie: "YouTube, strona" },
  { id: "9:16", label: "9:16", gdzie: "rolki, stories" },
  { id: "1:1", label: "1:1", gdzie: "post kwadratowy" },
  { id: "4:5", label: "4:5", gdzie: "post pionowy" },
];

export const NASTROJE = [
  { id: "korporacyjny", label: "Firmowy", opis: "spokojny rytm, bez emocji" },
  { id: "energetyczny", label: "Energiczny", opis: "szybki, na zapowiedź" },
  { id: "spokojny", label: "Spokojny", opis: "tło pod lektora" },
  { id: "kinowy", label: "Kinowy", opis: "szeroki, z napięciem" },
  { id: "sygnaly", label: "Sygnał", opis: "krótki dżingiel na końcówkę" },
  { id: "", label: "Bez muzyki", opis: "sam obraz" },
];

// Pierwsza grupa to przejścia wbudowane w FFmpeg, druga – własne przejścia z biblioteki
// serwera (/danaco/programy/media-zasoby/przejscia/xfade-danaco). Jedne i drugie obsługuje
// to samo narzędzie video_compose.
export const PRZEJSCIA = [
  { id: "fade", label: "Przenikanie" },
  { id: "dissolve", label: "Rozmycie ziarnem" },
  { id: "wipeleft", label: "Zmiatanie w lewo" },
  { id: "slideup", label: "Wjazd z dołu" },
  { id: "circleopen", label: "Otwarcie koła" },
  { id: "pixelize", label: "Piksele" },
  { id: "zegar", label: "Zegar" },
  { id: "romb", label: "Romb od środka" },
  { id: "zaluzje-pionowe", label: "Żaluzje pionowe" },
  { id: "schody", label: "Schody" },
  { id: "rozblysk-biel", label: "Rozbłysk bielą" },
  { id: "spirala", label: "Spirala" },
  { id: "zamiatanie-miekkie", label: "Miękkie zamiatanie" },
  { id: "siatka-kwadratow", label: "Siatka kwadratów" },
];

/** Polecenie dla asystenta: jedno wywołanie video_compose z ujęciami w kolejności z ekranu. */
export function montazPrompt(
  ujecia: Ujecie[],
  ustawienia: { tytul: string; kadr: Kadr; przejscie: string; nastroj: string },
): string {
  const lista = ujecia
    .map((u, i) => {
      const opis = [`${i + 1}. „${u.plik.name}” — ${u.sekundy.toFixed(1)} s, ruch: ${u.ruch}`];
      if (u.napis.trim()) opis.push(`napis: „${u.napis.trim()}”`);
      if (u.lektor.trim()) opis.push(`lektor czyta: „${u.lektor.trim()}”`);
      return opis.join(", ");
    })
    .join("\n");
  const muzyka = ustawienia.nastroj
    ? `Podkład dobierz sam z biblioteki serwera (asset_library, dział „media”, katalog „muzyka”), ` +
      `odmiana „${ustawienia.nastroj}” — wybierz utwór pasujący długością i powiedz, na co padło.`
    : "Film bez podkładu muzycznego.";
  return [
    `Złóż film narzędziem video_compose z tych ujęć, w tej kolejności:`,
    lista,
    ``,
    `Kadr: ${ustawienia.kadr}. Przejście między ujęciami: ${ustawienia.przejscie}.`,
    ustawienia.tytul.trim() ? `Napis otwierający: „${ustawienia.tytul.trim()}”.` : "Bez napisu otwierającego.",
    muzyka,
  ].join("\n");
}

export function MontazPanel({
  ujecia,
  onZmiana,
  onDodano,
  onBlad,
  ustawienia,
  onUstawienia,
  onZloz,
  zajete,
}: {
  ujecia: Ujecie[];
  onZmiana: (ujecia: Ujecie[]) => void;
  onDodano: (plik: FileInfo) => void;
  onBlad: (tekst: string) => void;
  ustawienia: { tytul: string; kadr: Kadr; przejscie: string; nastroj: string };
  onUstawienia: (ustawienia: { tytul: string; kadr: Kadr; przejscie: string; nastroj: string }) => void;
  onZloz: () => void;
  zajete: boolean;
}) {
  const [rozwiniete, setRozwiniete] = useState<number | null>(null);
  const dlugosc = ujecia.reduce((suma, u) => suma + u.sekundy, 0) - Math.max(0, ujecia.length - 1) * 0.6;

  const popraw = (numer: number, zmiana: Partial<Ujecie>) =>
    onZmiana(ujecia.map((u, i) => (i === numer ? { ...u, ...zmiana } : u)));

  const przesun = (numer: number, o: number) => {
    const cel = numer + o;
    if (cel < 0 || cel >= ujecia.length) return;
    const kopia = [...ujecia];
    [kopia[numer], kopia[cel]] = [kopia[cel], kopia[numer]];
    onZmiana(kopia);
  };

  return (
    <div className="space-y-5">
      <FileDrop
        accept={MONTAZ_ACCEPT}
        multiple
        compact={ujecia.length > 0}
        hint={
          ujecia.length
            ? "Dorzuć kolejne zdjęcia lub klipy"
            : "Zdjęcia i klipy, z których powstanie film (JPG, PNG, WEBP, MP4, MOV…)"
        }
        onUploaded={onDodano}
        onError={onBlad}
      />

      {ujecia.length === 0 ? (
        <div>
          <h2 className="text-sm font-medium text-fg">Co Nexus zrobi ze zdjęciami</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {[
              ["Filmik promocyjny", "Ujęcia z ruchem kamery, napisy, podkład z biblioteki serwera"],
              ["Rolka 9:16", "Ten sam materiał w kadrze pod telefon"],
              ["Portfolio w ruchu", "Prace jedna po drugiej, spokojne przenikanie"],
              ["Zapowiedź wydarzenia", "Mocny napis otwierający i energiczny podkład"],
            ].map(([tytul, opis]) => (
              <li key={tytul} className="rounded-xl border border-line bg-raised/60 px-4 py-3">
                <span className="block text-sm font-medium text-fg">{tytul}</span>
                <span className="mt-0.5 block text-xs text-muted">{opis}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">
            Muzyki nie musisz mieć — na serwerze leży biblioteka podkładów na wolnej licencji,
            a Nexus dobiera z niej utwór do nastroju filmu.
          </p>
        </div>
      ) : (
        <>
          <ol className="space-y-2">
            {ujecia.map((ujecie, numer) => (
              <li key={`${ujecie.plik.id}-${numer}`} className="rounded-2xl border border-line">
                <div className="flex items-center gap-2 px-2 py-2">
                  <span className="w-5 shrink-0 text-center text-xs font-medium text-muted">{numer + 1}</span>
                  {/* Storyboard bez obrazków to sama lista nazw plików – po kolejności ujęć
                    nie da się wtedy poznać, czy film ma sens. */}
                  <img
                    src={thumbnailUrl(ujecie.plik)}
                    alt=""
                    loading="lazy"
                    className="h-10 w-16 shrink-0 rounded-md border border-line/60 bg-app object-cover"
                  />
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left text-sm hover:underline"
                    onClick={() => setRozwiniete(rozwiniete === numer ? null : numer)}
                  >
                    {ujecie.napis.trim() || ujecie.plik.name}
                    {ujecie.lektor.trim() ? <span className="ml-2 text-xs text-accent">lektor</span> : null}
                    <span className="ml-2 text-xs text-muted">
                      {ujecie.sekundy.toFixed(1)} s · {RUCHY.find((r) => r.id === ujecie.ruch)?.label ?? ujecie.ruch}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="px-1.5 text-muted hover:text-fg disabled:opacity-30"
                    onClick={() => przesun(numer, -1)}
                    disabled={numer === 0}
                    aria-label={`Przesuń ujęcie ${numer + 1} w górę`}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="px-1.5 text-muted hover:text-fg disabled:opacity-30"
                    onClick={() => przesun(numer, 1)}
                    disabled={numer === ujecia.length - 1}
                    aria-label={`Przesuń ujęcie ${numer + 1} w dół`}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="px-1.5 text-muted hover:text-danger"
                    onClick={() => onZmiana(ujecia.filter((_, i) => i !== numer))}
                    aria-label={`Usuń ujęcie ${numer + 1}`}
                  >
                    ×
                  </button>
                </div>
                {rozwiniete === numer && (
                  <div className="grid gap-3 border-t border-line/60 px-3 py-3 sm:grid-cols-[1fr_auto_auto]">
                    <label className="block">
                      <span className={labelClass}>Napis na ujęciu</span>
                      <input
                        className={inputClass}
                        value={ujecie.napis}
                        maxLength={180}
                        placeholder="np. Remont pod klucz w 30 dni"
                        onChange={(event) => popraw(numer, { napis: event.target.value })}
                      />
                    </label>
                    <label className="block">
                      <span className={labelClass}>Czas</span>
                      <input
                        type="number"
                        className={`${inputClass} w-24`}
                        value={ujecie.sekundy}
                        min={1.2}
                        max={30}
                        step={0.5}
                        onChange={(event) =>
                          popraw(numer, {
                            sekundy: Math.min(30, Math.max(1.2, Number(event.target.value) || 1.2)),
                          })
                        }
                      />
                    </label>
                    <label className="block sm:col-span-3">
                      <span className={labelClass}>Lektor czyta w tym ujęciu</span>
                      <input
                        className={inputClass}
                        value={ujecie.lektor}
                        maxLength={400}
                        placeholder="np. Robimy meble na wymiar od dwudziestu lat."
                        onChange={(event) => popraw(numer, { lektor: event.target.value })}
                      />
                      <span className="mt-1 block text-xs text-muted">
                        Głos serwera przeczyta zdanie nad muzyką; na cztery sekundy wchodzi jedno zdanie.
                      </span>
                    </label>
                    <label className="block">
                      <span className={labelClass}>Ruch kamery</span>
                      <select
                        className={inputClass}
                        value={ujecie.ruch}
                        disabled={isVideo(ujecie.plik.mime, ujecie.plik.name)}
                        onChange={(event) => popraw(numer, { ruch: event.target.value as Ruch })}
                      >
                        {RUCHY.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}
              </li>
            ))}
          </ol>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className={labelClass}>Napis otwierający</span>
              <input
                className={inputClass}
                value={ustawienia.tytul}
                maxLength={120}
                placeholder="np. Pracownia Stolarska Kowalscy"
                onChange={(event) => onUstawienia({ ...ustawienia, tytul: event.target.value })}
              />
            </label>
            <label className="block">
              <span className={labelClass}>Kadr</span>
              <select
                className={inputClass}
                value={ustawienia.kadr}
                onChange={(event) => onUstawienia({ ...ustawienia, kadr: event.target.value as Kadr })}
              >
                {KADRY.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.label} — {k.gdzie}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className={labelClass}>Przejście</span>
              <select
                className={inputClass}
                value={ustawienia.przejscie}
                onChange={(event) => onUstawienia({ ...ustawienia, przejscie: event.target.value })}
              >
                {PRZEJSCIA.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block sm:col-span-2">
              <span className={labelClass}>Podkład muzyczny</span>
              <select
                className={inputClass}
                value={ustawienia.nastroj}
                onChange={(event) => onUstawienia({ ...ustawienia, nastroj: event.target.value })}
              >
                {NASTROJE.map((n) => (
                  <option key={n.id || "brak"} value={n.id}>
                    {n.label} — {n.opis}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className={buttonPrimary} onClick={onZloz} disabled={zajete}>
              Złóż film
            </button>
            <button type="button" className={buttonSecondary} onClick={() => onZmiana([])} disabled={zajete}>
              Wyczyść ujęcia
            </button>
            <p className="text-xs text-muted">
              {ujecia.length} {ujecia.length === 1 ? "ujęcie" : "ujęć"} · około {Math.max(1, Math.round(dlugosc))} s
              gotowego filmu
            </p>
          </div>
        </>
      )}
    </div>
  );
}
