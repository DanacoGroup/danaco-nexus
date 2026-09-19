// Zapytania JSON modułów twórczych (Strony, Obrazy, Tłumacz, Studio) i odpytywanie zadań w tle.

import { ApiError, type FileInfo } from "../../api";

const APP_HEADER = { "X-Nexus-Request": "1" };

export async function requestJson<T>(method: string, url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? APP_HEADER : { ...APP_HEADER, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    let message = `Błąd serwera (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = String(data.detail[0].msg);
    } catch {
      /* odpowiedź bez treści JSON */
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export interface JobState {
  id: string;
  kind: string;
  status: "running" | "done" | "failed" | "cancelled";
  progress: string;
  error: string;
  result: { summary: string; files: FileInfo[]; data?: unknown } | null;
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Przerwano", "AbortError"));
    });
  });

/** Odpytuje stan zadania modułu aż do zakończenia; `onProgress` dostaje każdy stan pośredni. */
export async function waitForJob(
  base: string,
  job: JobState,
  onProgress: (state: JobState) => void,
  signal?: AbortSignal,
): Promise<JobState> {
  let state = job;
  let delay = 400;
  while (state.status === "running") {
    await sleep(delay, signal);
    state = await requestJson<JobState>("GET", `${base}/zadania/${job.id}`, undefined, signal);
    onProgress(state);
    delay = Math.min(delay * 1.4, 2500);
  }
  return state;
}

export function cancelJob(base: string, jobId: string): Promise<JobState> {
  return requestJson<JobState>("DELETE", `${base}/zadania/${jobId}`);
}

export function errorText(failure: unknown): string {
  return failure instanceof Error ? failure.message : String(failure);
}
