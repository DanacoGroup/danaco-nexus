// Moduł Obrazy: usuwanie i zmiana tła, gumka obiektów, powiększanie AI – z porównaniem przed/po.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { downloadUrl, type FileInfo } from "../../api";
import { DownloadIcon } from "../../components/icons";
import type { ModulePageProps, NexusModule } from "../registry";
import { BeforeAfter } from "../_tworczy/BeforeAfter";
import { cancelJob, errorText, requestJson, waitForJob, type JobState } from "../_tworczy/http";
import { BrushIcon, ExpandIcon, ImageIcon, LayersIcon, ScissorsIcon } from "../_tworczy/icons";
import { buttonPrimary, buttonSecondary, ErrorBanner, FileDrop, inputClass, labelClass, ModuleHeader, Segmented, Spinner } from "../_tworczy/ui";
import { MaskCanvas, type MaskHandle } from "./MaskCanvas";

type Tool = "remove" | "background" | "erase" | "upscale";
type BackgroundMode = "color" | "gradient" | "image" | "blur" | "transparent";

const IMAGE_ACCEPT = ".jpg,.jpeg,.png,.webp,.bmp,.tif,.tiff,.heic";
const SWATCHES = ["#ffffff", "#f4f4f5", "#111113", "#e8dcc8", "#dbeafe", "#fde2e4", "#d1fae5"];
const BASE = "/api/obrazy";

interface Capabilities {
  remove_background: boolean;
  upscale: boolean;
}

