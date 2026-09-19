// Czytanie wiadomości: nagłówki, załączniki i treść HTML w izolowanym drzewie (Shadow DOM).

import { useEffect, useMemo, useRef, useState } from "react";
import { DownloadIcon, FileIcon, SparkIcon } from "../../components/icons";
import { formatSize } from "../../runState";
import { BackIcon, ImageIcon, ReplyIcon, StarIcon } from "../_biuro/icons";
import { attachmentUrl, formatAddress, imageProxyUrl, type MailMessage } from "./api";
import { EMAIL_BASE_STYLE, sanitizeEmailHtml } from "./sanitize";
import { buttonClass } from "../_biuro/ui";

function EmailHtml({ html }: { html: string }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const root = element.shadowRoot ?? element.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${EMAIL_BASE_STYLE}</style><div class="nexus-mail">${html}</div>`;
  }, [html]);
  return <div ref={host} className="overflow-hidden rounded-xl border border-line" />;
}

export function MessageView({
  message,
  flagged,
  onBack,
  onReply,
  onReplyWithNexus,
  onToggleFlag,
  onMarkUnread,
}: {
  message: MailMessage;
  flagged: boolean;
  onBack: () => void;
  onReply: () => void;
  onReplyWithNexus: () => void;
  onToggleFlag: () => void;
  onMarkUnread: () => void;
}) {
  const [showImages, setShowImages] = useState(false);
  useEffect(() => setShowImages(false), [message.uid, message.folder]);

  const sanitized = useMemo(() => {
    if (!message.html) return null;
    const byCid = new Map(
      message.attachments.filter((item) => item.content_id).map((item) => [item.content_id as string, item.index]),
    );
    return sanitizeEmailHtml(message.html, {
      showImages,
      cidUrl: (cid) => {
        const index = byCid.get(cid);
        return index === undefined ? null : attachmentUrl(message.folder, message.uid, index, true);
      },
      proxyUrl: imageProxyUrl,
    });
  }, [message, showImages]);

  const files = message.attachments.filter((item) => !(item.inline && item.content_id && message.html));
  const date = message.date ? new Date(message.date).toLocaleString("pl-PL", { dateStyle: "full", timeStyle: "short" }) : "";

  return (
    <article className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-1 border-b border-line px-3 py-2">
        <button type="button" className="icon-btn lg:hidden" onClick={onBack} aria-label="Wróć do listy">
          <BackIcon />
        </button>
        <button type="button" className={buttonClass.ghost} onClick={onReply}>
          <ReplyIcon size={17} /> Odpowiedz
        </button>
        <button type="button" className={`${buttonClass.ghost} text-accent`} onClick={onReplyWithNexus}>
          <SparkIcon size={17} /> Odpowiedz z Nexusem
        </button>
        <span className="flex-1" />
        <button type="button" className="icon-btn" onClick={onToggleFlag} aria-label={flagged ? "Usuń oznaczenie ważne" : "Oznacz jako ważne"} aria-pressed={flagged}>
          <StarIcon filled={flagged} className={flagged ? "text-accent" : ""} />
        </button>
        <button type="button" className={buttonClass.ghost} onClick={onMarkUnread}>
          Nieprzeczytana
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        <h2 className="text-xl font-semibold break-words">{message.subject || "(bez tematu)"}</h2>
        <div className="mt-3 space-y-0.5 text-sm">
          <div>
            <span className="text-muted">Od: </span>
            <span className="font-medium">{message.from.map(formatAddress).join(", ")}</span>
          </div>
          {message.to.length > 0 && (
            <div className="text-muted">Do: {message.to.map(formatAddress).join(", ")}</div>
          )}
          {message.cc.length > 0 && <div className="text-muted">DW: {message.cc.map(formatAddress).join(", ")}</div>}
          {date && <div className="text-xs text-muted">{date}</div>}
        </div>

        {files.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-2">
            {files.map((item) => (
              <li key={item.index}>
                <a
                  href={attachmentUrl(message.folder, message.uid, item.index)}
                  className="flex max-w-64 items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm hover:bg-hover"
                >
                  <FileIcon size={18} className="shrink-0 text-muted" />
                  <span className="min-w-0 flex-1 truncate">{item.name}</span>
                  <span className="shrink-0 text-xs text-muted">{formatSize(item.size)}</span>
                  <DownloadIcon size={16} className="shrink-0 text-muted" />
                </a>
              </li>
            ))}
          </ul>
        )}

        {sanitized && sanitized.blockedImages > 0 && !showImages && (
          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-side px-3 py-2 text-sm">
            <ImageIcon size={18} className="text-muted" />
            <span className="min-w-0 flex-1 text-muted">
              Zablokowano obrazy z internetu ({sanitized.blockedImages}) – mogą informować nadawcę o otwarciu wiadomości.
            </span>
            <button type="button" className={buttonClass.secondary} onClick={() => setShowImages(true)}>
              Pokaż obrazy
            </button>
          </div>
        )}

        <div className="mt-4">
          {sanitized ? (
            <EmailHtml html={sanitized.html} />
          ) : (
            <pre className="font-sans text-[15px] leading-relaxed whitespace-pre-wrap break-words">{message.text || "(pusta wiadomość)"}</pre>
          )}
        </div>
      </div>
    </article>
  );
}
