// Moduł Studio. Dwie części: „Nagranie” – przeróbka gotowego audio/wideo (transkrypcja, napisy,
// wycinanie, konwersja, streszczenie) oraz „Montaż” – złożenie nowego filmu ze zdjęć i klipów.
// Akcje wykonuje asystent w rozmowie widocznej obok.

import { useRef, useState } from "react";
import { api, downloadUrl, type FileInfo } from "../../api";
import type { ModulePageProps, NexusModule } from "../registry";
import { ChatPanel } from "../_tworczy/ChatPanel";
import { errorText } from "../_tworczy/http";
import { FilmIcon, ScissorsIcon } from "../_tworczy/icons";
import { ffmpegTime, formatTime, isVideo, parseTime, studioPrompt, type StudioAction, type StudioOptions } from "../_tworczy/logic";
import { buttonSecondary, ErrorBanner, FileDrop, inputClass, labelClass, ModuleHeader } from "../_tworczy/ui";
import { MontazPanel, montazPrompt, type Kadr, type Ujecie } from "./Montaz";
import { useConversation } from "../_tworczy/useConversation";

const MEDIA_ACCEPT = ".mp3,.wav,.m4a,.ogg,.flac,.aac,.mp4,.mov,.mkv,.webm,.avi";
const LANGUAGES = [
  { value: "pl", label: "polski" },
  { value: "en", label: "angielski" },
  { value: "de", label: "niemiecki" },
  { value: "uk", label: "ukraiński" },
  { value: "auto", label: "wykryj" },
];

const ACTIONS: { id: StudioAction; title: string; description: string; video?: boolean }[] = [
  { id: "transcribe", title: "Transkrypcja", description: "Tekst ze znacznikami czasu (TXT)" },
  { id: "subtitles", title: "Napisy", description: "Plik SRT lub VTT do wideo" },
  { id: "summary", title: "Streszczenie", description: "Tematy, ustalenia, zadania" },
  { id: "trim", title: "Wytnij fragment", description: "Zaznaczony zakres czasu" },
  { id: "convert", title: "Konwertuj", description: "Inny format pliku" },
  { id: "extract_audio", title: "Wyodrębnij dźwięk", description: "Ścieżka audio z wideo", video: true },
  { id: "normalize", title: "Wyrównaj głośność", description: "Standard EBU R128" },
  { id: "compress", title: "Kompresja wideo", description: "Mniejszy plik, dobra jakość", video: true },
];

const USTAWIENIA_POCZATKOWE = { tytul: "", kadr: "16:9" as Kadr, przejscie: "fade", nastroj: "korporacyjny" };