function ImagesPage(_: ModulePageProps) {
  const [source, setSource] = useState<FileInfo | null>(null);
  const [result, setResult] = useState<FileInfo | null>(null);
  const [history, setHistory] = useState<FileInfo[]>([]);
  const [tool, setTool] = useState<Tool>("remove");
  const [mode, setMode] = useState<BackgroundMode>("color");
  const [color, setColor] = useState("#ffffff");
  const [color2, setColor2] = useState("#dbeafe");
  const [angle, setAngle] = useState(90);
  const [blur, setBlur] = useState(18);
  const [backgroundImage, setBackgroundImage] = useState<FileInfo | null>(null);
  const [fast, setFast] = useState(false);
  const [brush, setBrush] = useState(32);
  const [maskEmpty, setMaskEmpty] = useState(true);
  const [scale, setScale] = useState<2 | 3 | 4>(2);
  const [model, setModel] = useState<"photo" | "anime">("photo");
  const [job, setJob] = useState<JobState | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [error, setError] = useState("");
  const mask = useRef<MaskHandle>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    requestJson<Capabilities>("GET", `${BASE}/mozliwosci`)
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
    return () => abort.current?.abort();
  }, []);

  const running = job?.status === "running";
  const unavailable =
    (tool === "remove" && capabilities?.remove_background === false) ||
    (tool === "upscale" && capabilities?.upscale === false);

  const request = (): { endpoint: string; body: Record<string, unknown> } | null => {
    if (!source) return null;
    switch (tool) {
      case "remove":
        return { endpoint: "usun-tlo", body: { file_id: source.id, fast } };
      case "background":
        return {
          endpoint: "zmien-tlo",
          body: {
            file_id: source.id,
            mode,
            color,
            color2,
            angle,
            blur_radius: blur,
            fast,
            background_file_id: mode === "image" ? backgroundImage?.id : undefined,
          },
        };
      case "erase": {
        const data = mask.current?.toDataUrl();
        return data ? { endpoint: "gumka", body: { file_id: source.id, mask: data } } : null;
      }
      case "upscale":
        return { endpoint: "powieksz", body: { file_id: source.id, scale, model } };
    }
  };

  const run = async () => {
    const call = request();
    if (!call) return;
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setError("");
    setResult(null);
    try {
      const started = await requestJson<JobState>("POST", `${BASE}/${call.endpoint}`, call.body);
      setJob(started);
      const final = await waitForJob(BASE, started, setJob, controller.signal);
      if (final.status === "done" && final.result?.files[0]) {
        const file = final.result.files[0];
        setResult(file);
        setHistory((items) => [file, ...items].slice(0, 12));
        setJob(null);
      } else if (final.status === "failed") {
        setError(final.error || "Operacja nie powiodła się.");
      }
    } catch (failure) {
      if ((failure as Error).name !== "AbortError") setError(errorText(failure));
    }
  };

  const cancel = () => {
    if (job) cancelJob(BASE, job.id).catch(() => undefined);
    abort.current?.abort();
    setJob(null);
  };

  const pickSource = (file: FileInfo | null) => {
    setSource(file);
    setResult(null);
    setJob(null);
    mask.current?.clear();
  };

  const tools: { value: Tool; label: string; icon: ReactNode }[] = [
    { value: "remove", label: "Usuń tło", icon: <ScissorsIcon size={15} /> },
    { value: "background", label: "Zmień tło", icon: <LayersIcon size={15} /> },
    { value: "erase", label: "Gumka", icon: <BrushIcon size={15} /> },
    { value: "upscale", label: "Powiększ", icon: <ExpandIcon size={15} /> },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ModuleHeader title="Obrazy" subtitle="Usuwanie i zmiana tła, gumka obiektów, powiększanie AI">
        {source && (
          <button type="button" className={buttonSecondary} onClick={() => pickSource(null)}>
            Nowy obraz
          </button>
        )}
      </ModuleHeader>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
        <div className="mx-auto grid max-w-6xl gap-5 lg:grid-cols-[320px_1fr]">
          <aside className="space-y-4">
            <Segmented label="Narzędzie" value={tool} onChange={setTool} options={tools} />
            {tool === "remove" && (
              <p className="text-sm text-muted">
                Model AI wycina główny obiekt (osobę, produkt, zwierzę) i zapisuje PNG z przezroczystym tłem.
              </p>
            )}
            {tool === "background" && (
              <div className="space-y-3">
                <label className="block">
                  <span className={labelClass}>Nowe tło</span>
                  <select className={inputClass} value={mode} onChange={(event) => setMode(event.target.value as BackgroundMode)}>
                    <option value="color">Jednolity kolor</option>
                    <option value="gradient">Gradient</option>
                    <option value="image">Inne zdjęcie</option>
                    <option value="blur">Rozmyte tło (portret)</option>
                    <option value="transparent">Przezroczyste</option>
                  </select>
                </label>
                {(mode === "color" || mode === "gradient") && (
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-1.5">
                      {SWATCHES.map((swatch) => (
                        <button
                          key={swatch}
                          type="button"
                          aria-label={`Kolor ${swatch}`}
                          className={`size-7 rounded-full border ${color === swatch ? "ring-2 ring-accent" : "border-line"}`}
                          style={{ background: swatch }}
                          onClick={() => setColor(swatch)}
                        />
                      ))}
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <label className="flex items-center gap-2">
                        <input type="color" value={color} onChange={(event) => setColor(event.target.value)} aria-label="Kolor" />
                        {mode === "gradient" ? "Początek" : "Kolor"}
                      </label>
                      {mode === "gradient" && (
                        <label className="flex items-center gap-2">
                          <input type="color" value={color2} onChange={(event) => setColor2(event.target.value)} aria-label="Koniec gradientu" />
                          Koniec
                        </label>
                      )}
                    </div>
                    {mode === "gradient" && (
                      <label className="block text-sm">
                        <span className={labelClass}>Kierunek: {angle}°</span>
                        <input type="range" min={0} max={360} step={15} value={angle} onChange={(event) => setAngle(Number(event.target.value))} className="w-full accent-[var(--accent)]" />
                      </label>
                    )}
                  </div>
                )}
                {mode === "blur" && (
                  <label className="block text-sm">
                    <span className={labelClass}>Siła rozmycia: {blur}</span>
                    <input type="range" min={2} max={80} value={blur} onChange={(event) => setBlur(Number(event.target.value))} className="w-full accent-[var(--accent)]" />
                  </label>
                )}
                {mode === "image" &&
                  (backgroundImage ? (
                    <div className="flex items-center gap-2 text-sm">
                      <img src={downloadUrl(backgroundImage, true)} alt="Nowe tło" className="size-14 rounded-lg object-cover" />
                      <span className="min-w-0 flex-1 truncate">{backgroundImage.name}</span>
                      <button type="button" className={buttonSecondary} onClick={() => setBackgroundImage(null)}>
                        Zmień
                      </button>
                    </div>
                  ) : (
                    <FileDrop compact accept={IMAGE_ACCEPT} hint="Zdjęcie nowego tła" onUploaded={setBackgroundImage} onError={setError} />
                  ))}
              </div>
            )}
            {tool === "erase" && (
              <div className="space-y-3 text-sm">
                <p className="text-muted">Zamaluj pędzlem obiekt do usunięcia (napis, przewód, przypadkową osobę) – miejsce wypełni tło z otoczenia.</p>
                <label className="block">
                  <span className={labelClass}>Pędzel: {brush} px</span>
                  <input type="range" min={6} max={120} value={brush} onChange={(event) => setBrush(Number(event.target.value))} className="w-full accent-[var(--accent)]" />
                </label>
                <button type="button" className={buttonSecondary} onClick={() => mask.current?.clear()} disabled={maskEmpty}>
                  Wyczyść zaznaczenie
                </button>
              </div>
            )}
            {tool === "upscale" && (
              <div className="space-y-3">
                <Segmented
                  label="Powiększenie"
                  value={String(scale) as "2" | "3" | "4"}
                  onChange={(value) => setScale(Number(value) as 2 | 3 | 4)}
                  options={[
                    { value: "2", label: "×2" },
                    { value: "3", label: "×3" },
                    { value: "4", label: "×4" },
                  ]}
                />
                <Segmented
                  label="Rodzaj obrazu"
                  value={model}
                  onChange={setModel}
                  options={[
                    { value: "photo", label: "Zdjęcie" },
                    { value: "anime", label: "Grafika / rysunek" },
                  ]}
                />
                <p className="text-sm text-muted">Real-ESRGAN działa na procesorze – duże zdjęcie może się przetwarzać kilka minut.</p>
              </div>
            )}
            {(tool === "remove" || (tool === "background" && mode !== "transparent")) && (
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" checked={fast} onChange={(event) => setFast(event.target.checked)} className="mt-1 accent-[var(--accent)]" />
                <span>
                  Tryb szybki <span className="text-muted">– kilka sekund zamiast ok. minuty, mniej dokładne krawędzie</span>
                </span>
              </label>
            )}
            {unavailable && (
              <p className="rounded-xl border border-line bg-raised px-3 py-2 text-sm text-muted">
                To narzędzie jest chwilowo niedostępne na serwerze.
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              {running ? (
                <>
                  <Spinner label={job?.progress || "Przetwarzanie…"} />
                  <button type="button" className={buttonSecondary} onClick={cancel}>
                    Anuluj
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className={buttonPrimary}
                  onClick={run}
                  disabled={!source || unavailable || (tool === "erase" && maskEmpty) || (tool === "background" && mode === "image" && !backgroundImage)}
                >
                  Wykonaj
                </button>
              )}
            </div>
            <ErrorBanner text={error} onClose={() => setError("")} />
            {history.length > 0 && (
              <div>
                <span className={labelClass}>Wyniki tej sesji</span>
                <div className="grid grid-cols-4 gap-2">
                  {history.map((file) => (
                    <button
                      key={file.id}
                      type="button"
                      title={`${file.name} – użyj jako źródła`}
                      className="aspect-square overflow-hidden rounded-lg border border-line hover:border-accent"
                      onClick={() => pickSource(file)}
                    >
                      <img src={downloadUrl(file, true)} alt={file.name} className="h-full w-full object-cover" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </aside>
          <section className="min-w-0">
            {!source ? (
              <FileDrop accept={IMAGE_ACCEPT} hint="Przeciągnij zdjęcie albo wybierz plik (JPG, PNG, WEBP, HEIC)" onUploaded={pickSource} onError={setError} />
            ) : result ? (
              <div className="space-y-3">
                <BeforeAfter before={downloadUrl(source, true)} after={downloadUrl(result, true)} alt={source.name} />
                <div className="flex flex-wrap justify-center gap-2">
                  <a className={buttonPrimary} href={downloadUrl(result)} download={result.name}>
                    <DownloadIcon size={16} /> Pobierz {result.name}
                  </a>
                  <button type="button" className={buttonSecondary} onClick={() => pickSource(result)}>
                    Edytuj dalej wynik
                  </button>
                  <button type="button" className={buttonSecondary} onClick={() => setResult(null)}>
                    Wróć do oryginału
                  </button>
                </div>
              </div>
            ) : tool === "erase" ? (
              <MaskCanvas ref={mask} src={downloadUrl(source, true)} brush={brush} onChange={setMaskEmpty} />
            ) : (
              <img src={downloadUrl(source, true)} alt={source.name} className="mx-auto block max-h-[62vh] max-w-full rounded-2xl border border-line" />
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export const module: NexusModule = {
  id: "obrazy",
  label: "Obrazy",
  description: "Usuwanie i zmiana tła, gumka obiektów, powiększanie AI z porównaniem przed/po.",
  icon: ImageIcon,
  order: 62,
  Page: ImagesPage,
};
