// Odtwarzanie mowy asystenta przez element <audio>.
//
// Element audio (w przeciwieństwie do AudioContext) sam dopasowuje się do zmiany
// urządzenia wyjściowego – np. słuchawek Bluetooth przełączanych w tryb zestawu
// głośnomówiącego po włączeniu mikrofonu – bez spowolnienia i trzasków.
// Na iPhonie element musi zostać „odblokowany” odtworzeniem w obsłudze dotknięcia.

const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";

let element: HTMLAudioElement | null = null;
let currentUrl = "";

function audio(): HTMLAudioElement {
  if (!element) {
    element = new Audio();
    element.preload = "auto";
  }
  return element;
}

/** Wywoływane synchronicznie w obsłudze kliknięcia (odblokowanie odtwarzania na iOS). */
export function unlockAudio(): void {
  const player = audio();
  // Adres blob: (dozwolony przez CSP strony), nie data:.
  const bytes = Uint8Array.from(atob(SILENCE.split(",")[1]), (char) => char.charCodeAt(0));
  if (currentUrl) URL.revokeObjectURL(currentUrl);
  currentUrl = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
  player.src = currentUrl;
  void player.play().catch(() => undefined);
}

/** Odtwarza plik WAV; kończy się po odtworzeniu, błędzie albo przerwaniu. */
export function playWav(data: ArrayBuffer, signal: AbortSignal): Promise<void> {
  const player = audio();
  if (currentUrl) URL.revokeObjectURL(currentUrl);
  currentUrl = URL.createObjectURL(new Blob([data], { type: "audio/wav" }));
  player.src = currentUrl;
  return new Promise<void>((resolve, reject) => {
    const finish = (error?: unknown) => {
      player.onended = null;
      player.onerror = null;
      signal.removeEventListener("abort", onAbort);
      if (error) reject(error);
      else resolve();
    };
    const onAbort = () => {
      player.pause();
      finish(new DOMException("Przerwano", "AbortError"));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener("abort", onAbort);
    player.onended = () => finish();
    player.onerror = () => finish(new Error("Nie udało się odtworzyć odpowiedzi."));
    player.play().catch((error: unknown) => finish(error));
  });
}

/** Zatrzymuje bieżące odtwarzanie. */
export function stopAudio(): void {
  if (element) {
    element.pause();
    element.currentTime = 0;
  }
}
