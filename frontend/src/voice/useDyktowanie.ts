// Dyktowanie do pola wiadomości.
//
// Rozmowa głosowa to osobny tryb: Nexus słucha i odpowiada na głos. Brakowało trzeciego
// sposobu — pracy w trybie pisanym, ale bez klawiatury: naciskasz mikrofon, mówisz,
// a rozpoznany tekst dopisuje się do tego, co już jest w polu. Wtedy można go jeszcze
// poprawić przed wysłaniem.

import { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../api";

export type StanDyktowania = "bezczynne" | "nagrywanie" | "rozpoznawanie";

/** Format nagrania obsługiwany przez tę przeglądarkę (pusty = domyślny przeglądarki). */
function formatNagrania(): string {
  for (const typ of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(typ)) return typ;
  }
  return "";
}

/** Czy przeglądarka w ogóle pozwala nagrywać (HTTPS, obecne API). */
export function dyktowanieDostepne(): boolean {
  return (
    typeof MediaRecorder !== "undefined" &&
    typeof navigator !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  );
}

export interface Dyktowanie {
  stan: StanDyktowania;
  blad: string;
  /** Włącza nagrywanie albo kończy je i wysyła nagranie do rozpoznania. */
  przelacz: () => void;
  wyczyscBlad: () => void;
}

export function useDyktowanie(naTekst: (tekst: string) => void): Dyktowanie {
  const [stan, setStan] = useState<StanDyktowania>("bezczynne");
  const [blad, setBlad] = useState("");
  const rejestrator = useRef<MediaRecorder | null>(null);
  const czesci = useRef<Blob[]>([]);
  const strumien = useRef<MediaStream | null>(null);
  const tekstRef = useRef(naTekst);
  tekstRef.current = naTekst;

  const zwolnij = useCallback(() => {
    strumien.current?.getTracks().forEach((sciezka) => sciezka.stop());
    strumien.current = null;
    rejestrator.current = null;
  }, []);

  // Odmontowanie okna nie może zostawić włączonego mikrofonu.
  useEffect(() => zwolnij, [zwolnij]);

  const zacznij = useCallback(async () => {
    setBlad("");
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      strumien.current = media;
      const format = formatNagrania();
      const nowy = new MediaRecorder(media, format ? { mimeType: format } : undefined);
      czesci.current = [];
      nowy.ondataavailable = (zdarzenie) => {
        if (zdarzenie.data.size > 0) czesci.current.push(zdarzenie.data);
      };
      nowy.onstop = async () => {
        const nagranie = new Blob(czesci.current, { type: format || "audio/webm" });
        zwolnij();
        if (nagranie.size < 1200) {
          // Stuknięcie zamiast wypowiedzi — nie ma czego rozpoznawać i nie ma o czym mówić.
          setStan("bezczynne");
          return;
        }
        setStan("rozpoznawanie");
        try {
          const tekst = (await transcribeAudio(nagranie)).trim();
          if (tekst) tekstRef.current(tekst);
          else setBlad("Nic nie usłyszałem — spróbuj jeszcze raz.");
        } catch (awaria) {
          setBlad(awaria instanceof Error ? awaria.message : "Nie udało się rozpoznać wypowiedzi.");
        } finally {
          setStan("bezczynne");
        }
      };
      rejestrator.current = nowy;
      nowy.start();
      setStan("nagrywanie");
    } catch {
      zwolnij();
      setStan("bezczynne");
      setBlad("Brak dostępu do mikrofonu. Zezwól na mikrofon w ustawieniach przeglądarki.");
    }
  }, [zwolnij]);

  const przelacz = useCallback(() => {
    if (stan === "nagrywanie") {
      rejestrator.current?.stop();
      return;
    }
    if (stan === "bezczynne") void zacznij();
  }, [stan, zacznij]);

  return { stan, blad, przelacz, wyczyscBlad: () => setBlad("") };
}