function StudioPage({ openConversation }: ModulePageProps) {
  const [tryb, setTryb] = useState<"nagranie" | "montaz">("nagranie");
  const [ujecia, setUjecia] = useState<Ujecie[]>([]);
  const [montaz, setMontaz] = useState(USTAWIENIA_POCZATKOWE);
  const [file, setFile] = useState<FileInfo | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [language, setLanguage] = useState("pl");
  const [subtitleFormat, setSubtitleFormat] = useState<"srt" | "vtt">("srt");
  const [format, setFormat] = useState("mp3");
  const [withNotes, setWithNotes] = useState(true);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const player = useRef<HTMLMediaElement | null>(null);
  const conversation = useConversation(conversationId);

  const video = file ? isVideo(file.mime, file.name) : false;
  const startSeconds = start ? parseTime(start) : null;
  const endSeconds = end ? parseTime(end) : null;
  const rangeError =
    (start && startSeconds === null) || (end && endSeconds === null)
      ? "Nieprawidłowy czas – użyj zapisu m:ss lub h:mm:ss."
      : startSeconds !== null && endSeconds !== null && endSeconds <= startSeconds
        ? "Koniec fragmentu musi być po początku."
        : "";

  const markFromPlayer = (which: "start" | "end") => {
    const current = player.current?.currentTime ?? 0;
    (which === "start" ? setStart : setEnd)(formatTime(current));
  };

  const wyslij = async (prompt: string, pliki: FileInfo[]) => {
    setStarting(true);
    setError("");
    try {
      if (conversationId) {
        await conversation.send(prompt, pliki);
      } else {
        // Nowa rozmowa: wiadomość wysłana przed podpięciem panelu, który sam podejmie trwające zadanie.
        const id = (await api.createConversation()).id;
        await api.sendMessage(
          id,
          prompt,
          pliki.map((plik) => plik.id),
        );
        setConversationId(id);
      }
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setStarting(false);
    }
  };

  const zlozFilm = async () => {
    if (!ujecia.length || conversation.running || starting) return;
    // Ten sam plik może wystąpić w kilku ujęciach – do rozmowy idzie raz.
    const pliki = ujecia
      .map((ujecie) => ujecie.plik)
      .filter((plik, numer, wszystkie) => wszystkie.findIndex((inny) => inny.id === plik.id) === numer);
    await wyslij(montazPrompt(ujecia, montaz), pliki);
  };

  const run = async (action: StudioAction) => {
    if (!file || conversation.running || starting) return;
    if (action === "trim" && startSeconds === null && endSeconds === null) {
      setError("Zaznacz początek lub koniec fragmentu.");
      return;
    }
    const options: StudioOptions = {
      language,
      subtitleFormat,
      format: action === "trim" ? "" : format,
      start: startSeconds,
      end: endSeconds,
      withNotes,
    };
    await wyslij(studioPrompt(action, options, file.name), [file]);
  };

  const reset = () => {
    setFile(null);
    setConversationId(null);
    setStart("");
    setEnd("");
    setUjecia([]);
    setMontaz(USTAWIENIA_POCZATKOWE);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ModuleHeader
        title="Studio"
        subtitle={
          tryb === "nagranie"
            ? "Nagranie: transkrypcja, napisy, cięcie, konwersja, streszczenie"
            : "Montaż: film ze zdjęć i klipów – ruch kamery, napisy, podkład"
        }
      >
        <div className="flex rounded-xl border border-line p-0.5">
          {(["nagranie", "montaz"] as const).map((pozycja) => (
            <button
              key={pozycja}
              type="button"
              className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                tryb === pozycja ? "bg-accent-soft text-fg" : "text-muted hover:text-fg"
              }`}
              aria-pressed={tryb === pozycja}
              onClick={() => setTryb(pozycja)}
            >
              {pozycja === "nagranie" ? "Nagranie" : "Montaż"}
            </button>
          ))}
        </div>
        {(file || ujecia.length > 0 || conversationId) && (
          <button type="button" className={buttonSecondary} onClick={reset}>
            Od nowa
          </button>
        )}
      </ModuleHeader>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
          <div className="mx-auto max-w-3xl space-y-5">
            <ErrorBanner text={error} onClose={() => setError("")} />
            {tryb === "montaz" ? (
              <MontazPanel
                ujecia={ujecia}
                onZmiana={setUjecia}
                onDodano={(plik) => setUjecia((poprzednie) => [...poprzednie, { plik, sekundy: 4, napis: "", lektor: "", ruch: isVideo(plik.mime, plik.name) ? "brak" : "najazd" }])}
                onBlad={setError}
                ustawienia={montaz}
                onUstawienia={setMontaz}
                onZloz={zlozFilm}
                zajete={conversation.running || starting}
              />
            ) : !file ? (
              // Samo pole na plik zostawiało na ekranie jeden prostokąt i pustkę pod nim —
              // po module nie było widać, że potrafi cokolwiek poza przyjęciem pliku.
              // Wykaz działań stoi więc od razu, zanim jest co przetwarzać.
              <>
                <FileDrop accept={MEDIA_ACCEPT} hint="Nagranie audio lub wideo (MP3, WAV, M4A, MP4, MOV, MKV…)" onUploaded={setFile} onError={setError} />
                <div>
                  <h2 className="text-sm font-medium text-fg">Co Studio zrobi z nagraniem</h2>
                  <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                    {ACTIONS.map((akcja) => (
                      <li key={akcja.id} className="rounded-xl border border-line bg-raised/60 px-4 py-3">
                        <span className="block text-sm font-medium text-fg">{akcja.title}</span>
                        <span className="mt-0.5 block text-xs text-muted">
                          {akcja.description}
                          {akcja.video ? " · tylko wideo" : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-xs text-muted">
                    Wszystko dzieje się po wgraniu pliku: wybierasz działanie, a Nexus wykonuje je
                    w rozmowie obok i oddaje gotowy plik.
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="overflow-hidden rounded-2xl border border-line bg-black/90">
                  {video ? (
                    <video ref={(element) => void (player.current = element)} src={downloadUrl(file, true)} controls className="max-h-[48vh] w-full" />
                  ) : (
                    <div className="bg-raised p-4">
                      <p className="mb-2 truncate text-sm font-medium">{file.name}</p>
                      <audio ref={(element) => void (player.current = element)} src={downloadUrl(file, true)} controls className="w-full" />
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-line p-3">
                  <ScissorsIcon className="mb-2 text-muted" />
                  {(["start", "end"] as const).map((which) => (
                    <label key={which} className="block">
                      <span className={labelClass}>{which === "start" ? "Początek" : "Koniec"}</span>
                      <div className="flex gap-1">
                        <input
                          className={`${inputClass} w-28 font-mono`}
                          value={which === "start" ? start : end}
                          onChange={(event) => (which === "start" ? setStart : setEnd)(event.target.value)}
                          placeholder="m:ss"
                        />
                        <button type="button" className={buttonSecondary} onClick={() => markFromPlayer(which)} title="Ustaw z bieżącej pozycji odtwarzacza">
                          Teraz
                        </button>
                      </div>
                    </label>
                  ))}
                  <p className={`basis-full text-xs ${rangeError ? "text-danger" : "text-muted"}`}>
                    {rangeError ||
                      (startSeconds !== null || endSeconds !== null
                        ? `Fragment: ${ffmpegTime(startSeconds ?? 0)} – ${endSeconds !== null ? ffmpegTime(endSeconds) : "koniec"}`
                        : "Zaznacz fragment, aby go wyciąć (odtwarzacz → „Teraz”).")}
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <label className="block">
                    <span className={labelClass}>Język mowy</span>
                    <select className={inputClass} value={language} onChange={(event) => setLanguage(event.target.value)}>
                      {LANGUAGES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className={labelClass}>Format wyniku</span>
                    <select className={inputClass} value={format} onChange={(event) => setFormat(event.target.value)}>
                      {(video ? ["mp4", "webm", "gif", "mp3", "wav", "m4a"] : ["mp3", "wav", "m4a", "ogg", "flac"]).map((item) => (
                        <option key={item} value={item}>
                          {item.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className={labelClass}>Napisy</span>
                    <select className={inputClass} value={subtitleFormat} onChange={(event) => setSubtitleFormat(event.target.value as "srt" | "vtt")}>
                      <option value="srt">SRT</option>
                      <option value="vtt">VTT</option>
                    </select>
                  </label>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={withNotes} onChange={(event) => setWithNotes(event.target.checked)} className="accent-[var(--accent)]" />
                  Streszczenie zapisz też jako notatkę DOCX
                </label>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {ACTIONS.filter((action) => !action.video || video).map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      className="rounded-2xl border border-line px-3.5 py-3 text-left transition-colors hover:border-accent hover:bg-accent-soft/40 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={() => run(action.id)}
                      disabled={conversation.running || starting || (action.id === "trim" && Boolean(rangeError))}
                    >
                      <span className="block text-sm font-medium">{action.title}</span>
                      <span className="block text-xs text-muted">{action.description}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
        {conversationId && (
          <aside className="flex min-h-[50vh] flex-col border-t border-line/60 lg:min-h-0 lg:w-[440px] lg:border-t-0 lg:border-l">
            <div className="flex items-center gap-2 border-b border-line/60 px-4 py-2.5">
              <h2 className="flex-1 text-sm font-medium">
                {tryb === "montaz" ? "Montaż i rozmowa o filmie" : "Wyniki i rozmowa o nagraniu"}
              </h2>
              <button type="button" className="text-sm text-accent hover:underline" onClick={() => openConversation(conversationId)}>
                Otwórz na czacie
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <ChatPanel
                conversation={conversation}
                conversationId={conversationId}
                placeholder={tryb === "montaz" ? "Popraw film, np. „skróć drugie ujęcie do 2 s”" : "Zapytaj o nagranie, np. „kto obiecał wysłać ofertę?”"}
                empty={<p>Wybierz akcję – wynik pojawi się tutaj.</p>}
              />
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

export const module: NexusModule = {
  id: "studio",
  label: "Studio",
  description:
    "Audio i wideo: transkrypcja, napisy, wycinanie fragmentów, konwersja i streszczenia nagrań, " +
    "a także montaż filmu ze zdjęć i klipów – z ruchem kamery, napisami i podkładem muzycznym.",
  icon: FilmIcon,
  order: 66,
  Page: StudioPage,
};

