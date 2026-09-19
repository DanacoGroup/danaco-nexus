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
  let body;
  if (file.mime.startsWith("image/")) body = <img src={url} alt={file.name} />;
  else if (file.mime.startsWith("video/")) body = <video src={url} controls autoPlay />;
  else if (file.mime.startsWith("audio/")) body = <audio src={url} controls autoPlay />;
  else body = <iframe src={url} title={file.name} />;

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={file.name} onClick={onClose}>
      <div className="modal-panel" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title" title={file.name}>
            {file.name} <span className="muted">· {formatSize(file.size)}</span>
          </span>
          <a className="icon-button" href={downloadUrl(file)} download={file.name} aria-label="Pobierz">
            <DownloadIcon />
          </a>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Zamknij">
            <CloseIcon />
          </button>
        </div>
        <div className={`modal-body ${file.mime.split("/")[0]}`}>{body}</div>
      </div>
    </div>
  );
}
