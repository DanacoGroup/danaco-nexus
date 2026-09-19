// Sekcja „Zainstaluj”: Android (APK), Windows (instalator), rozszerzenie przeglądarki i aplikacja PWA.

import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { DownloadIcon, InstallIcon, ShareIcon } from "../components/icons";
import { isIos, isStandalone, usePwa } from "../pwa";
import { formatSize } from "../runState";
import { PhoneIcon, PuzzleIcon, WindowsIcon, type IconProps } from "../shell/icons";
import { fetchDownloads, type DownloadInfo } from "../shell/startApi";

interface CardProps {
  icon: ComponentType<IconProps>;
  title: string;
  subtitle: string;
  children: ReactNode;
  action: ReactNode;
}

function InstallCard({ icon: CardIcon, title, subtitle, children, action }: CardProps) {
  return (
    <article className="landing-card flex flex-col rounded-3xl p-6">
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-2xl bg-accent-soft text-accent">
          <CardIcon size={22} />
        </span>
        <div>
          <h3 className="text-[17px] font-semibold tracking-tight">{title}</h3>
          <p className="text-xs text-muted">{subtitle}</p>
        </div>
      </div>
      <div className="mt-4 flex-1 text-sm leading-relaxed text-muted">{children}</div>
      <div className="mt-5">{action}</div>
    </article>
  );
}

const primary =
  "inline-flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-on-accent transition-colors hover:bg-accent-hover";
const disabled =
  "inline-flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-xl border border-dashed border-line-strong px-4 py-2.5 text-sm text-muted";

function DownloadButton({ info, name, label }: { info: DownloadInfo | undefined; name: string; label: string }) {
  if (!info?.available) {
    return (
      <span className={disabled} aria-disabled="true">
        Wkrótce do pobrania
      </span>
    );
  }
  return (
    <a className={primary} href={`/pobierz/${name}`} download>
      <DownloadIcon size={17} /> {label}
      {info.size ? <span className="font-normal opacity-75">· {formatSize(info.size)}</span> : null}
    </a>
  );
}

export function InstallSection() {
  const [downloads, setDownloads] = useState<Record<string, DownloadInfo>>({});
  const pwa = usePwa();
  useEffect(() => {
    fetchDownloads()
      .then((items) => setDownloads(Object.fromEntries(items.map((item) => [item.name, item]))))
      .catch(() => setDownloads({}));
  }, []);

  const ios = isIos();
  return (
    <section id="instalacja" className="scroll-mt-20 px-5 py-20 md:py-28">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-medium text-accent">Instalacja</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">Zainstaluj Nexusa tam, gdzie pracujesz</h2>
          <p className="mt-3 text-muted">
            Jedno konto, wspólne rozmowy i pliki. Po instalacji połącz urządzenie kluczem z modułu „Urządzenia”.
          </p>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <InstallCard icon={PhoneIcon} title="Android" subtitle="Telefon i tablet" action={<DownloadButton info={downloads["nexus-android.apk"]} name="nexus-android.apk" label="Pobierz APK" />}>
            Rozmowa głosowa w tle, asystent systemowy pod bocznym przyciskiem, języczek przy krawędzi ekranu i szkice
            odpowiedzi na SMS-y.
            <p className="mt-2 text-xs">Przy pierwszej instalacji Android poprosi o zgodę na instalację z tego źródła.</p>
          </InstallCard>
          <InstallCard
            icon={WindowsIcon}
            title="Windows"
            subtitle="Nexus Desktop · Windows 10 i 11"
            action={<DownloadButton info={downloads["nexus-desktop-setup.exe"]} name="nexus-desktop-setup.exe" label="Pobierz instalator" />}
          >
            Wysuwany panel przy krawędzi ekranu i skrót klawiszowy. Pomoc w każdym programie, wyszukiwanie plików,
            diagnostyka i sprzątanie komputera – zmiany dopiero po Twojej zgodzie.
          </InstallCard>
          <InstallCard
            icon={PuzzleIcon}
            title="Rozszerzenie"
            subtitle="Chrome · Edge · Danaco Lynx"
            action={<DownloadButton info={downloads["nexus-rozszerzenie.zip"]} name="nexus-rozszerzenie.zip" label="Pobierz ZIP" />}
          >
            <ol className="list-decimal space-y-1 pl-4 marker:text-accent">
              <li>Rozpakuj pobrane archiwum.</li>
              <li>
                Chrome/Edge: otwórz <code className="landing-code">chrome://extensions</code> lub{" "}
                <code className="landing-code">edge://extensions</code> i włącz <b>Tryb dewelopera</b>.
              </li>
              <li>
                Kliknij <b>Załaduj rozpakowane</b> i wskaż folder.
              </li>
              <li>
                Danaco Lynx: otwórz <code className="landing-code">lynx://rozszerzenia</code> i załaduj folder tak samo.
              </li>
            </ol>
          </InstallCard>
          <InstallCard
            icon={InstallIcon}
            title="Aplikacja z przeglądarki"
            subtitle="iPhone · iPad · każdy komputer"
            action={
              isStandalone() ? (
                <span className={disabled}>Aplikacja jest zainstalowana</span>
              ) : pwa.canInstall ? (
                <button type="button" className={primary} onClick={() => void pwa.install()}>
                  <InstallIcon size={17} /> Zainstaluj teraz
                </button>
              ) : (
                <a className={primary} href="/zaloguj">
                  Otwórz w przeglądarce
                </a>
              )
            }
          >
            {ios ? (
              <>
                W Safari stuknij <ShareIcon size={14} className="inline align-[-2px]" /> <b>Udostępnij</b>, a potem{" "}
                <b>Do ekranu początkowego</b>. Nexus otworzy się jak zwykła aplikacja, z powiadomieniami.
              </>
            ) : (
              <>
                Działa bez instalatora na każdym urządzeniu. W Chrome lub Edge wybierz <b>Zainstaluj Danaco Nexus</b> w pasku
                adresu albo w menu przeglądarki; na iPhonie – <b>Do ekranu początkowego</b> w Safari.
              </>
            )}
          </InstallCard>
        </div>
      </div>
    </section>
  );
}
