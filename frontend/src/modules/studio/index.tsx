// Moduł Studio: nagrania audio i wideo – odtwarzacz z zaznaczaniem fragmentu, transkrypcja, napisy,
// wycinanie, konwersja i streszczenie. Akcje wykonuje asystent w rozmowie widocznej obok.

import { useRef, useState } from "react";
import { api, downloadUrl, type FileInfo } from "../../api";
import type { ModulePageProps, NexusModule } from "../registry";
import { ChatPanel } from "../_tworczy/ChatPanel";
import { errorText } from "../_tworczy/http";
import { FilmIcon, ScissorsIcon } from "../_tworczy/icons";
import { ffmpegTime, formatTime, isVideo, parseTime, studioPrompt, type StudioAction, type StudioOptions } from "../_tworczy/logic";
import { buttonSecondary, ErrorBanner, FileDrop, inputClass, labelClass, ModuleHeader } from "../_tworczy/ui";
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

function StudioPage({ openConversation }: ModulePageProps) {
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
    setStarting(true);
    setError("");
    try {
      const prompt = studioPrompt(action, options, file.name);
      if (conversationId) {
        await conversation.send(prompt, [file]);
      } else {
        // Nowa rozmowa: wiadomość wysłana przed podpięciem panelu, który sam podejmie trwające zadanie.
        const id = (await api.createConversation()).id;
        await api.sendMessage(id, prompt, [file.id]);
        setConversationId(id);
      }
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setStarting(false);
    }
  };

  const reset = () => {
    setFile(null);
    setConversationId(null);
    setStart("");
    setEnd("");
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ModuleHeader title="Studio" subtitle="Audio i wideo: transkrypcja, napisy, cięcie, konwersja, streszczenie">
        {file && (
          <button type="button" className={buttonSecondary} onClick={reset}>
            Nowe nagranie
          </button>
        )}
      </ModuleHeader>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
          <div className="mx-auto max-w-3xl space-y-5">
            <ErrorBanner text={error} onClose={() => setError("")} />
            {!file ? (
              <FileDrop accept={MEDIA_ACCEPT} hint="Nagranie audio lub wideo (MP3, WAV, M4A, MP4, MOV, MKV…)" onUploaded={setFile} onError={setError} />
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
              <h2 className="flex-1 text-sm font-medium">Wyniki i rozmowa o nagraniu</h2>
              <button type="button" className="text-sm text-accent hover:underline" onClick={() => openConversation(conversationId)}>
                Otwórz na czacie
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <ChatPanel
                conversation={conversation}
                conversationId={conversationId}
                placeholder="Zapytaj o nagranie, np. „kto obiecał wysłać ofertę?”"
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
  description: "Audio i wideo: transkrypcja, napisy, wycinanie fragmentów, konwersja i streszczenia nagrań.",
  icon: FilmIcon,
  order: 66,
  Page: StudioPage,
};

