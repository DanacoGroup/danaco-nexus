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

export function FileCard({
  file,
  onPreview,
  compact = false,
}: {
  file: FileInfo;
  onPreview: (file: FileInfo) => void;
  compact?: boolean;
}) {
  const [thumbnailFailed, setThumbnailFailed] = useState(false);
  const showThumbnail = THUMBNAIL.test(file.mime) && !thumbnailFailed;
  const open = () => (canPreview(file) ? onPreview(file) : window.open(downloadUrl(file), "_blank"));
  return (
    <div
      className={`group flex min-w-0 items-center gap-2.5 rounded-xl border border-line bg-app p-1.5 pr-1 ${
        compact ? "max-w-[260px]" : ""
      }`}
    >
      <button
        type="button"
        className="grid size-11 shrink-0 place-items-center overflow-hidden rounded-lg bg-raised text-muted"
        onClick={open}
        title={canPreview(file) ? "Podgląd" : "Pobierz"}
      >
        {showThumbnail ? (
          <img
            src={thumbnailUrl(file)}
            alt=""
            loading="lazy"
            className="size-full object-cover"
            onError={() => setThumbnailFailed(true)}
          />
        ) : (
          <span className="flex flex-col items-center text-[10px] leading-tight font-semibold">
            <FileIcon size={16} />
            {extension(file.name)}
          </span>
        )}
      </button>
      <button type="button" className="flex min-w-0 flex-1 flex-col text-left" onClick={open}>
        <span className="truncate text-sm font-medium" title={file.name}>
          {file.name}
        </span>
        <span className="text-xs text-muted">{formatSize(file.size)}</span>
      </button>
      <div className="flex shrink-0">
        {canPreview(file) && !compact && (
          <button type="button" className="icon-btn size-8" onClick={() => onPreview(file)} aria-label="Podgląd">
            <EyeIcon size={17} />
          </button>
        )}
        <a className="icon-btn size-8" href={downloadUrl(file)} download={file.name} aria-label="Pobierz">
          <DownloadIcon size={17} />
        </a>
      </div>
    </div>
  );
}
