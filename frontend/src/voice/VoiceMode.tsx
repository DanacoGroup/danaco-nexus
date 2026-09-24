// Tryb rozmowy głosowej: słuchanie z wykrywaniem mowy, rozpoznanie na serwerze,
// odpowiedź czytana zdanie po zdaniu, przerywanie odpowiedzi głosem.

import { useCallback, useEffect, useRef, useState } from "react";
import { speakText, transcribeAudio, type VoiceConfig } from "../api";
import { CloseIcon } from "../components/icons";
import { useOknoModalne } from "../ui/useOknoModalne";
import { playAudio, stopAudio } from "./player";
import { speakable, takeSentences } from "./sentences";

type Phase = "starting" | "listening" | "hearing" | "transcribing" | "thinking" | "speaking" | "paused" | "error";

interface Props {
  config: VoiceConfig;
  replyText: string;
  replyDone: boolean;
  onSend: (text: string) => Promise<boolean>;
  onClose: () => void;
}

const FRAME_MS = 40;
const SPEECH_START_MS = 200;
const SPEECH_END_SILENCE_MS = 700;
const MIN_SPEECH_MS = 350;
const MAX_UTTERANCE_MS = 60_000;
const IDLE_RESTART_MS = 20_000;
const BARGE_IN_MS = 180;
const FILLER_AFTER_MS = 4500;
const FILLER = "Chwileczkę, już nad tym pracuję.";
const VOICE_KEY = "nexus-voice";

const PHASE_LABELS: Record<Phase, string> = {
  starting: "Przygotowuję mikrofon…",
  listening: "Słucham…",
  hearing: "Słucham…",
  transcribing: "Rozpoznaję…",
  thinking: "Myślę…",
  speaking: "Mówię – możesz przerwać",
  paused: "Mikrofon wyciszony",
  error: "Błąd",
};

