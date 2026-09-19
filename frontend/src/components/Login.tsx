// Ekran logowania administratora.

import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Logo } from "./icons";

const input =
  "mt-1.5 w-full rounded-xl border border-line bg-app px-3.5 py-2.5 text-[15px] outline-none transition-colors focus:border-accent";

export function Login({ onLoggedIn }: { onLoggedIn: (username: string) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.login(username.trim(), password);
      onLoggedIn(result.username);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Logowanie nie powiodło się.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="safe-top safe-bottom flex min-h-full items-center justify-center bg-side px-4">
      <form
        className="w-full max-w-sm animate-rise rounded-3xl border border-line bg-app p-7 shadow-xl dark:shadow-black/30"
        onSubmit={submit}
      >
        <div className="flex flex-col items-center text-center">
          <Logo size={52} className="rounded-2xl shadow-lg shadow-accent/25" />
          <h1 className="mt-4 text-xl font-semibold tracking-tight">Danaco Nexus</h1>
          <p className="mt-1 text-sm text-muted">
            Prywatny asystent AI do dokumentów, zdjęć, plików i automatyzacji
          </p>
        </div>
        <label className="mt-7 block text-sm font-medium">
          Login
          <input
            className={input}
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
          <div role="alert" className="mt-4 rounded-xl bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-xl bg-accent py-2.5 font-medium text-on-accent transition-colors hover:bg-accent-hover disabled:opacity-60"
        >
          {busy ? "Logowanie…" : "Zaloguj się"}
        </button>
      </form>
    </div>
  );
}
