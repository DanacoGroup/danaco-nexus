// Pole wiadomości: tekst, załączniki (przycisk, przeciąganie, wklejanie), wysyłanie i zatrzymywanie.

import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { uploadFile, type FileInfo } from "../api";
import { preferencje } from "../preferencje";
import { formatSize } from "../runState";
import { CloseIcon, FileIcon, MicIcon, PaperclipIcon, SendIcon, StopIcon, WaveIcon } from "./icons";
import { dyktowanieDostepne, useDyktowanie } from "../voice/useDyktowanie";

export const ACCEPTED_FILES =
  ".pdf,.doc,.docx,.odt,.rtf,.xls,.xlsx,.ods,.csv,.ppt,.pptx,.odp,.txt,.md,.html,.jpg,.jpeg,.png,.heic,.tif,.tiff,.bmp,.webp,.gif,.svg,.zip,.mp4,.mov,.mkv,.webm,.mp3,.wav,.m4a,.ogg,.flac";

interface Attachment {
  key: string;
  file: File;
  progress: number;
  status: "uploading" | "done" | "error";
  info?: FileInfo;
  error?: string;
  abort?: () => void;
}

interface Props {
  conversationId: string | null;
  running: boolean;
  onSend: (text: string, files: FileInfo[]) => Promise<boolean>;
  onStop: () => void;
  droppedFiles: File[];
  onDroppedConsumed: () => void;
  prefill: string;
  onPrefillConsumed: () => void;
  onVoice?: () => void;
}

let counter = 0;

