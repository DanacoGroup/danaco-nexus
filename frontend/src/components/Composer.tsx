// Pole wiadomości: tekst, załączniki (przycisk, przeciąganie, wklejanie), wysyłanie i zatrzymywanie.

import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { uploadFile, type FileInfo } from "../api";
import { formatSize } from "../runState";
import { CloseIcon, FileIcon, PaperclipIcon, SendIcon, StopIcon } from "./icons";

export const ACCEPTED_FILES =
  ".pdf,.doc,.docx,.odt,.rtf,.xls,.xlsx,.ods,.csv,.ppt,.pptx,.odp,.txt,.md,.html,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp,.gif,.svg,.zip,.mp4,.mov,.mkv,.webm,.mp3,.wav,.m4a,.ogg,.flac";

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
}

let counter = 0;

export function Composer(props: Props) {
  const { conversationId, running, onSend, onStop, droppedFiles, onDroppedConsumed, prefill, onPrefillConsumed } = props;
  const [text, setText] = useState("");
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
          setAttachments((items) => items.map((item) => (item.key === key ? { ...item, status: "done", info, progress: 1 } : item))),
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

  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 260)}px`;
  }, [text]);

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
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && window.innerWidth > 700) {
      event.preventDefault();
      void submit();
    }
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
    <div className="composer">
      {attachments.length > 0 && (
        <div className="attachments">
          {attachments.map((item) => (
            <div key={item.key} className={`attachment ${item.status}`} title={item.error ?? item.file.name}>
              <FileIcon size={16} />
              <span className="attachment-name">{item.file.name}</span>
              <span className="attachment-size">
                {item.status === "uploading"
                  ? `${Math.round(item.progress * 100)}%`
                  : item.status === "error"
                    ? "błąd"
                    : formatSize(item.file.size)}
              </span>
              <button type="button" className="attachment-remove" onClick={() => remove(item)} aria-label="Usuń załącznik">
                <CloseIcon size={14} />
              </button>
              {item.status === "uploading" && <span className="attachment-progress" style={{ width: `${item.progress * 100}%` }} />}
            </div>
          ))}
        </div>
      )}
      <div className="composer-row">
        <button type="button" className="icon-button attach" onClick={() => picker.current?.click()} aria-label="Dodaj pliki">
          <PaperclipIcon />
        </button>
        <input
          ref={picker}
          type="file"
          multiple
          hidden
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
          placeholder="Napisz, co mam zrobić z plikami…"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
        />
        {running ? (
          <button type="button" className="send-button stop" onClick={onStop} aria-label="Zatrzymaj">
            <StopIcon size={18} />
          </button>
        ) : (
          <button type="button" className="send-button" disabled={!canSend} onClick={() => void submit()} aria-label="Wyślij">
            {sending ? <span className="spinner light" /> : <SendIcon size={18} />}
          </button>
        )}
      </div>
    </div>
  );
}
