// Wspólny klient HTTP modułów Cloud, Poczta i Kalendarz (sesja przeglądarki + nagłówek CSRF).

import { ApiError } from "../../api";

const APP_HEADER = { "X-Nexus-Request": "1" };

async function errorMessage(response: Response): Promise<string> {
  let message = `Błąd serwera (${response.status})`;
  try {
    const data = await response.json();
    if (typeof data.detail === "string") message = data.detail;
    else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = String(data.detail[0].msg);
  } catch {
    /* odpowiedź bez treści JSON */
  }
  return message;
}

/** Zapytanie JSON do API Nexusa. */
export async function call<T>(method: string, url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? APP_HEADER : { ...APP_HEADER, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  return (await response.json()) as T;
}

/** Parametry adresu (pomija puste wartości). */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "" || value === false) continue;
    search.set(key, value === true ? "1" : String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

/** Wysyła surową treść (fragment pliku) z raportowaniem postępu (0–1). */
export function sendBlob(
  method: string,
  url: string,
  blob: Blob,
  onProgress?: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    xhr.setRequestHeader("X-Nexus-Request", "1");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          resolve(null);
        }
        return;
      }
      let message = `Błąd przesyłania (${xhr.status})`;
      try {
        message = JSON.parse(xhr.responseText).detail ?? message;
      } catch {
        /* odpowiedź bez JSON */
      }
      reject(new ApiError(xhr.status, message));
    };
    xhr.onerror = () => reject(new ApiError(0, "Błąd sieci podczas przesyłania."));
    xhr.onabort = () => reject(new ApiError(0, "Przesyłanie anulowane."));
    if (signal) {
      if (signal.aborted) {
        reject(new ApiError(0, "Przesyłanie anulowane."));
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(blob);
  });
}

/** Komunikat błędu do wyświetlenia. */
export function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