function recorderMime(): string {
  for (const type of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

function storedVoice(config: VoiceConfig): string {
  try {
    const value = localStorage.getItem(VOICE_KEY);
    if (value && config.voices.some((voice) => voice.id === value)) return value;
  } catch {
    // Brak pamięci przeglądarki – głos domyślny.
  }
  return config.default_voice;
}

/** Komunikat o nieudanym dostępie do mikrofonu — po polsku i z podpowiedzią, co zrobić. */
export function bladMikrofonu(failure: unknown): string {
  const nazwa = failure instanceof DOMException ? failure.name : "";
  switch (nazwa) {
    case "NotAllowedError":
    case "SecurityError":
      return "Brak zgody na mikrofon. Zezwól na mikrofon w ustawieniach przeglądarki i spróbuj ponownie.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "Nie znaleziono mikrofonu. Podłącz mikrofon albo wybierz inne urządzenie wejściowe w ustawieniach systemu.";
    case "NotReadableError":
      return "Mikrofon jest zajęty przez inny program. Zamknij go i spróbuj ponownie.";
    case "AbortError":
      return "Dostęp do mikrofonu został przerwany. Spróbuj ponownie.";
    default:
      break;
  }
  if (!window.isSecureContext) {
    return "Mikrofon działa tylko przez HTTPS albo na 127.0.0.1. Otwórz Nexusa pod adresem https://danaco-nexus.pl/czat.";
  }
  return "Nie udało się uruchomić mikrofonu. Sprawdź uprawnienia przeglądarki i urządzenie wejściowe.";
}

export function VoiceMode({ config, replyText, replyDone, onSend, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("starting");
  const [level, setLevel] = useState(0);
  const [heard, setHeard] = useState("");
  const [error, setError] = useState("");
  const [voice, setVoice] = useState(() => storedVoice(config));
  // Zmiana licznika uruchamia ponownie zdobywanie mikrofonu — po podłączeniu
  // urządzenia albo po udzieleniu zgody nie trzeba wychodzić z trybu rozmowy.
  const [proba, setProba] = useState(0);

  // Tryb głosowy zasłania całą aplikację; bez tego tabulacja chodziła po ekranie pod spodem,
  // a Esc nie zamykał rozmowy.
  const nakladka = useRef<HTMLDivElement>(null);
  useOknoModalne(nakladka, onClose);

  const phaseRef = useRef<Phase>("starting");
  const context = useRef<AudioContext | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const floor = useRef(0.01);
  const aboveSince = useRef(0);
  const speechStart = useRef(0);
  const lastVoice = useRef(0);
  const listenStart = useRef(0);
  const queue = useRef<string[]>([]);
  const cursor = useRef(0);
  const inflight = useRef<Promise<Blob>[]>([]);
  const speechAbort = useRef(new AbortController());
  const player = useRef(false);
  const abort = useRef<AbortController | null>(null);
  const awaitingReply = useRef(false);
  const sentAt = useRef(0);
  const fillerSaid = useRef(false);
  const replyRef = useRef({ text: replyText, done: replyDone });
  const wakeLock = useRef<{ release: () => Promise<void> } | null>(null);
  const voiceRef = useRef(voice);
  voiceRef.current = voice;
  replyRef.current = { text: replyText, done: replyDone };

  const go = (next: Phase) => {
    phaseRef.current = next;
    setPhase(next);
  };

  // --- nagrywanie ------------------------------------------------------------------------

  const startRecorder = useCallback(() => {
    if (!stream.current) return;
    recorder.current?.state === "recording" && recorder.current.stop();
    chunks.current = [];
    const mime = recorderMime();
    const next = new MediaRecorder(stream.current, mime ? { mimeType: mime } : undefined);
    next.ondataavailable = (event) => event.data.size && chunks.current.push(event.data);
    next.start(250);
    recorder.current = next;
    listenStart.current = performance.now();
  }, []);

  const listen = useCallback(() => {
    aboveSince.current = 0;
    go("listening");
    startRecorder();
  }, [startRecorder]);

  const finishUtterance = useCallback(async () => {
    const current = recorder.current;
    if (!current) return;
    go("transcribing");
    const blob = await new Promise<Blob>((resolve) => {
      current.onstop = () => resolve(new Blob(chunks.current, { type: current.mimeType || "audio/webm" }));
      current.stop();
    });
    recorder.current = null;
    try {
      abort.current = new AbortController();
      const text = (await transcribeAudio(blob, abort.current.signal)).trim();
      if (phaseRef.current !== "transcribing") return;
      if (!text || text.length < 2) {
        listen();
        return;
      }
      setHeard(text);
      go("thinking");
      cursor.current = 0;
      queue.current = [];
      fillerSaid.current = false;
      awaitingReply.current = true;
      sentAt.current = performance.now();
      if (!(await onSend(text))) {
        awaitingReply.current = false;
        listen();
      }
    } catch (failure) {
      if ((failure as Error).name === "AbortError") return;
      setError(failure instanceof Error ? failure.message : String(failure));
      listen();
    }
  }, [listen, onSend]);

  // --- odtwarzanie -----------------------------------------------------------------------

  const stopSpeaking = useCallback(() => {
    queue.current = [];
    inflight.current = [];
    speechAbort.current.abort();
    speechAbort.current = new AbortController();
    stopAudio();
  }, []);

  // Synteza najwyżej dwóch zdań naprzód – kolejne gra bez przerwy po poprzednim.
  const fill = () => {
    while (inflight.current.length < 2 && queue.current.length) {
      inflight.current.push(speakText(queue.current.shift() as string, voiceRef.current, speechAbort.current.signal));
    }
  };

  const playQueue = useCallback(async () => {
    if (player.current) return;
    player.current = true;
    try {
      fill();
      while (inflight.current.length) {
        const data = await (inflight.current.shift() as Promise<Blob>);
        fill();
        if (phaseRef.current !== "speaking" && phaseRef.current !== "thinking") break;
        go("speaking");
        await playAudio(data, speechAbort.current.signal);
      }
    } catch (failure) {
      if ((failure as Error).name !== "AbortError") {
        setError(failure instanceof Error ? failure.message : String(failure));
      }
    } finally {
      player.current = false;
    }
    const current = phaseRef.current;
    if (current !== "speaking" && current !== "thinking") return;
    if (queue.current.length) void playQueue();
    else if (replyRef.current.done && !awaitingReply.current) listen();
    else go("thinking");
  }, [listen]);

  // Nowy tekst odpowiedzi → kolejne zdania do przeczytania.
  useEffect(() => {
    if (!awaitingReply.current && phaseRef.current !== "speaking") return;
    const text = speakable(replyText);
    const { chunks: sentences, next } = takeSentences(text, cursor.current, replyDone);
    cursor.current = next;
    if (sentences.length) queue.current.push(...sentences);
    if (replyDone) awaitingReply.current = false;
    if (queue.current.length) void playQueue();
    else if (replyDone && !player.current && (phaseRef.current === "thinking" || phaseRef.current === "speaking")) {
      listen();
    }
  }, [replyText, replyDone, playQueue, listen]);

  // --- pętla analizy dźwięku (wykrywanie mowy i przerywania) ------------------------------

  const tick = useCallback(() => {
    const node = analyser.current;
    if (!node) return;
    const samples = new Float32Array(node.fftSize);
    node.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) sum += value * value;
    const rms = Math.sqrt(sum / samples.length);
    setLevel(rms);
    const now = performance.now();
    const current = phaseRef.current;
    const startThreshold = Math.max(0.018, floor.current * 3);

    if (current === "listening" || current === "hearing") {
      if (current === "listening" && rms < startThreshold) floor.current = floor.current * 0.97 + rms * 0.03;
      if (rms > startThreshold) {
        if (!aboveSince.current) aboveSince.current = now;
        lastVoice.current = now;
        if (current === "listening" && now - aboveSince.current > SPEECH_START_MS) {
          speechStart.current = aboveSince.current;
          go("hearing");
        }
      } else {
        aboveSince.current = 0;
      }
      if (current === "hearing") {
        const silence = now - lastVoice.current;
        const length = now - speechStart.current;
        if ((silence > SPEECH_END_SILENCE_MS && length > MIN_SPEECH_MS) || length > MAX_UTTERANCE_MS) {
          void finishUtterance();
        }
      } else if (now - listenStart.current > IDLE_RESTART_MS) {
        startRecorder();
      }
    } else if (current === "speaking") {
      // Przerwanie głosem: wyraźnie głośniej niż echo odtwarzanej odpowiedzi.
      const bargeThreshold = Math.max(0.05, floor.current * 6);
      if (rms > bargeThreshold) {
        if (!aboveSince.current) aboveSince.current = now;
        if (now - aboveSince.current > BARGE_IN_MS) {
          stopSpeaking();
          awaitingReply.current = false;
          cursor.current = Number.MAX_SAFE_INTEGER;
          startRecorder();
          speechStart.current = aboveSince.current;
          lastVoice.current = now;
          go("hearing");
        }
      } else {
        aboveSince.current = 0;
      }
    } else if (current === "thinking" && !fillerSaid.current && !replyRef.current.text && now - sentAt.current > FILLER_AFTER_MS) {
      fillerSaid.current = true;
      queue.current.push(FILLER);
      void playQueue();
    }
  }, [finishUtterance, playQueue, startRecorder, stopSpeaking]);

  // --- start i zakończenie ---------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const media = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream.current = media;
        const audioContext = new AudioContext();
        await audioContext.resume();
        context.current = audioContext;
        const node = audioContext.createAnalyser();
        node.fftSize = 1024;
        audioContext.createMediaStreamSource(media).connect(node);
        analyser.current = node;
        timer.current = window.setInterval(tick, FRAME_MS);
        try {
          wakeLock.current = await (navigator as Navigator & {
            wakeLock?: { request: (type: "screen") => Promise<{ release: () => Promise<void> }> };
          }).wakeLock?.request("screen") ?? null;
        } catch {
          // Blokada wygaszania ekranu jest opcjonalna.
        }
        listen();
      } catch (failure) {
        setError(bladMikrofonu(failure));
        go("error");
      }
    })();
    return () => {
      cancelled = true;
      if (timer.current) window.clearInterval(timer.current);
      stopSpeaking();
      recorder.current?.state === "recording" && recorder.current.stop();
      stream.current?.getTracks().forEach((track) => track.stop());
      void context.current?.close();
      void wakeLock.current?.release().catch(() => undefined);
    };
    // Uruchamiane przy otwarciu trybu rozmowy i przy ponowieniu po błędzie mikrofonu.
  }, [proba]);

  useEffect(() => {
    if (timer.current) {
      window.clearInterval(timer.current);
      timer.current = window.setInterval(tick, FRAME_MS);
    }
  }, [tick]);

  const toggleMute = () => {
    if (phaseRef.current === "paused") {
      stream.current?.getAudioTracks().forEach((track) => (track.enabled = true));
      listen();
      return;
    }
    stopSpeaking();
    recorder.current?.state === "recording" && recorder.current.stop();
    stream.current?.getAudioTracks().forEach((track) => (track.enabled = false));
    go("paused");
  };

  const tapOrb = () => {
    const current = phaseRef.current;
    if (current === "speaking") {
      stopSpeaking();
      awaitingReply.current = false;
      cursor.current = Number.MAX_SAFE_INTEGER;
      listen();
    } else if (current === "hearing" && performance.now() - speechStart.current > MIN_SPEECH_MS) {
      void finishUtterance();
    } else if (current === "paused") {
      toggleMute();
    }
  };

  const chooseVoice = (id: string) => {
    setVoice(id);
    try {
      localStorage.setItem(VOICE_KEY, id);
    } catch {
      // Wybór obowiązuje do zamknięcia karty.
    }
  };

  const active = phase === "hearing" || phase === "speaking";
  const scale = 1 + Math.min(level * (phase === "speaking" ? 2 : 6), 0.35);

  return (
    <div
      ref={nakladka}
      tabIndex={-1}
      className="safe-top safe-bottom fixed inset-0 z-50 flex flex-col items-center bg-app/95 px-6 backdrop-blur-xl"
      role="dialog"
      aria-modal="true"
      aria-label="Rozmowa głosowa"
      // Dwa znaczniki diagnostyczne: stan rozmowy i chwilowa głośność. Nie rysują niczego
      // i nie czyta ich żaden arkusz — są po to, żeby dało się zmierzyć zachowanie okna
      // z przeglądarki bez zaglądania do wnętrza komponentu. Nie usuwać jako „martwe”.
      data-phase={phase}
      data-level={level.toFixed(3)}
    >
      {/* Nazwa okna po lewej, wybór głosu po prawej — jak w każdym innym oknie produktu.
        Odwrotna kolejność w pasmie szerokości `md` na szerokim ekranie stawiała listę
        głosów na środku, a podpis obok niej, i nie było wiadomo, co jest czym. */}
      <div className="flex w-full max-w-2xl items-center justify-between gap-3 py-3">
        <span className="font-heading text-sm font-semibold text-fg">Rozmowa głosowa</span>
        <select
          value={voice}
          onChange={(event) => chooseVoice(event.target.value)}
          className="rounded-lg border border-line bg-raised px-3 py-1.5 text-sm text-fg outline-none"
          aria-label="Głos asystenta"
        >
          {config.voices.map((option) => (
            <option key={option.id} value={option.id}>
              Głos: {option.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex w-full max-w-md flex-1 flex-col items-center justify-center gap-10">
        <button
          type="button"
          onClick={tapOrb}
          aria-label={phase === "speaking" ? "Przerwij odpowiedź" : "Stan rozmowy"}
          className="relative grid size-52 place-items-center rounded-full outline-none"
        >
          <span
            className={`voice-orb absolute inset-0 rounded-full transition-transform duration-100 ${
              phase === "thinking" || phase === "transcribing" ? "animate-pulse" : ""
            } ${phase === "paused" || phase === "error" ? "opacity-40 grayscale" : ""}`}
            style={{ transform: `scale(${scale})` }}
          />
          <span
            className={`absolute inset-3 rounded-full bg-gradient-to-br from-white/25 to-transparent ${
              active ? "opacity-100" : "opacity-50"
            }`}
          />
        </button>
        <div className="min-h-24 w-full text-center">
          {error && phase === "error" ? (
            <p role="alert" className="text-balance text-lg font-medium text-danger">
              {error}
            </p>
          ) : (
            <div className={`text-lg font-medium ${phase === "thinking" ? "shimmer-text" : ""}`}>
              {PHASE_LABELS[phase]}
            </div>
          )}
          <p className="mt-1 text-xs text-muted">
            {phase === "speaking"
              ? "Dotknij kuli lub zacznij mówić, aby przerwać"
              : phase === "listening" || phase === "hearing"
                ? "Mów naturalnie – po chwili ciszy odpowiem"
                : ""}
          </p>
          {heard && <p className="mt-3 line-clamp-2 text-sm text-muted">„{heard}”</p>}
          {error && phase !== "error" && <p className="mt-2 text-xs text-danger">{error}</p>}
        </div>
      </div>

      <div className="flex w-full max-w-md items-center justify-center gap-6 pb-6">
        {phase === "error" ? (
          <button
            type="button"
            onClick={() => {
              setError("");
              go("starting");
              setProba((numer) => numer + 1);
            }}
            className="rounded-full bg-accent-fill px-6 py-4 text-sm font-medium text-on-accent transition-opacity hover:opacity-90"
          >
            Spróbuj ponownie
          </button>
        ) : (
        <button
          type="button"
          onClick={toggleMute}
          disabled={phase === "starting"}
          className={`grid size-16 place-items-center rounded-full border border-line transition-colors ${
            phase === "paused" ? "bg-fg text-app" : "bg-raised text-fg hover:bg-hover"
          }`}
          aria-label={phase === "paused" ? "Włącz mikrofon" : "Wycisz mikrofon"}
        >
          <MicIcon muted={phase === "paused"} />
        </button>
        )}
        <button
          type="button"
          onClick={onClose}
          // „danger-fill”, nie „danger”: biel na barwie tekstowej błędu ma w motywie
          // ciemnym 2,58:1, a znak zakończenia jest grafiką niosącą sens (1.4.11).
          className="grid size-16 place-items-center rounded-full bg-danger-fill text-on-accent transition-colors hover:bg-danger-fill-hover"
          aria-label="Zakończ rozmowę"
        >
          <CloseIcon size={26} />
        </button>
      </div>
    </div>
  );
}

function MicIcon({ muted }: { muted: boolean }) {
  return (
    <svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      {muted && <path d="M4 4l16 16" />}
    </svg>
  );
}
