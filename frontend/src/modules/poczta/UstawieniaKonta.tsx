// Podłączenie skrzynki pocztowej z poziomu aplikacji.
//
// Do tej pory konto zapisywał skrypt na serwerze, więc każdy, kto zalogował się do Nexusa,
// czytał tę samą skrzynkę. Teraz konto podaje się tutaj: hasło leci prosto do zapisu po
// stronie serwera (plik z prawami 600) i nigdy nie wraca z powrotem do przeglądarki.

import { useState, type FormEvent } from "react";
import { describe } from "../_biuro/http";
import { buttonClass, ErrorBanner, Field, inputClass } from "../_biuro/ui";
import { mailApi, type KontoPocztowe, type MailAccount } from "./api";

const PUSTE: KontoPocztowe = {
  login: "",
  haslo: "",
  adres: "",
  nazwa: "",
  etykieta: "",
  imap_host: "",
  imap_port: 993,
  smtp_host: "",
  smtp_port: 0,
  smtp_security: "ssl",
  podpis_html: "",
};

/** Ustawienia serwerów dla najczęstszych dostawców — żeby nie trzeba było ich szukać. */
const DOSTAWCY: { nazwa: string; domena: RegExp; imap: string; smtp: string; port: number }[] = [
  { nazwa: "Gmail", domena: /@gmail\.com$/i, imap: "imap.gmail.com", smtp: "smtp.gmail.com", port: 465 },
  { nazwa: "Outlook", domena: /@(outlook|hotmail|live)\./i, imap: "outlook.office365.com", smtp: "smtp.office365.com", port: 587 },
  { nazwa: "WP", domena: /@wp\.pl$/i, imap: "imap.wp.pl", smtp: "smtp.wp.pl", port: 465 },
  { nazwa: "Onet", domena: /@(onet|op|poczta\.onet)\./i, imap: "imap.poczta.onet.pl", smtp: "smtp.poczta.onet.pl", port: 465 },
  { nazwa: "Interia", domena: /@interia\.(pl|eu)$/i, imap: "poczta.interia.pl", smtp: "poczta.interia.pl", port: 465 },
  { nazwa: "o2", domena: /@o2\.pl$/i, imap: "poczta.o2.pl", smtp: "poczta.o2.pl", port: 465 },
];

function podpowiedzSerwerow(adres: string): Partial<KontoPocztowe> | null {
  const dostawca = DOSTAWCY.find((pozycja) => pozycja.domena.test(adres));
  if (!dostawca) return null;
  return {
    imap_host: dostawca.imap,
    smtp_host: dostawca.smtp,
    smtp_port: dostawca.port,
    smtp_security: dostawca.port === 587 ? "starttls" : "ssl",
  };
}

interface Props {
  konta: MailAccount[];
  /** Wywoływane po zapisaniu albo odłączeniu konta — strona przeładowuje stan poczty. */
  onZmiana: () => void;
  /** Zamknięcie ustawień (null, gdy poczta nie jest jeszcze podłączona i nie ma dokąd wracać). */
  onZamknij?: () => void;
}

