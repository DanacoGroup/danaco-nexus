// Zapytania API powłoki: zadania w toku, powiadomienia push, urządzenia, pliki do pobrania.

import { apiRequest } from "../api";

export interface ActiveTask {
  run_id: string;
  conversation_id: string;
  title: string;
  mode: string;
  status: "queued" | "running";
  created_at: string;
  started_at: string | null;
  tool: string;
}

export interface PushKey {
  available: boolean;
  public_key: string;
  subscriptions: number;
}

export type DeviceKind = "android" | "desktop" | "rozszerzenie" | "inne";

export interface Device {
  id: string;
  name: string;
  kind: DeviceKind;
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
  /** Cofnięcie wyloguje też okno aplikacji, które założyło klucz (telefon, Nexus Desktop). */
  wylogowuje_okno?: boolean;
}

export interface DownloadInfo {
  name: string;
  label: string;
  available: boolean;
  size?: number;
  updated_at?: string;
  sha256?: string;
}

export const startApi = {
  activeTasks: () => apiRequest<ActiveTask[]>("GET", "/api/w-toku"),
  pushKey: () => apiRequest<PushKey>("GET", "/api/push/klucz"),
  pushSubscribe: (subscription: PushSubscriptionJSON, name: string) =>
    apiRequest<{ ok: boolean }>("POST", "/api/push/subskrypcje", { ...subscription, name }),
  pushUnsubscribe: (endpoint: string) => apiRequest<{ ok: boolean }>("POST", "/api/push/wypisz", { endpoint }),
  pushTest: () => apiRequest<{ sent: number; removed: number; failed: number }>("POST", "/api/push/test"),
  devices: () => apiRequest<Device[]>("GET", "/api/urzadzenia"),
  // Klucz z modułu Sprzęt jest dla innego urządzenia: serwer nie wiąże go z sesją tego okna,
  // więc jego cofnięcie nie wyloguje przeglądarki, która go wydała.
  createDevice: (name: string, kind: DeviceKind) =>
    apiRequest<Device & { token: string }>("POST", "/api/urzadzenia", { name, kind, dla_innego_urzadzenia: true }),
  revokeDevice: (id: string) => apiRequest<{ ok: boolean }>("DELETE", `/api/urzadzenia/${id}`),
};

/** Lista instalatorów (publiczna – bez logowania). */
export async function fetchDownloads(): Promise<DownloadInfo[]> {
  const response = await fetch("/pobierz", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as DownloadInfo[];
}
