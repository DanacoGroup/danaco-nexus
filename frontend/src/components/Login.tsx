// Ekran logowania: właściciel instalacji i konta klientów portalu.

import { useState, type FormEvent } from "react";
import { api } from "../api";
import { EkranPrzejscia, ograniczonyRuch, useOtwarcie, ZnakRuchu } from "../ruch";
import { Logo } from "./icons";

const input =
  "mt-1.5 h-11 w-full rounded-md border border-line-control bg-app px-3.5 outline-none transition-colors focus:border-accent";

export function Login({ onLoggedIn }: { onLoggedIn: (username: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Nazwa konta zapamiętana na czas przejścia; dopiero jego koniec wpuszcza do aplikacji.
  const [zalogowany, setZalogowany] = useState("");
  // Ekran ładowania marki (`index.html`) zasłania każdą powierzchnię, nie tylko stronę
  // produktu. Bez tego karta logowania wchodziła **pod** rysującym się jeszcze łukiem:
  // przez blisko sekundę biały obrys znaku szedł przez pola formularza, a karta była
  // przygaszona. Teraz wejście karty czeka na ten sam sygnał co wejście strony produktu.
  const otwarcieTrwa = useOtwarcie(true);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.login(username.trim(), password);
      setZalogowany(result.username);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Logowanie nie powiodło się.");
    } finally {
      setBusy(false);
    }
  };

  // Domknięcie logowania: znak rysuje się i zapala, a potem otwiera się aplikacja.
  // Ujęcie `logowanie-*` z pakietu ruchu tutaj nie pasuje — jest makietą produktu
  // z cudzym adresem w formularzu i powitaniem „Dzień dobry, Dariuszu”, więc każdemu
  // pokazywałoby obce imię i drugi raz czynność, którą właśnie wykonał.
  if (zalogowany)
    return <EkranPrzejscia moment="logowanie" etykieta="Logowanie" onKoniec={() => onLoggedIn(zalogowany)} />;

  return (
    <div
      className="logowanie safe-top safe-bottom relative flex min-h-full items-center justify-center overflow-hidden bg-app px-4"
      data-otwarcie={otwarcieTrwa ? "gra" : "po"}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_55%_at_50%_50%,color-mix(in_srgb,var(--raised)_70%,transparent)_0%,transparent_100%)]"
      />
      <form
        className="logowanie-karta relative w-full max-w-sm rounded-xl border border-line bg-raised/95 p-7 shadow-[var(--shadow-floating)] backdrop-blur"
        onSubmit={submit}
      >
        <div className="flex flex-col items-center text-center">
          {/* Znak na ekranie logowania oddycha — okno ma wyglądać na włączone, zanim
            ktokolwiek się zaloguje. Przy ograniczonym ruchu zostaje zwykły znaczek. */}
          {ograniczonyRuch() ? (
            <Logo size={56} className="glow-ai rounded-xl" />
          ) : (
            <ZnakRuchu moment="spoczynek" rozmiar={64} etykieta="Danaco Nexus" />
          )}
          <h1 className="mt-4 text-xl font-semibold tracking-tight">Danaco Nexus</h1>
          <p className="mt-1 text-sm text-muted">
            Twój agent do dokumentów, zdjęć, plików i spraw codziennych
          </p>
        </div>
        <label className="mt-7 block text-sm font-medium">
          Login albo adres e-mail
          <input
            className={input}
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="mt-4 block text-sm font-medium">
          Hasło
          <input
            className={input}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            autoFocus
            required
          />
        </label>
        {error && (
          <div role="alert" className="mt-4 rounded-md border border-danger/40 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={busy}
          className="mt-7 h-11 w-full rounded-md bg-accent-fill font-medium text-on-accent transition-colors hover:bg-accent-fill-hover disabled:opacity-60"
        >
          {busy ? "Logowanie…" : "Zaloguj się"}
        </button>
      </form>
    </div>
  );
}
