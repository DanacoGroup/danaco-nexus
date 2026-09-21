// Synchronizacja chmury z komputerem i telefonem: adres serwera, kod QR, instrukcje aplikacji Nextcloud.

import { useEffect, useState } from "react";
import { describe } from "../_biuro/http";
import { CalendarIcon, CopyIcon } from "../_biuro/icons";
import { buttonClass, copyText, ErrorBanner, Loading } from "../_biuro/ui";
import { cloudApi, type SyncInfo } from "./api";

const STEPS: { title: string; link: keyof SyncInfo["clients"]; linkLabel: string; steps: string[] }[] = [
  {
    title: "Windows",
    link: "windows",
    linkLabel: "Pobierz Nextcloud Desktop",
    steps: [
      "Zainstaluj aplikację Nextcloud Desktop i uruchom ją.",
      "Wybierz „Zaloguj się”, wpisz adres serwera i zatwierdź.",
      "W przeglądarce otworzy się logowanie Nexusa – zaloguj się i przyznaj dostęp.",
      "Wskaż folder na dysku (np. C:\\Users\\…\\Nexus Cloud) i foldery do synchronizacji. Pliki pojawią się w Eksploratorze.",
    ],
  },
  {
    title: "Android",
    link: "android",
    linkLabel: "Nextcloud w Google Play",
    steps: [
      "Zainstaluj aplikację Nextcloud (Google Play albo F-Droid).",
      // „powyżej”, nie „obok”: kod QR stoi w osobnej sekcji **nad** kartami platform —
      // na każdej szerokości, a na telefonie dodatkowo nad adresem serwera.
      "Wybierz „Zaloguj się” i zeskanuj kod QR powyżej albo wpisz adres serwera.",
      "Zaloguj się kontem Nexusa w otwartym oknie przeglądarki.",
      "W ustawieniach aplikacji włącz „Automatyczne przesyłanie”, aby zdjęcia z telefonu trafiały do chmury.",
    ],
  },
  {
    title: "iPhone i iPad",
    link: "ios",
    linkLabel: "Nextcloud w App Store",
    steps: [
      "Zainstaluj aplikację Nextcloud z App Store.",
      "Wpisz adres serwera albo zeskanuj kod QR aparatem.",
      "Zaloguj się kontem Nexusa; pliki będą też widoczne w aplikacji Pliki.",
    ],
  },
];

export function SyncPanel({ onOpenCalendar }: { onOpenCalendar: () => void }) {
  const [info, setInfo] = useState<SyncInfo | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  useEffect(() => {
    cloudApi
      .syncInfo()
      .then(setInfo)
      .catch((failure) => setError(describe(failure)));
  }, []);

  const copy = (value: string) => copyText(value).then(() => setCopied(value));

  if (error) return <div className="p-5"><ErrorBanner message={error} /></div>;
  if (!info) return <Loading />;
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-6 px-4 py-6 md:px-6">
        <header>
          <h2 className="text-xl font-semibold">Synchronizacja z komputerem i telefonem</h2>
          <p className="mt-1 text-sm text-muted">
            Chmura Nexusa działa z oficjalnymi aplikacjami Nextcloud. Pliki zmieniane na komputerze, telefonie i tutaj są
            wszędzie takie same, a każda zmiana tworzy wersję, którą można przywrócić.
          </p>
        </header>

        <section className="flex flex-col gap-5 rounded-2xl border border-line bg-side p-4 sm:flex-row sm:items-center">
          <img
            src={info.qr}
            alt={`Kod QR z adresem serwera ${info.server_url}`}
            className="size-40 shrink-0 self-center rounded-xl bg-white p-1"
          />
          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <span className="block text-xs font-medium text-muted">Adres serwera</span>
              <div className="mt-1 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-lg bg-code px-3 py-2 font-mono text-sm">{info.server_url}</code>
                <button type="button" className="icon-btn" aria-label="Kopiuj adres serwera" onClick={() => copy(info.server_url)}>
                  <CopyIcon />
                </button>
              </div>
              {copied === info.server_url && <span className="text-xs text-success">Skopiowano</span>}
            </div>
            <div>
              <span className="block text-xs font-medium text-muted">WebDAV (np. dysk sieciowy, Total Commander)</span>
              <div className="mt-1 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-lg bg-code px-3 py-2 font-mono text-xs">{info.webdav_url}</code>
                <button type="button" className="icon-btn" aria-label="Kopiuj adres WebDAV" onClick={() => copy(info.webdav_url)}>
                  <CopyIcon />
                </button>
              </div>
            </div>
            <p className="text-xs text-muted">
              Logowanie odbywa się przez Nexusa (to samo konto). Programom bez logowania przez przeglądarkę podaj hasło
              aplikacji utworzone w chmurze: Ustawienia → Bezpieczeństwo → „Utwórz nowe hasło aplikacji”.
            </p>
          </div>
        </section>

        <div className="grid gap-4 md:grid-cols-3">
          {STEPS.map((platform) => (
            <section key={platform.title} className="flex flex-col rounded-2xl border border-line p-4">
              <h3 className="font-semibold">{platform.title}</h3>
              <ol className="mt-2 flex-1 list-decimal space-y-1.5 pl-5 text-sm text-muted">
                {platform.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              {info.clients[platform.link] && (
                <a className={`${buttonClass.secondary} mt-4`} href={info.clients[platform.link]} target="_blank" rel="noopener noreferrer">
                  {platform.linkLabel}
                </a>
              )}
            </section>
          ))}
        </div>

        <section className="flex flex-col gap-3 rounded-2xl border border-line p-4 sm:flex-row sm:items-center">
          <CalendarIcon className="shrink-0 text-accent" size={28} />
          <p className="min-w-0 flex-1 text-sm text-muted">
            Kalendarz synchronizuje się osobno (CalDAV) – na Androidzie przez aplikację DAVx⁵, na iPhonie w ustawieniach
            kont. Instrukcja jest w module Kalendarz.
          </p>
          <button type="button" className={buttonClass.secondary} onClick={onOpenCalendar}>
            Otwórz Kalendarz
          </button>
        </section>
      </div>
    </div>
  );
}
