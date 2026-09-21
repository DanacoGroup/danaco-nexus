// Panel rozmowy osadzony w module: historia tur, pole wiadomości z załącznikami, zatrzymywanie.

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { uploadFile, type FileInfo } from "../../api";
import { CloseIcon, PaperclipIcon, SendIcon, StopIcon } from "../../components/icons";
import { PreviewModal } from "../../components/PreviewModal";
import { AssistantMessage, UserMessage } from "../../components/Turns";
import type { ConversationState } from "./useConversation";
import { ErrorBanner } from "./ui";

interface Props {
  conversation: ConversationState;
  conversationId: string | null;
  placeholder: string;
  empty?: ReactNode;
  /** Przekształca treść wiadomości przed wysłaniem (np. dodaje znacznik strony). */
  prepare?: (text: string) => string;
  /** Przekształca treść wiadomości użytkownika do wyświetlenia. */
  display?: (text: string) => string;
  accept?: string;
}

export function ChatPanel({ conversation, conversationId, placeholder, empty, prepare, display, accept }: Props) {
  const { detail, running, error, clearError, send, stop } = conversation;
  const [text, setText] = useState("");
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [uploading, setUploading] = useState(0);
  const [preview, setPreview] = useState<FileInfo | null>(null);
  const [localError, setLocalError] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const stick = useRef(true);

  useEffect(() => {
    const element = scroller.current;
    if (element && stick.current) element.scrollTop = element.scrollHeight;
  }, [detail]);

  const submit = async () => {
    const message = text.trim();
    if ((!message && !files.length) || running || uploading || !conversationId) return;
    stick.current = true;
    if (await send(prepare ? prepare(message) : message, files)) {
      setText("");
      setFiles([]);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const attach = (list: FileList | null) => {
    for (const file of Array.from(list ?? [])) {
      setUploading((count) => count + 1);
      uploadFile(file, conversationId, () => undefined)
        .promise.then((info) => setFiles((current) => [...current, info]))
        .catch((failure: Error) => setLocalError(failure.message))
        .finally(() => setUploading((count) => count - 1));
    }
  };

  const turns = detail?.turns ?? [];
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        ref={scroller}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-4 md:px-4"
        onScroll={(event) => {
          const element = event.currentTarget;
          stick.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
        }}
      >
        {turns.length === 0 ? (
          <div className="flex h-full items-center justify-center px-4 text-center text-sm text-muted">{empty}</div>
        ) : (
          <div className="space-y-6">
            {turns.map((turn, index) =>
              turn.type === "user" ? (
                <UserMessage
                  key={`u${turn.id}`}
                  turn={display ? { ...turn, text: display(turn.text) } : turn}
                  onPreview={setPreview}
                />
              ) : (
                <AssistantMessage key={`a${turn.run_id ?? index}-${index}`} turn={turn} onPreview={setPreview} />
              ),
            )}
          </div>
        )}
      </div>
      <div className="space-y-2 border-t border-line/60 p-3">
        <ErrorBanner
          text={error || localError}
          onClose={() => {
            clearError();
            setLocalError("");
          }}
        />
        {(files.length > 0 || uploading > 0) && (
          <div className="flex flex-wrap gap-1.5">
            {files.map((file) => (
              <span key={file.id} className="inline-flex max-w-[220px] items-center gap-1 rounded-lg bg-raised px-2 py-1 text-xs">
                <span className="truncate">{file.name}</span>
                <button
                  type="button"
                  aria-label={`Usuń ${file.name}`}
                  className="text-muted hover:text-fg"
                  onClick={() => setFiles((current) => current.filter((item) => item.id !== file.id))}
                >
                  <CloseIcon size={13} />
                </button>
              </span>
            ))}
            {uploading > 0 && <span className="px-2 py-1 text-xs text-muted">Przesyłanie ({uploading})…</span>}
          </div>
        )}
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-raised/50 p-1.5 focus-within:border-accent">
          {accept && (
            <>
              <button type="button" className="icon-btn" aria-label="Dodaj plik" onClick={() => picker.current?.click()}>
                <PaperclipIcon size={18} />
              </button>
              <input
                ref={picker}
                type="file"
                multiple
                accept={accept}
                className="hidden"
                aria-label="Wybierz pliki do rozmowy"
                onChange={(event) => {
                  attach(event.target.files);
                  event.target.value = "";
                }}
              />
            </>
          )}
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            placeholder={placeholder}
            aria-label="Wiadomość"
            className="max-h-48 min-h-[44px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted"
          />
          {running ? (
            <button type="button" className="icon-btn bg-fg text-app hover:bg-fg/85 hover:text-app" onClick={stop} aria-label="Zatrzymaj">
              <StopIcon size={16} />
            </button>
          ) : (
            <button
              type="button"
              className="icon-btn bg-accent-fill text-on-accent hover:bg-accent-fill-hover hover:text-on-accent"
              onClick={submit}
              disabled={(!text.trim() && !files.length) || uploading > 0 || !conversationId}
              aria-label="Wyślij"
            >
              <SendIcon size={16} />
            </button>
          )}
        </div>
      </div>
      {preview && <PreviewModal file={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
