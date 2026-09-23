// Aplikacja instalowana (PWA): rejestracja service workera, aktualizacje i instalacja.

import { useEffect, useState } from "react";
import { registerSW } from "virtual:pwa-register";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

type Listener = () => void;

let deferredPrompt: BeforeInstallPromptEvent | null = null;
let updateReady = false;
let applyUpdate: (() => Promise<void>) | null = null;
const listeners = new Set<Listener>();
const notify = () => listeners.forEach((listener) => listener());

export function isStandalone(): boolean {
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    window.matchMedia?.("(display-mode: window-controls-overlay)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/** Okno aplikacji na Androida (`NexusAndroid/`) albo na komputer (Electron): „/” jest tam startem aplikacji. */
export function jestOknemAplikacji(userAgent: string = navigator.userAgent): boolean {
  return /NexusAndroid\/|Electron\//.test(userAgent);
}

export function isIos(): boolean {
  const platform = navigator.userAgent;
  return /iPhone|iPad|iPod/.test(platform) || (platform.includes("Macintosh") && navigator.maxTouchPoints > 1);
}

/** Rejestruje service worker (raz, przy starcie aplikacji). */
export function setupPwa(): void {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event as BeforeInstallPromptEvent;
    notify();
  });
  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    notify();
  });
  if (!("serviceWorker" in navigator) || import.meta.env.DEV) return;
  const update = registerSW({
    onNeedRefresh() {
      updateReady = true;
      notify();
    },
    onRegisteredSW(_url, registration) {
      // Aplikacja otwarta długo (np. zainstalowana) sprawdza aktualizacje co godzinę.
      if (registration) setInterval(() => void registration.update(), 60 * 60 * 1000);
    },
  });
  applyUpdate = () => update(true);
}

export interface PwaState {
  canInstall: boolean;
  iosHint: boolean;
  updateReady: boolean;
  install: () => Promise<void>;
  update: () => void;
}

export function usePwa(): PwaState {
  const [, setVersion] = useState(0);
  useEffect(() => {
    const listener = () => setVersion((value) => value + 1);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return {
    canInstall: deferredPrompt !== null && !isStandalone(),
    iosHint: isIos() && !isStandalone(),
    updateReady,
    install: async () => {
      if (!deferredPrompt) return;
      await deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      notify();
    },
    update: () => void applyUpdate?.(),
  };
}