export function Composer(props: Props) {
  const { conversationId, running, onSend, onStop, droppedFiles, onDroppedConsumed, prefill, onPrefillConsumed, onVoice } =
    props;
  const [text, setText] = useState("");
  // Dyktowanie dopisuje rozpoznaną wypowiedź do tego, co już jest w polu — tekst
  // zostaje do poprawienia przed wysłaniem, w odróżnieniu od rozmowy głosowej.
  const dyktowanie = useDyktowanie((rozpoznane) =>
    setText((biezacy) => (biezacy.trim() ? `${biezacy.trimEnd()} ${rozpoznane}` : rozpoznane)),
  );
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [sending, setSending] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);

  const addFiles = (files: File[]) => {
    for (const file of files) {
      const key = `a${++counter}`;
      const upload = uploadFile(file, conversationId, (progress) =>
        setAttachments((items) => items.map((item) => (item.key === key ? { ...item, progress } : item))),
      );
      setAttachments((items) => [...items, { key, file, progress: 0, status: "uploading", abort: upload.abort }]);
      upload.promise
        .then((info) =>
          setAttachments((items) =>
            items.map((item) => (item.key === key ? { ...item, status: "done", info, progress: 1 } : item)),
          ),
        )
        .catch((error: Error) =>
          setAttachments((items) =>
            items.map((item) => (item.key === key ? { ...item, status: "error", error: error.message } : item)),
          ),
        );
    }
  };

  useEffect(() => {
    if (droppedFiles.length) {
      addFiles(droppedFiles);
      onDroppedConsumed();
    }
  }, [droppedFiles]);

  useEffect(() => {
    if (prefill) {
      setText(prefill);
      onPrefillConsumed();
      textarea.current?.focus();
    }
  }, [prefill]);

  const resize = () => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    if (element.value) element.style.height = `${Math.min(element.scrollHeight, 260)}px`;
  };

  useEffect(resize, [text]);

  // Szerokość pola zmienia się z układem (obrót telefonu, panel boczny) – wysokość liczona na nowo.
  useEffect(() => {
    const element = textarea.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    let width = element.clientWidth;
    const observer = new ResizeObserver(() => {
      if (element.clientWidth !== width) {
        width = element.clientWidth;
        resize();
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const uploading = attachments.some((item) => item.status === "uploading");
  const ready = attachments.filter((item) => item.status === "done" && item.info);
  const canSend = !running && !sending && !uploading && (text.trim().length > 0 || ready.length > 0);

  const submit = async () => {
    if (!canSend) return;
    setSending(true);
    const ok = await onSend(text.trim(), ready.map((item) => item.info as FileInfo));
    setSending(false);
    if (ok) {
      setText("");
      setAttachments([]);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Na telefonie Enter dodaje nową linię; wysyła przycisk.
    if (event.key !== "Enter" || event.nativeEvent.isComposing || window.innerWidth <= 700) return;
    // Ustawienie konta („Ustawienia → Praca”): Enter albo Ctrl/⌘ + Enter. Kto pisze
    // wiadomości wielolinijkowe, nie chce ich wysyłać połową z nich.
    const ctrlem = preferencje().wysylka === "ctrl-enter";
    const wyslij = ctrlem ? event.ctrlKey || event.metaKey : !event.shiftKey;
    if (!wyslij) return;
    event.preventDefault();
    void submit();
  };

  const onPaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files);
    if (files.length) {
      event.preventDefault();
      addFiles(files);
    }
  };

  const remove = (item: Attachment) => {
    item.abort?.();
    setAttachments((items) => items.filter((entry) => entry.key !== item.key));
  };

  return (
    <div className="rounded-2xl border border-line bg-raised shadow-sm transition-colors focus-within:border-line-strong dark:shadow-black/20">
      {dyktowanie.blad && (
        <button
          type="button"
          role="alert"
          onClick={dyktowanie.wyczyscBlad}
          className="w-full rounded-t-2xl bg-danger-soft px-4 py-2 text-left text-sm text-danger"
        >
          {dyktowanie.blad}
        </button>
      )}
      {dyktowanie.stan === "nagrywanie" && (
        <p className="px-4 pt-2 text-sm text-muted" role="status" aria-live="polite">
          Słucham — mów, a potem naciśnij mikrofon jeszcze raz.
        </p>
      )}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-3 pt-3">
          {attachments.map((item) => (
            <div
              key={item.key}
              title={item.error ?? item.file.name}
              className={`relative flex max-w-[240px] items-center gap-2 overflow-hidden rounded-xl border py-1.5 pr-1 pl-2.5 text-sm ${
                item.status === "error" ? "border-danger/50 bg-danger-soft text-danger" : "border-line bg-app"
              }`}
            >
              <FileIcon size={16} className="shrink-0 text-muted" />
              <span className="min-w-0 truncate">{item.file.name}</span>
              <span className="shrink-0 text-xs text-muted">
                {item.status === "uploading"
                  ? `${Math.round(item.progress * 100)}%`
                  : item.status === "error"
                    ? "błąd"
                    : formatSize(item.file.size)}
              </span>
              <button type="button" className="icon-btn size-6" onClick={() => remove(item)} aria-label="Usuń załącznik">
                <CloseIcon size={14} />
              </button>
              {item.status === "uploading" && (
                <span
                  className="absolute bottom-0 left-0 h-0.5 bg-accent-fill transition-[width]"
                  style={{ width: `${item.progress * 100}%` }}
                />
              )}
            </div>
          ))}
        </div>
      )}
      <div className="flex items-end gap-1.5 p-2">
        <button
          type="button"
          className="icon-btn size-10 rounded-full"
          onClick={() => picker.current?.click()}
          aria-label="Dodaj pliki"
          title="Dodaj pliki"
        >
          <PaperclipIcon />
        </button>
        <input
          ref={picker}
          type="file"
          multiple
          hidden
          aria-label="Wybierz pliki do wysłania"
          accept={ACCEPTED_FILES}
          onChange={(event) => {
            addFiles(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        <textarea
          ref={textarea}
          rows={1}
          value={text}
          aria-label="Wiadomość do Nexusa"
          placeholder="Napisz do Nexusa…"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          className="max-h-[260px] min-h-10 flex-1 resize-none bg-transparent px-1 py-2 leading-6 text-fg outline-none placeholder:truncate placeholder:text-muted"
        />
        {dyktowanieDostepne() && !running && (
          <button
            type="button"
            className={`icon-btn size-10 rounded-full ${
              dyktowanie.stan === "nagrywanie" ? "glow-ai bg-danger-soft text-danger" : ""
            }`}
            onClick={dyktowanie.przelacz}
            disabled={dyktowanie.stan === "rozpoznawanie"}
            aria-label={dyktowanie.stan === "nagrywanie" ? "Zakończ dyktowanie" : "Dyktuj wiadomość"}
            title={dyktowanie.stan === "nagrywanie" ? "Zakończ dyktowanie" : "Dyktuj wiadomość"}
          >
            {dyktowanie.stan === "rozpoznawanie" ? <span className="spinner" /> : <MicIcon />}
          </button>
        )}
        {onVoice && !running && (
          <button
            type="button"
            className="icon-btn size-10 rounded-full"
            onClick={onVoice}
            aria-label="Rozmowa głosowa"
            title="Rozmowa głosowa"
          >
            <WaveIcon />
          </button>
        )}
        {running ? (
          <button
            type="button"
            className="grid size-10 shrink-0 place-items-center rounded-full bg-fg text-app transition-opacity hover:opacity-85"
            onClick={onStop}
            aria-label="Zatrzymaj"
          >
            <StopIcon size={16} />
          </button>
        ) : (
          <button
            type="button"
            // Aurora na przycisku wysyłki oznacza „gotowe do wysłania” (DESIGN_SYSTEM, rozdz. 4.2).
            className={`grid size-10 shrink-0 place-items-center rounded-full transition-all ${
              canSend ? "aurora-tlo glow-ai text-white hover:brightness-110" : "bg-line-strong text-muted"
            }`}
            disabled={!canSend}
            onClick={() => void submit()}
            aria-label="Wyślij"
          >
            {sending ? <span className="spinner" /> : <SendIcon size={18} />}
          </button>
        )}
      </div>
    </div>
  );
}
