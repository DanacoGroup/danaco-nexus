// Urządzenia: klucze dla rozszerzenia, Nexus Desktop i urządzeń własnych, lista i cofanie kluczy
// (także tych, które telefon i Nexus Desktop zakładają same z sesji okna), powiadomienia push
// na tym urządzeniu i instalatory do pobrania. Kod QR niesie adres serwera i klucz, ale dziś
// nie czyta go żaden klient Nexusa (docs/moduly/start.md, rozdz. „Urządzenia”).

import { useCallback, useEffect, useState, type ComponentType, type FormEvent } from "react";
import { ApiError } from "../../api";
import { AlertIcon, CheckIcon, CloseIcon, DownloadIcon, TrashIcon } from "../../components/icons";
import { formatSize } from "../../runState";
import { BellIcon, CopyIcon, DevicesIcon, KeyIcon, PhoneIcon, PuzzleIcon, WindowsIcon, type IconProps } from "../../shell/icons";
import { disablePush, enablePush, pushStatus, type PushStatus } from "../../shell/push";
import { fetchDownloads, startApi, type Device, type DeviceKind, type DownloadInfo } from "../../shell/startApi";
import { QrCode } from "./Qr";

export const KIND_LABELS: Record<DeviceKind, string> = {
  android: "Telefon z Androidem",
  desktop: "Nexus Desktop (Windows)",
  rozszerzenie: "Rozszerzenie przeglądarki",
  inne: "Inne urządzenie",
};

const KIND_ICONS: Record<DeviceKind, ComponentType<IconProps>> = {
  android: PhoneIcon,
  desktop: WindowsIcon,
  rozszerzenie: PuzzleIcon,
  inne: KeyIcon,
};

export const KIND_HINTS: Record<DeviceKind, string> = {
  // Telefon nie ma ekranu „Połącz z serwerem”, pola na klucz ani czytnika kodów: aplikacja
  // Android zakłada klucz sama, przy pierwszym zalogowaniu w oknie Nexusa. Podpowiedź mówiła
  // co innego, więc użytkownik szukał w aplikacji funkcji, której tam nie ma.
  android: "Aplikacji na telefonie nie podaje się klucza — wystarczy zalogować się w niej, a klucz urządzenia powstanie sam. Ten klucz nie będzie potrzebny, możesz go cofnąć.",
  // Pulpit ma prostszą drogę: „Połącz komputer” robi klucz z sesji okna. Ręczne wklejenie
  // zostaje jako zapas (`desktop/src/ui/settings.html` — sekcja „Wklej klucz ręcznie”).
  desktop: "W Nexus Desktop wystarczy „Połącz komputer” w ustawieniach — klucz powstanie z sesji okna. Ten klucz wklej, gdy wolisz zrobić to ręcznie.",
  rozszerzenie: "Kliknij ikonę rozszerzenia Nexus, otwórz ustawienia i wklej adres serwera oraz klucz.",
  inne: "Urządzenie wysyła klucz w nagłówku Authorization: Bearer <klucz>.",
};

/** Adres parowania w kodzie QR: serwer i klucz urządzenia (dziś tylko dla urządzeń własnych). */
export function pairingUri(server: string, token: string): string {
  return `danaconexus://sparuj?serwer=${encodeURIComponent(server)}&klucz=${encodeURIComponent(token)}`;
}

function formatDate(value: string | null): string {
  if (!value) return "nigdy";
  return new Date(value).toLocaleString("pl-PL", { dateStyle: "medium", timeStyle: "short" });
}

const card = "rounded-2xl border border-line bg-raised/40 p-5 md:p-6";
const input =
  "w-full rounded-xl border border-line bg-app px-3.5 py-2.5 text-[15px] outline-none transition-colors focus:border-accent";

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-hover"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setDone(true);
          window.setTimeout(() => setDone(false), 1500);
        });
      }}
    >
      {done ? <CheckIcon size={15} className="text-success" /> : <CopyIcon size={15} />} {done ? "Skopiowano" : label}
    </button>
  );
}

