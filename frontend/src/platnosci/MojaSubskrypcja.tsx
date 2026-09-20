// Ekran „Moja subskrypcja”: stan planu, limity, faktury oraz zmiana planu i rezygnacja.
// Zmiana planu i rezygnacja prowadzą do portalu rozliczeniowego Stripe — adres daje serwer.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api";
import { AlertIcon, DownloadIcon } from "../components/icons";
import { ExternalIcon } from "../shell/icons";
import {
  OPISY_FAKTURY,
  OPISY_STATUSU,
  data,
  kwota,
  opisOkresu,
  platnosciApi,
  type FakturaInfo,
  type SubskrypcjaInfo,
} from "./api";

const KARTA = "rounded-3xl border border-line bg-raised/40 p-5 md:p-6";
const PRZYCISK = "rounded-xl px-4 py-2.5 text-sm font-medium transition-colors";
const OBRAMOWANY = `${PRZYCISK} border border-line hover:bg-hover`;
// Faktury w tych stanach czekają na zapłatę – przy nich pokazujemy odsyłacz do płatności.
const DO_ZAPLATY = ["open", "uncollectible"];

function Pozycja({ etykieta, wartosc }: { etykieta: string; wartosc: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted">{etykieta}</dt>
      <dd className="mt-0.5 text-sm">{wartosc}</dd>
    </div>
  );
}

function Faktury({ faktury, zajety, onOdswiez }: { faktury: FakturaInfo[]; zajety: boolean; onOdswiez: () => void }) {
  return (
    <section className={KARTA}>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-heading text-lg">Faktury</h2>
        <button type="button" className={OBRAMOWANY} disabled={zajety} onClick={onOdswiez}>
          Pobierz ze Stripe
        </button>
      </header>
      {faktury.length === 0 ? (
        <p className="mt-4 text-sm text-muted">
          Nie ma jeszcze żadnej faktury. Pierwsza powstanie po pierwszej płatności i będzie tutaj do
          pobrania w PDF.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-line">
          {faktury.map((faktura) => (
            <li key={faktura.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">{faktura.numer || "Faktura bez numeru"}</p>
                <p className="text-xs text-muted">
                  {data(faktura.wystawiona_at)} · {kwota(faktura.kwota_gr, faktura.waluta)} ·{" "}
                  {OPISY_FAKTURY[faktura.status] ?? faktura.status}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {DO_ZAPLATY.includes(faktura.status) && faktura.strona_url && (
                  <a
                    className={`${PRZYCISK} inline-flex items-center gap-1.5 bg-accent-fill text-on-accent hover:bg-accent-fill-hover`}
                    href={faktura.strona_url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    <ExternalIcon size={15} /> Zapłać fakturę
                  </a>
                )}
                {faktura.pdf_url && (
                  <a
                    className={`${OBRAMOWANY} inline-flex items-center gap-1.5`}
                    href={faktura.pdf_url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    <DownloadIcon size={15} /> PDF
                  </a>
                )}
                {faktura.strona_url && !DO_ZAPLATY.includes(faktura.status) && (
                  <a
                    className="inline-flex items-center gap-1.5 text-sm text-accent"
                    href={faktura.strona_url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    <ExternalIcon size={15} /> Podgląd
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function MojaSubskrypcja({
  subskrypcja,
  poZakupie = false,
  onZmienPlan,
  onPortal,
  onOdswiez,
}: {
  subskrypcja: SubskrypcjaInfo;
  poZakupie?: boolean;
  onZmienPlan: () => void;
  onPortal: () => void;
  onOdswiez: () => void;
}) {
  const [faktury, setFaktury] = useState<FakturaInfo[]>([]);
  const [zajety, setZajety] = useState(false);
  const [blad, setBlad] = useState("");

  const wczytaj = useCallback(async (odswiez: boolean) => {
    setZajety(true);
    setBlad("");
    try {
      setFaktury(await platnosciApi.faktury(odswiez));
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się wczytać faktur.");
    } finally {
      setZajety(false);
    }
  }, []);

  useEffect(() => {
    // Zaraz po zakupie faktura bywa jeszcze tylko w Stripe – wtedy pobieramy ją od razu.
    void wczytaj(poZakupie);
  }, [wczytaj, poZakupie]);

  const zrezygnuj = async () => {
    setZajety(true);
    setBlad("");
    try {
      const { url } = await platnosciApi.rezygnacja();
      window.location.assign(url);
    } catch (awaria) {
      setBlad(awaria instanceof ApiError ? awaria.message : "Nie udało się otworzyć rezygnacji.");
      setZajety(false);
    }
  };

  const limity = subskrypcja.limity;
  const rozliczenie = opisOkresu(subskrypcja.okres);
  const mozeZrezygnowac = subskrypcja.ma_platny_plan && !subskrypcja.anuluj_na_koniec;
  return (
    <div className="space-y-4">
      <section className={KARTA}>
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-xl">Plan {subskrypcja.nazwa_planu}</h2>
            <p className="mt-1 text-sm text-muted">
              {OPISY_STATUSU[subskrypcja.status] ?? subskrypcja.status}
              {rozliczenie ? ` · ${rozliczenie}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={OBRAMOWANY} onClick={onZmienPlan}>
              Zmień plan
            </button>
            <button
              type="button"
              className={`${PRZYCISK} bg-accent-fill text-on-accent hover:bg-accent-fill-hover`}
              disabled={zajety || !subskrypcja.ma_konto_stripe}
              onClick={onPortal}
            >
              Zarządzaj płatnościami
            </button>
          </div>
        </header>
        {subskrypcja.anuluj_na_koniec && (
          <p className="mt-4 rounded-xl border border-warning/40 px-3.5 py-2.5 text-sm text-muted">
            Plan kończy się {data(subskrypcja.okres_do)} i nie odnowi się. Do tego dnia wznowisz go
            w rozliczeniach, bez ponownego zakupu.
          </p>
        )}
        <dl className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-3">
          <Pozycja etykieta="Okres od" wartosc={data(subskrypcja.okres_od)} />
          <Pozycja etykieta="Okres do" wartosc={data(subskrypcja.okres_do)} />
          <Pozycja etykieta="Największy plik" wartosc={`${limity.plik_mb} MB`} />
        </dl>
        {mozeZrezygnowac ? (
          <div className="mt-5 border-t border-line pt-4">
            <button type="button" className={`${OBRAMOWANY} text-danger`} disabled={zajety} onClick={() => void zrezygnuj()}>
              Zrezygnuj z planu
            </button>
            <p className="mt-2 text-sm text-muted">
              Rezygnację potwierdzasz w rozliczeniach Stripe. Plan działa do końca opłaconego okresu,
              a dane zostają na koncie.
            </p>
          </div>
        ) : (
          !subskrypcja.ma_konto_stripe && (
            <p className="mt-4 text-sm text-muted">
              Rozliczenia otworzysz po pierwszym zakupie — tam zmienisz kartę, plan i zrezygnujesz.
            </p>
          )
        )}
      </section>

      {blad && (
        <p role="alert" className="flex items-center gap-2 rounded-xl border border-line px-3.5 py-2.5 text-sm text-muted">
          <AlertIcon size={16} /> {blad}
        </p>
      )}

      <Faktury
        faktury={faktury}
        zajety={zajety}
        onOdswiez={() => {
          void wczytaj(true);
          onOdswiez();
        }}
      />
    </div>
  );
}