export function UstawieniaKonta({ konta, onZmiana, onZamknij }: Props) {
  const [dane, setDane] = useState<KontoPocztowe>(PUSTE);
  const [blad, setBlad] = useState("");
  const [komunikat, setKomunikat] = useState("");
  const [zajety, setZajety] = useState<"" | "sprawdzanie" | "zapis" | "usuwanie">("");

  const ustaw = (zmiany: Partial<KontoPocztowe>) => {
    setDane((poprzednie) => ({ ...poprzednie, ...zmiany }));
    setKomunikat("");
    setBlad("");
  };

  // Adres zwykle wystarcza, żeby podstawić serwery — użytkownik i tak może je poprawić.
  const ustawAdres = (adres: string) => {
    const podpowiedz = podpowiedzSerwerow(adres);
    ustaw({ adres, login: dane.login || adres, ...(dane.imap_host ? {} : (podpowiedz ?? {})) });
  };

  const sprawdz = async () => {
    setZajety("sprawdzanie");
    setBlad("");
    setKomunikat("");
    try {
      const wynik = await mailApi.sprawdzKonto(dane);
      setKomunikat(`Połączono. Skrzynka ma ${wynik.folders} folderów, wysyłka działa.`);
    } catch (awaria) {
      setBlad(describe(awaria));
    } finally {
      setZajety("");
    }
  };

  const zapisz = async (zdarzenie: FormEvent) => {
    zdarzenie.preventDefault();
    setZajety("zapis");
    setBlad("");
    setKomunikat("");
    try {
      await mailApi.zapiszKonto(dane);
      setDane(PUSTE);
      setKomunikat("Skrzynka podłączona.");
      onZmiana();
    } catch (awaria) {
      setBlad(describe(awaria));
    } finally {
      setZajety("");
    }
  };

  const odlacz = async (id: string) => {
    setZajety("usuwanie");
    setBlad("");
    try {
      await mailApi.usunKonto(id);
      onZmiana();
    } catch (awaria) {
      setBlad(describe(awaria));
    } finally {
      setZajety("");
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-heading text-xl font-semibold text-fg">Skrzynki pocztowe</h2>
          <p className="mt-1.5 text-sm text-muted">
            Konto podajesz tutaj. Hasło zapisuje się po stronie serwera i nigdy nie wraca do przeglądarki;
            Nexus czyta i przygotowuje wiadomości, ale nie wysyła nic bez Twojego zatwierdzenia.
          </p>
        </div>
        {onZamknij && (
          <button type="button" onClick={onZamknij} className={buttonClass.secondary}>
            Wróć do poczty
          </button>
        )}
      </div>

      {konta.length > 0 && (
        <ul className="mt-6 space-y-2">
          {konta.map((konto) => (
            <li
              key={konto.id}
              className="flex items-center justify-between gap-4 rounded-xl border border-line bg-raised px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-fg">{konto.address}</p>
                {konto.name && <p className="truncate text-xs text-muted">{konto.name}</p>}
              </div>
              <button
                type="button"
                disabled={zajety !== ""}
                onClick={() => void odlacz(konto.id)}
                className={buttonClass.secondary}
              >
                Odłącz
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={zapisz} className="mt-8 space-y-4">
        <h3 className="font-heading text-base font-semibold text-fg">
          {konta.length ? "Dodaj kolejną skrzynkę" : "Podłącz skrzynkę"}
        </h3>

        <Field label="Adres e-mail">
          <input
            className={inputClass}
            type="email"
            autoComplete="email"
            required
            value={dane.adres}
            onChange={(zdarzenie) => ustawAdres(zdarzenie.target.value)}
          />
        </Field>

        <Field label="Hasło skrzynki">
          <input
            className={inputClass}
            type="password"
            autoComplete="new-password"
            required
            value={dane.haslo}
            onChange={(zdarzenie) => ustaw({ haslo: zdarzenie.target.value })}
          />
        </Field>
        <p className="-mt-2 text-xs text-subtle">
          Gmail i Outlook wymagają hasła aplikacji, a nie hasła do konta.
        </p>

        <Field label="Nazwa nadawcy (widoczna u odbiorcy)">
          <input
            className={inputClass}
            value={dane.nazwa}
            onChange={(zdarzenie) => ustaw({ nazwa: zdarzenie.target.value })}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <Field label="Serwer odbioru (IMAP)">
            <input
              className={inputClass}
              required
              value={dane.imap_host}
              onChange={(zdarzenie) => ustaw({ imap_host: zdarzenie.target.value })}
            />
          </Field>
          <Field label="Port">
            <input
              className={inputClass}
              type="number"
              min={1}
              max={65535}
              value={dane.imap_port}
              onChange={(zdarzenie) => ustaw({ imap_port: Number(zdarzenie.target.value) })}
            />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-[1fr_8rem_8rem]">
          <Field label="Serwer wysyłki (SMTP)">
            <input
              className={inputClass}
              placeholder="jak IMAP"
              value={dane.smtp_host}
              onChange={(zdarzenie) => ustaw({ smtp_host: zdarzenie.target.value })}
            />
          </Field>
          <Field label="Port">
            <input
              className={inputClass}
              type="number"
              min={0}
              max={65535}
              placeholder="465"
              value={dane.smtp_port || ""}
              onChange={(zdarzenie) => ustaw({ smtp_port: Number(zdarzenie.target.value) })}
            />
          </Field>
          <Field label="Szyfrowanie">
            <select
              className={inputClass}
              value={dane.smtp_security}
              onChange={(zdarzenie) => ustaw({ smtp_security: zdarzenie.target.value as "ssl" | "starttls" })}
            >
              <option value="ssl">SSL</option>
              <option value="starttls">STARTTLS</option>
            </select>
          </Field>
        </div>

        {blad && <ErrorBanner message={blad} />}
        {komunikat && (
          <p role="status" className="rounded-lg border border-success/40 bg-success-soft px-3.5 py-2.5 text-sm text-success">
            {komunikat}
          </p>
        )}

        <div className="flex flex-wrap gap-3 pt-2">
          <button type="submit" disabled={zajety !== ""} className={buttonClass.primary}>
            {zajety === "zapis" ? "Sprawdzam i zapisuję…" : "Podłącz skrzynkę"}
          </button>
          <button
            type="button"
            disabled={zajety !== "" || !dane.adres || !dane.haslo || !dane.imap_host}
            onClick={() => void sprawdz()}
            className={buttonClass.secondary}
          >
            {zajety === "sprawdzanie" ? "Sprawdzam…" : "Sprawdź połączenie"}
          </button>
        </div>
      </form>
    </div>
  );
}