function NewDevice({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  // Domyślnie rozszerzenie: to jedyne urządzenie, któremu klucz trzeba wkleić. Telefon zakłada
  // klucz sam przy logowaniu, więc klucz „android” z tego formularza nigdy się nie przydaje.
  const [kind, setKind] = useState<DeviceKind>("rozszerzenie");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<(Device & { token: string }) | null>(null);
  const server = window.location.origin;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setCreated(await startApi.createDevice(name.trim() || KIND_LABELS[kind], kind));
      setName("");
      onCreated();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  };

  if (created) {
    return (
      <section className={`${card} border-accent/50`} aria-live="polite">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent">
            <KeyIcon size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold">Klucz dla „{created.name}” jest gotowy</h2>
            <p className="mt-1 text-sm text-muted">
              Klucz jest widoczny <b className="text-fg">tylko teraz</b>. {KIND_HINTS[created.kind]}
            </p>
          </div>
          <button type="button" className="icon-btn" onClick={() => setCreated(null)} aria-label="Zamknij">
            <CloseIcon size={18} />
          </button>
        </div>
        <div className="mt-5 grid gap-5 md:grid-cols-[auto_1fr] md:items-center">
          <div className="mx-auto rounded-2xl bg-white p-2">
            <QrCode text={pairingUri(server, created.token)} size={188} label="Kod QR do sparowania urządzenia" />
          </div>
          <div className="min-w-0 space-y-3">
            <div>
              <div className="mb-1 text-xs font-medium text-muted">Adres serwera</div>
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-lg bg-code px-3 py-2 font-mono text-sm">{server}</code>
                <CopyButton text={server} label="Kopiuj" />
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-muted">Klucz urządzenia</div>
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-lg bg-code px-3 py-2 font-mono text-sm">{created.token}</code>
                <CopyButton text={created.token} label="Kopiuj" />
              </div>
            </div>
            <p className="text-xs text-muted">
              Klucz daje pełny dostęp do Nexusa – nie wysyłaj go nikomu. „Cofnij” unieważnia go od razu, ale nie kończy
              logowania hasłem w oknie Nexusa na tamtym urządzeniu.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <form className={card} onSubmit={submit}>
      <h2 className="text-base font-semibold">Połącz nowe urządzenie</h2>
      <p className="mt-1 text-sm text-muted">
        Telefon, komputer z Nexus Desktop albo rozszerzenie przeglądarki łączą się z serwerem własnym kluczem.
      </p>
      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        {(Object.keys(KIND_LABELS) as DeviceKind[]).map((value) => {
          const KindIcon = KIND_ICONS[value];
          const active = kind === value;
          return (
            <button
              key={value}
              type="button"
              aria-pressed={active}
              onClick={() => setKind(value)}
              className={`flex items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-sm transition-colors ${
                active ? "border-accent bg-accent-soft text-fg" : "border-line text-muted hover:bg-hover hover:text-fg"
              }`}
            >
              <KindIcon size={18} className={active ? "text-accent" : ""} />
              <span className="leading-tight">{KIND_LABELS[value]}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          className={input}
          value={name}
          maxLength={100}
          onChange={(event) => setName(event.target.value)}
          placeholder={`Nazwa, np. ${kind === "android" ? "Mój telefon" : kind === "desktop" ? "Laptop w biurze" : "Chrome – praca"}`}
          aria-label="Nazwa urządzenia"
        />
        <button
          type="submit"
          disabled={busy}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-accent-fill px-5 py-2.5 font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-60"
        >
          {busy ? <span className="spinner" /> : <KeyIcon size={18} />} Utwórz klucz
        </button>
      </div>
      {error && (
        <div role="alert" className="mt-3 rounded-xl bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
          {error}
        </div>
      )}
    </form>
  );
}

const PUSH_TEXT: Record<PushStatus, string> = {
  unsupported: "Ta przeglądarka nie obsługuje powiadomień push (na iPhonie działają po dodaniu Nexusa do ekranu początkowego).",
  "server-off": "Powiadomienia push są wyłączone na serwerze.",
  denied: "Powiadomienia są zablokowane w ustawieniach przeglądarki dla tej witryny.",
  off: "Włącz, aby dostać powiadomienie, gdy zadanie skończy się w tle – także przy zamkniętej aplikacji.",
  on: "Ta przeglądarka dostaje powiadomienia o zakończonych zadaniach.",
};

function PushSection() {
  const [status, setStatus] = useState<PushStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    pushStatus()
      .then(setStatus)
      .catch(() => setStatus("unsupported"));
  }, []);

  const toggle = async () => {
    setBusy(true);
    setMessage("");
    try {
      setStatus(status === "on" ? await disablePush() : await enablePush());
    } catch (failure) {
      setMessage(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    try {
      const report = await startApi.pushTest();
      setMessage(report.sent ? `Wysłano powiadomienie próbne (${report.sent}).` : "Nie wysłano – brak aktywnych subskrypcji.");
    } catch (failure) {
      setMessage(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={card}>
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent">
          <BellIcon size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold">Powiadomienia na tym urządzeniu</h2>
          <p className="mt-1 text-sm text-muted">{status ? PUSH_TEXT[status] : "Sprawdzam…"}</p>
          {message && <p className="mt-2 text-sm">{message}</p>}
        </div>
      </div>
      {(status === "on" || status === "off") && (
        <div className="mt-4 flex flex-wrap gap-2 pl-[52px]">
          <button
            type="button"
            disabled={busy}
            onClick={() => void toggle()}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors disabled:opacity-60 ${
              status === "on" ? "border border-line hover:bg-hover" : "bg-accent-fill text-on-accent hover:bg-accent-fill-hover"
            }`}
          >
            {status === "on" ? "Wyłącz powiadomienia" : "Włącz powiadomienia"}
          </button>
          {status === "on" && (
            <button type="button" disabled={busy} onClick={() => void test()} className="rounded-xl border border-line px-4 py-2 text-sm hover:bg-hover disabled:opacity-60">
              Wyślij próbne
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function Downloads() {
  const [items, setItems] = useState<DownloadInfo[]>([]);
  useEffect(() => {
    fetchDownloads()
      .then(setItems)
      .catch(() => setItems([]));
  }, []);
  if (!items.length) return null;
  return (
    <section className={card}>
      <h2 className="text-base font-semibold">Aplikacje do pobrania</h2>
      <ul className="mt-3 divide-y divide-line">
        {items.map((item) => (
          <li key={item.name} className="flex items-center gap-3 py-2.5">
            <DownloadIcon size={18} className="text-muted" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{item.label}</span>
              <span className="block truncate text-xs text-muted">
                {item.available ? `${item.name} · ${formatSize(item.size ?? 0)}` : "wkrótce"}
              </span>
            </span>
            {item.available && (
              <a href={`/pobierz/${item.name}`} className="rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-hover" download>
                Pobierz
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function DevicesPage() {
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    startApi
      .devices()
      .then(setDevices)
      .catch((failure) => setError(failure instanceof ApiError ? failure.message : String(failure)));
  }, []);

  useEffect(load, [load]);

  const revoke = (device: Device) => {
    const skutek = device.wylogowuje_okno
      ? "Klucz przestanie działać, a okno Nexusa na tym urządzeniu zostanie wylogowane."
      : "Klucz przestanie działać od razu.";
    if (!window.confirm(`Odłączyć „${device.name}”? ${skutek}`)) return;
    startApi
      .revokeDevice(device.id)
      .then(load)
      .catch((failure) => setError(failure instanceof Error ? failure.message : String(failure)));
  };

  const active = devices?.filter((device) => !device.revoked) ?? [];
  const revoked = devices?.filter((device) => device.revoked) ?? [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-3xl space-y-5 px-4 pt-6 pb-16 md:px-6 md:pt-10">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-accent-soft text-accent">
            <DevicesIcon size={22} />
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Urządzenia</h1>
            <p className="text-sm text-muted">Telefon, komputer i przeglądarka połączone z Twoim Nexusem.</p>
          </div>
        </div>

        <NewDevice onCreated={load} />

        <section className={card}>
          <h2 className="text-base font-semibold">Połączone urządzenia</h2>
          <p className="mt-1 text-sm text-muted">
            Zgubiony telefon albo komputer odłącz przyciskiem „Cofnij” przy jego kluczu. Przy kluczu z dopiskiem
            „wyloguje też okno aplikacji” kończy to również logowanie w oknie Nexusa na tamtym urządzeniu.
          </p>
          {error && (
            <div role="alert" className="mt-3 flex items-center gap-2 rounded-xl bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
              <AlertIcon size={16} /> {error}
            </div>
          )}
          {devices === null && !error && <div className="mt-4 text-sm text-muted">Wczytuję…</div>}
          {devices !== null && active.length === 0 && (
            <div className="mt-3 rounded-2xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">
              Żadne urządzenie nie jest jeszcze połączone.
            </div>
          )}
          <ul className="mt-2 divide-y divide-line">
            {active.map((device) => {
              const KindIcon = KIND_ICONS[device.kind] ?? KeyIcon;
              return (
                <li key={device.id} className="flex items-center gap-3 py-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-hover text-muted">
                    <KindIcon size={18} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{device.name}</span>
                    <span className="block truncate text-xs text-muted">
                      {KIND_LABELS[device.kind] ?? device.kind} · ostatnio: {formatDate(device.last_used_at)}
                      {device.wylogowuje_okno && " · „Cofnij” wyloguje też okno aplikacji"}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => revoke(device)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition-colors hover:border-danger/50 hover:text-danger"
                  >
                    <TrashIcon size={15} /> Cofnij
                  </button>
                </li>
              );
            })}
          </ul>
          {revoked.length > 0 && (
            <details className="mt-3 text-sm text-muted">
              <summary className="cursor-pointer select-none">Cofnięte klucze ({revoked.length})</summary>
              <ul className="mt-2 space-y-1 pl-4">
                {revoked.map((device) => (
                  <li key={device.id} className="truncate">
                    {device.name} · utworzony {formatDate(device.created_at)}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>

        <PushSection />
        <Downloads />
      </div>
    </div>
  );
}
