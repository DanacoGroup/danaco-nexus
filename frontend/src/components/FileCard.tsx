// Karta pliku: miniatura, nazwa, rozmiar, podgląd i pobieranie.

import { useState } from "react";
import { downloadUrl, thumbnailUrl, type FileInfo } from "../api";
import { formatSize } from "../runState";
import { DownloadIcon, EyeIcon, FileIcon } from "./icons";

const PREVIEWABLE = /^(image\/|application\/pdf|audio\/|video\/|text\/plain)/;
const THUMBNAIL = /^(image\/(jpeg|png|webp|gif|tiff|bmp)|application\/pdf)/;

export function canPreview(file: FileInfo): boolean {
  return PREVIEWABLE.test(file.mime) && file.mime !== "image/svg+xml";
}

function extension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1).toUpperCase().slice(0, 4) : "PLIK";
}

export function FileCard({ file, onPreview, compact = false }: { file: FileInfo; onPreview: (file: FileInfo) => void; compact?: boolean }) {
  const [thumbnailFailed, setThumbnailFailed] = useState(false);
  const showThumbnail = THUMBNAIL.test(file.mime) && !thumbnailFailed;
  return (
    <div className={`file-card${compact ? " compact" : ""}`}>
      <button
        type="button"
        className="file-thumb"
        onClick={() => (canPreview(file) ? onPreview(file) : window.open(downloadUrl(file), "_blank"))}
        title={canPreview(file) ? "Podgląd" : "Pobierz"}
      >
        {showThumbnail ? (
          <img src={thumbnailUrl(file)} alt="" loading="lazy" onError={() => setThumbnailFailed(true)} />
        ) : (
          <span className="file-ext">
            <FileIcon size={18} />
            {extension(file.name)}
          </span>
        )}
      </button>
      <div className="file-meta">
        <span className="file-name" title={file.name}>
          {file.name}
        </span>
        <span className="file-size">{formatSize(file.size)}</span>
      </div>
      <div className="file-actions">
        {canPreview(file) && (
          <button type="button" className="icon-button" onClick={() => onPreview(file)} aria-label="Podgląd">
            <EyeIcon size={17} />
          </button>
        )}
        <a className="icon-button" href={downloadUrl(file)} download={file.name} aria-label="Pobierz">
          <DownloadIcon size={17} />
        </a>
      </div>
    </div>
  );
}
