// Podgląd pliku: obraz, PDF, audio, wideo, tekst.

import { useEffect } from "react";
import { downloadUrl, type FileInfo } from "../api";
import { formatSize } from "../runState";
import { CloseIcon, DownloadIcon } from "./icons";

export function PreviewModal({ file, onClose }: { file: FileInfo; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const url = downloadUrl(file, true);
  const kind = file.mime.split("/")[0];
  let body;
  if (kind === "image") body = <img src={url} alt={file.name} className="max-h-full max-w-full object-contain" />;
  else if (kind === "video") body = <video src={url} controls autoPlay className="max-h-full max-w-full" />;
  else if (kind === "audio") body = <audio src={url} controls autoPlay className="w-full max-w-md" />;
  else body = <iframe src={url} title={file.name} className="size-full rounded-lg bg-white" />;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-0 backdrop-blur-sm md:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={file.name}
      onClick={onClose}
    >
      <div
        className="safe-top flex size-full flex-col overflow-hidden bg-app shadow-2xl md:h-[90vh] md:max-w-5xl md:rounded-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
          <span className="min-w-0 flex-1 truncate text-sm font-medium" title={file.name}>
            {file.name} <span className="font-normal text-muted">· {formatSize(file.size)}</span>
          </span>
          <a className="icon-btn" href={downloadUrl(file)} download={file.name} aria-label="Pobierz">
            <DownloadIcon />
          </a>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zamknij">
            <CloseIcon />
          </button>
        </div>
        <div className="safe-bottom flex min-h-0 flex-1 items-center justify-center bg-side p-2 md:p-4">{body}</div>
      </div>
    </div>
  );
}
